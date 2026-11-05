"""Medical display decisions and actual-render checks; no claim of semantic automation."""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from .packagefreeze import _safe_path, _sha256
from .readiness import load

GROUPS = ("main_figures", "main_tables", "supp_figures", "supp_tables")
ROLES = {"selection", "population", "primary_results", "comparisons_or_robustness"}


def story_problems(plan: dict, benchmark: dict) -> list[str]:
    """Map scientific display tasks to real items; quantity alone is not quality."""
    items = {r["id"]: (group, r) for group in GROUPS for r in plan.get(group, [])}
    rows = benchmark.get("adaptation", {}).get("displays", {}).get("role_mapping", [])
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        return ["Benchmark display role_mapping must be a list of actual study decisions"]
    roles = [r.get("role") for r in rows]
    if set(roles) != ROLES or len(roles) != len(ROLES):
        return ["Map selection, population, primary_results and comparisons_or_robustness once each in the existing benchmark"]
    comparators = {r["citekey"] for r in benchmark.get("comparators", [])}
    problems = []
    for row in rows:
        role = row["role"]; selected = row.get("display_ids", [])
        if type(row.get("applicable")) is not bool or not isinstance(selected, list):
            problems.append(f"{role}: explicit applicability and actual display_ids required"); continue
        if len(str(row.get("scientific_reason", "")).strip()) < 40:
            problems.append(f"{role}: explain the actual scientific need or inapplicability, not a generic economy claim")
        refs = row.get("comparator_evidence", [])
        if not isinstance(refs,list) or not refs or any(not isinstance(r,dict) or r.get("citekey") not in comparators or not str(r.get("locator", "")).strip()
                           or len(str(r.get("adopt_or_depart", "")).strip()) < 30 for r in refs):
            problems.append(f"{role}: connect comparator page/figure/table and the actual adopt/depart decision")
        if not row["applicable"]:
            if selected: problems.append(f"{role}: inapplicable role cannot claim mapped displays")
            if role == "selection" and (row.get("process") != "none" or row.get("steps") != []):
                problems.append("selection: only an actual absence of selection can be inapplicable; supplement counts/compactness do not remove a real process")
            continue
        if not selected or any(key not in items for key in selected):
            problems.append(f"{role}: missing/unknown display, prose rationale cannot substitute for necessary evidence"); continue
        if role in {"selection", "population", "primary_results"} and not any(items[k][0].startswith("main_") for k in selected):
            problems.append(f"{role}: a core reader task needs a main-text display, not only supplementary material")
        if role == "selection":
            if row.get("process") not in {"single_stage", "multi_stage"} or not isinstance(row.get("steps"),list) or not row["steps"]:
                problems.append("selection: describe the actual selection steps/process before choosing displays")
            flow = [k for k in selected if items[k][0] == "main_figures" and items[k][1].get("archetype") == "flow_diagram"]
            if "Figure 1" not in flow:
                problems.append("Applicable participant/report/study selection needs a main Figure 1 flow diagram; a supplement count table is not its replacement")
            if len(str(row.get("counting_unit_and_branches", "")).strip()) < 40:
                problems.append("selection: explain counting units, sequential exclusions and nested/overlapping analysis branches")
        if role == "primary_results" and not any(items[k][1].get("archetype") != "flow_diagram" for k in selected if items[k][0].startswith("main_")):
            problems.append("primary_results: a selection diagram cannot substitute for a clinical result display")
        if role == "population":
            summaries = row.get("summaries", {})
            if any(len(str(summaries.get(field, "")).strip()) < 30 for field in ("categorical", "continuous")):
                problems.append("population: specify category denominators/percentages and continuous summaries or real unavailable/inapplicable reasons; recording availability alone is not a clinical summary")
    return problems


def flat_labels(labels: list[str]) -> list[str]:
    prefixes = Counter()
    for label in labels:
        m = re.match(r"^([A-Za-z][A-Za-z -]*\bdistribution)\s*:", str(label), re.I)
        if m: prefixes[m[1].casefold()] += 1
    return [f"Repeated '{key}:' in {n} row labels; use a clinical variable heading and indented categories"
            for key, n in prefixes.items() if n >= 3]


