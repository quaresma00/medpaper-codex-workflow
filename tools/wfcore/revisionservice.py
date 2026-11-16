"""Read-only revision preflight and explicit executor completion payloads."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from . import revision


def validation_current(project, record):
    proof = record.get("validation", {})
    if not proof.get("ok"):
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(proof["checked_at"])).total_seconds()
        return 0 <= age < 86400 and proof.get("input_signature") == revision.input_signature(project, record)
    except (KeyError, TypeError, ValueError):
        return False


def preflight(project, state, record, *, full=False):
    """Describe actual edits and existing evidence; never build or certify reading."""
    current = revision.snapshot(project)
    baseline = record.get("baseline", {})
    changed = sorted(p for p in set(current) | set(baseline) if current.get(p) != baseline.get(p))
    from .presentationdelta import classify
    classification = classify(project, record) if record.get("presentation_candidate") else {"class": "source_owned_revision"}
    blockers = revision.scope_problems(project, record, current)
    if record.get("status") != "active" or record.get("schema_version") != 2:
        blockers.append("A sealed active schema-2 revision is required")
    if state.current != record.get("review_stage"):
        blockers.append("Resolve the current scientific/review checkpoint before finishing this batch")
    pending = [item["id"] for item in record.get("items", []) if item.get("status") != "done"]
    limit = len(changed) if full else 20
    return {"read_only": True, "round": record["round_id"], "checkpoint": state.current,
            "pending_items": pending, "changed_count": len(changed), "changed_files": changed[:limit],
            "omitted_changes": max(0, len(changed) - limit),
            "classification": {key:(value if full else value[:20]) if isinstance(value,list) else value
                               for key,value in classification.items()},
            "blockers":blockers if full else blockers[:10],"blocker_count":len(blockers),
            "validation_current": validation_current(project, record),
            "checks": record.get("validation_stages", []),
            "next": "Resolve blockers/source reconciliation; build only actual dependants; supply real medical/visual observations, then finish with explicit per-item completion."}


def completion_marks(project, record, payload):
    """Prepare receipts only for explicitly attested items; no invented acceptance."""
    if not isinstance(payload,dict):
        raise ValueError("Completion must be a JSON object")
    if not isinstance(payload.get("summary"),str) or len(payload["summary"].strip()) < 40:
        raise ValueError("Completion summary must describe this round in at least 40 characters")
    rows = payload.get("items")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Completion items must be an explicit array of executor resolutions")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(i,str) or not i for i in ids):
        raise ValueError("Every completion item needs its actual string ID")
    pending = {i["id"]: i for i in record["items"] if i.get("status") != "done"}
    if len(ids) != len(set(ids)) or set(ids) != set(pending):
        raise ValueError("Completion must explicitly resolve every pending item once; no implicit auto-mark")
    current = revision.snapshot(project)
    allowed = set(record.get("allowed_files", []))
    result = []
    for row in rows:
        if not isinstance(row.get("summary"),str) or len(row["summary"].strip()) < 30:
            raise ValueError(f"{row['id']}: actual resolution summary is required")
        observations = row.get("validated_by")
        if not isinstance(observations, list) or not observations or any(not isinstance(x, str) or not x.strip() for x in observations):
            raise ValueError(f"{row['id']}: name actual completed checks/inspections; the tool cannot invent them")
        extra = row.get("files", [])
        if not isinstance(extra, list) or any(not isinstance(x, str) for x in extra):
            raise ValueError("Completion files must be project-relative paths")
        files = sorted({*pending[row['id']].get("affected_sources", []), *extra})
        changed, checked, deleted = [], [], []
        for raw in files:
            rel, path = revision._safe_path(Path(project), raw)
            if rel not in allowed or revision.renewable(rel):
                raise ValueError(f"Completion file is outside authored output scope: {rel}")
            old = record.get("baseline", {}).get(rel)
            if not path.is_file():
                if old is None: raise ValueError(f"Completion source is missing: {rel}")
                deleted.append(rel)
            elif old is not None and current.get(rel) == old:
                checked.append(rel)
            else:
                changed.append(rel)
        result.append(SimpleNamespace(item=row["id"], summary=row["summary"], changed_file=changed,
                                      checked_file=checked, deleted_file=deleted, validated_by=observations))
    return result
