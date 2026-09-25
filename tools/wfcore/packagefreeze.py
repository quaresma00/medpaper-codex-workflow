"""Freeze and verify the exact submission package presented to the final reviewer."""
from __future__ import annotations

import hashlib
import json
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


FREEZE_REL = "08_submission/package_review_freeze.json"
MANIFEST_REL = "08_submission/bundle/manifest.json"
EVIDENCE_REL = "08_submission/evidence/evidence_manifest.json"
REQUIRED_EVIDENCE = (
    "08_submission/target_journal.json",
    "08_submission/guidelines_extract.md",
    "08_submission/docx_style.json",
    "08_submission/submission_qc.md",
    "08_submission/package_content_baseline.json",
)
OPTIONAL_EVIDENCE = (
    "07_manuscript/scientific_master_freeze.json",
    "08_submission/integration/journal_workspace.json",
    "08_submission/integration/full_manuscript.md",
    "08_submission/integration/supplementary_methods.md",
    "08_submission/integration/title_page.md",
    "08_submission/integration/statements.md",
    "08_submission/cover_letter.md",
    "05_figures/legends.md",
    "04_tables/table_captions.md",
)


def _safe_path(project: Path, raw: str) -> tuple[str, Path]:
    rel = PurePosixPath(str(raw).replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError(f"unsafe project-relative path: {raw}")
    normalized = rel.as_posix()
    path = project.joinpath(*rel.parts).resolve()
    try:
        path.relative_to(project.resolve())
    except ValueError as exc:
        raise ValueError(f"path leaves the project directory: {raw}") from exc
    return normalized, path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def expected_files(project: Path) -> dict[str, Path]:
    """Return actual upload files only. Caches and working sources are not uploads."""
    project = project.resolve()
    files: dict[str, Path] = {}
    try:
        manifest = json.loads((project / MANIFEST_REL).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{MANIFEST_REL} is invalid JSON: {exc}") from exc
    for item in manifest.get("items", []):
        if item.get("upload", True) is False:
            continue
        normalized, path = _safe_path(project, str(item.get("file", "")))
        if not normalized.startswith("08_submission/bundle/"):
            raise ValueError(f"upload must be inside bundle: {normalized}")
        if path.name in {"manifest.json", "SUBMISSION_CHECKLIST.md"}:
            continue  # legacy handoff metadata is never uploaded
        if normalized == "08_submission/bundle/upload_manifest.json":
            raise ValueError("upload_manifest.json is reserved release metadata, not an upload filename")
        if normalized in files:
            raise ValueError(f"duplicate upload: {normalized}")
        if not path.is_file():
            raise ValueError(f"manifest item missing: {normalized}")
        files[normalized] = path
    if not files:
        raise ValueError("no actual upload files in manifest")
    return dict(sorted(files.items()))


def sync_evidence(project: Path) -> dict:
    """Refresh backstage locations without changing the approved upload identity."""
    records = []
    candidates = [*REQUIRED_EVIDENCE, *OPTIONAL_EVIDENCE,
                  "08_submission/submission_requirements.json", "08_submission/portal_fields.json"]
    for rel in candidates:
        path = project / rel
        if path.is_file():
            records.append({"path": rel, "sha256": _sha256(path)})
    # Requirement content matters to the audit, but its refresh is not an author revision.
    context = [row for row in records if row["path"] in {
        "08_submission/target_journal.json", "08_submission/guidelines_extract.md",
        "08_submission/submission_requirements.json", "08_submission/docx_style.json"}]
    payload = {"schema_version": 1, "files": records,
               "guideline_cache": "08_submission/cache/",
               "audit_context_id": hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest().upper()}
    from .readiness import atomic_json
    atomic_json(project / EVIDENCE_REL, payload)
    return payload


def build_freeze(project: Path) -> dict:
    files = expected_files(project)
    records = [
        {"path": rel, "sha256": _sha256(path), "size": path.stat().st_size}
        for rel, path in files.items()
    ]
    freeze_id = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest().upper()
    return {
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "freeze_id": freeze_id,
        "algorithm": "SHA-256",
        "files": records,
    }


def write_freeze(project: Path, output: Path | None = None) -> Path:
    project = project.resolve()
    output = (output or project.joinpath(*PurePosixPath(FREEZE_REL).parts)).resolve()
    try:
        output.relative_to(project)
    except ValueError as exc:
        raise ValueError("freeze manifest must remain inside the project directory") from exc
    payload = build_freeze(project)
    release = project / "08_submission/releases" / payload["freeze_id"]
    release.mkdir(parents=True, exist_ok=True)
    for record in payload["files"]:
        source = project / record["path"]
        relative = Path(record["path"]).relative_to("08_submission/bundle")
        destination = release / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if _sha256(destination) != record["sha256"]:
                raise ValueError(f"existing immutable release has drifted: {destination}")
        else:
            shutil.copy2(source, destination)
        destination.chmod(destination.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    payload["release_dir"] = release.relative_to(project).as_posix()
    release_manifest = release / "upload_manifest.json"
    if not release_manifest.exists():
        release_manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        release_manifest.chmod(release_manifest.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    sync_evidence(project)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def verify_freeze(project: Path, freeze: Path | None = None) -> tuple[bool, list[str], int]:
    project = project.resolve()
    freeze = (freeze or project.joinpath(*PurePosixPath(FREEZE_REL).parts)).resolve()
    try:
        payload = json.loads(freeze.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, [f"{FREEZE_REL} missing"], 0
    except json.JSONDecodeError as exc:
        return False, [f"{FREEZE_REL} invalid JSON: {exc}"], 0

    problems: list[str] = []
    if payload.get("schema_version") != 2 or payload.get("algorithm") != "SHA-256":
        problems.append("legacy/malformed freeze: return to S24 to confirm an upload-only read-only release")
    records = payload.get("files")
    if not isinstance(records, list):
        return False, problems + ["freeze manifest has no files list"], 0
    expected_freeze_id = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest().upper()
    if payload.get("freeze_id") != expected_freeze_id:
        problems.append("freeze_id does not match the frozen file records")

    recorded: dict[str, dict] = {}
    for item in records:
        if not isinstance(item, dict) or not item.get("path"):
            problems.append("freeze manifest contains a malformed file record")
            continue
        rel = str(item["path"]).replace("\\", "/")
        if rel in recorded:
            problems.append(f"duplicate freeze record: {rel}")
        recorded[rel] = item
    try:
        expected = expected_files(project)
    except (OSError, ValueError) as exc:
        return False, problems + [str(exc)], len(recorded)

    added = sorted(set(expected) - set(recorded))
    removed = sorted(set(recorded) - set(expected))
    if added:
        problems.append("not frozen: " + ", ".join(added[:8]))
    if removed:
        problems.append("frozen file now absent: " + ", ".join(removed[:8]))
    for rel in sorted(set(expected) & set(recorded)):
        item = recorded[rel]
        path = expected[rel]
        if item.get("size") != path.stat().st_size or item.get("sha256") != _sha256(path):
            problems.append(f"changed after user confirmation: {rel}")
    expected_release = "08_submission/releases/" + str(payload.get("freeze_id", ""))
    if payload.get("release_dir") != expected_release:
        problems.append("release directory does not match upload identity")
        return False, problems, len(recorded)
    _, release = _safe_path(project, expected_release)
    release_names = {"upload_manifest.json"}
    for rel, item in recorded.items():
        try:
            relative = PurePosixPath(rel).relative_to("08_submission/bundle")
        except ValueError:
            problems.append(f"not an upload record: {rel}")
            continue
        release_names.add(relative.as_posix())
        _, path = _safe_path(project, f"{expected_release}/{relative}")
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            problems.append(f"immutable release missing or changed: {relative}")
        elif path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            problems.append(f"release is no longer read-only: {relative}")
    observed = {p.relative_to(release).as_posix() for p in release.rglob("*") if p.is_file()}
    if observed != release_names:
        problems.append("release has missing or unexpected files")
    manifest = release / "upload_manifest.json"
    if manifest.is_file():
        try:
            saved = json.loads(manifest.read_text(encoding="utf-8"))
            if saved.get("files") != records or saved.get("freeze_id") != payload.get("freeze_id"):
                problems.append("release upload manifest does not match the confirmed files")
            if manifest.stat().st_mode & stat.S_IWUSR:
                problems.append("release upload manifest is writable")
        except (OSError, ValueError) as exc:
            problems.append(f"release upload manifest invalid: {exc}")
    return not problems, problems, len(recorded)
