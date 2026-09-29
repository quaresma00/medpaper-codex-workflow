"""Bind reported results to specific executed result objects, not a global number bag.

Labels and numerical correspondence are deterministic. Clinical meaning and whether the
analysis itself is valid still require the existing scientific and reader reviews.
"""
from __future__ import annotations

import json
import re

from .packagefreeze import _safe_path

CONTEXT_KEYS = {"outcome", "population", "comparison", "model", "timepoint", "unit", "denominator"}


def pointer(document, location):
    if not isinstance(location, str) or (location and not location.startswith("/")):
        raise ValueError("source pointer must use JSON Pointer syntax")
    for token in location.split("/")[1:] if location else []:
        token = token.replace("~1", "/").replace("~0", "~")
        document = document[int(token)] if isinstance(document, list) else document[token]
    return document


def facts(project):
    data = json.loads((project / "01_protocol/study_facts.json").read_text(encoding="utf-8"))
    catalog = data.get("numeric_facts")
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError("study_facts.numeric_facts must bind reported findings to executed result objects")
    resolved, documents = {}, {}
    for key, row in catalog.items():
        rel, path = _safe_path(project, row["source"])
        if not rel.startswith("03_analysis/results/") or path.suffix != ".json":
            raise ValueError(f"{key}: source must be executed analysis JSON")
        if rel not in documents:
            documents[rel] = json.loads(path.read_text(encoding="utf-8"))
        result = pointer(documents[rel], row["pointer"])
        context = result["context"]
        if (not isinstance(context, dict) or not CONTEXT_KEYS <= context.keys() or
                any(not isinstance(context[k], str) or not context[k].strip() for k in CONTEXT_KEYS)):
            raise ValueError(f"{key}: source needs explicit outcome/population/comparison/model/timepoint/unit/denominator")
        if row.get("context") != context:
            raise ValueError(f"{key}: fact context differs from its analysis source")
        values = result["values"]
        if not isinstance(values, dict) or not values:
            raise ValueError(f"{key}: source has no named numerical values")
        resolved[key] = {"context": context, "values": values,
                         "source": rel, "pointer": row["pointer"]}
    return resolved


def bindings(project, rel):
    location = ("08_submission/integration/claim_bindings.json" if rel.startswith("08_submission/")
                else "07_manuscript/claim_bindings.json")
    payload = json.loads((project / location).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("claims"), list):
        raise ValueError(f"{location}: invalid claims schema")
    return payload["claims"]


def claim_values(claim, catalog, label_text):
    from .checks.numbers import _walk
    strings = set()
    p_values = set()
    ids = claim.get("fact_ids", [])
    if not isinstance(ids, list) or not ids:
        raise ValueError("claim has no fact_ids")
    for key in ids:
        fact = catalog[key]
        # Require the source's actual outcome label, not an unrelated endpoint sharing a number.
        label = fact["context"]["outcome"]
        if label.casefold() not in label_text.casefold():
            raise ValueError(f"{key}: outcome label {label!r} missing from the bound text/label cells")
        _walk(fact["values"], strings)
        for name, value in fact["values"].items():
            if name.casefold() in {"p", "p_value", "pvalue", "adjusted_p", "q_value"}:
                p_values.add(float(value))
    return {float(s) for s in strings}, strings, p_values


def results_text(text, rel):
    if "full_manuscript" not in rel:
        return text
    # Only our study's quantitative summary/results require bindings here. Literature
    # statements retain citation checks and source review; do not bind them to our cohort.
    matches = list(re.finditer(r"^#\s+(.+?)\s*$", text, re.M))
    parts = []
    for i, heading in enumerate(matches):
        if heading.group(1).casefold() in {"abstract", "results"}:
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            parts.append(text[heading.end():end])
    return "\n\n".join(parts)


