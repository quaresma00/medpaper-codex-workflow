"""wf - the workflow driver.

Design intent: this CLI is the agent's only source of truth about *where it is*
and *what is allowed next*. `wf status` alone must be enough to resume work
correctly after a context reset, so it prints the invariants, the progress map,
the gate state, the last handoff and the full stage card.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import sys
from pathlib import Path

from . import checks, gates, paths, registry
from .state import State

BAR = "=" * 78
DASH = "-" * 78
STAGE_ALIASES = {
    # v1.2 combined title/author/journal work differently. Any active legacy tail stage
    # returns to canonical assembly so the independent and human review gates cannot be
    # skipped during an in-place engine upgrade.
    "S17_frontmatter": "S17_assemble",
    "S18_journal": "S17_assemble",
    "S19_polish": "S17_assemble",
    "S20_package": "S17_assemble",
}
NON_OVERRIDABLE_GATES = {
    "data_acquisition_complete",
    "reference_provenance",
    "refs_library",
    "bib_ris_match_library",
    "citekeys_resolve",
    "revision_rounds_closed",
    "s19_review_release_explicit",
    "scientific_master_frozen",
    "scientific_master_unchanged",
    "journal_workspace_ready",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _load(need_state: bool = True):
    tmp_state = State(paths.project_dir({}), ".wf")
    overrides = tmp_state.config() if tmp_state.config_file.exists() else {}
    pipe = registry.load(overrides)
    proj = paths.project_dir(pipe.layout)
    st = State(proj, pipe.layout.get("state_dir", ".wf"))
    if need_state:
        st.load()
        previous_version = str(st.data.get("pipeline_version", "unknown"))
        st.migrate_pipeline(str(pipe.meta.get("version", "0")),
                            [stage.id for stage in pipe.stages], STAGE_ALIASES)
        # v1.4 introduces the S19 scientific-master freeze and derived per-journal sources.
        # A legacy run already in the journal tail cannot prove that its 07_manuscript files
        # were not polished in place, so return it to S19 without deleting any artifact.
        if (previous_version != str(pipe.meta.get("version", "0")) and
                st.current in {stage.id for stage in pipe.stages[pipe.stage("S20_journal").index:]} and
                not (proj / "07_manuscript/scientific_master_freeze.json").is_file()):
            later = [stage.id for stage in pipe.stages_after("S19_human_review")]
            st.reset_forward(later)
            st.clear_decisions_for(later)
            st.rewind(
                "S19_human_review",
                "pipeline v1.4 requires review/freeze of the scientific master before "
                "journal-specific integration work",
            )
    return pipe, st, proj


def _mark(pipe, st, stage) -> str:
    if st.is_done(stage.id):
        return "x"
    if st.current == stage.id:
        return ">"
    return " "


def _print_progress(pipe, st) -> None:
    print("PROGRESS")
    for s in pipe.stages:
        m = _mark(pipe, st, s)
        loops = st.stage_info(s.id).get("loops", 0)
        suffix = ""
        if m == ">":
            suffix = "   <-- you are here" + (f" (revisit #{loops})" if loops else "")
        print(f"  [{m}] {s.index + 1:>2}. {s.id:<20} {s.title}{suffix}")


def _print_invariants(pipe) -> None:
    inv = pipe.policy.get("invariants", [])
    if not inv:
        return
    print("NON-NEGOTIABLE INVARIANTS")
    for i, line in enumerate(inv, 1):
        print(f"  {i}. {line}")
    print()


def _gate_lines(results) -> None:
    for r in results:
        print(f"  [{r.label}] {r.check}")
        if r.detail:
            print(f"         {r.detail}")
        for h in r.hints:
            print(f"         -> {h}")


def _declared_and_free(pipe) -> tuple[set[str], list[str]]:
    return pipe.all_declared_outputs(), pipe.freeform + pipe.policy.get("always_allowed", [])


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_init(args) -> int:
    pipe = registry.load()
    proj = paths.project_dir(pipe.layout)
    st = State(proj, pipe.layout.get("state_dir", ".wf"))
    if st.exists() and not args.force:
        print(f"run state already exists at {paths.rel(st.file)}")
        print("keeping existing artifacts and state; use --force only to reset intentionally")
        return 0
    for name in pipe.layout.get("dirs", {}):
        (proj / name).mkdir(parents=True, exist_ok=True)
        (proj / name / ".gitkeep").touch()
    for sub in (
        "02_data/raw", "02_data/acquisition", "02_data/derived", "03_analysis/code", "03_analysis/results",
        "04_tables/main", "04_tables/supplementary", "05_figures/code", "05_figures/out",
        "05_figures/qc", "06_refs/cache", "06_refs/fulltext", "06_refs/deepread",
        "08_submission/cache", "08_submission/bundle",
    ):
        (proj / sub).mkdir(parents=True, exist_ok=True)
        (proj / sub / ".gitkeep").touch()
    (proj / pipe.layout.get("temp_dir", "temp")).mkdir(parents=True, exist_ok=True)
    (proj / pipe.layout.get("temp_dir", "temp") / ".gitkeep").touch()

    st.create(pipe.meta.get("name", "pipeline"), pipe.meta.get("version", "0"), pipe.first().id)
    print(f"initialised {pipe.meta.get('name')} {pipe.meta.get('version')} at {paths.rel(proj)}")
    print(f"current stage: {pipe.first().id}")
    print("\nnext:  .venv/Scripts/python.exe tools/wf.py status")
    return 0


def cmd_status(args) -> int:
    pipe, st, proj = _load()
    stage = pipe.stage(st.current)
    results = gates.run_stage(pipe, st, proj, stage)
    ok, blocking, warned = gates.summarize(results)

    if args.json:
        print(json.dumps({
            "pipeline": pipe.meta.get("name"),
            "current": stage.id,
            "index": stage.index + 1,
            "total": len(pipe.stages),
            "title": stage.title,
            "card": paths.rel(stage.card_path()),
            "gate_ok": ok,
            "blocking": blocking,
            "warnings": warned,
            "outputs": stage.outputs,
            "results": [{"check": r.check, "label": r.label, "detail": r.detail} for r in results],
        }, indent=2, ensure_ascii=False))
        return 0

    print(BAR)
    print(f"{pipe.meta.get('name')} {pipe.meta.get('version')}  |  stage {stage.index + 1}/{len(pipe.stages)}  |  {stage.id}")
    print(stage.title)
    print(BAR)
    print()
    _print_invariants(pipe)
    _print_progress(pipe, st)
    print()
    print(f"GATE  ({len(results) - blocking - warned}/{len(results)} passing"
          + (f", {warned} warning(s)" if warned else "") + ")")
    if ok:
        print("  gate is GREEN -> you may run:  .venv/Scripts/python.exe tools/wf.py advance --note \"...\"")
    else:
        _gate_lines([r for r in results if not r.ok])
    print()

    notes = st.data.get("handoff", [])
    print("LAST HANDOFF")
    if notes:
        last = notes[-1]
        print(f"  [{last['stage']} @ {last['at']}]")
        for line in last["note"].splitlines():
            print(f"  {line}")
    else:
        print("  (none yet)")
    print()

    if stage.needs_user:
        print("!! THIS STAGE NEEDS INPUT FROM THE USER. Ask, then proceed.")
        print()

    print("DECLARED OUTPUTS FOR THIS STAGE (create these, nothing else)")
    for o in stage.outputs:
        flag = "ok " if (proj / o).exists() else "-- "
        print(f"  {flag} project/{o}")
    print()

    if not args.brief:
        card = stage.card_path()
        print(DASH)
        print(f"STAGE CARD  ({paths.rel(card)})")
        print(DASH)
        if card.exists():
            print(card.read_text(encoding="utf-8").rstrip())
        else:
            print(f"!! card file missing: {card}")
        print(DASH)
    return 0


def cmd_card(args) -> int:
    pipe, st, _ = _load(need_state=False)
    if args.stage:
        stage = pipe.resolve(args.stage)
    else:
        st.load()
        stage = pipe.stage(st.current)
    card = stage.card_path()
    if not card.exists():
        print(f"card missing: {card}")
        return 1
    print(card.read_text(encoding="utf-8").rstrip())
    return 0


def cmd_check(args) -> int:
    pipe, st, proj = _load()
    stage = pipe.resolve(args.stage) if args.stage else pipe.stage(st.current)
    results = gates.run_stage(pipe, st, proj, stage)
    ok, blocking, warned = gates.summarize(results)
    if args.json:
        print(json.dumps({
            "stage": stage.id, "gate_ok": ok, "blocking": blocking, "warnings": warned,
            "results": [{"check": r.check, "ok": r.ok, "label": r.label,
                         "detail": r.detail, "hints": r.hints} for r in results],
        }, indent=2, ensure_ascii=False))
        return 0 if ok else 2
    print(f"gate: {stage.id} - {stage.title}")
    print(DASH)
    _gate_lines(results)
    print(DASH)
    if ok:
        print(f"GREEN ({warned} warning(s))" if warned else "GREEN")
        return 0
    print(f"RED - {blocking} blocking issue(s)")
    return 2


def cmd_advance(args) -> int:
    pipe, st, proj = _load()
    stage = pipe.stage(st.current)
    results = gates.run_stage(pipe, st, proj, stage)
    ok, blocking, _ = gates.summarize(results)
    non_overridable_failures = [r for r in results if r.blocking and
                                r.check in NON_OVERRIDABLE_GATES]
    if non_overridable_failures:
        print(f"refusing to advance: {len(non_overridable_failures)} non-overridable "
              f"gate(s) failed in {stage.id}")
        print(DASH)
        _gate_lines(non_overridable_failures)
        print(DASH)
        failed_names = {result.check for result in non_overridable_failures}
        if "data_acquisition_complete" in failed_names:
            print("--force cannot waive full-data acquisition. Acquire the complete "
                  "protocol-defined universe and exhaust pagination; if access is truly "
                  "source-limited, obtain and record the user's explicit authorization.")
        reference_failures = failed_names & {
            "reference_provenance", "refs_library", "bib_ris_match_library", "citekeys_resolve"
        }
        if reference_failures:
            print("--force cannot waive bibliographic provenance. Re-fetch the real PubMed "
                  "record or remove/replace the citation.")
        if "revision_rounds_closed" in failed_names:
            print("--force cannot waive an unfinished revision round. Complete every recorded "
                  "item, return through its gates, and close the round at the review stage.")
        if "s19_review_release_explicit" in failed_names:
            print("--force cannot waive S19 review. Present the current versioned ZIP and exact "
                  "artifact paths, then wait for the user's explicit no-further-review statement.")
        return 2
    if not ok and not args.force:
        print(f"refusing to advance: {blocking} blocking issue(s) in {stage.id}")
        print(DASH)
        _gate_lines([r for r in results if not r.ok])
        print(DASH)
        print("fix them, or override deliberately with --force (recorded in state)")
        return 2

    note = args.note
    if pipe.policy.get("handoff_required", True) and not note and not st.notes_for(stage.id):
        print("refusing to advance: no handoff note recorded for this stage.")
        print('  .venv/Scripts/python.exe tools/wf.py advance --note "what was produced, what was decided, what is still open"')
        print("A handoff note is how the next session (or the next you, post-compaction) picks this up.")
        return 2
    if note:
        st.add_note(note, stage.id)
    if not ok and args.force:
        st.event("force_advance", f"{stage.id} with {blocking} blocking issue(s)")
        st.add_note(f"[FORCED ADVANCE] gate had {blocking} blocking issue(s): "
                    + "; ".join(f"{r.check}: {r.detail}" for r in results if r.blocking), stage.id)

    nxt = pipe.next_of(stage.id)
    st.complete(stage.id, nxt.id if nxt else None)
    if nxt:
        print(f"{stage.id} closed. now at {nxt.id} - {nxt.title}")
        print("\nnext:  .venv/Scripts/python.exe tools/wf.py status")
    else:
        print(f"{stage.id} closed. pipeline complete.")
    return 0


def cmd_loop(args) -> int:
    pipe, st, _ = _load()
    target = pipe.resolve(args.to)
    cur = pipe.stage(st.current)
    if target.index > cur.index:
        print(f"{target.id} is ahead of {cur.id}; use advance, not loop")
        return 1
    st.add_note(f"[LOOP] returning to {target.id}: {args.why}", cur.id)
    reset_ids = [target.id, *[s.id for s in pipe.stages_after(target.id)]]
    st.reset_forward(reset_ids[1:])
    st.clear_decisions_for(reset_ids)
    st.rewind(target.id, args.why)
    print(f"returned to {target.id} - {target.title}")
    print("stages after it are pending again; their artifacts were left untouched")
    return 0


def cmd_note(args) -> int:
    _, st, _ = _load()
    st.add_note(args.text)
    print(f"noted against {st.current}")
    return 0


def cmd_decide(args) -> int:
    _, st, _ = _load()
    if len(args.why.strip()) < 40:
        print("rationale too short (need >= 40 chars). A decision without a reason is a guess.")
        return 1
    st.record_decision(args.name, args.value, args.why)
    st.add_note(f"[DECISION] {args.name} = {args.value}\n{args.why}")
    print(f"recorded {args.name} = {args.value}")
    return 0


def cmd_tree(args) -> int:
    pipe, st, proj = _load()
    print(f"{pipe.meta.get('name')} {pipe.meta.get('version')}  ({len(pipe.stages)} stages)")
    print(DASH)
    for s in pipe.stages:
        m = _mark(pipe, st, s)
        print(f"[{m}] {s.index + 1:>2}. {s.id:<20} {s.title}")
        if args.verbose:
            for o in s.outputs:
                print(f"        out  {'ok' if (proj / o).exists() else '--'}  {o}")
            for g in s.gate:
                extra = " ".join(f"{k}={v}" for k, v in g.items() if k != "check")
                print(f"        gate {g['check']} {extra}".rstrip())
    print(DASH)
    for name, rec in st.data.get("decisions", {}).items():
        print(f"decision  {name} = {rec['value']}  ({rec['at']})")
    return 0


def cmd_clean(args) -> int:
    pipe, st, proj = _load()
    declared, allowed = _declared_and_free(pipe)
    tmp = pipe.layout.get("temp_dir", "temp")
    scratch, orphans = [], []
    for p in proj.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(proj).as_posix()
        if rel.startswith(f"{tmp}/"):
            if p.name != ".gitkeep":
                scratch.append(rel)
            continue
        if rel in declared or any(fnmatch.fnmatch(rel, g) for g in allowed):
            continue
        orphans.append(rel)

    print(f"scratch files in project/{tmp}/: {len(scratch)}")
    for r in scratch[:40]:
        print(f"  del  {r}")
    print(f"\nundeclared files elsewhere: {len(orphans)}")
    for r in orphans[:40]:
        print(f"  ??   {r}")
    if orphans:
        print("\nundeclared files are NOT auto-deleted. Either:")
        print("  - move them into the right folder, or")
        print("  - declare them in pipeline.toml (stage outputs / [freeform].globs), or")
        print("  - delete them yourself if they were scratch")
    if not args.apply:
        print("\n(dry run; pass --apply to delete the scratch files)")
        return 0
    for r in scratch:
        (proj / r).unlink(missing_ok=True)
    st.event("clean", f"deleted {len(scratch)} scratch file(s)")
    st.save()
    print(f"\ndeleted {len(scratch)} scratch file(s)")
    return 0


def cmd_doctor(args) -> int:
    pipe = registry.load()
    proj = paths.project_dir(pipe.layout)
    rows: list[tuple[str, str, str]] = []

    rows.append(("python", "ok", sys.version.split()[0]))
    rows.append(("pipeline.toml", "ok" if paths.pipeline_file().exists() else "MISSING",
                 paths.rel(paths.pipeline_file())))

    root = paths.repo_root()
    codex_files = (
        root / "AGENTS.md",
        root / ".agents/skills/medpaper-codex-pipeline/SKILL.md",
        root / ".agents/skills/medpaper-codex-pipeline/agents/openai.yaml",
        root / "reference/codex-integration.md",
    )
    missing_codex = [p.relative_to(root).as_posix() for p in codex_files if not p.is_file()]
    rows.append(("Codex integration", "ok" if not missing_codex else "MISSING",
                 "repository skill + instructions present" if not missing_codex else
                 "absent: " + ", ".join(missing_codex)))

    obsolete = (
        root / ".agents/AGENTS.md",
        root / ".medpaper-target",
        root / "tools/install_adapters.py",
        root / "tools/hooks/skill_guard.py",
        root / "reference/skill_policy.toml",
    )
    present_obsolete = [p.relative_to(root).as_posix() for p in obsolete if p.exists()]
    rows.append(("legacy adapters", "ok" if not present_obsolete else "BROKEN",
                 "none" if not present_obsolete else "remove: " + ", ".join(present_obsolete)))

    missing_cards = [s.id for s in pipe.stages if not s.card_path().exists()]
    rows.append(("stage cards", "ok" if not missing_cards else "MISSING",
                 f"{len(pipe.stages) - len(missing_cards)}/{len(pipe.stages)} present"
                 + (f" - absent: {', '.join(missing_cards)}" if missing_cards else "")))

    checks.load_all()
    used = {g["check"] for s in pipe.stages for g in s.gate}
    unknown = sorted(used - set(checks.known()))
    rows.append(("gate checks", "ok" if not unknown else "BROKEN",
                 f"{len(used)} used, {len(checks.known())} registered"
                 + (f" - unknown: {', '.join(unknown)}" if unknown else "")))

    st = State(proj, pipe.layout.get("state_dir", ".wf"))
    rows.append(("run state", "ok" if st.exists() else "not initialised", paths.rel(st.file)))

    # The driver is stdlib-only; the science deps belong to the project venv, so probe
    # that interpreter rather than whichever one happens to be running this command.
    sci = _science_python()
    rows.append(("science venv", "ok" if sci else "absent",
                 str(sci) if sci else "create it: uv venv .venv"))
    mods = ("matplotlib", "numpy", "openpyxl", "pandas", "scipy", "docx")
    if sci:
        found = _probe_modules(sci, mods)
        for mod in mods:
            why = {"matplotlib": "figures", "numpy": "figures/QC", "openpyxl": "tables",
                   "pandas": "analysis", "scipy": "QC grey-region labelling (optional)",
                   "docx": "deterministic Word submission files"}[mod]
            ok = found.get(mod)
            status = "ok" if ok else ("absent" if mod == "scipy" else "MISSING")
            rows.append((f"  {mod}", status, why if ok else
                         f"needed for {why}: uv pip install --python {sci} {mod}"))
    else:
        rows.append(("  science deps", "unknown", "cannot probe without a venv"))

    for exe, why in (("pandoc", "reference rendering"), ("Rscript", "R analyses"), ("git", "versioning")):
        p = shutil.which(exe)
        rows.append((exe, "ok" if p else "absent", p or f"optional, used for {why}"))

    import os
    key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY")
    rows.append(("NCBI_API_KEY", "ok" if key else "not set",
                 "10 req/s" if key else "3 req/s without a key; set NCBI_API_KEY to raise it"))

    width = max(len(r[0]) for r in rows)
    bad = 0
    for name, status, detail in rows:
        if status in ("MISSING", "BROKEN"):
            bad += 1
        print(f"{name:<{width}}  {status:<16} {detail}")
    print(DASH)
    print("doctor: OK" if bad == 0 else f"doctor: {bad} problem(s) need attention")
    return 0 if bad == 0 else 1


def _science_python() -> Path | None:
    """The venv interpreter that runs figures/tables/analysis, if it exists."""
    root = paths.repo_root()
    for cand in (root / ".venv/Scripts/python.exe", root / ".venv/bin/python"):
        if cand.exists():
            return cand
    return None


def _probe_modules(python: Path, mods) -> dict[str, bool]:
    import subprocess
    code = (
        "import importlib.util, json\n"
        f"m={list(mods)!r}\n"
        "print(json.dumps({x: importlib.util.find_spec(x) is not None for x in m}))"
    )
    try:
        out = subprocess.run([str(python), "-c", code], capture_output=True, text=True, timeout=60)
        return json.loads(out.stdout.strip() or "{}")
    except Exception:  # noqa: BLE001
        return {}


def cmd_config(args) -> int:
    pipe, st, _ = _load()
    if args.action == "list":
        for k, v in sorted(pipe.targets.items()):
            print(f"{k:<28} {v}")
        return 0
    if args.action == "get":
        print(pipe.targets.get(args.key, "<unset>"))
        return 0
    st.set_config(args.key, args.value)
    print(f"{args.key} = {args.value}   (project override written to {paths.rel(st.config_file)})")
    return 0


def cmd_invariants(args) -> int:
    pipe = registry.load()
    for i, line in enumerate(pipe.policy.get("invariants", []), 1):
        print(f"{i}. {line}")
    return 0


def cmd_checks(args) -> int:
    checks.load_all()
    pipe = registry.load()
    used: dict[str, list[str]] = {}
    for s in pipe.stages:
        for g in s.gate:
            used.setdefault(g["check"], []).append(s.id)
    for name in checks.known():
        where = used.get(name, [])
        print(f"{name:<28} {'used by ' + ', '.join(where) if where else '(unused)'}")
    return 0


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wf",
        description="medpaper workflow driver. Start with: wf status",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="scaffold project folders and create run state")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("status", help="where am I, what is blocking, and the full stage card")
    p.add_argument("--brief", action="store_true", help="omit the stage card")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("card", help="print a stage card")
    p.add_argument("stage", nargs="?")
    p.set_defaults(fn=cmd_card)

    p = sub.add_parser("check", help="run the gate for a stage without advancing")
    p.add_argument("stage", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("advance", help="close the current stage and move to the next")
    p.add_argument("--note", help="handoff note (required unless already noted)")
    p.add_argument("--force", action="store_true", help="advance despite a red gate; recorded in state")
    p.set_defaults(fn=cmd_advance)

    p = sub.add_parser("loop", help="deliberately return to an earlier stage")
    p.add_argument("--to", required=True)
    p.add_argument("--why", required=True)
    p.set_defaults(fn=cmd_loop)

    p = sub.add_parser("note", help="append to the handoff log")
    p.add_argument("text")
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("decide", help="record a gated decision with its rationale")
    p.add_argument("name")
    p.add_argument("value")
    p.add_argument("--why", required=True)
    p.set_defaults(fn=cmd_decide)

    p = sub.add_parser("tree", help="whole pipeline with status")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_tree)

    p = sub.add_parser("clean", help="report scratch/undeclared files; --apply deletes scratch")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_clean)

    p = sub.add_parser("doctor", help="environment and wiring check")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("config", help="view or override per-project targets")
    p.add_argument("action", choices=["list", "get", "set"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(fn=cmd_config)

    p = sub.add_parser("invariants", help="print the non-negotiable rules")
    p.set_defaults(fn=cmd_invariants)

    p = sub.add_parser("checks", help="list registered gate checks")
    p.set_defaults(fn=cmd_checks)

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd == "config" and args.action == "set" and (not args.key or args.value is None):
        ap.error("config set needs KEY and VALUE")
    if args.cmd == "config" and args.action == "get" and not args.key:
        ap.error("config get needs KEY")
    try:
        return args.fn(args)
    except SystemExit:
        raise
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

