"""Freeze and verify the journal-independent scientific master accepted at S19."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .reviewpackage import verify as verify_review_package


SCHEMA_VERSION = 1
FREEZE_REL = "07_manuscript/scientific_master_freeze.json"
CORE_FILES = (
    "01_protocol/artifact_plan.json",
    "06_refs/library.json",
    "06_refs/verified.json",
    "06_refs/refs.bib",
    "06_refs/refs.ris",
    "07_manuscript/title.md",
    "07_manuscript/abstract.md",
    "07_manuscript/keywords.md",
    "07_manuscript/introduction.md",
    "07_manuscript/methods.md",
    "07_manuscript/supplementary_methods.md",
    "07_manuscript/results.md",
    "07_manuscript/discussion.md",
    "07_manuscript/statements.md",
    "07_manuscript/reconciliation.md",
    "07_manuscript/full_manuscript.md",
    "07_manuscript/independent_publishability_review.md",
    "07_manuscript/human_review.md",
    "07_manuscript/review_packages/latest_review_package.json",
    "04_tables/table_captions.md",
    "05_figures/legends.md",
)
COLLECTION_GLOBS = (
    "03_analysis/results/*.json",
    "04_tables/main/*.xlsx",
    "04_tables/supplementary/*.xlsx",
    "05_figures/out/*.png",
    "05_figures/out/*.tif",
    "05_figures/out/*.tiff",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_files(project: Path, review_manifest: dict) -> list[dict]:
    project = project.resolve()
    required = {
        "07_manuscript/full_manuscript.md",
        "07_manuscript/human_review.md",
        "07_manuscript/review_packages/latest_review_package.json",
        str(review_manifest.get("archive_path", "")),
    }
    paths = [project / rel for rel in CORE_FILES if (project / rel).is_file()]
    for pattern in COLLECTION_GLOBS:
        paths.extend(path for path in project.glob(pattern) if path.is_file())
    archive_rel = str(review_manifest.get("archive_path", "")).strip()
    if archive_rel:
        paths.append(project / archive_rel)
    found = {path.relative_to(project).as_posix(): path for path in paths if path.is_file()}
    missing = sorted(rel for rel in required if not rel or rel not in found)
    if missing:
        raise ValueError("scientific-master input missing: " + ", ".join(missing))
    return [
        {"path": rel, "sha256": _sha256(path), "bytes": path.stat().st_size}
        for rel, path in sorted(found.items())
    ]


def _freeze_id(review_package_id: str, records: list[dict]) -> str:
    payload = {"review_package_id": review_package_id, "files": records}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_payload(project: Path, pipeline_version: str) -> dict:
    ok, details, review = verify_review_package(project)
    if not ok or review is None:
        raise ValueError("current S19 review package is invalid: " + "; ".join(details[:8]))
    records = collect_files(project, review)
    package_id = str(review["package_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": pipeline_version,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "freeze_id": _freeze_id(package_id, records),
        "review_package_id": package_id,
        "review_package_revision": review["package_revision"],
        "review_archive_path": review["archive_path"],
        "algorithm": "SHA-256",
        "files": records,
    }


def write(project: Path, pipeline_version: str) -> tuple[Path, dict, bool]:
    project = project.resolve()
    output = project / FREEZE_REL
    payload = build_payload(project, pipeline_version)
    if output.is_file():
        try:
            previous = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
        if previous.get("freeze_id") == payload["freeze_id"]:
            ok, _, verified = verify(project)
            if ok and verified is not None:
                return output, verified, False
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(output)
    ok, problems, verified = verify(project)
    if not ok or verified is None:
        raise ValueError("new scientific freeze did not verify: " + "; ".join(problems[:8]))
    return output, verified, True


def verify(project: Path) -> tuple[bool, list[str], dict | None]:
    project = project.resolve()
    path = project / FREEZE_REL
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, [f"{FREEZE_REL} is missing"], None
    except json.JSONDecodeError as exc:
        return False, [f"{FREEZE_REL} is invalid JSON: {exc}"], None
    problems: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("algorithm") != "SHA-256":
        problems.append("scientific freeze schema or hash algorithm is invalid")
    ok, review_problems, review = verify_review_package(project)
    if not ok or review is None:
        problems.append("current S19 review package is invalid: " + "; ".join(review_problems[:5]))
        return False, problems, payload
    if payload.get("review_package_id") != review.get("package_id"):
        problems.append("scientific freeze is bound to a different S19 review package")
    try:
        current = collect_files(project, review)
    except (OSError, ValueError) as exc:
        return False, problems + [str(exc)], payload
    recorded = payload.get("files")
    if not isinstance(recorded, list):
        return False, problems + ["scientific freeze has no files list"], payload
    if current != recorded:
        current_map = {item["path"]: item for item in current}
        recorded_map = {str(item.get("path", "")): item for item in recorded if isinstance(item, dict)}
        for rel in sorted(set(current_map) | set(recorded_map)):
            if rel not in recorded_map:
                problems.append(f"scientific source added after freeze: {rel}")
            elif rel not in current_map:
                problems.append(f"frozen scientific source is missing: {rel}")
            elif current_map[rel] != recorded_map[rel]:
                problems.append(f"scientific source changed after freeze: {rel}")
            if len(problems) >= 10:
                break
    expected_id = _freeze_id(str(review["package_id"]), current)
    if payload.get("freeze_id") != expected_id:
        problems.append("freeze_id does not match the current scientific source records")
    return not problems, problems, payload

