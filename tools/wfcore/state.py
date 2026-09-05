"""On-disk run state.

This file is the memory that survives context compaction. The agent never has to
remember where it is; it reads it back from here.
"""
from __future__ import annotations

import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class State:
    def __init__(self, root: Path, state_dir: str = ".wf"):
        self.project = root
        self.dir = root / state_dir
        self.file = self.dir / "state.json"
        self.handoff_file = self.dir / "handoff.md"
        self.config_file = self.dir / "config.toml"
        self.data: dict = {}

    # ---- lifecycle -----------------------------------------------------
    def exists(self) -> bool:
        return self.file.exists()

    def load(self) -> "State":
        if not self.exists():
            raise SystemExit(
                "no run state found. Initialise first:  .venv/Scripts/python.exe tools/wf.py init"
            )
        self.data = json.loads(self.file.read_text(encoding="utf-8"))
        return self

    def create(self, pipeline_name: str, pipeline_version: str, first_stage: str) -> "State":
        self.dir.mkdir(parents=True, exist_ok=True)
        self.data = {
            "schema": SCHEMA,
            "pipeline": pipeline_name,
            "pipeline_version": pipeline_version,
            "created_at": _now(),
            "current": first_stage,
            "stages": {first_stage: {"status": "active", "started_at": _now(), "loops": 0}},
            "decisions": {},
            "handoff": [],
            "events": [{"at": _now(), "kind": "init", "detail": first_stage}],
        }
        self.save()
        if not self.handoff_file.exists():
            self.handoff_file.write_text(
                "# Handoff log\n\n"
                "Append-only. One entry per stage close. Written by `wf note` / `wf advance`.\n"
                "Read this first when resuming after a context reset.\n",
                encoding="utf-8",
            )
        return self

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)

    def migrate_pipeline(self, pipeline_version: str, valid_stage_ids: list[str],
                         stage_aliases: dict[str, str] | None = None) -> bool:
        """Migrate engine metadata and renamed active stages without touching artifacts."""
        old_version = str(self.data.get("pipeline_version", "unknown"))
        current = str(self.data.get("current", ""))
        aliases = stage_aliases or {}
        changed = old_version != pipeline_version
        if current not in valid_stage_ids:
            replacement = aliases.get(current)
            if not replacement or replacement not in valid_stage_ids:
                raise SystemExit(
                    f"run state uses stage '{current}', which pipeline {pipeline_version} cannot migrate"
                )
            self.stage_info(current)["status"] = "superseded"
            self.stage_info(replacement)["status"] = "active"
            self.stage_info(replacement).setdefault("started_at", _now())
            self.data["current"] = replacement
            changed = True
        if changed:
            self.data["pipeline_version"] = pipeline_version
            self.event("pipeline_migration",
                       f"{old_version} -> {pipeline_version}; current {current} -> {self.data['current']}")
            self.save()
        return changed

    # ---- config --------------------------------------------------------
    def config(self) -> dict:
        if not self.config_file.exists():
            return {}
        try:
            return tomllib.loads(self.config_file.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise SystemExit(f"malformed {self.config_file}: {exc}")

    def set_config(self, key: str, value: str) -> None:
        cfg = self.config()
        tgt = cfg.setdefault("targets", {})
        try:
            tgt[key] = int(value)
        except ValueError:
            try:
                tgt[key] = float(value)
            except ValueError:
                tgt[key] = value
        lines = ["# Per-project overrides of [targets] in pipeline/pipeline.toml", "[targets]"]
        for k, v in sorted(tgt.items()):
            lines.append(f'{k} = {json.dumps(v)}' if not isinstance(v, str) else f'{k} = "{v}"')
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- accessors -----------------------------------------------------
    @property
    def current(self) -> str:
        return self.data["current"]

    def stage_info(self, sid: str) -> dict:
        return self.data.setdefault("stages", {}).setdefault(sid, {"status": "pending", "loops": 0})

    def status_of(self, sid: str) -> str:
        return self.stage_info(sid).get("status", "pending")

    def is_done(self, sid: str) -> bool:
        return self.status_of(sid) == "done"

    def decision(self, name: str) -> dict | None:
        return self.data.get("decisions", {}).get(name)

    # ---- mutations -----------------------------------------------------
    def event(self, kind: str, detail: str) -> None:
        self.data.setdefault("events", []).append({"at": _now(), "kind": kind, "detail": detail})

    def record_decision(self, name: str, value: str, why: str) -> None:
        self.data.setdefault("decisions", {})[name] = {
            "value": value,
            "rationale": why,
            "at": _now(),
            "stage": self.current,
        }
        self.event("decision", f"{name}={value}")
        self.save()

    def add_note(self, note: str, stage: str | None = None) -> None:
        stage = stage or self.current
        entry = {"stage": stage, "at": _now(), "note": note}
        self.data.setdefault("handoff", []).append(entry)
        self.save()
        with self.handoff_file.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {stage} - {entry['at']}\n\n{note}\n")

    def notes_for(self, stage: str) -> list[dict]:
        return [h for h in self.data.get("handoff", []) if h.get("stage") == stage]

    def complete(self, sid: str, next_sid: str | None) -> None:
        info = self.stage_info(sid)
        info["status"] = "done"
        info["completed_at"] = _now()
        if next_sid:
            nxt = self.stage_info(next_sid)
            nxt["status"] = "active"
            nxt.setdefault("started_at", _now())
            self.data["current"] = next_sid
        self.event("advance", f"{sid} -> {next_sid or 'END'}")
        self.save()

    def rewind(self, sid: str, why: str) -> None:
        """Go back to an earlier stage; later stages return to pending."""
        order = list(self.data.get("stages", {}).keys())
        self.stage_info(sid)["status"] = "active"
        self.stage_info(sid)["loops"] = self.stage_info(sid).get("loops", 0) + 1
        self.data["current"] = sid
        self.event("loop", f"back to {sid}: {why}")
        _ = order
        self.save()

    def reset_forward(self, stage_ids: list[str]) -> None:
        for sid in stage_ids:
            if sid in self.data.get("stages", {}):
                self.data["stages"][sid]["status"] = "pending"
        self.save()

    def clear_decisions_for(self, stage_ids: list[str]) -> None:
        """Invalidate decisions made in stages that are about to be rerun."""
        affected = set(stage_ids)
        decisions = self.data.get("decisions", {})
        removed = [name for name, rec in decisions.items() if rec.get("stage") in affected]
        for name in removed:
            del decisions[name]
        if removed:
            self.event("decisions_invalidated", ", ".join(sorted(removed)))
        self.save()
