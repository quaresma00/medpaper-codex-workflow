"""Native medical Word tables from declared XLSX sheets, without pipe-table conversion."""
from __future__ import annotations

import json
from pathlib import Path

from docx.enum.section import WD_SECTION_START, WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Twips

from .packagefreeze import _safe_path


def load_spec(project: Path, path: Path) -> tuple[list[dict], list[Path]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    entries = value.get("tables")
    if not isinstance(entries, list) or not entries:
        raise ValueError("table specification requires a nonempty tables list")
    files = [path]
    ids = set()
    for entry in entries:
        if not entry.get("id") or entry["id"] in ids:
            raise ValueError("table IDs must be explicit and unique")
        ids.add(entry["id"])
        source = _safe_path(project, entry.get("file", ""))[1]
        if source.suffix.lower() != ".xlsx" or not source.is_file():
            raise ValueError("table source must be an existing project XLSX")
        if not entry.get("sheet"):
            raise ValueError("declare the exact worksheet; never silently use the first sheet")
        if entry.get("orientation", "auto") not in {"auto", "portrait", "landscape"}:
            raise ValueError("table orientation must be auto, portrait or landscape")
        files.append(source)
    return entries, files


def _border(cell, top: int = 0, bottom: int = 0) -> None:
    properties = cell._tc.get_or_add_tcPr()
    old = properties.find(qn("w:tcBorders"))
    if old is not None:
        properties.remove(old)
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "bottom", "left", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        size = top if edge == "top" else bottom if edge == "bottom" else 0
        node.set(qn("w:val"), "single" if size else "nil")
        if size:
            node.set(qn("w:sz"), str(size))
            node.set(qn("w:color"), "000000")
        borders.append(node)
    properties.append(borders)


def _geometry(section, orientation: str, style: dict) -> None:
    width, height = (8.5, 11) if str(style["paper_size"]).upper() == "LETTER" else (8.2677, 11.6929)
    landscape = orientation == "landscape"
    section.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    section.page_width = Inches(height if landscape else width)
    section.page_height = Inches(width if landscape else height)
    margin = Inches(float(style["margins_in"]))
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = margin
    # Never restart numbering when crossing a table section.
    numbering = section._sectPr.find(qn("w:pgNumType"))
    if numbering is not None:
        numbering.attrib.pop(qn("w:start"), None)


def append_tables(doc, project: Path, entries: list[dict], style: dict) -> None:
    from openpyxl import load_workbook
    for entry in entries:
        source = _safe_path(project, entry["file"])[1]
        workbook = load_workbook(source, data_only=False)
        try:
            if entry["sheet"] not in workbook.sheetnames:
                raise ValueError(f"worksheet missing: {entry['sheet']}")
            sheet = workbook[entry["sheet"]]
            start = int(entry.get("header_start", 2))
            end = int(entry.get("header_end", start))
            ncol = int(entry.get("columns", sheet.max_column))
            if not 1 <= start <= end < sheet.max_row or ncol < 1 or ncol > sheet.max_column:
                raise ValueError("invalid header or column bounds")
            last = entry.get("body_end")
            if last is None:
                ruled = [r for r in range(end + 1, sheet.max_row + 1)
                         if all(sheet.cell(r, c).border.bottom.style for c in range(1, ncol + 1))]
                if len(ruled) != 1:
                    raise ValueError("ambiguous table/body boundary; declare body_end explicitly")
                last = ruled[0]
            last = int(last)
            if not end < last <= sheet.max_row:
                raise ValueError("invalid body_end")
            # No silent dropping of populated columns, title rows, or orphan notes.
            for row in sheet.iter_rows():
                if any(cell.value is not None for cell in row[ncol:]):
                    raise ValueError("populated columns fall outside the declared table")
            caption = str(entry.get("caption") or sheet.cell(1, 1).value or "").strip()
            if not caption or entry["id"].casefold() not in caption.casefold():
                raise ValueError("table caption must identify this table")
            notes = []
            for r in range(last + 1, sheet.max_row + 1):
                populated = [str(sheet.cell(r, c).value) for c in range(1, ncol + 1) if sheet.cell(r, c).value is not None]
                if len(populated) > 1:
                    raise ValueError("multiple populated cells after body_end; declare the complete body, do not discard data")
                notes.extend(populated)
            # Numeric XLSX display formats can change units/precision (0.12 shown as
            # 12%). Never silently publish raw storage values as formatted findings.
            for row in sheet.iter_rows(min_row=start, max_row=last, max_col=ncol):
                for cell in row:
                    if getattr(cell, "is_date", False) or (isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool)
                                        and cell.number_format not in {"General", "@"}):
                        raise ValueError(f"{cell.coordinate}: use explicit approved display text for formatted numbers/dates; do not change units or precision")
            values = [[sheet.cell(r, c).value for c in range(1, ncol + 1)] for r in range(start, last + 1)]
            if any(isinstance(value, str) and value.startswith("=") for row in values for value in row):
                raise ValueError("formula cells require an explicitly calculated value source; never render formulas as results")
            chars = [min(40, max(6, max(len(str(row[c] or "")) for row in values))) for c in range(ncol)]
            estimated = sum(char * float(style["body_font_pt"]) * 10 + 216 for char in chars)
            portrait_width = Inches((8.5 if str(style["paper_size"]).upper() == "LETTER" else 8.2677) - 2 * float(style["margins_in"])).twips
            orientation = entry.get("orientation", "auto")
            if orientation == "auto":
                orientation = "landscape" if ncol > 7 or estimated > portrait_width else "portrait"
            section = doc.add_section(WD_SECTION_START.NEW_PAGE)
            _geometry(section, orientation, style)
            doc.add_paragraph(caption)
            table = doc.add_table(rows=last - start + 1, cols=ncol)
            table.autofit = False
            caption_node = OxmlElement("w:tblCaption")
            caption_node.set(qn("w:val"), "medpaper-threeline:" + entry["id"])
            table._tbl.tblPr.append(caption_node)
            # Explicit nil table borders prevent an Office table theme reappearing.
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "bottom", "left", "right", "insideH", "insideV"):
                node = OxmlElement(f"w:{edge}"); node.set(qn("w:val"), "nil"); borders.append(node)
            table._tbl.tblPr.append(borders)
            width = section.page_width.twips - section.left_margin.twips - section.right_margin.twips
            weights = [char + 3 for char in chars]
            widths = [int(width * weight / sum(weights)) for weight in weights]
            widths[-1] += width - sum(widths)
            for column, amount in zip(table.columns, widths):
                column.width = Twips(amount)
            for r, row in enumerate(values):
                for c, value in enumerate(row):
                    cell = table.cell(r, c)
                    cell.text = "" if value is None else str(value)
                    cell.width = Twips(widths[c])
                    paragraph = cell.paragraphs[0]
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT if c == 0 else WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        run.bold = r <= end - start
                if r <= end - start:
                    repeat = OxmlElement("w:tblHeader")
                    table.rows[r]._tr.get_or_add_trPr().append(repeat)
            for merged in sheet.merged_cells.ranges:
                if merged.max_row < start or merged.min_row > last:
                    continue
                if (merged.min_row < start or merged.max_row > last or merged.max_col > ncol
                        or merged.min_row <= end < merged.max_row):
                    raise ValueError("merged cell crosses a header/body or table boundary")
                value = sheet.cell(merged.min_row, merged.min_col).value
                cell = table.cell(merged.min_row - start, merged.min_col - 1).merge(
                    table.cell(merged.max_row - start, merged.max_col - 1))
                cell.text = "" if value is None else str(value)
                for run in cell.paragraphs[0].runs:
                    run.bold = merged.max_row <= end
            for r, row in enumerate(table.rows):
                from docx.table import _Cell
                for tc in row._tr.tc_lst:
                    cell = _Cell(tc, table)
                    _border(cell, 12 if r == 0 else 0, 6 if r == end - start else 12 if r == len(values) - 1 else 0)
            for note in notes:
                doc.add_paragraph(note)
        finally:
            workbook.close()


