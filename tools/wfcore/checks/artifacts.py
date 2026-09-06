"""Artifact-plan, table and figure structural checks."""
from __future__ import annotations

import json
import re

from .. import xlsxlite
from . import Ctx, Result, check

PLAN = "01_protocol/artifact_plan.json"
LEGENDS = "05_figures/legends.md"
CAPTIONS = "04_tables/table_captions.md"
QC = "05_figures/qc/qc_report.json"

ART_CITE_RE = re.compile(
    r"\b(?:(supplementary|supplemental|suppl\.?)\s+)?(figure|fig\.?|table)\s*(S?\d+)",
    re.I,
)
FENCE_RE = re.compile(r"```.*?```", re.S)
GROUPS = ("main_figures", "main_tables", "supp_figures", "supp_tables")
RESULT_CLAIM_RE = re.compile(
    r"\b(?:(?:was|were|is|are|remained)\s+(?:significantly\s+|independently\s+)?"
    r"(?:higher|lower|greater|smaller|increased|decreased|reduced|improved|worse|better|"
    r"associated\s+with|correlated\s+with|unchanged)|"
    r"(?:significantly\s+(?:higher|lower|greater|smaller|increased|decreased|differed))|"
    r"(?:demonstrated|showed)\s+(?:an?\s+)?(?:significant\s+)?(?:increase|decrease|improvement))\b",
    re.I,
)
RESULT_ESTIMATE_RE = re.compile(
    r"\b(?:HR|OR|RR|IRR|SMD|MD|AUC|(?i:beta|coefficient))\s*(?:=|:)?\s*-?\d",
)
ABBREVIATION_LABEL_RE = re.compile(
    r"\bAbbreviations?\s*:[ \t]*([^\r\n]*(?:\n(?!\s*\n|\s*#|\s*(?:Figure|Table)\b)[^\r\n]+)*)",
    re.I,
)
DEFINITION_RE = re.compile(r"(?:^|;|\n)\s*(?:[-*]\s+)?([A-Za-z][A-Za-z0-9-]{1,24})\s*[,=:]\s*([^;\n]+)")


def abbreviation_definitions(text: str) -> dict[str, str]:
    """Read declared acronym/expansion pairs, including eGFR and HbA1c, not all capitals."""
    return {m.group(1): m.group(2).strip().rstrip(".")
            for m in DEFINITION_RE.finditer(text)
            if any(ch.isupper() for ch in m.group(1)) and m.group(2).strip().rstrip(".")}


def central_abbreviations(text: str) -> dict[str, str]:
    declarations = re.search(r"(?ms)^#\s+Declarations and Statements\s*$\n(.*?)(?=^#\s+|\Z)", text)
    if declarations is None:
        return {}
    match = re.search(r"(?ms)^##\s+Abbreviations\s*$\n(.*?)(?=^##\s+|\Z)", declarations.group(1))
    return abbreviation_definitions(match.group(1)) if match else {}


def _plan(ctx: Ctx) -> dict:
    return ctx.read_json(PLAN)


def _entries(plan: dict, groups=GROUPS) -> list[dict]:
    out = []
    for g in groups:
        for e in plan.get(g, []):
            e = dict(e)
            e["_group"] = g
            out.append(e)
    return out


def _canon(kind: str, num: str, supp: bool) -> str:
    kind = "Figure" if kind.lower().startswith("fig") else "Table"
    num = num.upper().lstrip("S")
    return f"{kind} {'S' if supp else ''}{num}"


def _plan_ids(plan: dict) -> set[str]:
    ids = set()
    for e in _entries(plan):
        supp = e["_group"].startswith("supp")
        m = re.search(r"(fig\w*|table)\s*(S?\d+)", str(e.get("id", "")), re.I)
        if m:
            ids.add(_canon(m.group(1), m.group(2), supp))
    return ids


