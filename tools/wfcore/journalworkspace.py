"""Create and verify the journal-specific integration layer derived from the S19 freeze."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .scientificfreeze import verify as verify_scientific_freeze


SCHEMA_VERSION = 1
MANIFEST_REL = "08_submission/integration/journal_workspace.json"
SOURCE_MAP = {
    "07_manuscript/full_manuscript.md": "08_submission/integration/full_manuscript.md",
    "07_manuscript/supplementary_methods.md": "08_submission/integration/supplementary_methods.md",
    "07_manuscript/statements.md": "08_submission/integration/statements.md",
    "05_figures/legends.md": "08_submission/integration/figure_legends.md",
    "04_tables/table_captions.md": "08_submission/integration/table_captions.md",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _project_path(project: Path, raw: str, *, prefix: str) -> Path:
    rel = PurePosixPath(str(raw).replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or ".." in rel.parts or not rel.as_posix().startswith(prefix):
        raise ValueError(f"unsafe journal-workspace path: {raw}")
    path = project.joinpath(*rel.parts).resolve()
    try:
        path.relative_to(project.resolve())
    except ValueError as exc:
        raise ValueError(f"journal-workspace path leaves project: {raw}") from exc
    return path


def _target(project: Path) -> tuple[dict, str]:
    path = project / "08_submission/target_journal.json"
    try:
        target = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("08_submission/target_journal.json is missing") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"target_journal.json is invalid: {exc}") from exc
    canonical = json.dumps(target, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return target, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def initialise(project: Path, *, replace: bool = False) -> tuple[Path, dict, bool]:
    project = project.resolve()
    ok, problems, freeze = verify_scientific_freeze(project)
    if not ok or freeze is None:
        raise ValueError("scientific master is not frozen: " + "; ".join(problems[:8]))
    target, target_hash = _target(project)
    manifest_path = project / MANIFEST_REL
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
        same = (previous.get("scientific_freeze_id") == freeze.get("freeze_id") and
                previous.get("target_journal_sha256") == target_hash)
        if same:
            verified, verify_problems, current = verify(project, require_pristine=False)
            if verified and current is not None:
                return manifest_path, current, False
        if not replace:
            raise ValueError(
                "an integration workspace for another master/journal already exists; "
                "use --replace only after preserving any submission attempt that still has value"
            )
        archive_root = project / "08_submission/journal_archives"
        archive_root.mkdir(parents=True, exist_ok=True)
        journal = str(previous.get("journal", "previous-journal"))
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in journal).strip("-")[:48]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = archive_root / f"{slug or 'previous-journal'}-{stamp}"
        archive.mkdir(parents=True, exist_ok=False)
        integration = project / "08_submission/integration"
        if integration.is_dir():
            shutil.move(str(integration), str(archive / "integration"))
        bundle = project / "08_submission/bundle"
        if bundle.is_dir() and any(bundle.iterdir()):
            shutil.move(str(bundle), str(archive / "bundle"))
            bundle.mkdir(parents=True, exist_ok=True)

    records_by_path = {item["path"]: item for item in freeze["files"]}
    copies = []
    for source_rel, destination_rel in SOURCE_MAP.items():
        source = project / source_rel
        if not source.is_file():
            continue
        frozen = records_by_path.get(source_rel)
        if not frozen or frozen.get("sha256") != _sha256(source):
            raise ValueError(f"source is not part of the current scientific freeze: {source_rel}")
        destination = project / destination_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copies.append({
            "source": source_rel,
            "source_sha256": frozen["sha256"],
            "destination": destination_rel,
            "initial_destination_sha256": _sha256(destination),
        })
    if not any(item["source"] == "07_manuscript/full_manuscript.md" for item in copies):
        raise ValueError("frozen full manuscript is unavailable")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scientific_freeze_id": freeze["freeze_id"],
        "review_package_id": freeze["review_package_id"],
        "journal": target.get("journal"),
        "issn": target.get("issn"),
        "target_journal_sha256": target_hash,
        "files": copies,
        "boundary": "journal-specific copies only; frozen 07_manuscript sources remain unchanged",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path, payload, True


def verify(project: Path, *, require_pristine: bool = False) -> tuple[bool, list[str], dict | None]:
    project = project.resolve()
    manifest_path = project / MANIFEST_REL
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, [f"{MANIFEST_REL} is missing"], None
    except json.JSONDecodeError as exc:
        return False, [f"{MANIFEST_REL} is invalid JSON: {exc}"], None
    problems: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append("journal workspace schema is invalid")
    ok, freeze_problems, freeze = verify_scientific_freeze(project)
    if not ok or freeze is None:
        problems.append("scientific master changed: " + "; ".join(freeze_problems[:5]))
        return False, problems, payload
    if payload.get("scientific_freeze_id") != freeze.get("freeze_id"):
        problems.append("journal workspace derives from a different scientific freeze")
    try:
        target, target_hash = _target(project)
    except ValueError as exc:
        return False, problems + [str(exc)], payload
    if payload.get("target_journal_sha256") != target_hash:
        problems.append("target journal metadata changed after the integration workspace was created")
    if payload.get("journal") != target.get("journal") or payload.get("issn") != target.get("issn"):
        problems.append("journal identity does not match target_journal.json")
    frozen = {item["path"]: item for item in freeze.get("files", [])}
    records = payload.get("files")
    if not isinstance(records, list) or not records:
        return False, problems + ["journal workspace has no derived-file records"], payload
    seen: set[tuple[str, str]] = set()
    for item in records:
        source_rel = str(item.get("source", ""))
        destination_rel = str(item.get("destination", ""))
        if SOURCE_MAP.get(source_rel) != destination_rel:
            problems.append(f"unexpected journal-workspace mapping: {source_rel} -> {destination_rel}")
            continue
        if (source_rel, destination_rel) in seen:
            problems.append(f"duplicate journal-workspace mapping: {source_rel}")
            continue
        seen.add((source_rel, destination_rel))
        source_record = frozen.get(source_rel)
        if not source_record or source_record.get("sha256") != item.get("source_sha256"):
            problems.append(f"workspace origin is not in the current freeze: {source_rel}")
            continue
        try:
            destination = _project_path(
                project, destination_rel, prefix="08_submission/integration/"
            )
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if not destination.is_file():
            problems.append(f"journal integration file is missing: {destination_rel}")
        elif require_pristine and _sha256(destination) != item.get("initial_destination_sha256"):
            problems.append(f"journal integration copy changed before S20 closed: {destination_rel}")
    return not problems, problems, payload

