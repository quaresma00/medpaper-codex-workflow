"""Build and verify versioned S19 scientific-review ZIP packages."""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath


SCHEMA_VERSION = 1
REVIEW_DIR_REL = "07_manuscript/review_packages"
LATEST_MANIFEST_REL = f"{REVIEW_DIR_REL}/latest_review_package.json"
REQUIRED_FILES = (
    "07_manuscript/full_manuscript.md",
    "07_manuscript/independent_publishability_review.md",
    "06_refs/refs.bib",
    "06_refs/refs.ris",
)
OPTIONAL_FILES = (
    "07_manuscript/supplementary_methods.md",
    "05_figures/legends.md",
    "04_tables/table_captions.md",
)
COLLECTION_GLOBS = (
    "04_tables/main/*.xlsx",
    "04_tables/supplementary/*.xlsx",
    "05_figures/out/*.png",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_project_rel(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    rel = PurePosixPath(value.replace("\\", "/"))
    win = PureWindowsPath(value)
    return not rel.is_absolute() and not win.is_absolute() and ".." not in rel.parts


def collect_sources(project: Path) -> list[dict]:
    missing = [rel for rel in REQUIRED_FILES if not (project / rel).is_file()]
    if missing:
        raise ValueError("required S19 review material missing: " + ", ".join(missing))
    paths = [project / rel for rel in REQUIRED_FILES]
    paths.extend(project / rel for rel in OPTIONAL_FILES if (project / rel).is_file())
    for pattern in COLLECTION_GLOBS:
        paths.extend(path for path in project.glob(pattern) if path.is_file())
    unique = sorted({path.resolve() for path in paths})
    return [
        {
            "path": path.relative_to(project.resolve()).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in unique
    ]


def _source_fingerprint(sources: list[dict]) -> str:
    canonical = json.dumps(
        [{"path": item["path"], "sha256": item["sha256"], "bytes": item["bytes"]}
         for item in sources],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_latest(project: Path) -> dict | None:
    path = project / LATEST_MANIFEST_REL
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed {LATEST_MANIFEST_REL}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{LATEST_MANIFEST_REL} must contain one JSON object")
    return payload


def _review_readme(revision: int, package_id: str, sources: list[dict]) -> str:
    listed = "\n".join(f"- {item['path']}" for item in sources)
    return (
        "S19 scientific manuscript review package\n"
        "========================================\n\n"
        f"Revision: v{revision:03d}\nPackage ID: {package_id}\n\n"
        "This package is for scientific and editorial review before journal selection.\n"
        "It is not the journal-formatted submission package. Patient-level data, credentials,\n"
        "full-text literature files and internal analysis code are intentionally excluded.\n\n"
        "Suggested review order:\n"
        "1. 07_manuscript/full_manuscript.md\n"
        "2. 07_manuscript/supplementary_methods.md, if included\n"
        "3. Tables and rendered PNG figures\n"
        "4. 06_refs/refs.ris or 06_refs/refs.bib for reference metadata\n"
        "5. 07_manuscript/independent_publishability_review.md\n\n"
        "Included project files:\n" + listed + "\n"
    )


def verify(project: Path) -> tuple[bool, list[str], dict | None]:
    try:
        manifest = _read_latest(project)
    except (OSError, ValueError) as exc:
        return False, [str(exc)], None
    if manifest is None:
        return False, [f"{LATEST_MANIFEST_REL} is missing"], None
    problems: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append("review-package manifest schema is not supported")
    archive_rel = manifest.get("archive_path")
    if not _safe_project_rel(archive_rel) or not str(archive_rel).startswith(REVIEW_DIR_REL + "/"):
        problems.append("archive_path is missing or outside the S19 review-package directory")
        archive = None
    else:
        archive = project / str(archive_rel)
        if not archive.is_file():
            problems.append(f"review archive missing: {archive_rel}")
        elif _sha256(archive) != manifest.get("archive_sha256"):
            problems.append(f"review archive changed after creation: {archive_rel}")
    try:
        current_sources = collect_sources(project)
    except (OSError, ValueError) as exc:
        problems.append(str(exc))
        current_sources = []
    if current_sources != manifest.get("source_files"):
        problems.append("review materials changed after the latest S19 ZIP was built")
    expected_id = _source_fingerprint(current_sources) if current_sources else None
    if expected_id != manifest.get("package_id"):
        problems.append("review package ID does not match the current source set")

    if archive and archive.is_file() and not problems[:2]:
        try:
            with zipfile.ZipFile(archive) as zf:
                corrupt = zf.testzip()
                if corrupt:
                    problems.append(f"review archive has a corrupt member: {corrupt}")
                expected_members = {item["path"] for item in current_sources}
                expected_members.update({"REVIEW_README.txt", "review_manifest.json"})
                names = set(zf.namelist())
                if names != expected_members:
                    problems.append("review archive member list differs from the current manifest")
                for item in current_sources:
                    if item["path"] not in names:
                        continue
                    actual = hashlib.sha256(zf.read(item["path"])).hexdigest()
                    if actual != item["sha256"]:
                        problems.append(f"archived content hash mismatch: {item['path']}")
                if "review_manifest.json" in names:
                    inside = json.loads(zf.read("review_manifest.json").decode("utf-8"))
                    if (inside.get("package_id") != manifest.get("package_id") or
                            inside.get("source_files") != manifest.get("source_files")):
                        problems.append("internal and external review manifests do not match")
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"review archive cannot be verified: {exc}")
    return not problems, problems, manifest


def build(project: Path, pipeline_version: str) -> tuple[Path, dict, bool]:
    project = project.resolve()
    sources = collect_sources(project)
    package_id = _source_fingerprint(sources)
    previous = _read_latest(project)
    if previous and previous.get("package_id") == package_id:
        ok, _, verified = verify(project)
        if ok and verified:
            return project / verified["archive_path"], verified, False
    revision = int(previous.get("package_revision", 0)) + 1 if previous else 1
    review_dir = project / REVIEW_DIR_REL
    review_dir.mkdir(parents=True, exist_ok=True)
    archive_rel = f"{REVIEW_DIR_REL}/S19-review-v{revision:03d}-{package_id[:12]}.zip"
    archive = project / archive_rel
    temporary = archive.with_suffix(".zip.tmp")
    created_at = _now()
    inside_manifest = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": pipeline_version,
        "stage": "S19_human_review",
        "package_revision": revision,
        "package_id": package_id,
        "created_at": created_at,
        "source_files": sources,
    }
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for item in sources:
            zf.write(project / item["path"], item["path"])
        zf.writestr("REVIEW_README.txt", _review_readme(revision, package_id, sources))
        zf.writestr(
            "review_manifest.json",
            json.dumps(inside_manifest, indent=2, ensure_ascii=False) + "\n",
        )
    with zipfile.ZipFile(temporary) as zf:
        corrupt = zf.testzip()
        if corrupt:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"new review ZIP failed integrity testing at {corrupt}")
    temporary.replace(archive)
    external = dict(inside_manifest)
    external.update({"archive_path": archive_rel, "archive_sha256": _sha256(archive)})
    manifest_path = project / LATEST_MANIFEST_REL
    manifest_tmp = manifest_path.with_suffix(".json.tmp")
    manifest_tmp.write_text(
        json.dumps(external, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest_tmp.replace(manifest_path)
    ok, details, verified = verify(project)
    if not ok or verified is None:
        raise ValueError("new review ZIP did not verify: " + "; ".join(details))
    return archive, verified, True