# ---------------------------------------------------------------------------
@check("artifact_plan_sane")
def artifact_plan_sane(ctx: Ctx) -> Result:
    rel = ctx.spec.get("path", PLAN)
    if not ctx.p(rel).exists():
        return Result(False, "artifact_plan_sane", f"{rel} missing")
    try:
        plan = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "artifact_plan_sane", f"{rel} invalid JSON: {exc}")

    problems: list[str] = []
    max_fig = ctx.target("main_figures_max", 6)
    max_tab = ctx.target("main_tables_max", 5)
    if len(plan.get("main_figures", [])) > max_fig:
        problems.append(f"{len(plan['main_figures'])} main figures, cap {max_fig}")
    if len(plan.get("main_tables", [])) > max_tab:
        problems.append(f"{len(plan['main_tables'])} main tables, cap {max_tab}")
    if not plan.get("main_figures") and not plan.get("main_tables"):
        problems.append("no main display items planned")

    seen: set[str] = set()
    for e in _entries(plan):
        eid = str(e.get("id", "")).strip()
        tag = f"{e['_group']}:{eid or '<no id>'}"
        if not eid:
            problems.append(f"{e['_group']}: entry without an id")
            continue
        if eid in seen:
            problems.append(f"duplicate id {eid}")
        seen.add(eid)
        for field in ("title", "content", "source_results"):
            if not e.get(field):
                problems.append(f"{tag}: missing '{field}'")
        if not e.get("file"):
            problems.append(f"{tag}: missing 'file'")
        if e["_group"].endswith("figures"):
            if e.get("width") not in ("single", "double", "1.5"):
                problems.append(f"{tag}: width must be single | 1.5 | double")
            if not e.get("script"):
                problems.append(f"{tag}: missing 'script'")
            arch = e.get("archetype")
            if not arch:
                problems.append(f"{tag}: missing 'archetype' (see reference/archetypes.toml)")
            elif arch not in _known_archetypes():
                problems.append(f"{tag}: archetype '{arch}' is not in reference/archetypes.toml")
            elif arch == "other" and not e.get("archetype_rationale"):
                problems.append(f"{tag}: archetype 'other' requires 'archetype_rationale'")

    # supplementary tables share one workbook, distinct sheets
    supp = plan.get("supp_tables", [])
    files = {e.get("file") for e in supp if e.get("file")}
    if len(files) > 1:
        problems.append(f"supplementary tables spread over {len(files)} files; must be one workbook")
    sheets = [e.get("sheet") for e in supp]
    if len(sheets) != len(set(sheets)):
        problems.append("supplementary table sheet names are not unique")
    # main tables: one file each
    mfiles = [e.get("file") for e in plan.get("main_tables", [])]
    if len(mfiles) != len(set(mfiles)):
        problems.append("main tables must each live in their own xlsx file")

    # numbering must be 1..N with no gaps
    for group, prefix in (("main_figures", "Figure"), ("main_tables", "Table"),
                          ("supp_figures", "Figure S"), ("supp_tables", "Table S")):
        nums = []
        for e in plan.get(group, []):
            m = re.search(r"(\d+)\s*$", str(e.get("id", "")))
            if m:
                nums.append(int(m.group(1)))
        if nums and sorted(nums) != list(range(1, len(nums) + 1)):
            problems.append(f"{group}: numbering is not {prefix}1..{prefix}{len(nums)} (got {sorted(nums)})")

    if problems:
        return Result(False, "artifact_plan_sane", "; ".join(problems[:10]))
    n = len(_entries(plan))
    return Result(True, "artifact_plan_sane", f"{n} display item(s) planned, ids and files consistent")


