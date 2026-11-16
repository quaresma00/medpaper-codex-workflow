"""Loads pipeline.toml (the SSOT) plus per-project config overrides.

Stdlib only: tomllib requires Python >= 3.11.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import paths


@dataclass
class Stage:
    id: str
    title: str
    card: str
    outputs: list[str] = field(default_factory=list)
    gate: list[dict] = field(default_factory=list)
    needs_user: bool = False
    loopable: bool = False
    index: int = 0

    def card_path(self) -> Path:
        return paths.pipeline_dir() / self.card


@dataclass
class Pipeline:
    meta: dict
    layout: dict
    policy: dict
    targets: dict
    freeform: list[str]
    stages: list[Stage]
    raw: dict

    # ---- lookups -------------------------------------------------------
    def stage(self, sid: str) -> Stage:
        for s in self.stages:
            if s.id == sid:
                return s
        raise KeyError(f"unknown stage: {sid}")

    def resolve(self, token: str) -> Stage:
        """Accept exact id, index (1-based), or unique prefix/substring."""
        token = (token or "").strip()
        if not token:
            raise KeyError("empty stage token")
        for s in self.stages:
            if s.id == token:
                return s
        if token.isdigit():
            i = int(token)
            if 1 <= i <= len(self.stages):
                return self.stages[i - 1]
        low = token.lower()
        hits = [s for s in self.stages if s.id.lower().startswith(low)]
        if len(hits) == 1:
            return hits[0]
        hits = [s for s in self.stages if low in s.id.lower()]
        if len(hits) == 1:
            return hits[0]
        raise KeyError(f"stage token '{token}' matched {len(hits)} stages")

    def next_of(self, sid: str) -> Stage | None:
        s = self.stage(sid)
        if s.index + 1 < len(self.stages):
            return self.stages[s.index + 1]
        return None

    def stages_after(self, sid: str) -> list[Stage]:
        return self.stages[self.stage(sid).index + 1 :]

    def first(self) -> Stage:
        return self.stages[0]

    def target(self, key: str, default=None):
        return self.targets.get(key, default)

    def all_declared_outputs(self) -> set[str]:
        out: set[str] = set()
        for s in self.stages:
            out.update(s.outputs)
        return out


def load(config_overrides: dict | None = None) -> Pipeline:
    pf = paths.pipeline_file()
    if not pf.exists():
        raise SystemExit(f"pipeline definition missing: {pf}")
    data = tomllib.loads(pf.read_text(encoding="utf-8"))

    stages: list[Stage] = []
    for i, raw in enumerate(data.get("stage", [])):
        stages.append(
            Stage(
                id=raw["id"],
                title=raw.get("title", raw["id"]),
                card=raw.get("card", f"stages/{raw['id']}.md"),
                outputs=list(raw.get("outputs", [])),
                gate=list(raw.get("gate", [])),
                needs_user=bool(raw.get("needs_user", False)),
                loopable=bool(raw.get("loopable", False)),
                index=i,
            )
        )
    if not stages:
        raise SystemExit("pipeline.toml declares no stages")

    # Exact project-owned outputs are declarations, never shared study-specific
    # glob exceptions or a waiver of their owning stage/scientific checks.
    support = (config_overrides or {}).get("support_outputs", [])
    if not isinstance(support, list):
        raise ValueError("Project support_outputs must be an array of file/owning_stage/purpose records")
    from pathlib import PurePosixPath
    existing = {name for stage in stages for name in stage.outputs}
    owners = {stage.id:stage for stage in stages}
    roots = {"00_input","01_protocol","02_data","03_analysis","04_tables","05_figures","06_refs","07_manuscript","08_submission"}
    for row in support:
        if not isinstance(row,dict) or not isinstance(row.get("file"),str):
            raise ValueError("Each project support output needs an exact relative file")
        name = row["file"]
        part = PurePosixPath(name)
        if (part.is_absolute() or ".." in part.parts or not part.parts or part.parts[0] not in roots
                or any(char in name for char in "\\:*?[]") or part.as_posix()!=name or len(part.parts)<2):
            raise ValueError(f"Unsafe project support output: {name}")
        if name in existing:
            raise ValueError(f"Duplicate or reassigned existing output: {name}")
        owner = row.get("owning_stage")
        if owner not in owners or not isinstance(row.get("purpose"),str) or len(row["purpose"].strip())<20:
            raise ValueError(f"{name}: supply its real owning_stage and concrete purpose")
        owners[owner].outputs.append(name)
        existing.add(name)

    targets = dict(data.get("targets", {}))
    if config_overrides:
        targets.update(config_overrides.get("targets", {}))

    return Pipeline(
        meta=data.get("meta", {}),
        layout=data.get("layout", {}),
        policy=data.get("policy", {}),
        targets=targets,
        freeform=list(data.get("freeform", {}).get("globs", [])),
        stages=stages,
        raw=data,
    )
