"""Canonical manuscript and submission-DOCX checks (stdlib only)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from . import Ctx, Result, check


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "rel": PKG_REL}
TEXT_ROLES = {"manuscript", "title_page", "cover_letter", "supplementary",
              "statements", "figure_legends"}
FORBIDDEN_PARAGRAPH_CONTROLS = (
    "outlineLvl", "keepNext", "keepLines", "pageBreakBefore",
)
THEMATIC_BREAK_RE = re.compile(
    r"(?m)^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})\s*$"
)
PIPE_TABLE_DIVIDER_RE = re.compile(
    r"(?m)^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)


def _h1s(text: str) -> list[tuple[str, int]]:
    return [(m.group(1).strip(), m.start())
            for m in re.finditer(r"(?m)^#\s+([^#\n].*)$", text)]


def _figure_ids(ctx: Ctx) -> list[str] | None:
    path = ctx.p("01_protocol/artifact_plan.json")
    if not path.is_file():
        return None
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return [str(item.get("id", "")).strip()
            for group in ("main_figures", "supp_figures")
            for item in plan.get(group, []) if str(item.get("id", "")).strip()]


def _canon_figure_id(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().rstrip(".")).casefold()


def _markdown_legend_problems(text: str, expected: list[str], cap: int) -> list[str]:
    section = re.search(r"(?ms)^#\s+Figure legends\s*$\n?(.*)\Z", text)
    if section is None:
        return ["Figure legends section cannot be parsed"]
    body = section.group(1)
    matches = list(re.finditer(r"(?mi)^#{2,6}\s+(Figure\s+S?\d+)\.?\s*(.*)$", body))
    blocks: dict[str, tuple[int, int]] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = (match.group(2) + "\n" + body[match.end():end]).strip()
        blocks[_canon_figure_id(match.group(1))] = (
            len(content), len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", content)))
    wanted = {_canon_figure_id(x): x for x in expected}
    problems: list[str] = []
    seen = [_canon_figure_id(match.group(1)) for match in matches]
    duplicates = sorted({item for item in seen if seen.count(item) > 1})
    if duplicates:
        problems.append("duplicate figure legend heading(s): " + ", ".join(duplicates))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        body_lines = [line.strip() for line in body[match.end():end].splitlines()
                      if line.strip()]
        if body_lines and re.match(rf"^{re.escape(match.group(1))}\b", body_lines[0], re.I):
            problems.append(f"{match.group(1)} is repeated at the start of its legend body")
    for key, display in wanted.items():
        if key not in blocks:
            problems.append(f"Figure legends lacks {display}")
            continue
        chars, words = blocks[key]
        if chars < 40:
            problems.append(f"{display} legend is only {chars} characters")
        if words > cap:
            problems.append(f"{display} legend is {words} words (maximum {cap})")
    extras = sorted(set(blocks) - set(wanted))
    if extras:
        problems.append("unplanned figure legend(s): " + ", ".join(extras))
    return problems


@check("supplementary_methods_clean")
def supplementary_methods_clean(ctx: Ctx) -> Result:
    """Supplementary Methods is prose; display tables live in the table workbook."""
    rel = ctx.spec.get("path", "07_manuscript/supplementary_methods.md")
    if not ctx.p(rel).is_file():
        return Result(True, "supplementary_methods_clean", "no supplementary Methods file")
    text = ctx.read(rel)
    problems = []
    if (PIPE_TABLE_DIVIDER_RE.search(text) or
            re.search(r"<table\b", text, re.I | re.S) or
            re.search(r"^\s*\+[=-]{3,}(?:\+[=-]{3,})+\+\s*$", text, re.M)):
        problems.append("contains an embedded Markdown/HTML/grid table")
    if THEMATIC_BREAK_RE.search(text):
        problems.append("contains a Markdown thematic break/horizontal rule")
    if problems:
        return Result(
            False,
            "supplementary_methods_clean",
            f"{rel}: " + "; ".join(problems),
            [
                "Move tabular material into artifact_plan.json as Table S*, build it under "
                "04_tables/supplementary/ with tools/tables/threeline.py, and cite that table from prose.",
                "Use blank paragraphs, not '---', '***' or '___', to separate supplementary Methods text.",
            ],
        )
    return Result(True, "supplementary_methods_clean",
                  "supplementary Methods contains prose only; no table or horizontal-rule residue")


@check("manuscript_structure")
def manuscript_structure(ctx: Ctx) -> Result:
    rel = "07_manuscript/full_manuscript.md"
    if not ctx.p(rel).is_file():
        return Result(False, "manuscript_structure", f"{rel} missing")
    text = ctx.read(rel)
    heads = _h1s(text)
    problems: list[str] = []
    if not heads:
        return Result(False, "manuscript_structure", "no level-1 headings found")
    expected = ["abstract", "introduction", "methods", "results", "discussion",
                "references", "figure legends"]
    positions: dict[str, int] = {}
    for name in expected:
        matches = [pos for heading, pos in heads if heading.casefold() == name]
        if len(matches) != 1:
            problems.append(f"expected exactly one '# {name.title()}', found {len(matches)}")
        else:
            positions[name] = matches[0]
    if len(positions) == len(expected):
        seq = [positions[x] for x in expected]
        if seq != sorted(seq):
            problems.append("section order must be Abstract, Introduction, Methods, Results, Discussion, References, Figure legends")
        if heads[-1][0].casefold() != "figure legends":
            problems.append("Figure legends must be the final level-1 section")
    declarations = [pos for heading, pos in heads
                    if heading.casefold() == "declarations and statements"]
    if len(declarations) > 1:
        problems.append("expected at most one '# Declarations and Statements'")
    elif declarations and "discussion" in positions and "references" in positions and not (
            positions["discussion"] < declarations[0] < positions["references"]):
        problems.append("Declarations and Statements must be between Discussion and References")
    title = heads[0][0]
    if title.casefold() in expected or len(re.findall(r"[A-Za-z][A-Za-z'-]*", title)) < 5:
        problems.append("the first level-1 heading is not a substantive selected title")
    title_file = ctx.p("07_manuscript/title.md")
    if title_file.exists():
        chosen = re.sub(r"(?m)^#\s+", "", title_file.read_text(encoding="utf-8").strip(), count=1).strip()
        if chosen != title:
            problems.append("full manuscript title differs from title.md")
    if "abstract" in positions and "introduction" in positions:
        between = text[positions["abstract"]:positions["introduction"]]
        lines = [ln.strip() for ln in between.splitlines() if re.match(r"^Keywords\s*:", ln, re.I)]
        if len(lines) != 1:
            problems.append(f"expected one Keywords line after Abstract, found {len(lines)}")
        else:
            payload = re.sub(r"^Keywords\s*:\s*", "", lines[0], flags=re.I)
            if any(ch in payload for ch in "/;&"):
                problems.append("Keywords must use commas only; '/', ';' and '&' are forbidden")
            terms = [x.strip() for x in payload.split(",") if x.strip()]
            if not 3 <= len(terms) <= 6:
                problems.append(f"Keywords must contain 3-6 terms, found {len(terms)}")
            if len({x.casefold() for x in terms}) != len(terms):
                problems.append("Keywords contain duplicates")
    if "references" in positions:
        ref_block_end = positions.get("figure legends", len(text))
        ref_block = text[positions["references"]:ref_block_end]
        if "{#refs}" not in ref_block and not re.search(r"(?m)^\s*\d+[.)]\s+", ref_block):
            problems.append("References section has neither a Pandoc refs placeholder nor a rendered list")
    planned = _figure_ids(ctx)
    if planned is None:
        problems.append("01_protocol/artifact_plan.json is missing or invalid")
    elif "figure legends" in positions:
        problems.extend(_markdown_legend_problems(
            text, planned, int(ctx.target("figure_legend_words_max", 180))))
    if problems:
        return Result(False, "manuscript_structure", "; ".join(problems[:8]),
                      ["Rebuild with tools/manuscript/assemble.py, then apply later edits without moving protected sections."])
    return Result(True, "manuscript_structure",
                  "selected title plus Abstract/Keywords/body/References/Figure legends are present in journal order")


@check("assembly_matches_sources")
def assembly_matches_sources(ctx: Ctx) -> Result:
    """At S17 only, prove the canonical first assembly exactly contains its source files."""
    from .. import paths

    tool = paths.tools_dir() / "manuscript/assemble.py"
    env = {**os.environ, "MEDPAPER_PROJECT": str(ctx.project),
           "MEDPAPER_ROOT": str(paths.repo_root()), "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run([sys.executable, str(tool), "--check"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", env=env)
    except OSError as exc:
        return Result(False, "assembly_matches_sources", f"cannot run assembler: {exc}")
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode:
        return Result(False, "assembly_matches_sources", output or "canonical assembly differs",
                      ["Edit the component source, then rerun tools/manuscript/assemble.py."])
    return Result(True, "assembly_matches_sources", "full manuscript exactly matches the gated source sections")


@check("docx_style_config")
def docx_style_config(ctx: Ctx) -> Result:
    rel = "08_submission/docx_style.json"
    if not ctx.p(rel).is_file():
        return Result(False, "docx_style_config", f"{rel} missing")
    try:
        data = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "docx_style_config", f"invalid JSON: {exc}")
    required = ["font_family", "body_font_pt", "title_font_pt", "section_heading_font_pt",
                "subsection_heading_font_pt", "line_spacing", "paragraph_spacing_after_pt",
                "margins_in", "paper_size", "all_text_black", "external_hyperlinks",
                "source", "fallbacks"]
    problems = [f"missing {k}" for k in required if k not in data]
    font = str(data.get("font_family", "")).strip()
    if not font or font.casefold() == "aptos":
        problems.append("font_family must be a journal-mandated font or Times New Roman, never Aptos")
    for key, lo, hi in (("body_font_pt", 8, 14), ("title_font_pt", 10, 20),
                        ("section_heading_font_pt", 8, 18),
                        ("subsection_heading_font_pt", 8, 18),
                        ("line_spacing", 1, 3), ("margins_in", 0.5, 2),
                        ("paragraph_spacing_after_pt", 0, 24)):
        value = data.get(key)
        if not isinstance(value, (int, float)) or not lo <= value <= hi:
            problems.append(f"{key} must be numeric in {lo}-{hi}")
    if data.get("all_text_black") is not True:
        problems.append("all_text_black must be true")
    if data.get("external_hyperlinks") is not False:
        problems.append("external_hyperlinks must be false")
    if str(data.get("paper_size", "")).upper() not in {"A4", "LETTER"}:
        problems.append("paper_size must be A4 or LETTER")
    source = str(data.get("source", "")).strip()
    if len(source) < 12 or re.search(r"<|>|todo|tbd", source, re.I):
        problems.append("source must cite the official rule or state that the journal is silent")
    fallbacks = data.get("fallbacks")
    if not isinstance(fallbacks, list):
        problems.append("fallbacks must be a list naming every silent field")
        fallbacks = []
    allowed_fallbacks = {
        "font_family": "Times New Roman", "body_font_pt": 12, "title_font_pt": 14,
        "section_heading_font_pt": 12, "subsection_heading_font_pt": 12,
        "line_spacing": 2.0, "paragraph_spacing_after_pt": 0,
        "margins_in": 1.0, "paper_size": "A4",
    }
    unknown = sorted(str(x) for x in fallbacks if str(x) not in allowed_fallbacks)
    if unknown:
        problems.append("fallbacks must use canonical field names; unknown: " + ", ".join(unknown))
    if len({str(x) for x in fallbacks}) != len(fallbacks):
        problems.append("fallbacks contains duplicate field names")
    for key in fallbacks:
        if key in allowed_fallbacks and data.get(key) != allowed_fallbacks[key]:
            problems.append(f"journal-silent {key} must use fallback {allowed_fallbacks[key]!r}")
    if "font_family" not in fallbacks and font and font.casefold() not in source.casefold():
        problems.append("journal-mandated font_family must be named in source")
    target_path = ctx.p("08_submission/target_journal.json")
    if target_path.is_file():
        try:
            guide_url = str(json.loads(target_path.read_text(encoding="utf-8")).get("guidelines_url", "")).strip()
        except json.JSONDecodeError:
            guide_url = ""
        if guide_url and guide_url not in source:
            problems.append("source must include target_journal.json guidelines_url")
    if problems:
        return Result(False, "docx_style_config", "; ".join(problems[:8]))
    return Result(True, "docx_style_config",
                  f"Word style frozen: {font}, {data['body_font_pt']} pt, {data['line_spacing']} spacing")


def _docx_text(root) -> str:
    return "\n".join("".join(t.text or "" for t in p.findall(".//w:t", NS))
                       for p in root.findall(".//w:p", NS))


def _docx_legend_problems(root, expected: list[str], cap: int) -> list[str]:
    paragraphs: list[tuple[str, str]] = []
    for p in root.findall(".//w:p", NS):
        text = "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()
        pstyle = p.find("w:pPr/w:pStyle", NS)
        style_id = "" if pstyle is None else pstyle.get(f"{{{W}}}val", "")
        if text:
            paragraphs.append((text, style_id))
    try:
        start = next(i for i, (text, _) in enumerate(paragraphs)
                     if text.casefold() == "figure legends") + 1
    except StopIteration:
        return ["Figure legends heading is missing"]
    headings = []
    for i in range(start, len(paragraphs)):
        text, style_id = paragraphs[i]
        match = re.match(r"^(Figure\s+S?\d+)\.?\s*(.*)$", text, re.I)
        if match and style_id == "SectionHeading":
            headings.append((i, match.group(1), match.group(2)))
    blocks: dict[str, tuple[int, int]] = {}
    for j, (idx, figure_id, suffix) in enumerate(headings):
        end = headings[j + 1][0] if j + 1 < len(headings) else len(paragraphs)
        content = "\n".join([suffix] + [text for text, _ in paragraphs[idx + 1:end]]).strip()
        blocks[_canon_figure_id(figure_id)] = (
            len(content), len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", content)))
    wanted = {_canon_figure_id(x): x for x in expected}
    problems: list[str] = []
    seen = [_canon_figure_id(item[1]) for item in headings]
    duplicates = sorted({item for item in seen if seen.count(item) > 1})
    if duplicates:
        problems.append("duplicate figure legend heading(s): " + ", ".join(duplicates))
    for idx, figure_id, _ in headings:
        if idx + 1 < len(paragraphs) and re.match(
                rf"^{re.escape(figure_id)}\b", paragraphs[idx + 1][0], re.I):
            problems.append(f"{figure_id} is repeated at the start of its legend body")
    for key, display in wanted.items():
        if key not in blocks:
            problems.append(f"DOCX Figure legends lacks {display}")
            continue
        chars, words = blocks[key]
        if chars < 40:
            problems.append(f"DOCX {display} legend is only {chars} characters")
        if words > cap:
            problems.append(f"DOCX {display} legend is {words} words (maximum {cap})")
    extras = sorted(set(blocks) - set(wanted))
    if extras:
        problems.append("DOCX has unplanned figure legend(s): " + ", ".join(extras))
    return problems


def _audit_docx(path: Path, style: dict, role: str,
                planned_figures: list[str] | None = None, legend_cap: int = 180) -> list[str]:
    problems: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            if zf.testzip():
                return [f"{path.name}: corrupt DOCX"]
            names = zf.namelist()
            xmls = {n: zf.read(n) for n in names
                    if n.startswith("word/") and n.endswith((".xml", ".rels"))}
    except (zipfile.BadZipFile, OSError) as exc:
        return [f"{path.name}: unreadable DOCX ({exc})"]
    try:
        root = ET.fromstring(xmls["word/document.xml"])
    except (KeyError, ET.ParseError) as exc:
        return [f"{path.name}: invalid document.xml ({exc})"]
    docxml = xmls["word/document.xml"]
    raw_text = _docx_text(root)
    if "\u2193" in raw_text:
        problems.append(f"{path.name}: forbidden down-arrow character remains")
    if root.findall(".//w:hyperlink", NS) or any(
            "HYPERLINK" in (node.text or "").upper()
            for node in root.findall(".//w:instrText", NS)):
        problems.append(f"{path.name}: hyperlink remains")
    for name, blob in xmls.items():
        if not name.endswith(".xml"):
            continue
        part = ET.fromstring(blob)
        if any(node.get(f"{{{W}}}type") in (None, "textWrapping")
               for node in part.findall(".//w:br", NS)) or part.findall(".//w:cr", NS):
            problems.append(f"{path.name}: manual line-break control remains in {name}")
        if any("\u2193" in (node.text or "") for node in part.findall(".//w:t", NS)):
            problems.append(f"{path.name}: forbidden down-arrow character remains in {name}")
        for tag in FORBIDDEN_PARAGRAPH_CONTROLS:
            if part.findall(f".//w:{tag}", NS):
                problems.append(f"{path.name}: forbidden {tag} paragraph control remains in {name}")
        if part.findall(".//w:pBdr", NS):
            problems.append(f"{path.name}: paragraph border/horizontal-rule residue remains in {name}")
    for name, blob in xmls.items():
        if not name.endswith(".rels"):
            continue
        try:
            relroot = ET.fromstring(blob)
        except ET.ParseError:
            continue
        for rel in relroot.findall("rel:Relationship", NS):
            if rel.get("TargetMode") == "External" and "hyperlink" in rel.get("Type", "").lower():
                problems.append(f"{path.name}: external hyperlink relationship remains")
    font = str(style.get("font_family", ""))
    if font.casefold() == "times new roman" and any(b"Aptos" in b for b in xmls.values()):
        problems.append(f"{path.name}: Aptos remains in Word XML")
    for p in root.findall(".//w:p", NS):
        ppr = p.find("w:pPr", NS)
        pstyle = None if ppr is None else ppr.find("w:pStyle", NS)
        style_id = "" if pstyle is None else pstyle.get(f"{{{W}}}val", "")
        allowed_pts = ({float(style["title_font_pt"])} if style_id == "ManuscriptTitle" else
                       {float(style["section_heading_font_pt"]),
                        float(style["subsection_heading_font_pt"])} if style_id == "SectionHeading" else
                       {float(style["body_font_pt"])})
        paragraph_text = "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()
        spacing_node = None if ppr is None else ppr.find("w:spacing", NS)
        if paragraph_text and (spacing_node is None or
                spacing_node.get(f"{{{W}}}line") !=
                str(int(round(float(style["line_spacing"]) * 240))) or
                spacing_node.get(f"{{{W}}}after", "0") !=
                str(int(round(float(style["paragraph_spacing_after_pt"]) * 20)))):
            problems.append(f"{path.name}: inconsistent line/paragraph spacing")
        for run in p.findall(".//w:r", NS):
            if not "".join(t.text or "" for t in run.findall(".//w:t", NS)).strip():
                continue
            rpr = run.find("w:rPr", NS)
            rf = None if rpr is None else rpr.find("w:rFonts", NS)
            color = None if rpr is None else rpr.find("w:color", NS)
            size = None if rpr is None else rpr.find("w:sz", NS)
            if rf is None or rf.get(f"{{{W}}}ascii") != font or rf.get(f"{{{W}}}hAnsi") != font:
                problems.append(f"{path.name}: a text run does not explicitly use {font}")
                break
            if color is None or color.get(f"{{{W}}}val", "").upper() not in {"000000", "AUTO"}:
                problems.append(f"{path.name}: a text run is not black")
                break
            if size is None or size.get(f"{{{W}}}val", "") not in {
                    str(int(round(value * 2))) for value in allowed_pts}:
                problems.append(f"{path.name}: inconsistent size in {style_id or 'body'} paragraph")
                break
        if style_id.casefold().startswith("heading"):
            problems.append(f"{path.name}: built-in outline heading style remains on visible text")
            break
    if role == "manuscript":
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        exact = {name: [i for i, line in enumerate(lines) if line.casefold() == name]
                 for name in ("abstract", "references", "figure legends")}
        keywords = [i for i, line in enumerate(lines) if line.casefold().startswith("keywords:")]
        for name, indices in exact.items():
            if len(indices) != 1:
                problems.append(f"{path.name}: expected one {name.title()} heading, found {len(indices)}")
        if len(keywords) != 1:
            problems.append(f"{path.name}: expected one Keywords line, found {len(keywords)}")
        positions = [exact["abstract"][0] if len(exact["abstract"]) == 1 else -1,
                     keywords[0] if len(keywords) == 1 else -1,
                     exact["references"][0] if len(exact["references"]) == 1 else -1,
                     exact["figure legends"][0] if len(exact["figure legends"]) == 1 else -1]
        if all(x >= 0 for x in positions) and positions != sorted(positions):
            problems.append(f"{path.name}: protected manuscript sections are out of order")
        if planned_figures is not None:
            problems.extend(f"{path.name}: {problem}" for problem in
                            _docx_legend_problems(root, planned_figures, legend_cap))
    elif role == "figure_legends":
        count = sum(1 for line in raw_text.splitlines()
                    if line.strip().casefold() == "figure legends")
        if count != 1:
            problems.append(f"{path.name}: expected one Figure legends heading, found {count}")
    if role == "supplementary" and root.findall(".//w:tbl", NS):
        problems.append(
            f"{path.name}: supplementary Methods contains a table instead of a separate "
            "three-line supplementary table"
        )
    return problems


@check("docx_bundle_ready")
def docx_bundle_ready(ctx: Ctx) -> Result:
    manifest_rel = "08_submission/bundle/manifest.json"
    style_rel = "08_submission/docx_style.json"
    try:
        manifest = ctx.read_json(manifest_rel)
        style = ctx.read_json(style_rel)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return Result(False, "docx_bundle_ready", f"cannot read manifest/style config: {exc}")
    roles: dict[str, list[Path]] = {}
    problems: list[str] = []
    source_check = supplementary_methods_clean(ctx)
    if not source_check.ok:
        problems.append(source_check.detail)
    planned = _figure_ids(ctx)
    if planned is None:
        problems.append("01_protocol/artifact_plan.json is missing or invalid")
    for item in manifest.get("items", []):
        role = str(item.get("role", "")).casefold()
        raw = str(item.get("file", ""))
        path = ctx.p(raw)
        roles.setdefault(role, []).append(path)
        if role in TEXT_ROLES and path.suffix.casefold() != ".docx":
            problems.append(f"{role}: narrative upload must be DOCX, got {path.name}")
        if path.suffix.casefold() == ".docx":
            problems.extend(_audit_docx(path, style, role, planned,
                                        int(ctx.target("figure_legend_words_max", 180))))
    for role in ("manuscript", "title_page", "cover_letter"):
        if not any(p.suffix.casefold() == ".docx" for p in roles.get(role, [])):
            problems.append(f"no DOCX for required role '{role}'")
    if ctx.p("07_manuscript/supplementary_methods.md").exists():
        if not any(p.suffix.casefold() == ".docx" for p in roles.get("supplementary", [])):
            problems.append("supplementary Methods exists but no supplementary DOCX is packaged")
    if problems:
        return Result(False, "docx_bundle_ready", "; ".join(sorted(set(problems))[:10]),
                      ["Rebuild affected Word files with tools/manuscript/build_docx.py."])
    count = sum(path.suffix.casefold() == ".docx" for paths in roles.values() for path in paths)
    return Result(True, "docx_bundle_ready",
                  f"{count} DOCX file(s): black journal font, consistent sizes, no links or outline headings")

