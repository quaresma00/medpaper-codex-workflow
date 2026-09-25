"""Small, evidence-bound writing and display readiness checkpoints."""
from __future__ import annotations

import json
from pathlib import Path

from .packagefreeze import _safe_path, _sha256

CONTRACT = "01_protocol/analysis_contract.json"
FACTS = "01_protocol/study_facts.json"
FREEZE = "01_protocol/writing_readiness.json"
PROTOTYPES = "01_protocol/display_review.json"
CONTRACT_KEYS = (
    "population_and_period", "eligibility", "unit_and_denominators", "outcomes",
    "missing_duplicates_outliers", "validation_and_adjudication", "models_and_sensitivity",
    "exploratory_vs_confirmatory", "evidence_boundaries",
)
STORY_KEYS = ("clinical_question", "main_finding", "clinical_relevance", "cannot_claim")


def load(project: Path, rel: str) -> dict:
    _, path = _safe_path(project, rel)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{rel} must contain an object")
    return value


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _populated(value) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"todo", "tbd", "unknown", "pending"}
    return True


def writing_sources(project: Path) -> dict[str, str]:
    contract, facts = load(project, CONTRACT), load(project, FACTS)
    for rel, doc, keys in ((CONTRACT, contract, CONTRACT_KEYS), (FACTS, facts, STORY_KEYS)):
        missing = [key for key in keys if not _populated(doc.get(key))]
        if missing:
            raise ValueError(f"{rel}: unresolved fields: {', '.join(missing)}")
    support = facts.get("result_sources")
    if not isinstance(support, list) or not support:
        raise ValueError("study_facts.result_sources must identify executed result JSONs")
    for rel in support:
        if not str(rel).startswith("03_analysis/results/") or not str(rel).endswith(".json"):
            raise ValueError(f"not a result source: {rel}")
        json.loads(_safe_path(project, rel)[1].read_text(encoding="utf-8"))
    explicit = [CONTRACT, FACTS, "01_protocol/protocol_final.md", "01_protocol/protocol_diff.md",
                "02_data/acquisition_manifest.json"]
    files = {rel: _safe_path(project, rel)[1] for rel in explicit}
    files.update({rel: _safe_path(project, rel)[1] for rel in support})
    for pattern in ("03_analysis/code/**/*", "03_analysis/results/*.json"):
        for path in project.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[path.relative_to(project).as_posix()] = path
    if not any(rel.startswith("03_analysis/code/") for rel in files):
        raise ValueError("no executed analysis source code")
    for rel, path in files.items():
        if not path.is_file():
            raise ValueError(f"writing-readiness input missing: {rel}")
    return {rel: _sha256(path) for rel, path in sorted(files.items())}


def freeze_writing(project: Path) -> dict:
    from .state import State

    state = State(project).load()
    if state.current != "S06_protocol_final":
        raise ValueError("writing freeze is created only at S06 after analysis has converged")
    for name, value in (("analysis_converged", "YES"), ("go_nogo_2", "GO")):
        if (state.decision(name) or {}).get("value") != value:
            raise ValueError(f"{name}={value} must be recorded before freezing")
    payload = {"schema_version": 1, "files": writing_sources(project)}
    atomic_json(project / FREEZE, payload)
    return payload


def verify_writing(project: Path) -> list[str]:
    try:
        frozen = load(project, FREEZE)
        current = writing_sources(project)
        if frozen.get("schema_version") != 1 or frozen.get("files") != current:
            return ["analysis, protocol or clinical story changed after S06; return to its owner and refreeze"]
    except (OSError, ValueError, TypeError) as exc:
        return [str(exc)]
    return []


def verify_displays(project: Path) -> list[str]:
    """Require an actual low-cost preview and a substantive reader account per display."""
    try:
        plan = load(project, "01_protocol/artifact_plan.json")
        review = load(project, PROTOTYPES)
        expected = {entry["id"]: entry for group in
                    ("main_figures", "main_tables", "supp_figures", "supp_tables")
                    for entry in plan.get(group, [])}
        rows = review.get("items", [])
        observed = {row["id"]: row for row in rows}
        if len(observed) != len(rows) or set(expected) != set(observed):
            return ["display review must cover each planned display exactly once"]
        problems = []
        for key, entry in expected.items():
            row = observed[key]
            rel, preview = _safe_path(project, row.get("preview", ""))
            allowed = {".png", ".svg", ".pdf"} if key.startswith("Figure") else {".md", ".csv"}
            if not rel.startswith("01_protocol/prototypes/") or preview.suffix.lower() not in allowed:
                problems.append(f"{key}: preview must be a cheap prototype under 01_protocol/prototypes")
            if not preview.is_file() or row.get("preview_sha256") != _sha256(preview):
                problems.append(f"{key}: preview is missing or changed since reader review")
            for field in ("question", "reader_explanation", "denominator_units_missingness",
                          "encoding_overlap", "layout", "reviewer"):
                if not _populated(row.get(field)) or len(str(row[field]).strip()) < 8:
                    problems.append(f"{key}: substantive {field} is required")
            if row.get("verdict") != "PASS":
                problems.append(f"{key}: reader test has not passed")
            sources = entry.get("source_results", [])
            source_hashes = {r: _sha256(_safe_path(project, r)[1]) for r in sources}
            if row.get("source_hashes") != source_hashes:
                problems.append(f"{key}: reader review does not match current result sources")
        return problems
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [str(exc)]