@check("legends_cover_plan")
def legends_cover_plan(ctx: Ctx) -> Result:
    for rel in (PLAN, LEGENDS, CAPTIONS):
        if not ctx.p(rel).exists():
            return Result(False, "legends_cover_plan", f"{rel} missing")
    plan = _plan(ctx)
    problems: list[str] = []

    for rel, groups, minlen, what in (
        (LEGENDS, ("main_figures", "supp_figures"), 40, "figure legend"),
        (CAPTIONS, ("main_tables", "supp_tables"), 40, "table caption"),
    ):
        text = ctx.read(rel)
        blocks = _split_blocks(text)
        if rel == LEGENDS:
            section_count = len(re.findall(r"(?mi)^#\s+Figure legends\s*$", text))
            if section_count != 1:
                problems.append(
                    f"{rel}: expected exactly one '# Figure legends' heading, found {section_count}"
                )
            matches = list(re.finditer(
                r"(?mi)^#{2,6}\s+(Figure\s+S?\d+)\.?\s*(.*)$", text))
            canon = [re.sub(r"\s+", " ", match.group(1)).casefold() for match in matches]
            duplicates = sorted({item for item in canon if canon.count(item) > 1})
            if duplicates:
                problems.append(f"{rel}: duplicate figure legend heading(s): " +
                                ", ".join(duplicates))
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                body_lines = [line.strip() for line in text[match.end():end].splitlines()
                              if line.strip()]
                if body_lines and re.match(
                        rf"^{re.escape(match.group(1))}\b", body_lines[0], re.I):
                    problems.append(
                        f"{rel}: {match.group(1)} is repeated at the start of its legend body"
                    )
        for e in _entries(plan, groups):
            eid = str(e.get("id", "")).strip()
            key = next((k for k in blocks if _same_id(k, eid)), None)
            if key is None:
                problems.append(f"{rel}: no {what} for {eid}")
            elif len(blocks[key].strip()) < minlen:
                problems.append(f"{rel}: {what} for {eid} is only {len(blocks[key].strip())} chars")
            elif rel == LEGENDS:
                words = len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", blocks[key]))
                cap = int(ctx.target("figure_legend_words_max", 180))
                if words > cap:
                    problems.append(f"{rel}: {what} for {eid} is {words} words (maximum {cap})")
        if rel == CAPTIONS and "abbrevi" not in text.lower() and "footnote" not in text.lower():
            problems.append(f"{rel}: no footnote/abbreviation block anywhere - three-line tables need one")

    if problems:
        return Result(
            False,
            "legends_cover_plan",
            "; ".join(problems[:8]),
            ["Every planned display item needs a concise, self-contained legend written before the figure is drawn."],
        )
    return Result(True, "legends_cover_plan", "every planned display item has a concise substantive legend/caption")


@check("legend_no_results_restatement")
def legend_no_results_restatement(ctx: Ctx) -> Result:
    rel = ctx.spec.get("path", LEGENDS)
    if not ctx.p(rel).is_file():
        return Result(False, "legend_no_results_restatement", f"{rel} missing")
    value = ctx.read(rel)
    section = re.search(r"(?ms)^#\s+Figure legends\s*$\n(.*?)(?=^#\s+|\Z)", value)
    if section:
        value = section.group(1)
    elif rel != LEGENDS:
        return Result(False, "legend_no_results_restatement", f"{rel}: Figure legends section absent")
    blocks = {key: content for key, content in _split_blocks(value).items()
              if re.match(r"(?:supplementary\s+)?fig", key, re.I)}
    if not blocks:
        if ctx.p(PLAN).is_file() and not _entries(_plan(ctx), ("main_figures", "supp_figures")):
            return Result(True, "legend_no_results_restatement", "no figures planned")
        return Result(False, "legend_no_results_restatement", f"{rel}: no figure legend blocks")
    problems = []
    for figure_id, content in blocks.items():
        body = ABBREVIATION_LABEL_RE.sub(" ", content)
        if RESULT_CLAIM_RE.search(body):
            problems.append(f"{figure_id}: contains a directional/comparative result claim")
        # Reference/null values decode the axes; they are not observed study estimates.
        estimate_body = re.sub(
            r"\b(?i:reference|null|no-effect)\b[^\n.!?]{0,60}\b(?:HR|OR|RR|IRR)\s*[=:]?\s*1(?:\.0+)?(?![\d.])",
            " ", body,
        )
        estimate_body = re.sub(
            r"\b(?i:chance|reference)\b[^\n.!?]{0,60}\bAUC\s*[=:]?\s*0\.50*(?!\d)",
            " ", estimate_body,
        )
        if RESULT_ESTIMATE_RE.search(estimate_body):
            problems.append(f"{figure_id}: repeats a numerical result estimate")
    if problems:
        return Result(False, "legend_no_results_restatement", "; ".join(problems[:8]),
                      ["Keep only the descriptive title, panel map, encodings, symbols, and essential decoding definitions."])
    return Result(True, "legend_no_results_restatement",
                  f"{len(blocks)} legend(s) have no obvious result claims; semantic review remains required")


