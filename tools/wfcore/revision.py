"""Scoped revisions: owners supply rules; a review checkpoint is not rewound."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json
from .evidence import renewable

SCIENTIFIC_KINDS = {"study-design", "data", "analysis", "final-protocol"}
LIFECYCLE_CHECKS = {
    "no_future_artifacts", "single_section_written", "temp_clean", "revision_rounds_closed",
    "manuscript_review_package_current", "s19_review_release_explicit", "review_round_approved", "scientific_master_frozen",
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
        tracked_acceptance = rel.startswith((".wf/executor_acceptance_", ".wf/benchmark_")) and rel.endswith(".json")
        if ((rel.startswith(".wf/") and not tracked_acceptance) or rel.startswith(("temp/", "08_submission/releases/", "07_manuscript/review_packages/"))
                or "__pycache__" in path.parts or path.name == ".gitkeep"):
            continue
        if rel.startswith("02_data/raw/") or "/cache/" in rel or "/fulltext/" in rel:
            st = path.stat()
            result[rel] = f"stat:{st.st_size}:{st.st_mtime_ns}"
        else:
            result[rel] = _sha256(path)
    return result


def input_signature(project: Path, revision: dict, files: dict | None = None) -> str:
    from . import paths
    from .state import State
    state = State(project).load()
    engine = {p.relative_to(paths.repo_root()).as_posix(): _sha256(p)
              for folder in ("tools", "pipeline", "reference") for p in (paths.repo_root() / folder).rglob("*")
              if p.is_file() and p.suffix.lower() in {".py", ".r", ".toml", ".md"}}
    files = snapshot(project) if files is None else files
    from .buildproof import load as build_receipts
    observed={}
    for output,receipt in build_receipts(project).items():
        if output not in revision.get("allowed_files",[]):continue
        inputs={}
        for name in receipt.get("sources",{}):
            if name in receipt.get("engine_inputs",[]):continue
            path=Path(name)
            try:
                rel=path.resolve().relative_to(project.resolve()).as_posix()
                digest=files.get(rel)
            except ValueError:
                digest=None
            inputs[name]=digest if digest is not None else _sha256(path) if path.is_file() else None
        observed[output]={"inputs":inputs,"entrypoints":receipt.get("entrypoints",[]),"parameters":receipt.get("parameters",{})}
    payload = {"files": {r: h for r, h in files.items() if not renewable(r)},
               "engine": engine, "decisions": state.data.get("decisions", {}),
               "pipeline_version": state.data.get("pipeline_version"), "engine_pin": state.data.get("engine_pin"),
               "config": state.config(), "scope": revision.get("allowed_files", []),
               "checks": revision.get("checks", []), "stages": revision.get("validation_stages", []),"observed_build_inputs":observed}
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


def scope_problems(project: Path, revision: dict, files: dict | None = None) -> list[str]:
    before, now = revision.get("baseline", {}), snapshot(project) if files is None else files
    allowed = set(revision.get("allowed_files", []))
    changed = {rel for rel in set(before) | set(now) if before.get(rel) != now.get(rel)}
    # Only renewable source receipts/cache and backstage QC can be control maintenance.
    # Manuscripts, results, scripts, figures and tables are never exempt.
    def maintenance(rel):
        if renewable(rel):
            return True
        # A new journal may preserve the old integration/bundle, but only as byte-identical
        # new archive files. Existing archived attempts are never mutable control records.
        if (any(i["kind"] in {"journal", "journal-switch"} for i in revision["items"]) and rel not in before
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
        rebuild.update(closure(project, item["affected_sources"], change_type=item["change_type"],
                               baseline_documents=revision.get("baseline_documents"), extra_edges=revision.get("dependency_edges")))
    journal_change = any(i["kind"] in {"journal", "journal-switch"} for i in revision["items"])
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
    scientific_inputs = substantive or any(r.startswith(("02_data/", "03_analysis/")) or r in {
        "01_protocol/protocol_v1.md", "01_protocol/protocol_final.md", "01_protocol/analysis_contract.json"} for r in sources)
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
            if not scientific_inputs and spec["check"] == "data_acquisition_complete":
                continue  # Unplanned raw/manifest drift is still rejected by scope/signature checks.
            if not scientific_inputs and spec["check"] == "writing_ready":
                spec = {**spec, "reuse_analysis": True}
            checks.append({"stage": sid, "spec": spec})
    consistency = ("manuscript_structure", "assembly_matches_sources", "supplementary_methods_clean",
                   "citekeys_resolve", "numbers_have_provenance", "artifact_refs_consistent", "executor_acceptance")
    if revision["review_stage"] == "S19_human_review":
        for spec in pipeline.stage("S19_human_review").gate:
            if spec["check"] in consistency:
                checks.append({"stage": "S19_human_review", "spec": spec})
    else:
        for spec in pipeline.stage("S24_package_human_review").gate:
            if spec["check"] not in LIFECYCLE_CHECKS | {"outputs_exist", "md_sections", "decision_recorded"}:
                checks.append({"stage": "S24_package_human_review", "spec": spec})
    unique = {json.dumps(row, sort_keys=True): row for row in checks}
    if not scientific_inputs:
        unique={k:row for k,row in unique.items() if row["spec"]["check"]!="data_acquisition_complete"}
    controls = set()
    for stage, control in (("S07_artifacts", ".wf/benchmark_science_lock.json"),
                           ("S20_journal", ".wf/benchmark_journal_lock.json"),
                           ("S17_assemble", ".wf/executor_acceptance_science.json"),
                           ("S22_polish", ".wf/executor_acceptance_journal_pre.json"),
                           ("S23_package", ".wf/executor_acceptance_journal_final.json")):
        if stage in stages: controls.add(control)
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
        controls.add("08_submission/integration/presentation_map.json")
        controls.update("08_submission/integration/prepolish/"+name for name in
                        ("facts.json","full_manuscript.md","supplementary_methods.md","title_page.md",
                         "statements.md","figure_legends.md","supplementary_figure_legends.md"))
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


def add_dependency(project: Path, pipeline, path: Path, revision: dict, source: str, output: str, why: str) -> None:
    """Extend a discovered consumer edge, not user feedback or permission to edit its inputs."""
    if revision.get("schema_version") != 2 or revision.get("status") != "active" or len(why.strip()) < 30:
        raise ValueError("dependency extension needs an active sealed round and a concrete reason")
    source, _ = _safe_path(project, source); output, _ = _safe_path(project, output)
    if source not in revision["allowed_files"]:
        raise ValueError("dependency must originate in the existing affected closure")
    if output.startswith((".wf/", "temp/", "02_data/raw/", "08_submission/releases/")):
        raise ValueError("dependency cannot authorize raw, control or frozen-release writes")
    if not any(i["change_type"]=="scientific" for i in revision["items"]) and (
            output.startswith(("02_data/","03_analysis/")) or output in {
                "01_protocol/protocol_v1.md","01_protocol/protocol_final.md","01_protocol/analysis_contract.json","01_protocol/study_facts.json"}):
        raise ValueError("a presentation dependency cannot authorize scientific input/result changes")
    if revision["review_stage"] == "S24_package_human_review" and not output.startswith("08_submission/"):
        raise ValueError("journal dependency cannot authorize changing the scientific master")
    row = {"input":source, "output":output, "why":why.strip()}
    edges = revision.setdefault("dependency_edges", [])
    if not any(e["input"] == source and e["output"] == output for e in edges):
        edges.append(row)
    plan_scope(project,pipeline,revision); revision.pop("validation",None)
    atomic_json(path,revision)


def _selected_checks(state, revision):
    """The same pinned, de-duplicated rules apply at validation and evidence refresh."""
    seen = set()
    for row in revision["checks"]:
        spec = row["spec"]
        if spec["check"] in {"prose_not_lists", "display_numbering_consistent", "journal_profile_valid"} and state.pin_excludes(row["stage"], spec.get("since")):
            continue
        contextual = spec["check"] in {"outputs_exist", "handoff_recorded", "decision_recorded", "reference_provenance"}
        identity = json.dumps([row["stage"] if contextual else None, spec], sort_keys=True)
        if identity in seen:
            continue
        seen.add(identity)
        yield row


def validate(project: Path, pipeline, state, revision: dict, *, check_identities: dict | None = None) -> tuple[list, str, dict]:
    from . import checks
    from .checks import Ctx, Result
    checks.load_all()
    files = snapshot(project)
    problems = scope_problems(project, revision, files)
    results = [Result(not problems, "revision_scope_unchanged", "; ".join(problems[:10]) or "unaffected files preserved")]
    if problems:
        # Resolve the actual scope first; no expensive dependent check has passed yet.
        return results, input_signature(project, revision, files), files
    from .gatecache import Receipts, descriptor
    receipts = Receipts(project,pipeline,state)
    recorded = []

    def evaluate(row):
        spec = row["spec"]
        stage = pipeline.stage(row["stage"])
        fn = checks.get(spec["check"])
        cache_id = None
        try:
            cache_id = receipts.identity(stage,spec)
            result = receipts.get(cache_id)
            if result is None:
                result = fn(Ctx(pipeline, state, project, stage, spec))
                if cache_id == receipts.identity(stage,spec):
                    receipts.put(cache_id,result)
            stable = cache_id == receipts.identity(stage, spec)
            if cache_id and not stable:
                result = Result(False, spec["check"], "check inputs changed during validation; rerun after inputs settle")
            if check_identities is not None:
                key = descriptor(stage, spec)
                if cache_id and result.ok and stable:
                    check_identities[key] = cache_id
                else:
                    check_identities.pop(key, None)
        except Exception as exc:
            result = Result(False, spec["check"], f"{type(exc).__name__}: {exc}")
        if "severity" in spec and not result.ok:
            result.severity = spec["severity"]
        return result, cache_id

    for row in _selected_checks(state, revision):
        result, cache_id = evaluate(row)
        if cache_id:
            recorded.append((len(results), row, cache_id))
        results.append(result)
    # A later live-source gate may renew evidence consumed by an earlier pure check.
    # Recheck only those changed identities once, without repeating live requests/stages.
    for index, row, old_identity in recorded:
        if old_identity != receipts.identity(pipeline.stage(row["stage"]), row["spec"]):
            results[index], _ = evaluate(row)
    receipts.save()
    # Checks may renew evidence, but must never alter authored sources while certifying them.
    after = snapshot(project)
    drift = {r for r in set(files) | set(after) if not renewable(r) and files.get(r) != after.get(r)}
    if drift:
        results.append(Result(False, "validation_source_drift", ", ".join(sorted(drift))))
    return results, input_signature(project, revision, after), after


def check_round(project: Path, pipeline, state, path: Path, revision: dict) -> int:
    if revision.get("status") != "active":
        raise ValueError("seal the feedback batch before checking")
    if revision.get("schema_version") != 2:
        raise ValueError("finish the legacy round through its recorded stage gates")
    if revision.get("presentation_candidate"):
        from .presentationdelta import classify
        revision["content_classification"] = classify(project, revision)
        atomic_json(path, revision)
        if revision["content_classification"]["class"] != "presentation":
            print(json.dumps(revision["content_classification"], ensure_ascii=False))
            print("Changed science needs its source-owned scientific item; uncertain wording needs actual --meaning-review, never a numeric-only waiver.")
            return 2
    previous = revision.get("validation",{})
    try:
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(previous.get("checked_at",""))).total_seconds()
    except ValueError:
        age = -1
    evidence = {r:h for r,h in snapshot(project).items() if renewable(r)}
    if (previous.get("ok") and 0 <= age < 86400 and
            previous.get("input_signature") == input_signature(project,revision) and
            previous.get("renewable_evidence") == evidence and
            not any(r["stage"] in {"S13_reflib","S25_submission_audit"} for r in revision["checks"])):
        print("Scoped checks reused: exact files/rules/configuration/evidence unchanged; freshness not extended")
        return 0
    check_identities = {}
    results, signature, files = validate(project, pipeline, state, revision, check_identities=check_identities)
    from .determinism import content_sha256
    revision["validation"] = {"input_signature": signature, "ok": not any(r.blocking for r in results),
                              "checked_at": datetime.now(timezone.utc).isoformat(),
                              "artifact_hashes": {rel: (h if not h.startswith("stat:") else _sha256(project / rel))
                                                  for rel, h in files.items() if rel in revision["allowed_files"] and not renewable(rel)},
                              "artifact_content": {rel: content_sha256(project / rel) for rel in files
                                                   if rel in revision["allowed_files"] and not renewable(rel)
                                                   and (Path(rel).suffix.lower() in {".docx", ".xlsx"}
                                                        or rel in {"04_tables/manifest.json", "05_figures/qc/qc_report.json"})},
                              "renewable_evidence": {r: h for r, h in files.items() if renewable(r)},
                              "check_identities": check_identities,
                              "results": [{"check": r.check, "ok": r.ok, "detail": r.detail,
                                           "severity": r.severity} for r in results]}
    atomic_json(path, revision)
    for result in results:
        if not result.ok:
            print(f"[{result.label}] {result.check}: {result.detail}")
    print(f"Scoped checks: {sum(r.ok for r in results)}/{len(results)}; checkpoint remains {state.current}")
    return 0 if revision["validation"]["ok"] else 2


def refresh_evidence(project: Path, pipeline, state, revision: dict) -> None:
    """On close, changed evidence reruns its actual gates, not every manuscript check."""
    from . import checks
    from .checks import Ctx
    current = {r: h for r, h in snapshot(project).items() if renewable(r)}
    if current == revision.get("validation", {}).get("renewable_evidence"):
        return
    checks.load_all()
    # Reuse a pure check only when the exact successfully validated inputs still match.
    # A check being cacheable does not exempt it from changed reference/guideline evidence.
    # Unknown/live checks remain conservative, including in legacy rounds without identities.
    from .gatecache import INPUTS, Receipts, descriptor
    receipts = Receipts(project, pipeline, state)
    checked = revision.get("validation", {})
    identities = dict(checked.get("check_identities", {}))
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(checked.get("checked_at", ""))).total_seconds()
    except (ValueError, TypeError):
        age = -1
    bound_round = bool(checked.get("ok") and 0 <= age < 86400
                       and checked.get("input_signature") == input_signature(project, revision))
    failures = []
    refreshed = []
    rows = list(_selected_checks(state, revision))
    # Renew live/unknown evidence before checking pure consumers of that evidence.
    rows.sort(key=lambda row: row["spec"]["check"] in INPUTS)
    for row in rows:
        spec = row["spec"]
        stage = pipeline.stage(row["stage"])
        key = descriptor(stage, spec)
        cache_id = receipts.identity(stage, spec)
        if bound_round and cache_id and identities.get(key) == cache_id:
            continue
        result = receipts.get(cache_id)
        if result is None:
            result = checks.get(spec["check"])(Ctx(pipeline, state, project, stage, spec))
            if cache_id == receipts.identity(stage, spec):
                receipts.put(cache_id, result)
        if "severity" in spec and not result.ok:
            result.severity = spec["severity"]
        if result.blocking:
            failures.append(f"{result.check}: {result.detail}")
        if cache_id and result.ok and cache_id == receipts.identity(stage, spec):
            identities[key] = cache_id
        else:
            identities.pop(key, None)
        refreshed.append({"check": result.check, "ok": result.ok, "detail": result.detail,
                          "severity": result.severity})
    receipts.save()
    for row in rows:
        stage, spec = pipeline.stage(row["stage"]), row["spec"]
        key = descriptor(stage, spec)
        if key in identities and identities[key] != receipts.identity(stage, spec):
            failures.append(f"{spec['check']}: evidence changed during refresh; rerun scoped checks")
    if failures:
        raise ValueError("renewed evidence is invalid: " + "; ".join(failures[:8]))
    # Preserve the original checked_at: evidence renewal must not extend proof freshness.
    checked["check_identities"] = identities
    checked["renewable_evidence"] = {r: h for r, h in snapshot(project).items() if renewable(r)}
    checked["evidence_refresh_results"] = refreshed


def record_build(project: Path, output: Path, sources: list[Path], *, entrypoints=None, tool=None, parameters=None) -> None:
    """A real builder receipt, not a user-typed 'validated' label."""
    from .buildproof import record
    receipt = record(project, output, sources, entrypoints=entrypoints, tool=tool, parameters=parameters)
    revision = active(project)
    if not revision or revision.get("schema_version") != 2:
        return
    rel = output.resolve().relative_to(project.resolve()).as_posix()
    revision.setdefault("build_receipts", {})[rel] = receipt
    atomic_json(project / ".wf/revisions" / f"{revision['round_id']}.json", revision)


def baseline_capture_allowed(project: Path) -> bool:
    """Only source-based package jobs may renew the content baseline in-place at S24."""
    revision = active(project)
    if not revision or not permits(project, "S23_package"):
        return False
    if all(i["change_type"] == "layout" for i in revision["items"]):
        return False
    from .packagecontent import build_baseline, BASELINE_REL
    try:
        current = build_baseline(project)
    except (OSError,ValueError):
        return False
    old_path = project / BASELINE_REL
    previous = json.loads(old_path.read_text(encoding="utf-8")) if old_path.is_file() else {}
    old = {r["path"]: r for r in previous.get("records", [])}
    for row in current["records"]:
        prior = old.get(row["path"], {})
        if (row.get("content_sha256",row.get("visible_text_sha256")) == prior.get("content_sha256",prior.get("visible_text_sha256")) and
                row.get("source_sha256") == prior.get("source_sha256") and
                row.get("upstream_sha256") == prior.get("upstream_sha256")):
            continue
        receipt = revision.get("build_receipts", {}).get(row["path"], {})
        from .buildproof import content_digest
        if (receipt.get("sha256") != _sha256(project / row["path"]) and
                receipt.get("content_sha256") != content_digest(project / row["path"])) or not receipt.get("sources"):
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
