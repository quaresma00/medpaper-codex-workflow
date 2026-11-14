"""Reuse unchanged independent live PubMed checks for a short, explicit freshness window."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from . import refproof
from .packagefreeze import _safe_path
from .readiness import atomic_json

REL = ".wf/reference_live.json"
CRITICAL_STAGES = {"S13_reflib", "S25_submission_audit"}
CHECKPOINT_SECONDS = 120


def checkpoint_identity(project, stage):
    """The same exact live checkpoint, never a generic cache or stage-to-stage PASS."""
    if stage not in CRITICAL_STAGES:
        return None
    try:
        state=json.loads((project/".wf/state.json").read_text(encoding="utf-8"))
        journal=project/"08_submission/journal_context.json"
        context=json.loads(journal.read_text(encoding="utf-8")).get("context_id") if journal.is_file() else None
        root=Path(__file__).resolve().parents[2]
        rules=("tools/wfcore/liverefs.py", "tools/wfcore/refproof.py", "tools/wfcore/checks/refs.py",
               "tools/pubmed/eutils.py", "pipeline/pipeline.toml")
        return {"stage":stage,"pipeline_version":state.get("pipeline_version"),
                "engine_pin":state.get("engine_pin"),"revision":state.get("active_revision_round"),
                "journal_context":context,"library_sha256":refproof.file_sha256(project/"06_refs/library.json"),
                "verification_sha256":refproof.file_sha256(project/"06_refs/verified.json"),
                "rules":{rel:refproof.file_sha256(root/rel) for rel in rules}}
    except (OSError,ValueError,KeyError,TypeError):
        return None


def checkpoint_sources(project, entries, stage, max_hours=24):
    """Avoid a second network round-trip for check -> advance within 120 seconds.

    Local verification is still required by the caller on every invocation. This
    also reparses/hash-checks actual independent XML; no timestamp is refreshed.
    """
    expected=checkpoint_identity(project,stage)
    if expected is None:
        return None
    try:
        payload=json.loads((project/REL).read_text(encoding="utf-8"))
        if not isinstance(payload,dict) or payload.get("checkpoint")!=expected:
            return None
    except (OSError,ValueError,TypeError):
        return None
    return cached_sources(project,entries,min(float(max_hours),CHECKPOINT_SECONDS/3600))


def cached_sources(project, entries, max_hours=24):
    try:
        if not math.isfinite(max_hours) or max_hours <= 0:
            return None
        payload = json.loads((project / REL).read_text(encoding="utf-8"))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(payload["at"])).total_seconds()
        if age < 0 or age > max_hours * 3600:
            return None
        sources = {}
        for row in payload["payloads"]:
            rel, path = _safe_path(project, row["path"])
            if not rel.startswith("06_refs/cache/gate_efetch_pubmed_"):
                return None
            if refproof.file_sha256(path) != row["sha256"]:
                return None
            sources.update(refproof.parse_pubmed_payload(path.read_bytes()))
        if set(sources) != {str(e["pmid"]) for e in entries}:
            return None
        if any(refproof.compare_entry_to_source(e, sources[str(e["pmid"])]) for e in entries):
            return None
        return sources
    except (OSError, ValueError, KeyError, TypeError):
        return None


def store_sources(project, live_records, *, stage=None):
    payloads = {}
    for row in live_records:
        rel = row.get("cache_file", "")
        if not rel.startswith("06_refs/cache/gate_efetch_pubmed_"):
            return  # a mocked/test record or non-independent source cannot seed the cache
        _, path = _safe_path(project, rel)
        if not path.is_file():
            return
        payloads[rel] = {"path": rel, "sha256": refproof.file_sha256(path)}
    payload={"at":datetime.now(timezone.utc).isoformat(),"payloads":list(payloads.values())}
    checkpoint=checkpoint_identity(project,stage)
    if checkpoint is not None:
        payload["checkpoint"]=checkpoint
    atomic_json(project/REL,payload)
