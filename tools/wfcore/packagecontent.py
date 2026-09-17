"""Bind submission DOCX visible text to the S23 package build.

Binary Word changes are allowed after capture when visible text is unchanged, which permits
manual layout work. Any text drift or upstream-source drift requires a workflow rewind and a
new S23 build/capture.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


BASELINE_REL = "08_submission/package_content_baseline.json"
MANIFEST_REL = "08_submission/bundle/manifest.json"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
DEFAULT_SOURCES = {
    "manuscript": "08_submission/integration/full_manuscript.md",
    "title_page": "08_submission/integration/title_page.md",
    "cover_letter": "08_submission/cover_letter.md",
    "supplementary": "08_submission/integration/supplementary_methods.md",
    "statements": "08_submission/integration/statements.md",
    "declarations": "08_submission/integration/statements.md",
    "figure_legends": "05_figures/legends.md",
}


def _safe_path(project: Path, raw: str) -> tuple[str, Path]:
    rel = PurePosixPath(str(raw).replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError(f"unsafe project-relative path: {raw}")
    path = project.joinpath(*rel.parts).resolve()
    try:
        path.relative_to(project.resolve())
    except ValueError as exc:
        raise ValueError(f"path leaves the project directory: {raw}") from exc
    return rel.as_posix(), path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def visible_text(path: Path) -> str:
    """Extract stable visible paragraph text from the main DOCX document part."""
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError(f"cannot read visible Word text from {path.name}: {exc}") from exc
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))
        paragraphs.append(unicodedata.normalize("NFC", text.replace("\u00a0", " ")))
    return "\n".join(paragraphs).rstrip() + "\n"


def _manifest(project: Path) -> tuple[Path, dict]:
    _, path = _safe_path(project, MANIFEST_REL)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{MANIFEST_REL} missing") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{MANIFEST_REL} is invalid JSON: {exc}") from exc
    return path, data


def build_baseline(project: Path) -> dict:
    project = project.resolve()
    manifest_path, manifest = _manifest(project)
    records: list[dict] = []
    seen: set[str] = set()
    for item in manifest.get("items", []):
        raw = str(item.get("file", "")).strip()
        rel, path = _safe_path(project, raw)
        if path.suffix.casefold() != ".docx":
            continue
        if rel in seen:
            raise ValueError(f"duplicate DOCX manifest item: {rel}")
        seen.add(rel)
        if not path.is_file():
            raise ValueError(f"manifest DOCX missing: {rel}")
        role = str(item.get("role", "")).strip().casefold()
        source_raw = str(item.get("source") or DEFAULT_SOURCES.get(role, "")).strip()
        record = {
            "path": rel,
            "role": role,
            "binary_sha256": _sha256_file(path),
            "visible_text_sha256": _sha256_bytes(visible_text(path).encode("utf-8")),
        }
        if source_raw:
            source_rel, source_path = _safe_path(project, source_raw)
            if not source_path.is_file():
                raise ValueError(f"source for {rel} is missing: {source_rel}")
            record["source"] = source_rel
            record["source_sha256"] = _sha256_file(source_path)
        records.append(record)
    if not records:
        raise ValueError("manifest contains no DOCX files to bind")
    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest": MANIFEST_REL,
        "manifest_sha256": _sha256_file(manifest_path),
        "records": sorted(records, key=lambda item: item["path"]),
    }


def write_baseline(project: Path, *, replace: bool = False) -> Path:
    project = project.resolve()
    _, output = _safe_path(project, BASELINE_REL)
    if output.exists() and not replace:
        raise ValueError(f"{BASELINE_REL} already exists; rebuild at S23 and use --replace")
    payload = build_baseline(project)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def verify_baseline(project: Path) -> tuple[bool, list[str], int]:
    project = project.resolve()
    _, baseline_path = _safe_path(project, BASELINE_REL)
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, [f"{BASELINE_REL} missing"], 0
    except json.JSONDecodeError as exc:
        return False, [f"{BASELINE_REL} is invalid JSON: {exc}"], 0
    problems: list[str] = []
    if baseline.get("schema_version") != 1:
        problems.append("package-content baseline schema is invalid")
    try:
        manifest_path, manifest = _manifest(project)
    except ValueError as exc:
        return False, problems + [str(exc)], 0
    if baseline.get("manifest_sha256") != _sha256_file(manifest_path):
        problems.append("bundle manifest changed after the S23 content baseline")

    current_docx: set[str] = set()
    for item in manifest.get("items", []):
        try:
            rel, path = _safe_path(project, str(item.get("file", "")))
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if path.suffix.casefold() == ".docx":
            current_docx.add(rel)
    records = baseline.get("records")
    if not isinstance(records, list):
        return False, problems + ["package-content baseline has no records list"], 0
    recorded = {str(item.get("path", "")): item for item in records if isinstance(item, dict)}
    if set(recorded) != current_docx:
        added = sorted(current_docx - set(recorded))
        removed = sorted(set(recorded) - current_docx)
        if added:
            problems.append("DOCX absent from S23 content baseline: " + ", ".join(added[:8]))
        if removed:
            problems.append("baseline DOCX absent from manifest: " + ", ".join(removed[:8]))

    formatting_only = 0
    for rel in sorted(set(recorded) & current_docx):
        item = recorded[rel]
        try:
            _, path = _safe_path(project, rel)
            current_binary = _sha256_file(path)
            current_text = _sha256_bytes(visible_text(path).encode("utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{rel}: {exc}")
            continue
        if current_text != item.get("visible_text_sha256"):
            problems.append(
                f"{rel}: visible Word text changed after S23; route to the owning source stage and rebuild"
            )
        elif current_binary != item.get("binary_sha256"):
            formatting_only += 1
        source_raw = str(item.get("source", "")).strip()
        if source_raw:
            try:
                _, source_path = _safe_path(project, source_raw)
                current_source = _sha256_file(source_path)
            except (OSError, ValueError) as exc:
                problems.append(f"{rel}: source {source_raw} cannot be verified ({exc})")
                continue
            if current_source != item.get("source_sha256"):
                problems.append(
                    f"{rel}: source {source_raw} changed after S23; rebuild the DOCX and recapture at S23"
                )
    if problems:
        return False, problems, len(records)
    detail = f"{len(records)} DOCX visible-text baseline(s) match"
    if formatting_only:
        detail += f"; {formatting_only} binary change(s) are formatting-only"
    return True, [detail], len(records)

