#!/usr/bin/env python3
"""Route a user-requested revision to its earliest owning workflow stage."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wfcore import paths, registry  # noqa: E402
from wfcore.state import State  # noqa: E402
from wfcore import revision as scoped  # noqa: E402


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
    "journal-figure-layout": "S23_package",
    "journal-table-layout": "S23_package",
    "figure-layout": "S11_figures",
    "table-layout": "S10_tables",
    "methods-wording": "S08_methods",
}

ROUND_SCHEMA = 2
REVIEW_STAGES = {"S19_human_review", "S24_package_human_review"}

# Only decisions whose evidence can be changed by the requested kind are invalidated in a
# batch revision. Owner stages supply rules without resetting the stage tail.
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
    # At S24 this edits only the journal integration copy. The S19 branch below upgrades
    # it to COMMON_MANUSCRIPT_INVALIDATION because the accepted scientific master is then
    # still the file under review.
    "manuscript-copyedit": PACKAGE_INVALIDATION | {"polish_reviewed"},
    "journal": PACKAGE_INVALIDATION | {"journal_chosen", "polish_reviewed"},
    "title-page-or-statements": PACKAGE_INVALIDATION | {"polish_reviewed"},
    "cover-letter-or-package-structure": PACKAGE_INVALIDATION,
    "word-format-only": PACKAGE_INVALIDATION,
    "journal-figure-layout": PACKAGE_INVALIDATION,
    "journal-table-layout": PACKAGE_INVALIDATION,
    "figure-layout": PACKAGE_INVALIDATION | {"manuscript_human_reviewed", "figures_visually_confirmed"},
    "table-layout": PACKAGE_INVALIDATION | {"manuscript_human_reviewed", "tables_visually_confirmed"},
    "methods-wording": PACKAGE_INVALIDATION | {"manuscript_human_reviewed"},
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
        sources = [source.replace("\\", "/") for source in sources]
        if (not isinstance(acceptance, list) or not acceptance or
                not all(isinstance(x, str) and len(x.strip()) >= 8 for x in acceptance)):
            raise ValueError(f"items[{index}].acceptance_criteria must contain substantive checks")
        owner = resolve_route(kind, review_stage, pipe)
        default_type = ("layout" if kind in {"figure-layout", "table-layout", "word-format-only",
                        "journal-figure-layout", "journal-table-layout"} else
                        "wording" if kind in {"manuscript-copyedit", "methods-wording"} else
                        "administrative" if kind in {"title-page-or-statements", "journal",
                        "cover-letter-or-package-structure"} else "scientific")
        change_type = item.get("change_type", default_type)
        if change_type not in {"layout", "wording", "administrative", "scientific"}:
            raise ValueError("change_type must distinguish layout, wording, administrative or scientific")
        if kind in scoped.SCIENTIFIC_KINDS and change_type != "scientific":
            raise ValueError("data/design/model changes cannot be downgraded to cosmetic revisions")
        if change_type != "scientific" and any(s.replace("\\", "/").startswith(("02_data/", "03_analysis/", "01_protocol/protocol", "01_protocol/analysis_contract")) for s in sources):
            raise ValueError("non-scientific revision may not edit scientific analysis sources")
        if change_type == "layout" and any(s.replace("\\", "/").endswith(".md") for s in sources):
            raise ValueError("Markdown wording changes are not layout-only")
        if any(s.replace("\\", "/").startswith((".wf/", "temp/", "08_submission/releases/")) for s in sources):
            raise ValueError("workflow controls, scratch and immutable releases are not editable revision sources")
        if item.get("changed_fields"):
            raise ValueError("field-level pruning is not supported; declare file consumers conservatively")
        if pipe.stage(owner).index > pipe.stage(review_stage).index:
            raise ValueError(f"{kind} belongs after {review_stage}; finish the current review first")
        if kind in {"journal-figure-layout", "journal-table-layout"} and any(
                not rel.replace("\\", "/").startswith("08_submission/") for rel in sources):
            raise ValueError("journal layout changes must name derived submission sources only")
        normalized.append({
            "kind": kind,
            "request": request,
            "owning_stage": owner,
            "change_type": change_type,
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


def _cmd_batch(args, project: Path, pipe, state: State, kinds: list[str]) -> int:
    active = state.data.get("active_revision_round")
    if active:
        round_path, revision = _load_round(state)
        if revision.get("schema_version") != 2:
            raise ValueError("finish the existing legacy round before opening a scoped revision")
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
            "origin_stage": review_stage,
            "created_at": _now(),
            "status": "collecting",
            "full_builds": 0,
            "feedback_updates": [],
            "items": [],
            "baseline": scoped.snapshot(project),
        }
    plan = _read_batch_plan(args.plan.resolve(), kinds, review_stage, pipe)
    if any(update.get("feedback_sha256") == plan["feedback_sha256"] for update in revision["feedback_updates"]):
        print("identical feedback already recorded; no duplicate items or rebuild")
        if args.sealed and revision.get("status") == "collecting":
            return _seal_round(state, pipe, args.why or plan["feedback_verbatim"])
        return 0
    revision["status"] = "collecting"
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
    revision.pop("validation", None)
    scoped.plan_scope(project, pipe, revision)
    _write_round(round_path, revision)
    state.data["active_revision_round"] = revision["round_id"]
    state.event("revision_round_opened" if not active else "revision_round_extended",
                f"{revision['round_id']}: {len(revision['items'])} item(s)")
    state.save()
    print(f"collected {revision['round_id']}: {len(revision['items'])} item(s); builds deferred")
    if not args.sealed:
        print("When the user has finished this feedback batch, run seal --why <their instruction>.")
        return 0
    return _seal_round(state, pipe, args.why or plan["feedback_verbatim"])


def _seal_round(state: State, pipe, why: str) -> int:
    if len(why.strip()) < 10:
        raise ValueError("seal requires the user's end-of-batch or apply-now instruction")
    round_path, revision = _load_round(state)
    project = state.dir.parent
    if revision.get("schema_version") != 2:
        raise ValueError("legacy active round: finish its recorded work before opening a v1.6 scoped round; do not discard its evidence")
    if revision.get("baseline") is None:
        raise ValueError("revision lacks its pre-edit baseline")
    if revision.get("review_stage") == "S24_package_human_review" and any(
            any(s.startswith(("01_protocol/", "02_data/", "03_analysis/", "04_tables/", "05_figures/", "06_refs/", "07_manuscript/"))
                for s in item["affected_sources"]) for item in revision["items"]):
        science = [i for i in revision["items"] if any(not s.startswith(("00_input/", "08_submission/"))
                                                    for s in i["affected_sources"])]
        if any(any(s.startswith("08_submission/") for s in i["affected_sources"]) for i in science):
            raise ValueError("split scientific sources and journal-package sources into separate items")
        for item in science:
            if item["kind"] == "manuscript-copyedit":
                item["owning_stage"] = "S19_human_review"
        revision["deferred_package_items"] = [i for i in revision["items"] if i not in science]
        revision["items"] = science
        revision["review_stage"] = "S19_human_review"
        state.data["current"] = "S19_human_review"
        state.data["resume_package_revision"] = revision["round_id"]
        state.save()
    scoped.plan_scope(project, pipe, revision)
    revision.update({"status": "active", "sealed_at": _now(), "seal_instruction": why})
    _write_round(round_path, revision)
    review_stage = revision["review_stage"]
    invalidations: set[str] = set()
    for item in revision["items"]:
        names = set(INVALIDATE_BY_KIND[item["kind"]])
        if item["change_type"] != "scientific":
            names.discard("independent_publishability")
        if review_stage == "S19_human_review":
            names.add("manuscript_human_reviewed")
        invalidations.update(names)
    removed = _clear_decisions(state, invalidations)
    state.add_note(f"[SCOPED REVISION] {revision['round_id']}; owner rules execute in place; no stage tail reset")
    print(f"revision round {revision['round_id']}: {len(revision['items'])} total item(s)")
    print(f"review return point: {review_stage}; earliest owner: {revision['earliest_stage']}")
    print(f"invalidated decisions: {', '.join(removed) if removed else 'none'}")
    print(f"current checkpoint: {state.current}; stage completion history preserved")
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
    print(f"full builds: {revision.get('full_builds', 0)}; affected closure: {len(revision.get('rebuild_files', []))} files")
    for rel in revision.get("rebuild_files", []):
        print(f"    change/rebuild: {rel}")
    print(f"check only: {', '.join(revision.get('validation_stages', []))}")
    print(f"reuse/protect: {len(revision.get('reuse_files', []))} unchanged files")
    for item in revision["items"]:
        print(f"  [{item['status']}] {item['id']} {item['kind']} -> {item['owning_stage']}")
        print(f"      {item['request']}")
        print(f"      sources: {', '.join(item['affected_sources'])}")
        print(f"      acceptance: {'; '.join(item['acceptance_criteria'])}")
    return 0


def _cmd_mark(args, project: Path, state: State) -> int:
    path, revision = _load_round(state)
    if revision.get("status") == "collecting":
        raise ValueError("cannot mark while collecting feedback; seal the batch first")
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
    if revision.get("status") == "collecting":
        raise ValueError("cannot close while collecting feedback; seal and implement the batch first")
    pending = [item["id"] for item in revision["items"] if item.get("status") != "done"]
    if pending:
        raise ValueError("cannot close; pending items: " + ", ".join(pending))
    if state.current != revision["review_stage"]:
        raise ValueError(
            f"cannot close until the gated workflow returns to {revision['review_stage']}; current={state.current}"
        )
    if len(args.summary.strip()) < 40:
        raise ValueError("close summary must describe the completed round in at least 40 characters")
    if revision.get("schema_version") == 2:
        checked = revision.get("validation", {})
        if not checked.get("ok") or checked.get("input_signature") != scoped.input_signature(state.dir.parent, revision):
            raise ValueError("run rework.py check on the final files; typed validation labels alone cannot close a round")
        checked_at = datetime.fromisoformat(checked.get("checked_at", ""))
        if not 0 <= (datetime.now(timezone.utc) - checked_at).total_seconds() < 86400:
            raise ValueError("scoped validation expired; rerun checks before closing")
        for item in revision["items"]:
            for receipt in item.get("changed_files", []):
                if _sha256_file(state.dir.parent / receipt["path"]) != receipt["sha256"]:
                    raise ValueError("a marked file changed; mark its final version again before closing")
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
    parser.add_argument("command", choices=["plan", "start", "batch", "seal", "build", "status", "mark", "close", "check"])
    parser.add_argument("--sealed", action="store_true", help="user already asked to apply this complete batch now")
    parser.add_argument("--scope", choices=["full", "targeted"], default="targeted")
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
        if args.command == "seal":
            return _seal_round(state, pipe, args.why or "")
        if args.command == "check":
            path, revision = _load_round(state)
            return scoped.check_round(project, pipe, state, path, revision)
        if args.command == "build":
            path, revision = _load_round(state)
            if revision.get("status") == "collecting":
                raise ValueError("feedback collection is open; seal before building")
            if args.scope == "full" and revision.get("full_builds", 0) >= 2:
                raise ValueError("two full builds already used; identify unstable input and use targeted correction")
            if args.scope == "full":
                revision["full_builds"] = revision.get("full_builds", 0) + 1
            else:
                if not args.why:
                    raise ValueError("targeted build needs --why naming the changed artifacts")
            revision.setdefault("builds", []).append({"at": _now(), "scope": args.scope, "why": args.why})
            _write_round(path, revision)
            print(f"{args.scope} build recorded; use the persisted dependency closure")
            return 0
        if args.command in {"batch", "start"}:
            if args.plan is None:
                raise ValueError("revision needs --plan with affected sources; start no longer rewinds the stage tail")
            if args.command == "start":
                args.sealed = True
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