def table_problems(doc) -> list[str]:
    problems = []
    for table in doc.tables:
        label = table._tbl.tblPr.find(qn("w:tblCaption"))
        if label is None or not label.get(qn("w:val"), "").startswith("medpaper-threeline:"):
            continue
        rows = table.rows
        for index, row in enumerate(rows):
            header = row._tr.trPr is not None and row._tr.trPr.find(qn("w:tblHeader")) is not None
            next_header = index + 1 < len(rows) and rows[index + 1]._tr.trPr is not None and rows[index + 1]._tr.trPr.find(qn("w:tblHeader")) is not None
            from docx.table import _Cell
            for tc in row._tr.tc_lst:
                cell = _Cell(tc, table)
                borders = cell._tc.get_or_add_tcPr().find(qn("w:tcBorders"))
                expected = {"top": 12 if index == 0 else 0,
                            "bottom": 6 if header and not next_header else 12 if index == len(rows) - 1 else 0}
                for edge in ("top", "bottom", "left", "right", "insideH", "insideV"):
                    node = borders.find(qn("w:" + edge)) if borders is not None else None
                    size = expected.get(edge, 0)
                    if node is None or node.get(qn("w:val")) != ("single" if size else "nil") or (size and node.get(qn("w:sz")) != str(size)):
                        problems.append(f"{label.get(qn('w:val'))}: incorrect {edge} rule at row {index + 1}")
    return sorted(set(problems))
