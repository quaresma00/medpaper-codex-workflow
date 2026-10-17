"""Freeze and verify the journal-independent scientific master accepted at S19."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .reviewpackage import verify as verify_review_package


SCHEMA_VERSION = 5
FREEZE_REL = "07_manuscript/scientific_master_freeze.json"
CORE_FILES = (
    "01_protocol/artifact_benchmark.md",
    "01_protocol/study_facts.json",
    "07_manuscript/claim_bindings.json",
    "01_protocol/artifact_plan.json",
    "06_refs/library.json",
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
    "05_figures/out/*.pdf",
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
    round_based = bool(review_manifest.get("round_id"))
    required = {
        "07_manuscript/full_manuscript.md",
        "07_manuscript/human_review.md",
    }
    if round_based:
        required.update((f".wf/review_rounds/{review_manifest['round_id']}.json", review_manifest["report_path"]))
    else:
        required.update(("07_manuscript/review_packages/latest_review_package.json", str(review_manifest.get("archive_path", ""))))
    paths = [project / rel for rel in CORE_FILES if (project / rel).is_file()
             and not (round_based and rel.startswith("07_manuscript/review_packages/"))]
    if round_based:
        paths.extend(project / rel for rel in required)
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
    from .reviewrounds import latest, approved
    if latest(project, "manuscript") is not None:
        review = approved(project, "manuscript")
        binding = {"round_id": review["id"], "report_path": review["report"]["path"]}
        records = collect_files(project, binding)
        return {"schema_version": SCHEMA_VERSION, "pipeline_version": pipeline_version,
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "freeze_id": _freeze_id(review["id"], records), "review_round_id": review["id"],
                "algorithm": "SHA-256", "files": records}
    # Compatibility only for an already built legacy review package. New stage gates
    # require a review round, so a ZIP cannot release a newly running S19 workflow.
    ok, details, review = verify_review_package(project)
    if not ok or review is None:
        raise ValueError("current S19 review package is invalid: " + "; ".join(details[:8]))
    records = collect_files(project, review)
    package_id = str(review["package_id"])
    return {
        "schema_version": 4,
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
    if payload.get("schema_version") not in (1, 2, 3, 4, SCHEMA_VERSION) or payload.get("algorithm") != "SHA-256":
        problems.append("scientific freeze schema or hash algorithm is invalid")
    if payload.get("schema_version") == SCHEMA_VERSION:
        from .reviewrounds import approved
        try:
            round_record = approved(project, "manuscript")
            review = {"round_id": round_record["id"], "report_path": round_record["report"]["path"]}
            token = round_record["id"]
            if payload.get("review_round_id") != token:
                problems.append("scientific freeze is bound to a different approved review round")
        except (OSError, ValueError, KeyError) as exc:
            return False, problems + [str(exc)], payload
    else:
        ok, review_problems, review = verify_review_package(project)
        if not ok or review is None:
            problems.append("legacy S19 review package is invalid: " + "; ".join(review_problems[:5]))
            return False, problems, payload
        token = str(review["package_id"])
        if payload.get("review_package_id") != token:
            problems.append("scientific freeze is bound to a different legacy S19 review package")
    try:
        current = collect_files(project, review)
    except (OSError, ValueError) as exc:
        return False, problems + [str(exc)], payload
    recorded = payload.get("files")
    if not isinstance(recorded, list):
        return False, problems + ["scientific freeze has no files list"], payload
    # Legacy receipts included a renewable verification file. Its identity is checked
    # separately by the non-overridable reference gates; refreshing it is not science rework.
    scientific_records = [item for item in recorded if item.get("path") != "06_refs/verified.json"]
    if payload.get("schema_version") in (1, 2, 3):
        # Benchmark coverage added in v1.11 is not a retroactive change to an approved
        # manuscript. Preserve exactly what an older freeze bound; new v4 freezes bind it.
        bound = {item.get("path") for item in scientific_records}
        current = [item for item in current if item["path"] != "01_protocol/artifact_benchmark.md" or item["path"] in bound]
    if payload.get("schema_version") in (1, 2):
        # Verify exactly what the legacy receipt covered; do not silently rewrite it or
        # treat newly recognized backstage files as a change to the approved manuscript.
        bound = {item.get("path") for item in scientific_records}
        added_coverage = {"01_protocol/study_facts.json", "07_manuscript/claim_bindings.json"}
        current = [item for item in current if item["path"] not in added_coverage or item["path"] in bound]
    if current != scientific_records:
        current_map = {item["path"]: item for item in current}
        recorded_map = {str(item.get("path", "")): item for item in scientific_records if isinstance(item, dict)}
        for rel in sorted(set(current_map) | set(recorded_map)):
            if rel not in recorded_map:
                problems.append(f"scientific source added after freeze: {rel}")
            elif rel not in current_map:
                problems.append(f"frozen scientific source is missing: {rel}")
            elif current_map[rel] != recorded_map[rel]:
                problems.append(f"scientific source changed after freeze: {rel}")
            if len(problems) >= 10:
                break
    expected_id = _freeze_id(token, recorded)
    if payload.get("freeze_id") != expected_id:
        problems.append("freeze_id does not match the current scientific source records")
    return not problems, problems, payload
