"""Actual-file submission measurements, separate from human visual acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .packagefreeze import expected_files, _sha256
from .readiness import atomic_json

RECEIPT = ".wf/submission_measurements.json"
CHECKLIST = "08_submission/evidence/SUBMISSION_CHECKLIST.md"
BEGIN, END = "<!-- medpaper measured begin -->", "<!-- medpaper measured end -->"
RULE_FILES = [Path(__file__), *(Path(__file__).with_name(name + ".py") for name in
    ("wordtables", "submission", "journalrules", "journalspec", "determinism", "buildproof", "cslpatch", "qualitylimits")),
    Path(__file__).parents[1]/"manuscript/build_docx.py"]


def measure(project: Path) -> dict:
    from manuscript.build_docx import load_style, audit_docx, planned_figure_ids, figure_legend_cap
    from .submission import verify_portal
    files = expected_files(project)  # Empty/missing manifest must fail, never PASS zero files.
    manifest_path = project / "08_submission/bundle/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    style_path = project / "08_submission/docx_style.json"
    style = load_style(style_path)
    rows = []
    for entry in manifest.get("items", []):
        rel = entry.get("file")
        if rel not in files:
            continue
        path = files[rel]
        defects = []
        if path.suffix.lower() == ".docx":
            kind = entry.get("role", "")
            scope = entry.get("legend_scope", style.get("figure_legend_scope", "all"))
            figures = planned_figure_ids(project, scope) if kind in {"manuscript", "figure_legends"} else None
            defects = audit_docx(path, style, kind, figures, figure_legend_cap())
            from docx import Document
            from docx.oxml.ns import qn
            doc = Document(path)
            if style.get("page_numbers", True):
                for index, section in enumerate(doc.sections):
                    footer = section.footer._element
                    fields = [node.text or "" for node in footer.iter(qn("w:instrText"))] + [
                        node.get(qn("w:instr"), "") for node in footer.iter(qn("w:fldSimple"))]
                    if not any("PAGE" in value.split() for value in fields):
                        defects.append(f"section {index + 1}: missing actual PAGE footer field")
                    numbering = section._sectPr.find(qn("w:pgNumType"))
                    if numbering is not None and numbering.get(qn("w:start")) is not None:
                        defects.append(f"section {index + 1}: numbering restarts")
        rows.append({"file": rel, "sha256": _sha256(path), "status": "FAIL" if defects else "PASS",
                     "checks": "DOCX structure/typography/native tables/page fields" if path.suffix.lower() == ".docx" else "manifest existence and identity only",
                     "defects": defects})
    portal_defects = verify_portal(project)
    rows.append({"file": "08_submission/portal_fields.json", "status": "FAIL" if portal_defects else "PASS",
                 "checks": "actual final-DOCX fields, typed journal limits and administrative binding", "defects": portal_defects})
    sources = {rel: _sha256(path) for rel, path in files.items()}
    for rel in ("08_submission/bundle/manifest.json", "08_submission/docx_style.json",
                "08_submission/submission_requirements.json", "08_submission/target_journal.json",
                "08_submission/portal_fields.json", "00_input/author_info.json"):
        if (project / rel).is_file():
            sources[rel] = _sha256(project / rel)
    engine = {str(path.resolve()): _sha256(path) for path in RULE_FILES}
    signature = hashlib.sha256(json.dumps({"sources": sources, "engine": engine}, sort_keys=True).encode()).hexdigest()
    return {"schema_version": 1, "input_signature": signature, "sources": sources, "engine": engine, "rows": rows,
            "ok": all(row["status"] == "PASS" for row in rows),
            "visual_acceptance": "Not certified by these measurements; actual final rendered pages must be inspected."}


def write(project: Path) -> dict:
    payload = measure(project)
    atomic_json(project / RECEIPT, payload)
    path = project / CHECKLIST
    previous = path.read_text(encoding="utf-8") if path.is_file() else "# Submission files\n\n"
    if BEGIN in previous:
        if END not in previous:
            raise ValueError("incomplete measured checklist block; preserve and repair it explicitly")
        left, rest = previous.split(BEGIN, 1)
        _, right = rest.split(END, 1)
        previous = left.rstrip() + "\n\n" + right.lstrip()
    lines = [BEGIN, "## Measured final-file checks", "", payload["visual_acceptance"], ""]
    for row in payload["rows"]:
        lines.append(f"- {row['status']} `{row['file']}`: {row['checks']}")
        lines.extend(f"  - {defect}" for defect in row["defects"])
    lines += ["", END, ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(previous.rstrip() + "\n\n" + "\n".join(lines), encoding="utf-8")
    return payload


def verify(project: Path) -> list[str]:
    try:
        receipt = json.loads((project / RECEIPT).read_text(encoding="utf-8"))
        # Hash current sources/rules first. Do not repeat passed measurements on unchanged files.
        for rel, digest in receipt["sources"].items():
            if not (project / rel).is_file() or _sha256(project / rel) != digest:
                return [f"submission measurement stale: {rel}; measure final files again"]
        current_files = expected_files(project)
        if any(rel not in receipt["sources"] for rel in current_files):
            return ["submission upload inventory changed"]
        # The receipt signature includes code identity, preventing stale-rule reuse.
        for path in RULE_FILES:
            if receipt.get("engine", {}).get(str(path.resolve())) != _sha256(path):
                return ["measurement rules changed; remeasure final files"]
        return [] if receipt.get("ok") else ["actual-file measurements contain failed rows"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [str(exc)]
