"""Freeze and verify the exact submission package presented to the final reviewer."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


FREEZE_REL = "08_submission/package_review_freeze.json"
MANIFEST_REL = "08_submission/bundle/manifest.json"
REQUIRED_EVIDENCE = (
    "08_submission/target_journal.json",
    "08_submission/guidelines_extract.md",
    "08_submission/docx_style.json",
    "08_submission/submission_qc.md",
)
OPTIONAL_EVIDENCE = (
    "07_manuscript/full_manuscript.md",
    "07_manuscript/supplementary_methods.md",
    "07_manuscript/title_page.md",
    "07_manuscript/statements.md",
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
    """Return every package and evidence file that the independent audit must see."""
    project = project.resolve()
    required = (MANIFEST_REL, *REQUIRED_EVIDENCE)
    files: dict[str, Path] = {}
    missing: list[str] = []
    for rel in required:
        normalized, path = _safe_path(project, rel)
        if not path.is_file():
            missing.append(normalized)
        else:
            files[normalized] = path
    if missing:
        raise ValueError("required review evidence missing: " + ", ".join(missing))

    try:
        manifest = json.loads(files[MANIFEST_REL].read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{MANIFEST_REL} is invalid JSON: {exc}") from exc
    for item in manifest.get("items", []):
        normalized, path = _safe_path(project, str(item.get("file", "")))
        if not path.is_file():
            raise ValueError(f"manifest item missing: {normalized}")
        files[normalized] = path

    for folder_rel in ("08_submission/bundle", "08_submission/cache"):
        _, folder = _safe_path(project, folder_rel)
        if folder.is_dir():
            for path in sorted(p for p in folder.rglob("*") if p.is_file()):
                rel = path.relative_to(project).as_posix()
                files[rel] = path
    if not any(rel.startswith("08_submission/cache/") for rel in files):
        raise ValueError("no cached official journal guideline snapshot is available")

    for rel in OPTIONAL_EVIDENCE:
        normalized, path = _safe_path(project, rel)
        if path.is_file():
            files[normalized] = path
    return dict(sorted(files.items()))


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
        "schema_version": 1,
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
    if payload.get("schema_version") != 1 or payload.get("algorithm") != "SHA-256":
        problems.append("freeze manifest schema or hash algorithm is invalid")
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
    except ValueError as exc:
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
    return not problems, problems, len(recorded)