def validate_prose(project, rel, text):
    from .checks.numbers import _offenders, _scrub, NUM_RE
    relevant = rel.endswith(("results.md", "abstract.md", "full_manuscript.md"))
    if not relevant:
        return []
    body = results_text(text, rel)
    if not NUM_RE.search(_scrub(body)):
        return []
    try:
        catalog = facts(project)
        rows = bindings(project, rel)
        covered = body
        count = 0
        for row in rows:
            if row.get("path") != rel:
                continue
            quote = row.get("text", "")
            if not isinstance(quote, str) or not quote.strip() or quote not in body:
                raise ValueError("claim text is missing or changed; update the affected binding")
            floats, strings, p_values = claim_values(row, catalog, quote)
            bad = _offenders(quote, floats, strings, set(), p_values)
            if bad:
                raise ValueError(f"claim contains values absent from its own fact(s): {bad[:5]}")
            covered = covered.replace(quote, " ")
            count += 1
        if NUM_RE.search(_scrub(covered)):
            raise ValueError("reported numeric text lacks a source-bound claim; bind each reported finding, not a whole section")
        if not count:
            raise ValueError("no result claims bound")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return [f"{rel}: {exc}"]
    return []


def validate_tables(project, paths):
    from . import xlsxlite
    from .checks.numbers import _offenders, _scrub, NUM_RE
    from openpyxl import load_workbook
    problems = []
    catalog = None
    for path in paths:
        rel = path.relative_to(project).as_posix()
        cells = [(s, c, v) for s, c, v in xlsxlite.numeric_cell_values(path) if NUM_RE.search(_scrub(str(v)))]
        if not cells:
            continue
        try:
            if catalog is None:
                catalog = facts(project)
            rows = [r for r in bindings(project, rel) if r.get("path") == rel]
            index = {(r.get("sheet"), r.get("cell")): r for r in rows}
            if len(index) != len(rows):
                raise ValueError("duplicate table-cell bindings")
            workbook = load_workbook(path, read_only=True, data_only=True)
            try:
                for sheet, cell, value in cells:
                    row = index.get((sheet, cell))
                    if row is None or row.get("text") != str(value):
                        raise ValueError(f"{sheet}!{cell}: missing/stale exact-value binding")
                    labels = " ".join(str(workbook[sheet][c].value or "") for c in row.get("label_cells", []))
                    floats, strings, p_values = claim_values(row, catalog, labels + " " + str(value))
                    if _offenders(str(value), floats, strings, set(), p_values):
                        raise ValueError(f"{sheet}!{cell}: value not from its own fact(s)")
            finally:
                workbook.close()
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            problems.append(f"{rel}: {exc}")
    return problems


def copy_for_journal(project):
    """Bind unchanged initial journal prose; never overwrite an existing journal mapping."""
    from .readiness import atomic_json
    source = project / "07_manuscript/claim_bindings.json"
    destination = project / "08_submission/integration/claim_bindings.json"
    if not source.is_file() or destination.exists():
        return
    rows = json.loads(source.read_text(encoding="utf-8"))["claims"]
    rows = [{**r, "path": r["path"].replace("07_manuscript/", "08_submission/integration/", 1)}
            for r in rows if r.get("path") == "07_manuscript/full_manuscript.md"]
    atomic_json(destination, {"schema_version": 1, "claims": rows})


def assembled_bindings(project, text):
    path = project / "07_manuscript/claim_bindings.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    original = [r for r in payload["claims"] if r.get("path") != "07_manuscript/full_manuscript.md"]
    seen, assembled = set(), []
    for row in original:
        if row.get("path") not in {"07_manuscript/results.md", "07_manuscript/abstract.md"}:
            continue
        if row.get("text") and row["text"] in text:
            key = json.dumps([row["text"], row.get("fact_ids")], sort_keys=True)
            if key not in seen:
                assembled.append({**row, "path": "07_manuscript/full_manuscript.md"})
                seen.add(key)
    return {"schema_version": 1, "claims": original + assembled}
