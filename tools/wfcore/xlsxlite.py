"""Minimal read-only .xlsx reader built on zipfile + ElementTree.

Exists so the gate engine stays dependency-free: gates must run even when the
science virtualenv (openpyxl/pandas) is broken or absent. Reads cell values and
enough style information to verify three-line (booktabs) table rules.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _col_to_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


@dataclass
class Cell:
    ref: str
    row: int
    col: int
    value: str | None
    style: int | None


@dataclass
class BorderSpec:
    top: bool = False
    bottom: bool = False
    left: bool = False
    right: bool = False


@dataclass
class Sheet:
    name: str
    cells: list[Cell] = field(default_factory=list)

    @property
    def max_row(self) -> int:
        return max((c.row for c in self.cells), default=0)

    @property
    def max_col(self) -> int:
        return max((c.col for c in self.cells), default=0)

    def row_cells(self, row: int) -> list[Cell]:
        return sorted((c for c in self.cells if c.row == row), key=lambda c: c.col)

    def row_text(self, row: int) -> list[str]:
        return [c.value or "" for c in self.row_cells(row)]

    def values(self) -> list[str]:
        return [c.value for c in self.cells if c.value not in (None, "")]


class Workbook:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.sheets: list[Sheet] = []
        self._borders: list[BorderSpec] = []
        self._xf_border: list[int] = []
        self._load()

    # ---- parsing -------------------------------------------------------
    def _load(self) -> None:
        with zipfile.ZipFile(self.path) as zf:
            shared = self._shared_strings(zf)
            self._load_styles(zf)
            wb = ET.fromstring(zf.read("xl/workbook.xml"))
            rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rel_map = {
                el.get("Id"): el.get("Target")
                for el in rels
                if el.get("Id")
            }
            for sh in wb.findall("m:sheets/m:sheet", NS):
                name = sh.get("name", "?")
                rid = sh.get(f"{{{NS['r']}}}id")
                target = rel_map.get(rid, "")
                if not target:
                    continue
                member = "xl/" + target.lstrip("/").removeprefix("xl/")
                if member not in zf.namelist():
                    continue
                self.sheets.append(self._parse_sheet(name, zf.read(member), shared))

    @staticmethod
    def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in zf.namelist():
            return []
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        out = []
        for si in root.findall("m:si", NS):
            out.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        return out

    def _load_styles(self, zf: zipfile.ZipFile) -> None:
        if "xl/styles.xml" not in zf.namelist():
            return
        root = ET.fromstring(zf.read("xl/styles.xml"))
        for b in root.findall("m:borders/m:border", NS):
            spec = BorderSpec()
            for side in ("top", "bottom", "left", "right"):
                el = b.find(f"m:{side}", NS)
                setattr(spec, side, el is not None and el.get("style") not in (None, "none"))
            self._borders.append(spec)
        for xf in root.findall("m:cellXfs/m:xf", NS):
            self._xf_border.append(int(xf.get("borderId", "0")))

    def _parse_sheet(self, name: str, blob: bytes, shared: list[str]) -> Sheet:
        sheet = Sheet(name=name)
        root = ET.fromstring(blob)
        for c in root.iter(f"{{{NS['m']}}}c"):
            ref = c.get("r", "")
            m = CELL_RE.match(ref)
            if not m:
                continue
            ctype = c.get("t")
            v = c.find("m:v", NS)
            if ctype == "s" and v is not None and v.text is not None:
                idx = int(v.text)
                val = shared[idx] if 0 <= idx < len(shared) else None
            elif ctype == "inlineStr":
                is_el = c.find("m:is", NS)
                val = "".join(t.text or "" for t in is_el.iter(f"{{{NS['m']}}}t")) if is_el is not None else None
            else:
                val = v.text if v is not None else None
            style = int(c.get("s")) if c.get("s") is not None else None
            sheet.cells.append(
                Cell(ref=ref, row=int(m.group(2)), col=_col_to_index(m.group(1)), value=val, style=style)
            )
        return sheet

    # ---- style access --------------------------------------------------
    def border_of(self, cell: Cell) -> BorderSpec:
        if cell.style is None or cell.style >= len(self._xf_border):
            return BorderSpec()
        bid = self._xf_border[cell.style]
        if bid >= len(self._borders):
            return BorderSpec()
        return self._borders[bid]

    def sheet(self, name: str) -> Sheet | None:
        for s in self.sheets:
            if s.name == name:
                return s
        return None


def numeric_cell_values(path: Path) -> list[tuple[str, str, str]]:
    """-> [(sheet, ref, raw_value)] for cells whose text contains a number."""
    wb = Workbook(path)
    out = []
    for sh in wb.sheets:
        for c in sh.cells:
            if c.value and re.search(r"\d", c.value):
                out.append((sh.name, c.ref, c.value))
    return out
