"""One active journal attempt, with source-bound rules and no inherited guide defaults."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone
from urllib.parse import urlparse

from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json, load

CONTEXT = "08_submission/journal_context.json"
TARGET = "08_submission/target_journal.json"
REQUIREMENTS = "08_submission/submission_requirements.json"
CONFIGS = (TARGET, REQUIREMENTS, "08_submission/docx_style.json", "08_submission/guidelines_extract.md")
MANAGED = ("target_journal.json", "journal_context.json", "submission_requirements.json", "docx_style.json",
           "guidelines_extract.md", "integration", "bundle", "cache", "evidence", "cover_letter.md",
           "submission_qc.md", "package_content_baseline.json", "portal_fields.json", "package_review_freeze.json",
           "package_human_review.md", "independent_submission_audit.md", "submission_checklist.md", "final_copy")
CONTROLS = (".wf/submission_measurements.json", ".wf/benchmark_journal_lock.json",
            ".wf/executor_acceptance_journal_pre.json", ".wf/executor_acceptance_journal_final.json",
            ".wf/review_rounds/package.json", ".wf/final_copy.json")


def now(): return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest().upper()


def identity(target):
    journal = str(target.get("journal", "")).strip()
    issn = str(target.get("issn", "")).strip().upper()
    article = str(target.get("article_type", "")).strip()
    stage = target.get("submission_stage", "initial")
    if not journal or not re.fullmatch(r"\d{4}-\d{3}[\dX]", issn) or not article or stage not in {"initial", "revision"}:
        raise ValueError("Set the actual journal, ISSN, article_type and submission_stage (initial/revision)")
    return {"journal": journal, "issn": issn, "article_type": article, "submission_stage": stage}


def enabled(project):
    if (project/CONTEXT).is_file(): return True
    state=project/".wf/state.json"
    return bool(state.is_file() and json.loads(state.read_text(encoding="utf-8")).get("journal_context_required"))


def begin(project: Path, target: dict) -> dict:
    """Archive task-managed journal files before installing a freshly chosen target.

    Never change scientific sources, raw data, unrelated submission notes, releases or
    completed-stage history. This is a journal change, not another scientific approval.
    """
    project = project.resolve(); ident = identity(target)
    from .scientificfreeze import verify
    ok, problems, freeze = verify(project)
    if not ok: raise ValueError("Scientific master must verify before journal adaptation: " + "; ".join(problems))
    from .revision import active
    revision = active(project)
    if revision and (revision.get("status") != "active" or not any(i["kind"] in {"journal", "journal-switch"} for i in revision.get("items", []))):
        raise ValueError("Use a sealed journal-switch revision before replacing an active journal context")
    old = load(project, CONTEXT) if (project/CONTEXT).is_file() else None
    if old and old.get("identity") == ident:
        return current(project)  # Idempotent resume preserves author edits and actual guide captures.
    previous = old or (load(project, TARGET) if (project / TARGET).is_file() else {})
    attempt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = project / "08_submission"
    archive = root / "journal_archives" / attempt
    selected = [root / name for name in MANAGED if (root / name).exists()]
    # Resolve/check every move first, including Windows junction/symlink escape cases.
    for path in [*selected, archive]: _safe_path(project, path.relative_to(project).as_posix())
    archive_created = bool(selected)
    moves = []
    writes = {}
    try:
        if selected: archive.mkdir(parents=True, exist_ok=False)
        for path in selected:
            destination = archive / path.name
            shutil.move(str(path), str(destination)); moves.append((path, destination))
        for rel in CONTROLS:
            source = _safe_path(project, rel)[1]
            if source.is_file():
                dest = project / ".wf/journal_attempts" / attempt / rel.removeprefix(".wf/")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(dest)); moves.append((source, dest))
        receipts = project / ".wf/build_receipts.json"
        if receipts.is_file():
            writes[receipts]=receipts.read_bytes()
            all_rows = json.loads(receipts.read_text(encoding="utf-8"))
            journal = {k: v for k, v in all_rows.items() if k.startswith("08_submission/")}
            if journal:
                atomic_json(project / ".wf/journal_attempts" / attempt / "build_receipts.json", journal)
                atomic_json(receipts, {k: v for k, v in all_rows.items() if k not in journal})
        root.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "attempt_id": attempt, "identity": ident,
                   "context_id": digest({"identity": ident, "attempt": attempt}), "created_at": now(),
                   "scientific_freeze_id": freeze["freeze_id"], "sources": {}, "assets": {},
                   "previous_archive": archive.relative_to(project).as_posix() if archive_created else None}
        for path in (project/TARGET,project/CONTEXT): writes[path]=None
        atomic_json(project / TARGET, {**target, **ident})
        atomic_json(project / CONTEXT, payload)
    except Exception:
        # Roll back moves if setup fails; never remove source/user files.
        for path,raw in writes.items():
            if raw is None: path.unlink(missing_ok=True)
            else: path.write_bytes(raw)
        for src, dest in reversed(moves):
            if dest.exists() and not src.exists():
                src.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(dest), str(src))
        raise
    from .state import State
    if State(project).exists():
        state = State(project).load()
        state.clear_decisions_for(["S20_journal", "S22_polish", "S23_package", "S24_package_human_review", "S25_submission_audit"])
        state.data["journal_context_required"]=True
        state.data["active_journal_context_id"]=payload["context_id"]
        state.event("journal_context_started", f"{previous.get('journal', '')} -> {ident['journal']}; context={payload['context_id']}; completed stages and science preserved")
        state.save()
    return payload


def current(project):
    context = load(project, CONTEXT)
    if context.get("identity") != identity(load(project, TARGET)):
        raise ValueError("Target journal/article/submission stage differs from the active context; use journal.py begin")
    state=project/".wf/state.json"
    active=json.loads(state.read_text(encoding="utf-8")).get("active_journal_context_id") if state.is_file() else None
    if active and active!=context.get("context_id"): raise ValueError("Restored context belongs to a different journal attempt")
    return context


def allowed_url(project, url):
    target = load(project, TARGET)
    parsed = urlparse(url)
    hosts = {urlparse(str(target.get("guidelines_url", ""))).hostname, *target.get("official_domains", [])}
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.hostname not in hosts or parsed.username or parsed.password:
        raise ValueError("Use a verified official guideline host; add a genuinely linked publisher/CDN host to target official_domains when needed")
    return url


def source_problems(project, context):
    problems = []
    handoff=context.get("browser_handoff",{})
    if isinstance(handoff,dict) and handoff.get("status")=="waiting_for_user":
        problems.append("Official-guide browser handoff is waiting for the user; obtain the actual guide after verification before sealing/building")
    if not context.get("sources"): return problems+["No actual guideline source captured for this attempt"]
    main = load(project, TARGET).get("guidelines_url")
    if not any(main in {r.get("url"), r.get("final_url")} for r in context["sources"].values()):
        problems.append("The current target guidelines_url has no captured source")
    for key, source in context["sources"].items():
        if not isinstance(source,dict):
            problems.append(f"{key}: invalid captured source record");continue
        try:
            allowed_url(project, source["url"]); allowed_url(project, source.get("final_url", source["url"]))
            if source.get("context_id") != context["context_id"]: raise ValueError("belongs to another journal attempt")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(source["fetched_at"])).total_seconds()/86400
            if not 0 <= age <= 90: raise ValueError("source capture must be current, not future-dated or stale")
            for field in ("raw", "text"):
                path = _safe_path(project, source[field])[1]
                if not path.is_file() or _sha256(path) != source[field+"_sha256"]: raise ValueError("captured source changed or is missing")
        except (OSError, ValueError, KeyError, TypeError) as exc: problems.append(f"{key}: {exc}")
    return problems


def projection(project, rel):
    """Metadata freshness is evidence, not a command to reformat an unchanged Word."""
    if rel == TARGET:
        value = load(project, rel)
        excluded = {"guidelines_fetched_at", "scie_verified_at", "jcr_verified_at", "integrity_checked_at",
                    "scie_source_url", "jcr_source", "integrity_sources", "scie_indexed", "jcr_quartile", "integrity_status"}
        return digest({k: v for k, v in value.items() if k not in excluded})
    return _sha256(_safe_path(project, rel)[1])


def seal(project):
    context = current(project)
    problems = source_problems(project, context)
    from .guidelinerules import validate
    problems += validate(project, context)
    if problems: raise ValueError("; ".join(problems[:10]))
    hashes = {rel: projection(project, rel) for rel in CONFIGS}
    asset_hashes = {}
    for asset in context.get("assets", {}).values():
        path = _safe_path(project, asset["file"])[1]
        if not path.is_file() or _sha256(path) != asset["sha256"]: raise ValueError("Current captured CSL/template asset changed")
        asset_hashes[asset["file"]] = asset["sha256"]
    requirements = load(project, REQUIREMENTS)
    requirements["journal_context_id"] = context["context_id"]
    atomic_json(project / REQUIREMENTS, requirements)
    hashes[REQUIREMENTS] = projection(project, REQUIREMENTS)
    # Raw-page/footer changes do not force DOCX builds when executable rules/configs agree.
    build_files = {rel: h for rel, h in hashes.items() if rel != "08_submission/guidelines_extract.md"}
    context["seal"] = {"at": now(), "configs": hashes, "assets": asset_hashes,
                       "build_id": digest({"context_id":context["context_id"],"style":hashes["08_submission/docx_style.json"],
                                           "profile":hashes[TARGET],"assets":asset_hashes}),
                       "rules_id": digest({"context_id": context["context_id"], "configs": build_files, "assets": asset_hashes}),
                       "rule_ids": [r["id"] for r in requirements["guide_rules"]]}
    atomic_json(project / CONTEXT, context)
    return context


def problems(project):
    try:
        context = current(project)
        result = source_problems(project, context)
        sealed = context.get("seal", {})
        if not sealed: return result + ["Current guideline rules/configuration are not sealed; run journal.py seal"]
        if set(sealed.get("configs",{}))!=set(CONFIGS): return result+["Sealed guide configuration inventory is incomplete"]
        from .guidelinerules import validate
        result+=validate(project,context)
        for rel, value in sealed["configs"].items():
            if projection(project, rel) != value: result.append(f"Guideline configuration changed: {rel}; reconcile rules then seal")
        for rel, value in sealed.get("assets", {}).items():
            if _sha256(_safe_path(project, rel)[1]) != value: result.append(f"Current CSL asset changed: {rel}")
        expected_build=digest({"context_id":context["context_id"],"style":sealed["configs"]["08_submission/docx_style.json"],
                               "profile":sealed["configs"][TARGET],"assets":sealed.get("assets",{})})
        if sealed.get("build_id")!=expected_build: result.append("Sealed journal build identity is inconsistent")
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc: return [str(exc)]


def guard(project):
    if enabled(project):
        failures = problems(project)
        if failures: raise ValueError("Current-journal guard: " + "; ".join(failures[:8]))


def build_identity(project):
    guard(project)
    if not enabled(project): return {}
    row = current(project)
    return {"journal_context_id": row["context_id"], "journal_build_id": row["seal"]["build_id"]}
