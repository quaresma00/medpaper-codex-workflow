"""Scoped revisions: owners supply rules; a review checkpoint is not rewound."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json

SCIENTIFIC_KINDS = {"study-design", "data", "analysis", "final-protocol"}
LIFECYCLE_CHECKS = {
    "no_future_artifacts", "single_section_written", "temp_clean", "revision_rounds_closed",
    "manuscript_review_package_current", "s19_review_release_explicit", "scientific_master_frozen",
    "bundle_matches_freeze", "submission_audit_matches_freeze",
}
REVIEW_OUTPUTS = {"07_manuscript/human_review.md", "07_manuscript/scientific_master_freeze.json",
                  "08_submission/package_human_review.md", "08_submission/package_review_freeze.json"}


def active(project: Path) -> dict | None:
    state = project / ".wf/state.json"
    if not state.is_file():
        return None
    data = json.loads(state.read_text(encoding="utf-8"))
    round_id = data.get("active_revision_round")
    return json.loads((state.parent / "revisions" / f"{round_id}.json").read_text(encoding="utf-8")) if round_id else None


def snapshot(project: Path) -> dict[str, str]:
    """Bind deliverables, sources and small evidence; large raw/cache trees use file stats.

    This detects accidental scope drift, not malicious same-privilege timestamp forgery.
    Acquisition/reference integrity gates still independently validate their real receipts.
    """
    result = {}
    for path in sorted(project.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project).as_posix()
        if (rel.startswith((".wf/", "temp/", "08_submission/releases/", "07_manuscript/review_packages/"))
                or "__pycache__" in path.parts or path.name == ".gitkeep"):
            continue
        if rel.startswith("02_data/raw/") or "/cache/" in rel or "/fulltext/" in rel:
            st = path.stat()
            result[rel] = f"stat:{st.st_size}:{st.st_mtime_ns}"
        else:
            result[rel] = _sha256(path)
    return result


def input_signature(project: Path, revision: dict) -> str:
    from . import paths
    from .state import State
    state = State(project).load()
    engine = {p.relative_to(paths.repo_root()).as_posix(): _sha256(p)
              for folder in ("tools", "pipeline") for p in (paths.repo_root() / folder).rglob("*")
              if p.is_file() and p.suffix in {".py", ".toml", ".md"}}
    payload = {"files": snapshot(project), "engine": engine, "decisions": state.data.get("decisions", {}),
               "config": state.config(), "scope": revision.get("allowed_files", []),
               "checks": revision.get("checks", []), "stages": revision.get("validation_stages", [])}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def permits(project: Path, stage: str) -> bool:
    revision = active(project)
    return bool(revision and revision.get("schema_version") == 2 and revision.get("status") == "active"
                and stage in revision.get("validation_stages", []))


def guard_outputs(project: Path, outputs: list[Path]) -> None:
    revision = active(project)
    if not revision:
        return
    if revision.get("status") == "collecting":
        raise ValueError("feedback collection is open; seal the batch before building")
    if revision.get("schema_version") != 2:
        return  # Finish an already-open legacy round using its existing stage gates.
    allowed = set(revision.get("allowed_files", []))
    for path in outputs:
        try:
            rel = path.resolve().relative_to(project.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError("revision output leaves the project") from exc
        if rel not in allowed:
            raise ValueError(f"out-of-scope build: {rel}; declare its dependency before writing")


def scope_problems(project: Path, revision: dict) -> list[str]:
    before, now = revision.get("baseline", {}), snapshot(project)
    allowed = set(revision.get("allowed_files", []))
    changed = {rel for rel in set(before) | set(now) if before.get(rel) != now.get(rel)}
    # Only renewable source receipts/cache and backstage QC can be control maintenance.
    # Manuscripts, results, scripts, figures and tables are never exempt.
    def maintenance(rel):
        if "/cache/" in rel or rel == "06_refs/verified.json" or rel.startswith("08_submission/evidence/"):
            return True
        # A new journal may preserve the old integration/bundle, but only as byte-identical
        # new archive files. Existing archived attempts are never mutable control records.
        if (any(i["kind"] == "journal" for i in revision["items"]) and rel not in before
                and rel.startswith("08_submission/journal_archives/")):
            tail = rel.split("/", 3)[-1]
            return before.get("08_submission/" + tail) == now.get(rel)
        return False
    return [f"unplanned change: {rel}" for rel in sorted(changed - allowed) if not maintenance(rel)]


def plan_scope(project: Path, pipeline, revision: dict) -> None:
    from .dependencies import closure
    sources = sorted({rel.replace("\\", "/") for item in revision["items"] for rel in item["affected_sources"]})
    for rel in sources:
        _safe_path(project, rel)
    rebuild = set()
    for item in revision["items"]:
        rebuild.update(closure(project, item["affected_sources"], change_type=item["change_type"]))
    journal_change = any(i["kind"] == "journal" for i in revision["items"])
    if journal_change:
        # Choosing a different journal legitimately affects its whole derived package,
        # never the accepted scientific master. It still does not replay completed stages.
        rebuild.update(rel for rel in revision["baseline"] if rel.startswith("08_submission/") and
                       not rel.startswith(("08_submission/releases/", "08_submission/journal_archives/")))
        rebuild.update(output for sid in ("S20_journal", "S21_authors", "S22_polish", "S23_package")
                       for output in pipeline.stage(sid).outputs if output.startswith("08_submission/"))
    # Never automatically rewrite a journal layer while scientific approval is pending.
    if revision["review_stage"] == "S19_human_review":
        rebuild = {r for r in rebuild if not r.startswith("08_submission/")}
    stages = {item["owning_stage"] for item in revision["items"]}
    if any(r.startswith("03_analysis/") or r in {"01_protocol/protocol_final.md", "01_protocol/analysis_contract.json"} for r in sources):
        stages.add("S06_protocol_final")
        rebuild.update({"01_protocol/study_facts.json", "01_protocol/writing_readiness.json",
                        "01_protocol/analysis_contract.json", "01_protocol/protocol_final.md", "01_protocol/protocol_diff.md"})
    if any(r.startswith("04_tables/") for r in rebuild):
        stages.add("S10_tables")
    if any(r.startswith("05_figures/") for r in rebuild):
        stages.add("S11_figures")
    if any(r.startswith("08_submission/bundle/") for r in rebuild):
        stages.add("S23_package")
    if set(rebuild) & {"08_submission/integration/full_manuscript.md", "08_submission/integration/supplementary_methods.md"}:
        stages.add("S22_polish")
    for stage in pipeline.stages:
        if stage.id in {"S18_independent_review", "S19_human_review", "S24_package_human_review", "S25_submission_audit"}:
            continue
        if set(stage.outputs) & rebuild:
            stages.add(stage.id)
    if any(r.startswith("07_manuscript/") for r in rebuild):
        stages.add("S17_assemble")
    substantive = any(i["change_type"] == "scientific" for i in revision["items"])
    if substantive and revision["review_stage"] == "S19_human_review":
        stages.add("S18_independent_review")
        if any(r.startswith(("04_tables/", "05_figures/", "03_analysis/results/")) for r in rebuild):
            stages.add("S12_reconcile")
    stages.discard(revision["review_stage"])
    stages.update(revision.get("extra_validation_stages", []))
    # A copyedit owned by S19 still uses content checks, not S19's approval lifecycle.
    checks = []
    for sid in sorted(stages, key=lambda s: pipeline.stage(s).index):
        for spec in pipeline.stage(sid).gate:
            if spec["check"] in LIFECYCLE_CHECKS:
                continue
            if spec["check"] == "journal_workspace_ready" and revision["review_stage"] == "S19_human_review":
                continue
            # Pristine means a first journal copy, not a revised integration layer.
            if spec["check"] == "journal_workspace_ready":
                spec = {**spec, "require_pristine": False}
            checks.append({"stage": sid, "spec": spec})
    consistency = ("manuscript_structure", "assembly_matches_sources", "supplementary_methods_clean",
                   "citekeys_resolve", "numbers_have_provenance", "artifact_refs_consistent")
    if revision["review_stage"] == "S19_human_review":
        for spec in pipeline.stage("S19_human_review").gate:
            if spec["check"] in consistency:
                checks.append({"stage": "S19_human_review", "spec": spec})
    else:
        for spec in pipeline.stage("S24_package_human_review").gate:
            if spec["check"] not in LIFECYCLE_CHECKS | {"outputs_exist", "md_sections", "decision_recorded"}:
                checks.append({"stage": "S24_package_human_review", "spec": spec})
    unique = {json.dumps(row, sort_keys=True): row for row in checks}
    controls = set()
    for sid in stages:
        for output in pipeline.stage(sid).outputs:
            if (output.endswith(("manifest.json", "qc_report.json", "_review.md", "_qc.md", "moved_to_legend.md"))
                    or output in {"08_submission/package_content_baseline.json", "08_submission/portal_fields.json"}):
                controls.add(output)
    if any(r.startswith("08_submission/bundle/") for r in rebuild):
        controls.update({"08_submission/bundle/manifest.json", "08_submission/package_content_baseline.json",
                         "08_submission/portal_fields.json"})
    if revision.get("resume_from_science"):
        controls.add("08_submission/integration/journal_workspace.json")
    if "S05_analysis" in stages:
        controls.update({"03_analysis/analysis_log.md", "03_analysis/notes.md", "03_analysis/method_scan.md"})
    if "S12_reconcile" in stages:
        controls.add("07_manuscript/reconciliation.md")
    if "S22_polish" in stages:
        controls.update({"08_submission/integration/polish_report.json", "08_submission/integration/polish_log.md"})
        if revision.get("resume_from_science") or any(i["change_type"] == "administrative" for i in revision["items"]):
            controls.update({"08_submission/integration/prepolish/" + name for name in
                             ("facts.json", "full_manuscript.md", "supplementary_methods.md", "title_page.md", "statements.md")})
    if substantive:
        for sid in stages & {"S18_independent_review"}:
            controls.update(pipeline.stage(sid).outputs)
    revision.update({"rebuild_files": sorted(rebuild), "validation_stages": sorted(stages),
                     "checks": list(unique.values()), "allowed_files": sorted((rebuild | controls) - REVIEW_OUTPUTS),
                     "requires_independent_science_review": substantive,
                     "reuse_files": sorted(set(revision.get("baseline", {})) - ((rebuild | controls) - REVIEW_OUTPUTS))})


def validate(project: Path, pipeline, state, revision: dict) -> tuple[list, str]:
    from . import checks
    from .checks import Ctx, Result
    checks.load_all()
    problems = scope_problems(project, revision)
    results = [Result(not problems, "revision_scope_unchanged", "; ".join(problems[:10]) or "unaffected files preserved")]
    seen = set()
    for row in revision["checks"]:
        spec = row["spec"]
        contextual = spec["check"] in {"outputs_exist", "handoff_recorded", "decision_recorded", "reference_provenance"}
        identity = json.dumps([row["stage"] if contextual else None, spec], sort_keys=True)
        if identity in seen:
            continue
        seen.add(identity)
        fn = checks.get(spec["check"])
        try:
            result = fn(Ctx(pipeline, state, project, pipeline.stage(row["stage"]), spec))
        except Exception as exc:
            result = Result(False, spec["check"], f"{type(exc).__name__}: {exc}")
        if "severity" in spec and not result.ok:
            result.severity = spec["severity"]
        results.append(result)
    return results, input_signature(project, revision)


def check_round(project: Path, pipeline, state, path: Path, revision: dict) -> int:
    if revision.get("status") != "active":
        raise ValueError("seal the feedback batch before checking")
    if revision.get("schema_version") != 2:
        raise ValueError("finish the legacy round through its recorded stage gates")
    results, signature = validate(project, pipeline, state, revision)
    revision["validation"] = {"input_signature": signature, "ok": not any(r.blocking for r in results),
                              "checked_at": datetime.now(timezone.utc).isoformat(),
                              "artifact_hashes": {rel: _sha256(project / rel) for rel in revision["allowed_files"]
                                                  if (project / rel).is_file()},
                              "results": [{"check": r.check, "ok": r.ok, "detail": r.detail,
                                           "severity": r.severity} for r in results]}
    atomic_json(path, revision)
    for result in results:
        if not result.ok:
            print(f"[{result.label}] {result.check}: {result.detail}")
    print(f"Scoped checks: {sum(r.ok for r in results)}/{len(results)}; checkpoint remains {state.current}")
    return 0 if revision["validation"]["ok"] else 2


def record_build(project: Path, output: Path, sources: list[Path]) -> None:
    """A real builder receipt, not a user-typed 'validated' label."""
    revision = active(project)
    if not revision or revision.get("schema_version") != 2:
        return
    rel = output.resolve().relative_to(project.resolve()).as_posix()
    revision.setdefault("build_receipts", {})[rel] = {
        "sha256": _sha256(output),
        "sources": {str(p.resolve()): _sha256(p) for p in sources if p is not None},
    }
    atomic_json(project / ".wf/revisions" / f"{revision['round_id']}.json", revision)


def baseline_capture_allowed(project: Path) -> bool:
    """Only source-based package jobs may renew the content baseline in-place at S24."""
    revision = active(project)
    if not revision or not permits(project, "S23_package"):
        return False
    if all(i["change_type"] == "layout" for i in revision["items"]):
        return False
    from .packagecontent import build_baseline, BASELINE_REL
    current = build_baseline(project)
    old_path = project / BASELINE_REL
    previous = json.loads(old_path.read_text(encoding="utf-8")) if old_path.is_file() else {}
    old = {r["path"]: r for r in previous.get("records", [])}
    for row in current["records"]:
        prior = old.get(row["path"], {})
        if (row.get("visible_text_sha256") == prior.get("visible_text_sha256") and
                row.get("source_sha256") == prior.get("source_sha256")):
            continue
        receipt = revision.get("build_receipts", {}).get(row["path"], {})
        if receipt.get("sha256") != _sha256(project / row["path"]) or not receipt.get("sources"):
            return False
        if any(not Path(p).is_file() or _sha256(Path(p)) != h for p, h in receipt["sources"].items()):
            return False
        if row.get("source") and str((project / row["source"]).resolve()) not in receipt["sources"]:
            return False
    return True


def resume_package(project: Path, pipeline, state) -> str:
    """After renewed S19 approval, reopen only the package dependency closure at S24."""
    from .dependencies import closure
    prior_id = state.data["resume_package_revision"]
    directory = state.dir / "revisions"
    prior = json.loads((directory / f"{prior_id}.json").read_text(encoding="utf-8"))
    if prior.get("status") != "complete":
        raise ValueError("scientific revision must close before package adaptation resumes")
    numbers = [int(p.stem[1:]) for p in directory.glob("R*.json") if p.stem[1:].isdigit()]
    round_id = f"R{max(numbers, default=0) + 1:03d}"
    current_files = snapshot(project)
    changed = [rel for rel in prior["rebuild_files"]
               if prior["baseline"].get(rel) != current_files.get(rel)]
    dependants = [rel for rel in closure(project, changed) if rel.startswith("08_submission/")]
    # Rebinding the origin does not copy over journal edits. The agent merges only changed
    # scientific passages, then the rebase tool verifies changed destinations before binding.
    dependants.append("08_submission/integration/journal_workspace.json")
    items = prior.get("deferred_package_items", []) + [{
        "kind": "cover-letter-or-package-structure", "change_type": "administrative",
        "owning_stage": "S23_package", "affected_sources": sorted(set(dependants)),
        "request": "Merge the newly approved scientific delta into the existing journal copies and affected uploads; preserve unrelated journal edits.",
        "acceptance_criteria": ["Journal origin matches the new S19 freeze", "Changed science and all actual consumers agree", "Unrelated files are preserved"],
        "status": "pending", "resolution": None, "changed_files": [], "validated_by": [],
    }]
    for index, item in enumerate(items, 1):
        item["id"] = f"{round_id}-{index:02d}"
    revision = {"schema_version": 2, "round_id": round_id, "status": "active",
                "review_stage": "S24_package_human_review", "origin_stage": "S24_package_human_review",
                "earliest_stage": "S20_journal", "resume_from_science": prior_id,
                "created_at": datetime.now(timezone.utc).isoformat(), "full_builds": 0,
                "feedback_updates": prior["feedback_updates"], "items": items,
                "baseline": snapshot(project), "extra_validation_stages": ["S20_journal", "S22_polish", "S23_package"]}
    plan_scope(project, pipeline, revision)
    atomic_json(directory / f"{round_id}.json", revision)
    state.data.pop("resume_package_revision", None)
    state.data["active_revision_round"] = round_id
    state.complete("S19_human_review", "S24_package_human_review")
    state.event("revision_package_resumed", f"{prior_id} -> {round_id}; completed stages preserved")
    state.save()
    return round_id