def _display_sources(ctx: Ctx) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for rel in (LEGENDS, CAPTIONS):
        if ctx.p(rel).is_file():
            sources.append((rel, ctx.read(rel)))
    for path in ctx.glob("04_tables/main/*.xlsx") + ctx.glob("04_tables/supplementary/*.xlsx"):
        try:
            wb = xlsxlite.Workbook(path)
        except Exception:  # noqa: BLE001 - the table gates report malformed workbooks
            continue
        value = "\n".join(text for sheet in wb.sheets for text in sheet.values())
        sources.append((path.relative_to(ctx.project).as_posix(), value))
    return sources


@check("abbreviations_centralized")
def abbreviations_centralized(ctx: Ctx) -> Result:
    """Move a crowded display-item abbreviation list into Declarations and Statements."""
    sources = _display_sources(ctx)
    local_labels = sorted({rel for rel, value in sources if ABBREVIATION_LABEL_RE.search(value)})
    local_defs = {term: expansion for _, value in sources
                  for match in ABBREVIATION_LABEL_RE.finditer(value)
                  for term, expansion in abbreviation_definitions(match.group(1)).items()}
    largest_list = max((len(match.group(1).split()) for _, value in sources
                        for match in ABBREVIATION_LABEL_RE.finditer(value)), default=0)
    threshold = int(ctx.target("abbreviation_centralize_threshold", 8))
    word_threshold = int(ctx.target("abbreviation_local_words_max", 50))

    target = {}
    if ctx.p("08_submission/target_journal.json").is_file():
        try:
            target = ctx.read_json("08_submission/target_journal.json")
        except json.JSONDecodeError:
            target = {}
    placement = str(target.get("abbreviation_placement", "central")).strip().lower()
    if placement == "local_required":
        source = str(target.get("abbreviation_rule_source", "")).strip()
        guide = str(target.get("guidelines_url", "")).strip()
        if not guide or guide not in source:
            return Result(False, "abbreviations_centralized",
                          "local_required override lacks the exact official guidelines URL")
        return Result(True, "abbreviations_centralized",
                      "journal-mandated local abbreviation definitions retained with source")
    if placement != "central":
        return Result(False, "abbreviations_centralized",
                      "abbreviation_placement must be central or local_required")

    statements_rel = "07_manuscript/statements.md"
    statements = ctx.read(statements_rel) if ctx.p(statements_rel).is_file() else ""
    full = ctx.read("07_manuscript/full_manuscript.md") if ctx.p("07_manuscript/full_manuscript.md").is_file() else ""
    central_defs = central_abbreviations(full or statements)
    central_present = bool(central_defs)
    problems: list[str] = []
    acronyms = set(local_defs) | set(central_defs)
    refers_to_central = any(re.search(r"abbreviations[^\n]*Declarations and Statements", value, re.I)
                           for _, value in sources)
    needs_central = len(acronyms) > threshold or largest_list > word_threshold or refers_to_central
    if needs_central:
        if not re.search(r"(?mi)^#\s+Declarations and Statements\s*$", full or statements):
            problems.append("many display abbreviations require '# Declarations and Statements'")
        if not central_present:
            problems.append("many display abbreviations require a '## Abbreviations' master list")
        missing = sorted(set(local_defs) - set(central_defs))
        if central_present and missing:
            problems.append("master list lacks: " + ", ".join(missing[:12]))
        if local_labels:
            problems.append("remove repeated local Abbreviations blocks from: " + ", ".join(local_labels[:6]))
        if not central_abbreviations(full):
            problems.append("full manuscript lacks the centralized Declarations and Statements/Abbreviations section")
    elif central_present and local_labels:
        problems.append("abbreviations are duplicated centrally and in individual figures/tables")
    if problems:
        return Result(False, "abbreviations_centralized", "; ".join(problems[:8]))
    if needs_central:
        return Result(True, "abbreviations_centralized",
                      f"{len(acronyms)} display abbreviations are defined once in Declarations and Statements")
    return Result(True, "abbreviations_centralized",
                  f"{len(acronyms)} display abbreviation(s); centralization threshold is {threshold}")