def panel_problems(svg: Path, entry: dict) -> list[str]:
    labels = entry.get("panels", [])
    if len(labels) < 2: return []
    if not all(isinstance(x, str) and re.fullmatch(r"[A-Z]", x) for x in labels) or len(set(labels)) != len(labels):
        return ["Multiplot panels need unique standalone uppercase letters in reading order"]
    try:
        root = ET.fromstring(svg.read_bytes())
        canvas = [float(x) for x in root.attrib.get("viewBox", "").split()]
    except (ET.ParseError, ValueError) as exc:
        raise ValueError("Invalid actual SVG for panel-tag inspection") from exc
    if len(canvas)!=4 or not all(math.isfinite(x) for x in canvas) or min(canvas[2:])<=0:
        raise ValueError("Actual SVG needs a finite positive viewBox for panel-tag inspection")
    width, height = canvas[2:]
    texts = [("".join(n.itertext()).strip(), n) for n in root.iter() if n.tag.split("}")[-1] == "text"]
    layout = entry.get("panel_layout", {})
    cols = layout.get("columns")
    if type(cols) is not int or not 1 <= cols <= len(labels):
        return ["Record panel_layout.columns for the actual composition; keep letters separate from facet titles"]
    bounds = layout.get("bounds")
    if bounds is None:
        rows = math.ceil(len(labels) / cols)
        bounds = [[(i % cols)/cols, (i//cols)/rows, (i%cols+1)/cols, (i//cols+1)/rows] for i in range(len(labels))]
    if (not isinstance(bounds, list) or len(bounds) != len(labels) or any(not isinstance(b, list) or len(b) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in b)
            or not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1) for b in bounds)):
        return ["panel_layout.bounds must give each actual panel's normalized [left,top,right,bottom] rectangle"]
    problems = []
    for letter, bound in zip(labels, bounds):
        found = [node for value, node in texts if value == letter]
        if len(found) != 1:
            problems.append(f"{letter}: one independent panel tag is required; a letter embedded in a title is insufficient"); continue
        node = found[0]
        try:
            x, y = float(node.attrib["x"])/width, float(node.attrib["y"])/height
        except (KeyError, ValueError):
            problems.append(f"{letter}: tag coordinates require actual visual resolution"); continue
        if node.get("transform") or not (bound[0] <= x <= bound[0]+.20*(bound[2]-bound[0]) and
                                          bound[1] <= y <= bound[1]+.20*(bound[3]-bound[1])):
            problems.append(f"{letter}: tag is not in its panel's upper-left margin; inspect the actual render")
    return problems


def production_problems(project: Path, kind: str) -> list[str]:
    plan = load(project, "01_protocol/artifact_plan.json")
    reviews = load(project, "01_protocol/display_review.json").get("final_reviews", {})
    groups = ("main_tables", "supp_tables") if kind == "table" else ("main_figures", "supp_figures")
    problems = []
    for group in groups:
        for entry in plan.get(group, []):
            key = entry["id"]; rel, path = _safe_path(project, entry["file"])
            row = reviews.get(key, {})
            if row.get("reviewed_file") != rel or not path.is_file() or row.get("sha256") != _sha256(path):
                problems.append(f"{key}: actual production file needs current rendered medical review, not a prototype PASS"); continue
            try:
                preview_rel, preview = _safe_path(project, row.get("rendered_preview", ""))
                if preview.suffix.lower() not in {".png", ".pdf", ".svg"} or not preview.is_file() or row.get("rendered_sha256") != _sha256(preview):
                    raise ValueError("missing/stale actual rendered preview")
                if kind == "table" and preview_rel == rel: raise ValueError("the workbook itself is not a rendered page")
            except (OSError, ValueError):
                problems.append(f"{key}: bind the actual rendered image/page used for medical reading")
            for field in ("reader_explanation", "layout_and_style"):
                if len(str(row.get(field, "")).strip()) < 60:
                    problems.append(f"{key}: describe concrete {field} from the production render")
            if row.get("verdict") != "PASS": problems.append(f"{key}: resolve real display defects before Results writing")
            if kind == "table":
                from openpyxl import load_workbook
                book = load_workbook(path, read_only=True, data_only=True)
                try:
                    sheet = entry.get("sheet")
                    if sheet not in book.sheetnames:
                        problems.append(f"{key}: actual planned worksheet missing"); continue
                    problems.extend(f"{key}: {p}" for p in flat_labels([r[0] for r in book[sheet].iter_rows(min_row=3, values_only=True) if r and r[0] is not None]))
                finally: book.close()
            elif entry.get("renderer", "R").upper() == "R":
                audit = project/"05_figures/qc"/(path.stem+".artist.json")
                if audit.is_file():
                    actual = load(project,audit.relative_to(project).as_posix())
                    if actual.get("n_axes",0)>1 and len(entry.get("panels",[]))<2:
                        problems.append(f"{key}: actual render has multiple panels; declare and tag them rather than omitting panel metadata")
                if len(entry.get("panels",[]))<2:
                    continue
                sidecar = project/"05_figures/qc"/(path.stem+".render.svg")
                if not sidecar.is_file():
                    problems.append(f"{key}: actual SVG needed for independent panel-tag inspection")
                else:
                    problems.extend(f"{key}: {p}" for p in panel_problems(sidecar, entry))
    return problems
