"""Journal-attempt ownership for scoped feedback and byte-preserving transfers."""
from pathlib import Path
import re

from . import journalcontext as jc
from .packagefreeze import _safe_path
from .readiness import load

SWITCH_KINDS = {"journal", "journal-switch"}
ADMIN_KINDS = SWITCH_KINDS | {"journal-format", "journal-figure-layout", "journal-table-layout",
    "word-format-only", "title-page-or-statements", "cover-letter-or-package-structure"}
LEGACY_ADMIN_FILES = {jc.TARGET, jc.CONTEXT, jc.REQUIREMENTS,
    "08_submission/docx_style.json", "08_submission/guidelines_extract.md", "08_submission/cover_letter.md"}


def managed_path(rel):
    parts = rel.split("/")
    return len(parts) >= 2 and parts[0] == "08_submission" and parts[1] in jc.MANAGED


def scoped_item(item):
    sources = item.get("affected_sources", [])
    return (item.get("change_type") in {"administrative", "layout"} and item.get("kind") in ADMIN_KINDS
            and bool(sources) and all(managed_path(rel) for rel in sources))


def context_for_items(project):
    return jc.current(project) if (project / jc.CONTEXT).is_file() else {}


def obsolete_items(project, record):
    bound = [(item.get("id"), item.get("journal_context_id")) for item in record.get("items", []) if item.get("journal_context_id")]
    if not bound:
        return []
    context_id = context_for_items(project).get("context_id")
    return [identifier for identifier, owner in bound if owner != context_id]


def select_switch(record, previous_id, requested=None):
    candidates = [item for item in record.get("items", [])
                  if item.get("kind") in SWITCH_KINDS and item.get("status") == "pending"
                  and item.get("change_type") == "administrative"
                  and scoped_item(item)
                  and not item.get("journal_transfer")
                  and item.get("journal_context_id") in {None, previous_id}]
    if requested:
        candidates = [item for item in candidates if item.get("id") == requested]
    elif any(item.get("journal_context_id") == previous_id for item in candidates):
        candidates = [item for item in candidates if item.get("journal_context_id") == previous_id]
    if len(candidates) != 1:
        raise ValueError("Select one pending sealed journal-switch for the current attempt with journal.py begin --revision-item")
    return candidates[0]


def archived_context(project: Path, archive: str):
    if not re.fullmatch(r"08_submission/journal_archives/\d{8}T\d{12}Z", archive or ""):
        raise ValueError("Name the exact archived attempt listed by journal.py status or the transfer history")
    row = load(project, f"{archive}/journal_context.json")
    if row.get("identity") != jc.identity(load(project, f"{archive}/target_journal.json")):
        raise ValueError("Archived journal context and target differ")
    if row.get("context_id") != jc.digest({"identity": row["identity"], "attempt": row.get("attempt_id")}):
        raise ValueError("Archived journal attempt identity is invalid")
    return row


def archive_locations(project):
    """Index actual journal archive identities for closed-round receipt validation."""
    root = project / "08_submission/journal_archives"
    if not root.is_dir():
        return {}
    locations = {}
    for attempt in root.iterdir():
        path = attempt.relative_to(project).as_posix()
        if not (attempt / "journal_context.json").is_file():
            continue  # Older pre-context attempt.
        row = archived_context(project, path)
        context_id = row["context_id"]
        if context_id in locations:
            raise ValueError("Multiple archives claim the same journal attempt")
        locations[context_id] = path
    return locations


def historical_path(rel, archive):
    if managed_path(rel):
        return f"{archive}/{rel.removeprefix('08_submission/')}"
    if rel in jc.CONTROLS:
        return f".wf/journal_attempts/{archive.rsplit('/', 1)[-1]}/{rel.removeprefix('.wf/')}"
    return rel


def retire_item(project, record, item_id, successor_id, reason, legacy_archive=None):
    if len(reason.strip()) < 30:
        raise ValueError("Record the actual author-directed reason for replacing the older journal-specific request")
    if record.get("schema_version") != 2 or record.get("status") != "active":
        raise ValueError("Settle obsolete work inside the sealed active scoped revision")
    items = {item["id"]: item for item in record["items"]}
    old, successor = items.get(item_id), items.get(successor_id)
    if not old or not successor or old is successor or not scoped_item(old):
        raise ValueError("Only a journal-owned administrative/layout item can be superseded; keep scientific and shared author-source work")
    current_id = jc.current(project)["context_id"]
    if successor.get("journal_context_id") != current_id or not scoped_item(successor):
        raise ValueError("The successor must be an actual administrative/layout item of the current journal attempt")
    context_id = old.get("journal_context_id")
    if context_id == current_id:
        raise ValueError("An item of the current journal cannot be retired as obsolete transfer work")
    if not context_id:
        if not set(old["affected_sources"]) <= LEGACY_ADMIN_FILES or not legacy_archive:
            raise ValueError("Legacy transfer settlement requires --archive and solely dedicated journal configuration or cover-letter sources")
        archived = archived_context(project, legacy_archive)
        context_id, archive = archived["context_id"], legacy_archive
        if not any(_safe_path(project, f"{archive}/{rel.removeprefix('08_submission/')}")[1].is_file()
                   for rel in old["affected_sources"]):
            raise ValueError("The selected journal archive contains none of the old item's actual declared sources")
    else:
        if legacy_archive:
            raise ValueError("A context-bound item uses its recorded transfer history")
        matches = [row["archive"] for row in record.get("journal_transfers", [])
                   if row.get("from_context_id") == context_id and row.get("archive")]
        if len(matches) != 1:
            raise ValueError("The item's old attempt lacks a recorded journal transfer archive")
        archive = matches[0]
        if archived_context(project, archive)["context_id"] != context_id:
            raise ValueError("Recorded archive belongs to a different attempt")
    if context_id == current_id:
        raise ValueError("An archive of the current attempt cannot supersede this work")
    record["items"].remove(old)
    record.setdefault("retired_journal_items", []).append({
        "item": old, "disposition": "retired_after_completion" if old["status"] == "done" else "superseded",
        "successor_id": successor_id, "journal_context_id": context_id, "archive": archive,
        "reason": reason.strip(), "at": jc.now(),
    })
    record.pop("validation", None)