@check("artifact_refs_consistent")
def artifact_refs_consistent(ctx: Ctx) -> Result:
    if not ctx.p(PLAN).exists():
        return Result(False, "artifact_refs_consistent", f"{PLAN} missing")
    plan = _plan(ctx)
    planned = _plan_ids(plan)
    cited: set[str] = set()
    scanned = []
    for rel in ctx.spec.get("paths", []):
        if not ctx.p(rel).exists():
            continue
        scanned.append(rel)
        text = FENCE_RE.sub(" ", ctx.read(rel))
        for supp, kind, num in ART_CITE_RE.findall(text):
            cited.add(_canon(kind, num, bool(supp) or num.upper().startswith("S")))
    if not scanned:
        return Result(False, "artifact_refs_consistent", "no manuscript files to scan")

    problems = []
    ghosts = sorted(cited - planned)
    if ghosts:
        problems.append(f"cited but not planned: {', '.join(ghosts)}")
    if ctx.spec.get("require_all_cited"):
        orphans = sorted(planned - cited)
        if orphans:
            problems.append(f"planned but never cited: {', '.join(orphans)}")
    if ctx.spec.get("require_rendered"):
        for e in _entries(plan):
            f = e.get("file")
            if f and not ctx.p(f).exists():
                problems.append(f"{e.get('id')}: {f} not rendered")
    if problems:
        return Result(
            False,
            "artifact_refs_consistent",
            "; ".join(problems[:8]),
            ["Text and artifact plan must agree exactly. Fix whichever is wrong; do not silently renumber."],
        )
    return Result(
        True,
        "artifact_refs_consistent",
        f"{len(cited)} artifact citation(s) across {len(scanned)} file(s) all match the plan",
    )


# ---------------------------------------------------------------------------
@check("tables_match_plan")
def tables_match_plan(ctx: Ctx) -> Result:
    plan = _plan(ctx)
    problems = []
    for e in _entries(plan, ("main_tables", "supp_tables")):
        f = e.get("file")
        if not f:
            continue
        p = ctx.p(f)
        if not p.exists():
            problems.append(f"{e.get('id')}: {f} not built")
            continue
        sheet = e.get("sheet")
        if sheet:
            try:
                wb = xlsxlite.Workbook(p)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{f} unreadable: {exc}")
                continue
            if wb.sheet(sheet) is None:
                problems.append(f"{f}: sheet '{sheet}' absent (has: {[s.name for s in wb.sheets]})")
    if problems:
        return Result(False, "tables_match_plan", "; ".join(problems[:8]))
    n = len(_entries(plan, ("main_tables", "supp_tables")))
    return Result(True, "tables_match_plan", f"{n} planned table(s) built at the planned locations")


@check("tables_threeline")
def tables_threeline(ctx: Ctx) -> Result:
    files = ctx.glob("04_tables/main/*.xlsx") + ctx.glob("04_tables/supplementary/*.xlsx")
    if not files:
        return Result(False, "tables_threeline", "no xlsx tables found under 04_tables/")
    problems: list[str] = []
    checked = 0
    for p in files:
        try:
            wb = xlsxlite.Workbook(p)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{p.name}: unreadable ({exc})")
            continue
        for sh in wb.sheets:
            checked += 1
            problems.extend(f"{p.name}[{sh.name}] {msg}" for msg in _audit_sheet(wb, sh))
    if problems:
        return Result(
            False,
            "tables_threeline",
            f"{len(problems)} defect(s): " + "; ".join(problems[:8]),
            [
                "Build tables with tools/tables/threeline.py, which enforces the rules automatically.",
                "Three-line = rule above header, rule below header, rule below last data row. Nothing else.",
            ],
        )
    return Result(True, "tables_threeline", f"{checked} sheet(s) conform to three-line format")


