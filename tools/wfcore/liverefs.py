"""Reuse unchanged independent live PubMed checks for a short, explicit freshness window."""
from datetime import datetime, timezone
import json

from . import refproof
from .packagefreeze import _safe_path
from .readiness import atomic_json

REL = ".wf/reference_live.json"


def cached_sources(project, entries, max_hours=24):
    try:
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


def store_sources(project, live_records):
    payloads = {}
    for row in live_records:
        rel = row.get("cache_file", "")
        if not rel.startswith("06_refs/cache/gate_efetch_pubmed_"):
            return  # a mocked/test record or non-independent source cannot seed the cache
        _, path = _safe_path(project, rel)
        if not path.is_file():
            return
        payloads[rel] = {"path": rel, "sha256": refproof.file_sha256(path)}
    atomic_json(project / REL, {"at": datetime.now(timezone.utc).isoformat(),
                                "payloads": list(payloads.values())})
