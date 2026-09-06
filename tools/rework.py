#!/usr/bin/env python3
"""Route a user-requested revision to its earliest owning workflow stage."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wfcore import paths, registry  # noqa: E402
from wfcore.state import State  # noqa: E402


ROUTES = {
    "study-design": "S03_protocol",
    "data": "S04_data",
    "analysis": "S05_analysis",
    "final-protocol": "S06_protocol_final",
    "artifact-plan-or-legend": "S07_artifacts",
    "methods": "S08_methods",
    "results-wording": "S09_results",
    "tables": "S10_tables",
    "figures": "S11_figures",
    "references": "S13_reflib",
    "introduction": "S14_introduction",
    "discussion": "S16_discussion",
    "title-abstract-keywords": "S17_assemble",
    "journal": "S20_journal",
    "title-page-or-statements": "S21_authors",
    "cover-letter-or-package-structure": "S23_package",
}

ROUND_SCHEMA = 1
REVIEW_STAGES = {"S19_human_review", "S24_package_human_review"}

# Only decisions whose evidence can be changed by the requested kind are invalidated in a
# batch revision.  The legacy single-item `start` command retains the older conservative
# all-forward invalidation behavior for compatibility.
COMMON_MANUSCRIPT_INVALIDATION = {
    "independent_publishability", "manuscript_human_reviewed", "polish_reviewed",
    "submission_files_visually_confirmed", "submission_package_user_confirmed",
    "submission_package_independent_audit",
}
PACKAGE_INVALIDATION = {
    "submission_files_visually_confirmed", "submission_package_user_confirmed",
    "submission_package_independent_audit",
}
INVALIDATE_BY_KIND = {
    "study-design": COMMON_MANUSCRIPT_INVALIDATION | {
        "analysis_converged", "go_nogo_2", "tables_visually_confirmed",
        "figures_visually_confirmed", "journal_chosen",
    },
    "data": COMMON_MANUSCRIPT_INVALIDATION | {
        "analysis_converged", "go_nogo_2", "tables_visually_confirmed",
        "figures_visually_confirmed", "journal_chosen",
    },
    "analysis": COMMON_MANUSCRIPT_INVALIDATION | {
        "analysis_converged", "go_nogo_2", "tables_visually_confirmed",
        "figures_visually_confirmed", "journal_chosen",
    },
    "final-protocol": COMMON_MANUSCRIPT_INVALIDATION | {
        "analysis_converged", "go_nogo_2", "journal_chosen",
    },
    "artifact-plan-or-legend": COMMON_MANUSCRIPT_INVALIDATION | {
        "tables_visually_confirmed", "figures_visually_confirmed", "journal_chosen",
    },
    "methods": COMMON_MANUSCRIPT_INVALIDATION,
    "results-wording": COMMON_MANUSCRIPT_INVALIDATION,
    "tables": COMMON_MANUSCRIPT_INVALIDATION | {"tables_visually_confirmed"},
    "figures": COMMON_MANUSCRIPT_INVALIDATION | {"figures_visually_confirmed"},
    "references": COMMON_MANUSCRIPT_INVALIDATION,
    "introduction": COMMON_MANUSCRIPT_INVALIDATION,
    "discussion": COMMON_MANUSCRIPT_INVALIDATION,
    "title-abstract-keywords": COMMON_MANUSCRIPT_INVALIDATION,
    "manuscript-copyedit": COMMON_MANUSCRIPT_INVALIDATION,
    "journal": PACKAGE_INVALIDATION | {"journal_chosen", "polish_reviewed"},
    "title-page-or-statements": PACKAGE_INVALIDATION | {"polish_reviewed"},
    "cover-letter-or-package-structure": PACKAGE_INVALIDATION,
    "word-format-only": PACKAGE_INVALIDATION,
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _round_dir(state: State) -> Path:
    return state.dir / "revisions"


def _round_path(state: State, round_id: str) -> Path:
    return _round_dir(state) / f"{round_id}.json"


def _load_round(state: State) -> tuple[Path, dict]:
    round_id = state.data.get("active_revision_round")
    if not round_id:
        raise ValueError("no active revision round")
    path = _round_path(state, str(round_id))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid revision round: {path}")
    return path, payload


def _write_round(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _next_round_id(state: State) -> str:
    numbers = []
    for path in _round_dir(state).glob("R*.json") if _round_dir(state).exists() else []:
        if path.stem[1:].isdigit():
            numbers.append(int(path.stem[1:]))
    return f"R{max(numbers, default=0) + 1:03d}"


def _valid_project_rel(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = Path(value.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def _read_batch_plan(path: Path, kinds: list[str], review_stage: str, pipe) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("revision plan must contain one JSON object")
    feedback = str(payload.get("feedback_verbatim", "")).strip()
    interpretation = str(payload.get("interpretation", "")).strip()
    ambiguous = payload.get("ambiguous_or_requires_user_decision", [])
    if len(feedback) < 10:
        raise ValueError("feedback_verbatim is missing or too short")
    if len(interpretation) < 40:
        raise ValueError("interpretation must explain the requested outcome in at least 40 characters")
    if not isinstance(ambiguous, list):
        raise ValueError("ambiguous_or_requires_user_decision must be an array")
    if ambiguous:
        raise ValueError("revision plan still contains an unresolved ambiguity/user decision")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("revision plan must contain at least one atomic item")
    normalized = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"items[{index}] is not an object")
        kind = item.get("kind")
        if kind not in kinds:
            raise ValueError(f"items[{index}].kind must be one of {kinds}")
        request = str(item.get("request", "")).strip()
        sources = item.get("affected_sources")
        acceptance = item.get("acceptance_criteria")
        if len(request) < 10:
            raise ValueError(f"items[{index}].request is missing or too short")
        if not isinstance(sources, list) or not sources or not all(_valid_project_rel(x) for x in sources):
            raise ValueError(f"items[{index}].affected_sources must list project-relative source paths")
        if (not isinstance(acceptance, list) or not acceptance or
                not all(isinstance(x, str) and len(x.strip()) >= 8 for x in acceptance)):
            raise ValueError(f"items[{index}].acceptance_criteria must contain substantive checks")
        normalized.append({
            "kind": kind,
            "request": request,
            "owning_stage": resolve_route(kind, review_stage, pipe),
            "affected_sources": sources,
            "acceptance_criteria": acceptance,
            "status": "pending",
            "resolution": None,
            "changed_files": [],
            "validated_by": [],
        })
    return {
        "feedback_verbatim": feedback,
        "feedback_sha256": _sha256_text(feedback),
        "interpretation": interpretation,
        "items": normalized,
    }


def _clear_decisions(state: State, names: set[str]) -> list[str]:
    decisions = state.data.get("decisions", {})
    removed = sorted(name for name in names if name in decisions)
    for name in removed:
        del decisions[name]
    if removed:
        state.event("revision_decisions_invalidated", ", ".join(removed))
        state.save()
    return removed


def _rewind_batch(state: State, pipe, target: str, why: str) -> bool:
    current = pipe.stage(state.current)
    destination = pipe.stage(target)
    if destination.index > current.index:
        return False
    state.add_note(f"[REVISION ROUND] returning to {target}: {why}", current.id)
    state.reset_forward([stage.id for stage in pipe.stages_after(target)])
    state.rewind(target, why)
    return True


def _cmd_batch(args, project: Path, pipe, state: State, kinds: list[str]) -> int:
    active = state.data.get("active_revision_round")
    if active:
        round_path, revision = _load_round(state)
        review_stage = revision["review_stage"]
    else:
        if state.current not in REVIEW_STAGES:
            raise ValueError("a new revision round can start only while the user is reviewing at S19 or S24")
        review_stage = state.current
        round_id = _next_round_id(state)
        round_path = _round_path(state, round_id)
        revision = {
            "schema_version": ROUND_SCHEMA,
            "round_id": round_id,
            "review_stage": review_stage,
            "created_at": _now(),
            "status": "active",
            "feedback_updates": [],
            "items": [],
        }
    plan = _read_batch_plan(args.plan.resolve(), kinds, review_stage, pipe)
    first_new = len(revision["items"]) + 1
    for offset, item in enumerate(plan["items"]):
        item["id"] = f"{revision['round_id']}-{first_new + offset:02d}"
        revision["items"].append(item)
    revision["feedback_updates"].append({
        "at": _now(), "feedback_verbatim": plan["feedback_verbatim"],
        "feedback_sha256": plan["feedback_sha256"], "interpretation": plan["interpretation"],
    })
    revision["earliest_stage"] = min(
        (item["owning_stage"] for item in revision["items"]),
        key=lambda stage_id: pipe.stage(stage_id).index,
    )
    revision["updated_at"] = _now()
    _write_round(round_path, revision)
    state.data["active_revision_round"] = revision["round_id"]
    state.event("revision_round_opened" if not active else "revision_round_extended",
                f"{revision['round_id']}: {len(revision['items'])} item(s)")
    state.save()
    invalidations: set[str] = set()
    for item in plan["items"]:
        invalidations.update(INVALIDATE_BY_KIND[item["kind"]])
    # A late package-round correction passes the scientific-review checkpoint on its way
    # back to S24. The user will inspect the changed content in the actual package there;
    # retain the earlier S19 approval while still requiring a fresh S18 independent verdict.
    if review_stage == "S24_package_human_review":
        invalidations.discard("manuscript_human_reviewed")
    removed = _clear_decisions(state, invalidations)
    target = min(
        (item["owning_stage"] for item in plan["items"]),
        key=lambda stage_id: pipe.stage(stage_id).index,
    )
    rewound = _rewind_batch(
        state, pipe, target,
        f"{revision['round_id']} user feedback; {len(plan['items'])} new atomic item(s)",
    )
    print(f"revision round {revision['round_id']}: {len(revision['items'])} total item(s)")
    print(f"review return point: {review_stage}; earliest owner: {revision['earliest_stage']}")
    print(f"invalidated decisions: {', '.join(removed) if removed else 'none'}")
    print(f"current stage: {state.current}" + (" (rewound)" if rewound else " (unchanged)"))
    print("run tools/rework.py status after context compaction; do not reread the full conversation")
    return 0


def _cmd_status(state: State) -> int:
    try:
        _, revision = _load_round(state)
    except ValueError:
        print("no active revision round")
        return 0
    print(f"{revision['round_id']}  status={revision['status']}  return={revision['review_stage']}")
    print(f"earliest owner: {revision['earliest_stage']}; current stage: {state.current}")
    for item in revision["items"]:
        print(f"  [{item['status']}] {item['id']} {item['kind']} -> {item['owning_stage']}")
        print(f"      {item['request']}")
        print(f"      sources: {', '.join(item['affected_sources'])}")
        print(f"      acceptance: {'; '.join(item['acceptance_criteria'])}")
    return 0


def _cmd_mark(args, project: Path, state: State) -> int:
    path, revision = _load_round(state)
    if state.current != revision["review_stage"]:
        raise ValueError(
            f"mark items only after the gated workflow returns to {revision['review_stage']}; "
            f"current={state.current}"
        )
    item = next((entry for entry in revision["items"] if entry["id"] == args.item), None)
    if item is None:
        raise ValueError(f"unknown item {args.item}")
    if len(args.summary.strip()) < 30:
        raise ValueError("mark summary must state what changed in at least 30 characters")
    if not args.changed_file:
        raise ValueError("mark requires at least one --changed-file")
    if not args.validated_by:
        raise ValueError("mark requires at least one --validated-by check or inspection")
    changed = []
    changed_names: set[str] = set()
    for rel in args.changed_file:
        if not _valid_project_rel(rel):
            raise ValueError(f"unsafe changed-file path: {rel}")
        source = project / rel
        if not source.is_file():
            raise ValueError(f"changed file does not exist: {rel}")
        normalized = Path(rel).as_posix()
        changed_names.add(normalized)
        changed.append({"path": normalized, "sha256": _sha256_file(source)})
    required_sources = {Path(rel).as_posix() for rel in item.get("affected_sources", [])}
    missing_sources = sorted(required_sources - changed_names)
    if missing_sources:
        raise ValueError(
            "mark must hash every declared affected source; missing: " + ", ".join(missing_sources)
        )
    item.update({
        "status": "done", "resolution": args.summary.strip(), "changed_files": changed,
        "validated_by": args.validated_by, "completed_at": _now(),
    })
    revision["updated_at"] = _now()
    _write_round(path, revision)
    print(f"marked {args.item} done; {len(changed)} changed file(s), {len(args.validated_by)} validation(s)")
    return 0


def _cmd_close(args, state: State) -> int:
    path, revision = _load_round(state)
    pending = [item["id"] for item in revision["items"] if item.get("status") != "done"]
    if pending:
        raise ValueError("cannot close; pending items: " + ", ".join(pending))
    if state.current != revision["review_stage"]:
        raise ValueError(
            f"cannot close until the gated workflow returns to {revision['review_stage']}; current={state.current}"
        )
    if len(args.summary.strip()) < 40:
        raise ValueError("close summary must describe the completed round in at least 40 characters")
    revision.update({"status": "complete", "completed_at": _now(), "completion_summary": args.summary.strip()})
    _write_round(path, revision)
    state.data.pop("active_revision_round", None)
    state.event("revision_round_closed", revision["round_id"])
    state.add_note(f"[REVISION COMPLETE] {revision['round_id']}: {args.summary.strip()}", state.current)
    state.save()
    print(f"closed {revision['round_id']}; user review may now continue")
    return 0


def resolve_route(kind: str, current: str, pipe) -> str:
    if kind == "manuscript-copyedit":
        current_index = pipe.stage(current).index
        if current_index < pipe.stage("S19_human_review").index:
            raise ValueError("manuscript-copyedit routing is available from S19 onward")
        return ("S22_polish" if current_index >= pipe.stage("S22_polish").index
                else "S19_human_review")
    if kind == "word-format-only":
        current_index = pipe.stage(current).index
        if current_index < pipe.stage("S23_package").index:
            raise ValueError("word-format-only routing is available after the package is built")
        return ("S23_package" if current == "S23_package"
                else "S24_package_human_review")
    return ROUTES[kind]


def main() -> int:
    kinds = sorted([*ROUTES, "manuscript-copyedit", "word-format-only"])
    parser = argparse.ArgumentParser(
        description="plan, route and persist user-requested medpaper revision rounds")
    parser.add_argument("command", choices=["plan", "start", "batch", "status", "mark", "close"])
    parser.add_argument("--kind", choices=kinds)
    parser.add_argument("--why",
                        help="specific user-requested change and why this route owns it")
    parser.add_argument("--plan", type=Path,
                        help="JSON plan for a new or extended multi-item revision round")
    parser.add_argument("--item", help="revision item id for mark")
    parser.add_argument("--changed-file", action="append", default=[],
                        help="project-relative changed source; repeat as needed")
    parser.add_argument("--validated-by", action="append", default=[],
                        help="completed gate/test/inspection; repeat as needed")
    parser.add_argument("--summary", help="resolution or round-completion summary")
    parser.add_argument("--project", type=Path, default=None)
    args = parser.parse_args()
    project = args.project.resolve() if args.project else paths.project_dir().resolve()
    try:
        pipe = registry.load()
        state = State(project, pipe.layout.get("state_dir", ".wf")).load()
        if args.command == "status":
            return _cmd_status(state)
        if args.command == "batch":
            if args.plan is None:
                raise ValueError("batch requires --plan <revision-plan.json>")
            return _cmd_batch(args, project, pipe, state, kinds)
        if args.command == "mark":
            if not args.item or not args.summary:
                raise ValueError("mark requires --item and --summary")
            return _cmd_mark(args, project, state)
        if args.command == "close":
            if not args.summary:
                raise ValueError("close requires --summary")
            return _cmd_close(args, state)
        if not args.kind or not args.why:
            raise ValueError(f"{args.command} requires --kind and --why")
        if len(args.why.strip()) < 20:
            raise ValueError("rework reason is too short; name the requested change and affected artifact")
        current = state.current
        target = resolve_route(args.kind, current, pipe)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"rework route error: {exc}", file=sys.stderr)
        return 2
    if pipe.stage(target).index > pipe.stage(current).index:
        print(f"rework route error: {target} is ahead of current stage {current}", file=sys.stderr)
        return 2
    print(f"revision route: {args.kind}: {current} -> {target}")
    if args.command == "plan":
        return 0
    tool = paths.tools_dir() / "wf.py"
    env = {**os.environ, "MEDPAPER_PROJECT": str(project),
           "MEDPAPER_ROOT": str(paths.repo_root()), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(tool), "loop", "--to", target, "--why",
         f"user-requested {args.kind} revision: {args.why.strip()}"],
        text=True, env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())