def _audit_sheet(wb: xlsxlite.Workbook, sh: xlsxlite.Sheet) -> list[str]:
    out: list[str] = []
    if sh.max_row == 0:
        return ["is empty"]

    rows = {}
    for r in range(1, sh.max_row + 1):
        cells = sh.row_cells(r)
        specs = [wb.border_of(c) for c in cells]
        rows[r] = {
            "text": " ".join(c.value or "" for c in cells).strip(),
            "top": any(s.top for s in specs),
            "bottom": any(s.bottom for s in specs),
            "vert": any(s.left or s.right for s in specs),
        }

    title = rows[1]["text"]
    if not title:
        out.append("row 1 must hold the table title")
    elif len(title) > 250:
        out.append(f"title is {len(title)} chars - too long for a table title")
    if rows[1]["top"] or rows[1]["bottom"]:
        out.append("title row must not be ruled")

    ruled = [r for r, v in rows.items() if v["top"] or v["bottom"]]
    if not ruled:
        return out + ["no horizontal rules at all - not a three-line table"]

    header = min(ruled)
    last_ruled = max(ruled)
    if not (rows[header]["top"] and rows[header]["bottom"]):
        out.append(f"header row {header} needs a rule above and below")
    if not rows[last_ruled]["bottom"]:
        out.append(f"bottom rule missing (row {last_ruled})")
    interior = [r for r in ruled if header < r < last_ruled]
    if interior:
        out.append(f"interior rule(s) at row(s) {interior} - only three rules allowed")
    if any(v["vert"] for v in rows.values()):
        out.append("vertical rules present")

    body_rows = [r for r in range(header + 1, last_ruled + 1) if rows[r]["text"]]
    if not body_rows:
        out.append("no data rows between the rules")
    footnotes = [r for r in range(last_ruled + 1, sh.max_row + 1) if rows[r]["text"]]
    if not footnotes:
        out.append("no footnote row beneath the bottom rule")
    else:
        total = sum(len(rows[r]["text"]) for r in footnotes)
        if total > 1500:
            out.append(f"footnotes are {total} chars - that is an analysis report, not a table footnote")

    for c in sh.cells:
        if c.value and len(c.value) > 300:
            out.append(f"cell {c.ref} holds {len(c.value)} chars of prose")
            break
    return out


# ---------------------------------------------------------------------------
@check("figures_match_plan")
def figures_match_plan(ctx: Ctx) -> Result:
    plan = _plan(ctx)
    problems = []
    entries = _entries(plan, ("main_figures", "supp_figures"))
    for e in entries:
        for key, what in (("file", "preview"), ("script", "plot script")):
            v = e.get(key)
            if v and not ctx.p(v).exists():
                problems.append(f"{e.get('id')}: {what} {v} missing")
        tiff = e.get("tiff")
        if tiff and not ctx.p(tiff).exists():
            problems.append(f"{e.get('id')}: print master {tiff} missing")
        elif not tiff:
            problems.append(f"{e.get('id')}: no 'tiff' print master declared")
    if problems:
        return Result(False, "figures_match_plan", "; ".join(problems[:8]))
    return Result(True, "figures_match_plan", f"{len(entries)} figure(s) rendered with print masters")


@check("figures_qc_pass")
def figures_qc_pass(ctx: Ctx) -> Result:
    if not ctx.p(QC).exists():
        return Result(
            False,
            "figures_qc_pass",
            f"{QC} missing",
            ["Run: .venv/Scripts/python.exe tools/figures/qc.py --all  (writes the QC report)"],
        )
    try:
        rep = ctx.read_json(QC)
    except json.JSONDecodeError as exc:
        return Result(False, "figures_qc_pass", f"{QC} invalid JSON: {exc}")
    figs = {str(f.get("id")): f for f in rep.get("figures", [])}
    plan = _plan(ctx)
    problems = []
    for e in _entries(plan, ("main_figures", "supp_figures")):
        eid = str(e.get("id"))
        f = figs.get(eid)
        if f is None:
            problems.append(f"{eid}: no QC entry")
            continue
        failed = [c.get("name") for c in f.get("checks", []) if not c.get("ok")]
        if failed:
            problems.append(f"{eid}: failing {', '.join(failed)}")
        if not f.get("visual_reviewed"):
            problems.append(f"{eid}: never visually reviewed (deterministic QC alone is not enough)")
    if problems:
        return Result(
            False,
            "figures_qc_pass",
            "; ".join(problems[:8]),
            [
                "Fix the plotting code, re-render, re-run QC, then open the PNG and look at it.",
                "Set visual_reviewed only after the rendered PNG was actually inspected.",
            ],
        )
    return Result(True, "figures_qc_pass", f"{len(figs)} figure(s) pass QC and were visually reviewed")


