"""Bind reported results to specific executed result objects, not a global number bag.

Labels and numerical correspondence are deterministic. Clinical meaning and whether the
analysis itself is valid still require the existing scientific and reader reviews.
"""
from __future__ import annotations

import hashlib
import json
import re

from .packagefreeze import _safe_path

CONTEXT_KEYS = {"outcome", "population", "comparison", "model", "timepoint", "unit", "denominator"}
PROSE_CONTEXT_KEYS = {"population", "comparison", "model", "timepoint"}


def fingerprint(value):
    """Semantic finding/text identity, not the binary identity of unrelated export rows."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


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
        resolved[key]["fingerprint"] = fingerprint(resolved[key])
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
        from .clinicalpresentation import label as clinical_label
        label = fact["context"]["outcome"]
        if claim.get("_project") is not None: label=clinical_label(label,claim["_project"])
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
            parts.append(text[heading.start():end])
    return "\n\n".join(parts)


def _phrase(value, text):
    value = re.sub(r"\s+", " ", value).strip()
    text = re.sub(r"\s+", " ", text)
    return bool(value and re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text, re.I))


def _section_scopes(text, rel, quote):
    if "full_manuscript" not in rel:
        return [text]
    headings = list(re.finditer(r"^#\s+(.+?)\s*$", text, re.M))
    scopes = []
    for i, heading in enumerate(headings):
        if heading[1].casefold() in {"abstract", "results"}:
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            section = text[heading.end():end]
            if quote in section:
                scopes.append(section)
    return scopes


def _outline(text):
    """Actual heading paths and direct introductions, not the first word 'Results'."""
    rows, stack = [], []
    matches = list(re.finditer(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", text, re.M))
    for i, match in enumerate(matches):
        level = len(match[1])
        while stack and rows[stack[-1]]["level"] >= level:
            stack.pop()
        row = {"level": level, "path": [rows[j]["title"] for j in stack] + [match[2]],
               "title": match[2], "start": match.start(), "content": match.end(),
               "end": matches[i+1].start() if i+1 < len(matches) else len(text),
               "ancestors": list(stack)}
        rows.append(row); stack.append(i)
    return rows


def _locate_claim(body, quote, claim, outline):
    """One current occurrence; sibling/other-summary text is not inherited context."""
    section = claim.get("section")
    if section is not None and (not isinstance(section, list) or not section or
                                any(not isinstance(x, str) or not x.strip() for x in section)):
        raise ValueError("claim section must be an actual nonempty Markdown heading path")
    found = []
    for match in re.finditer(re.escape(quote), body):
        preceding = [i for i, row in enumerate(outline) if row["start"] <= match.start()]
        node = outline[preceding[-1]] if preceding else None
        # A real parent heading is a valid locator scope. Assembly adds the chapter
        # around component subsections; the unique occurrence keeps its leaf context.
        if section is not None and (node is None or node["path"][:len(section)] != section):
            continue
        pieces = []
        if node:
            pieces.extend(body[outline[j]["start"]:outline[j]["end"]] for j in node["ancestors"])
            pieces.append(body[node["start"]:match.end()])
        else:
            pieces.append(body[:match.end()])
        found.append((match.start(), match.end(), "\n\n".join(pieces)))
    occurrence = claim.get("occurrence")
    if occurrence is not None:
        if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 1 or occurrence > len(found):
            raise ValueError("claim occurrence must identify an actual 1-based occurrence inside its section")
        found = [found[occurrence-1]]
    if len(found) != 1:
        raise ValueError("claim text is missing or ambiguous; bind each occurrence with its actual section/occurrence instead of certifying repeated sentences together")
    return found[0]


def _not_applicable(value):
    # Only an explicit, explained source assertion; "none"/unknown is not N/A.
    return bool(re.match(r"^\s*(?:n/?a\b|not applicable\b)", value, re.I) and len(value.strip()) >= 30)


def validate_context(project, rel, text, claim, catalog, *, required, label_lookup=None,
                     context_scope=None, alternatives_by_field=None):
    """Bind a scoped executor read-back to the real finding and current prose.

    Literal evidence is checked mechanically. Nonliteral meaning requires an actual,
    substantive executor observation; it is not certified by this numeric gate and is
    still read by the existing S18/S25 reviewer. No independent review is invented here.
    """
    evidence = claim.get("context_evidence")
    if evidence is None and not required:
        return
    ids = claim.get("fact_ids", [])
    if not isinstance(evidence, dict) or set(evidence) != set(ids):
        raise ValueError("claim context_evidence must bind its own fact_ids; use actual same-sentence/section context, not repeated boilerplate")
    quote = claim["text"]
    scopes = [context_scope] if context_scope is not None else _section_scopes(text, rel, quote)
    if not scopes:
        raise ValueError("claim has no current Abstract/Results context")
    from .clinicalpresentation import label as clinical_label
    label_lookup = label_lookup or (lambda value: clinical_label(value, project))
    for key in ids:
        fact = catalog[key]
        item = evidence[key]
        if not isinstance(item, dict) or item.get("fact_fingerprint") != fact["fingerprint"] or item.get("claim_fingerprint") != fingerprint(quote):
            raise ValueError(f"{key}: stale/missing fact or claim context fingerprint; read the affected finding and current text again")
        observations = item.get("observations")
        applicable = {field for field in PROSE_CONTEXT_KEYS if not _not_applicable(fact["context"][field])}
        if not isinstance(observations, dict) or not applicable <= observations.keys() or set(observations) - CONTEXT_KEYS:
            raise ValueError(f"{key}: context read-back needs applicable population/comparison/model/timepoint observations; source-explained N/A is allowed")
        for field, observed in observations.items():
            expected = label_lookup(fact["context"][field])
            # A known alternative exported context is not a free synonym. Inspect only
            # this same claim, not unrelated paragraphs or another study's vocabulary.
            alternatives = alternatives_by_field[field] if alternatives_by_field is not None else {
                label_lookup(other["context"][field]) for other in catalog.values()
                if not _not_applicable(other["context"][field])}
            expected_words = set(re.findall(r"\w+", expected.casefold()))
            # A broad exported label such as "adjusted model" is not contradictory
            # to "Cox model adjusted for age and sex". Subset labels remain a real
            # read-back question; do not force the full technical model into prose.
            # A scope's explicit subgroup title also controls a finding that does not
            # repeat its population in every sentence.
            attributed_text = quote + "\n" + "\n".join(re.findall(r"^\s{0,3}#{1,6}\s+(.+)$", scopes[0], re.M))
            foreign = [term for term in alternatives if _phrase(term, attributed_text) and
                       not set(re.findall(r"\w+", term.casefold())) <= expected_words]
            if foreign and not _phrase(expected, quote):
                raise ValueError(f"{key}: {field} text names another exported context {foreign[0]!r}; resolve the finding/text attribution")
            if isinstance(observed, str):
                if not observed.strip() or observed not in quote or not _phrase(expected, observed):
                    raise ValueError(f"{key}: {field} literal evidence does not align the current claim with source context {expected!r}")
                continue
            if not isinstance(observed, dict):
                raise ValueError(f"{key}: {field} needs literal evidence or a scoped executor read-back")
            mode = observed.get("mode")
            if mode in {"pending", "needs_review", "unknown"}:
                raise ValueError(f"{key}: {field} context remains pending; complete the existing executor/author scientific judgement")
            if mode == "not_applicable":
                if not _not_applicable(fact["context"][field]) or len(str(observed.get("reason", "")).strip()) < 30:
                    raise ValueError(f"{key}: {field} N/A must be explained by the actual analysis source")
                continue
            anchor = observed.get("quote", "")
            scope = observed.get("scope", "claim")
            if not isinstance(anchor, str) or not anchor.strip() or scope not in {"claim", "section"}:
                raise ValueError(f"{key}: {field} needs an exact current-context quote and claim/section scope")
            if scope == "claim":
                present = anchor in quote
            else:
                # A section anchor must actually precede or occur in this finding in
                # every matching scope; Abstract context cannot certify main Results.
                present = all(anchor in part[:part.rindex(quote) + len(quote)] for part in scopes)
            if not present:
                raise ValueError(f"{key}: {field} context anchor is absent, later than the finding or belongs to another section")
            if mode == "literal":
                if not _phrase(expected, anchor):
                    raise ValueError(f"{key}: {field} literal context differs from source {expected!r}")
            elif mode == "read_back":
                interpretation = str(observed.get("interpretation", "")).strip()
                reason = str(observed.get("reason", "")).strip()
                if (observed.get("reviewer") != "executor" or len(interpretation) < 30 or len(reason) < 60 or
                        interpretation.casefold() in {anchor.casefold(), expected.casefold()} or
                        reason.casefold() in {anchor.casefold(), expected.casefold(), interpretation.casefold()}):
                    raise ValueError(f"{key}: {field} needs an actual executor interpretation and source-based reasoning, not a copied field or PASS assertion")
            else:
                raise ValueError(f"{key}: {field} unsupported context observation mode; unresolved meaning stays pending")


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
        from .state import State, version_tuple
        state = State(project).load().data
        context_required = version_tuple(str(state.get("engine_pin", state.get("pipeline_version", "0")))) >= (1, 26, 0)
        percentage_required = version_tuple(str(state.get("pipeline_version", "0"))) >= (1, 16, 0)
        # Reuse the existing display vocabulary without rereading the plan for every
        # fact/claim/dimension. This does not cache validation across changed files.
        label_cache = {}
        def context_label(value):
            from .clinicalpresentation import label as clinical_label
            if value not in label_cache:
                label_cache[value] = clinical_label(value, project)
            return label_cache[value]
        covered = list(body)
        outline = _outline(body)
        used_spans = set()
        alternatives_by_field = None
        count = 0
        for row in rows:
            if row.get("path") != rel:
                continue
            quote = row.get("text", "")
            if not isinstance(quote, str) or not quote.strip() or quote not in body:
                raise ValueError("claim text is missing or changed; update the affected binding")
            floats, strings, p_values = claim_values({**row,"_project":project}, catalog, quote)
            current_context = context_required or row.get("context_evidence") is not None
            if current_context:
                start, end, scope = _locate_claim(body, quote, row, outline)
                if any(start < prior_end and prior_start < end for prior_start, prior_end in used_spans):
                    raise ValueError("duplicate/overlapping bindings target the same claim occurrence")
                if alternatives_by_field is None:
                    alternatives_by_field = {field: {context_label(fact["context"][field]) for fact in catalog.values()
                                                     if not _not_applicable(fact["context"][field])}
                                             for field in CONTEXT_KEYS}
                validate_context(project, rel, text, row, catalog, required=context_required,
                                 label_lookup=context_label, context_scope=scope,
                                 alternatives_by_field=alternatives_by_field)
                spans = [(start, end)]
            else:
                # Completed old projects retain their original rule; new/opt-in work
                # requires one actual occurrence and cannot swallow duplicates.
                spans = [(m.start(), m.end()) for m in re.finditer(re.escape(quote), body)]
            from .proportions import validate as validate_proportions
            proportion_errors=validate_proportions(row,catalog,quote,required=percentage_required)
            if proportion_errors: raise ValueError("; ".join(proportion_errors))
            bad = _offenders(quote, floats, strings, set(), p_values)
            if bad:
                raise ValueError(f"claim contains values absent from its own fact(s): {bad[:5]}")
            for start, end in spans:
                covered[start:end] = " " * (end-start)
                used_spans.add((start, end))
            count += 1
        if NUM_RE.search(_scrub("".join(covered))):
            raise ValueError("reported numeric text lacks a source-bound claim; bind each reported finding, not a whole section")
        if not count:
            raise ValueError("no result claims bound")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return [f"{rel}: {exc}"]
    return []


def table_unit_constants(project,path,sheet,cell,value):
    """Only a source-bound 'per N' unit in a real header/note, never result-cell amnesty."""
    if not re.search(r"\bper\s+[1-9]\d*",str(value),re.I): return set()
    from .packagefreeze import _safe_path
    from . import xlsxlite
    rel=path.relative_to(project).as_posix()
    rows=[r for r in bindings(project,rel) if r.get("path")==rel and r.get("sheet")==sheet and r.get("cell")==cell and r.get("kind")=="unit_scale"]
    if not rows: return set()
    if len(rows)!=1: raise ValueError("Duplicate unit-scale binding")
    row=rows[0]
    if row.get("text")!=str(value) or len(str(row.get("reason","")))<20: raise ValueError("Unit constant needs exact cell text and scientific unit rationale")
    book=xlsxlite.Workbook(path); sh=book.sheet(sheet)
    target=next(c for c in sh.cells if c.ref==cell)
    top=[c.row for c in sh.cells if book.border_of(c).top]
    bottom=[c.row for c in sh.cells if book.border_of(c).bottom]
    if not top or not bottom: raise ValueError("Unit constant needs a structured three-line table")
    header=max(r for r in bottom if r<max(bottom)) if len(set(bottom))>1 else min(top)
    if not (target.row<=header or target.row>max(bottom)): raise ValueError("Result-body cells cannot use a unit-constant exemption")
    source_rel,source=_safe_path(project,row.get("source_path",""))
    quote=row.get("source_quote","")
    if not source_rel.startswith(("01_protocol/","03_analysis/code/")) or not isinstance(quote,str) or len(quote)<20 or quote not in source.read_text(encoding="utf-8"):
        raise ValueError("Unit constant needs an exact source quote from the real protocol/producer")
    allowed=set(re.findall(r"\bper\s+([1-9]\d*(?:,\d{3})*)\b",str(value),re.I))
    source_units={v.replace(",","") for v in re.findall(r"\bper\s+([1-9]\d*(?:,\d{3})*)\b",quote,re.I)}
    normalized={v.replace(",","") for v in allowed}
    if not allowed or not normalized<=source_units: raise ValueError("Only explicit source-supported 'per N' unit scaling is permitted")
    from .checks.numbers import _scrub,NUM_RE
    remaining=re.sub(r"\bper\s+[1-9]\d*(?:,\d{3})*\b"," ",str(value),flags=re.I)
    if NUM_RE.search(_scrub(remaining)): raise ValueError("A unit binding cannot exempt other reported numbers, even if the value equals its unit scale")
    return allowed|normalized


def validate_tables(project, paths):
    from . import xlsxlite
    from .checks.numbers import _offenders, _scrub, NUM_RE
    from openpyxl import load_workbook
    from .state import State,version_tuple
    state=State(project).load().data
    strict=version_tuple(str(state.get("engine_pin",state.get("pipeline_version","0"))))>=(1,26,0)
    problems = []
    catalog = None
    for path in paths:
        rel = path.relative_to(project).as_posix()
        cells = [(s, c, v) for s, c, v in xlsxlite.numeric_cell_values(path) if NUM_RE.search(_scrub(str(v)))]
        if not cells:
            continue
        try:
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
                    if row.get("kind")=="unit_scale":
                        allowed=table_unit_constants(project,path,sheet,cell,value)
                        if _offenders(str(value),set(),set(),allowed): raise ValueError("Unit binding cannot hide additional result values")
                        continue
                    if catalog is None: catalog=facts(project)
                    labels = " ".join(str(workbook[sheet][c].value or "") for c in row.get("label_cells", []))
                    floats, strings, p_values = claim_values({**row,"_project":project}, catalog, labels + " " + str(value))
                    from .proportions import validate as validate_proportions,table_percentage_text
                    header=workbook[sheet].cell(2,workbook[sheet][cell].column).value
                    shown=table_percentage_text(value,header)
                    issues=validate_proportions(row,catalog,shown,required=strict or bool(row.get("proportions")))
                    if issues: raise ValueError(f"{sheet}!{cell}: "+"; ".join(issues))
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
    original=json.loads(source.read_text(encoding="utf-8"))
    external=[{**r,"path":r["path"].replace("07_manuscript/","08_submission/integration/",1)}
              for r in original.get("source_claims",[]) if r.get("path")=="07_manuscript/full_manuscript.md"]
    atomic_json(destination, {"schema_version": 1, "claims": rows,"source_claims":external})


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
            current = row.get("context_evidence") is not None
            key = json.dumps([row["text"], row.get("fact_ids"),
                              row.get("path") if current else None,
                              row.get("section") if current else None,
                              row.get("occurrence") if current else None], sort_keys=True)
            if key not in seen:
                derived = {**row, "path": "07_manuscript/full_manuscript.md"}
                if current:
                    chapter = "Results" if row["path"].endswith("results.md") else "Abstract"
                    section = row.get("section", [])
                    derived["section"] = section if section and section[0] == chapter else [chapter] + section
                assembled.append(derived)
                seen.add(key)
    external=[r for r in payload.get("source_claims",[]) if r.get("path")!="07_manuscript/full_manuscript.md"]
    derived=[{**r,"path":"07_manuscript/full_manuscript.md"} for r in external if r.get("text") and r["text"] in text]
    return {**payload,"schema_version": 1, "claims": original + assembled,"source_claims":external+derived}
