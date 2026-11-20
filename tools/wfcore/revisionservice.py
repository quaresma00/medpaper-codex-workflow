"""Read-only revision preflight and explicit executor completion payloads."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from time import monotonic
from types import SimpleNamespace

from . import revision


def validation_current(project, record, *, files=None, progress=None):
    proof = record.get("validation", {})
    if not proof.get("ok"):
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(proof["checked_at"])).total_seconds()
        return 0 <= age < 86400 and proof.get("input_signature") == revision.input_signature(
            project, record, files, progress=progress)
    except (KeyError, TypeError, ValueError):
        return False


def preflight(project, state, record, *, full=False):
    """Describe actual edits and existing evidence; never build or certify reading."""
    started = last_output = monotonic()

    def phase(message):
        nonlocal last_output
        last_output = monotonic()
        print(f"Revision preflight [{last_output - started:.1f}s]: {message}", file=sys.stderr, flush=True)

    def observe(category, count):
        if monotonic() - last_output >= 3:
            phase(f"{count} file identities read; inspecting {category}")

    phase("scanning project files")
    skipped_links = set()
    current = revision.snapshot(project, progress=observe, skipped_links=skipped_links)
    baseline = revision.project_baseline(record)
    changed = sorted(p for p in set(current) | set(baseline) if current.get(p) != baseline.get(p))
    phase(f"{len(current)} project files observed; checking scope and changed content")
    reference_problems = None
    classification = {"class": "source_owned_revision"}
    if record.get("presentation_candidate"):
        from .evidence import reference_renewal_problems
        from .presentationdelta import classify
        reference_problems = reference_renewal_problems(project, baseline, current)
        classification = classify(project, record, current=current, reference_problems=reference_problems)
    blockers = revision.scope_problems(project, record, current, reference_problems=reference_problems)
    link_prefixes = tuple(f"{link}/" for link in skipped_links)
    legacy_links = [path for path in changed if path not in current and (path in skipped_links or path.startswith(link_prefixes))]
    if record.get("status") != "active" or record.get("schema_version") != 2:
        blockers.append("A sealed active schema-2 revision is required")
    if state.current != record.get("review_stage"):
        blockers.append("Resolve the current scientific/review checkpoint before finishing this batch")
    pending = [item["id"] for item in record.get("items", []) if item.get("status") != "done"]
    limit = len(changed) if full else 20
    if not blockers and record.get("validation", {}).get("ok"):
        phase("checking recorded validation against current files and workflow rules")
    current_validation = not blockers and validation_current(project, record, files=current, progress=observe)
    return {"read_only": True, "round": record["round_id"], "checkpoint": state.current,
            "pending_items": pending, "changed_count": len(changed), "changed_files": changed[:limit],
            "omitted_changes": max(0, len(changed) - limit),
            "classification": {key:(value if full else value[:20]) if isinstance(value,list) else value
                               for key,value in classification.items()},
            "blockers":blockers if full else blockers[:10],"blocker_count":len(blockers),
            "linked_baseline_paths": legacy_links if full else legacy_links[:20],
            "linked_baseline_count": len(legacy_links),
            "linked_baseline_note": ("The saved baseline recorded a link or its descendants. Review the original source and scope. "
                                     "Linked paths were not traversed and historical drift was not waived." if legacy_links else None),
            "validation_current": current_validation,
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
    allowed = set(record.get("allowed_files", []))
    observed = {}
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
            if rel not in observed:
                observed[rel] = revision._file_identity(path, rel, path.stat()) if path.is_file() else None
            if observed[rel] is None:
                if old is None: raise ValueError(f"Completion source is missing: {rel}")
                deleted.append(rel)
            elif old is not None and observed[rel] == old:
                checked.append(rel)
            else:
                changed.append(rel)
        result.append(SimpleNamespace(item=row["id"], summary=row["summary"], changed_file=changed,
                                      checked_file=checked, deleted_file=deleted, validated_by=observations))
    return result