@check("bundle_complete")
def bundle_complete(ctx: Ctx) -> Result:
    rel = "08_submission/bundle/manifest.json"
    if not ctx.p(rel).exists():
        return Result(False, "bundle_complete", f"{rel} missing")
    try:
        man = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "bundle_complete", f"{rel} invalid JSON: {exc}")
    items = man.get("items", [])
    problems = []
    roles = {str(i.get("role", "")).lower() for i in items}
    for need in ("title_page", "manuscript", "cover_letter", "figures", "tables", "checklist"):
        if need not in roles:
            problems.append(f"no bundle item with role '{need}'")
    listed = set()
    for i in items:
        f = i.get("file")
        if not f:
            problems.append(f"item {i.get('role')} has no file")
            continue
        listed.add(f)
        if not ctx.p(f).exists():
            problems.append(f"{f} listed but absent")
        if not i.get("required_by"):
            problems.append(f"{f}: no 'required_by' reference to the journal guideline")
    on_disk = {
        p.relative_to(ctx.project).as_posix()
        for p in (ctx.project / "08_submission/bundle").rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    stray = sorted(on_disk - listed)
    if stray:
        problems.append(f"{len(stray)} file(s) in the bundle are not in the manifest: {', '.join(stray[:5])}")
    if problems:
        return Result(False, "bundle_complete", "; ".join(problems[:8]))
    return Result(True, "bundle_complete", f"{len(items)} bundle item(s), each present and traced to a guideline rule")


@check("bundle_matches_freeze")
def bundle_matches_freeze(ctx: Ctx) -> Result:
    from ..packagefreeze import verify_freeze

    ok, problems, count = verify_freeze(ctx.project)
    if not ok:
        return Result(
            False,
            "bundle_matches_freeze",
            "; ".join(problems[:10]),
            [
                "Do not audit a package different from the one the user approved.",
                "Return to S24, reconcile the changes, ask the user to confirm OK again, then create a new freeze.",
            ],
        )
    return Result(True, "bundle_matches_freeze", f"{count} approved package/evidence file(s) unchanged")


@check("submission_audit_matches_freeze")
def submission_audit_matches_freeze(ctx: Ctx) -> Result:
    freeze_rel = "08_submission/package_review_freeze.json"
    audit_rel = ctx.spec.get("path", "08_submission/independent_submission_audit.md")
    try:
        freeze = ctx.read_json(freeze_rel)
        audit = ctx.read(audit_rel)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return Result(False, "submission_audit_matches_freeze", f"audit/freeze unreadable: {exc}")
    freeze_id = str(freeze.get("freeze_id", "")).strip()
    if len(freeze_id) != 64 or freeze_id not in audit:
        return Result(
            False,
            "submission_audit_matches_freeze",
            "independent audit does not identify the exact current freeze_id",
            ["Put `Freeze ID: <freeze_id>` under the audit Verdict heading after reviewing that frozen package."],
        )
    return Result(True, "submission_audit_matches_freeze", f"audit identifies freeze {freeze_id[:12]}...")


# ---------------------------------------------------------------------------
def _known_archetypes() -> set[str]:
    import tomllib
    from .. import paths
    p = paths.reference_dir() / "archetypes.toml"
    if not p.exists():
        return set()
    try:
        return set(tomllib.loads(p.read_text(encoding="utf-8")).get("archetype", {}))
    except tomllib.TOMLDecodeError:
        return set()


def _split_blocks(text: str) -> dict[str, str]:
    """Split legends/captions on headings or leading bold/plain 'Figure N.' labels."""
    blocks: dict[str, str] = {}
    pattern = re.compile(
        r"^\s{0,3}(?:#{1,6}\s*)?\**\s*((?:supplementary\s+)?(?:figure|fig\.?|table)\s*S?\d+)\b[.:)]?\**",
        re.I | re.M,
    )
    marks = list(pattern.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        blocks[m.group(1)] = text[m.end():end]
    return blocks


def _same_id(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower()).replace("figure", "fig")  # noqa: E731
    return norm(a) == norm(b)

