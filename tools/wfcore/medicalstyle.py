"""Reader-facing diagnostics and explicit medical meaning checks, never a word ban.

No source rewriting, medical inference from keywords, or claim to inspect unprovided papers.
Scanned text is local; a missing text layer still requires actual visual/semantic review.
"""
import hashlib
import json
from pathlib import Path
import re
from .packagefreeze import _safe_path, _sha256
from .readiness import load

RULES = {
    "runtime_count": (r"\b[\d,]+\s+(?:[A-Za-z-]+\s+){0,3}lines?\s+read\b", "Reading-log count: establish clinical counting unit; never relabel file lines as patients/reports."),
    "implementation_detail": (r"\b(?:Unicode normalization|concatenated legacy records|first\s+\d+\s+alphanumeric characters|vocabulary frozen)\b", "Assess scientific necessity in main Methods; move implementation detail, not validity-critical definitions, to supplement when appropriate."),
    "processing_label": (r"\b(?:collapse step|strict(?:\s+[A-Za-z-]+){0,4}\s+contrasts?|publications collapsed|near-duplicates and clusters removed)\b", "Replace/define internal processing labels in clinical terms without changing the procedure or source-specific model."),
    "opaque_endpoint": (r"\bComposite\s+[A-Z]\b", "Use the clinical endpoint name or decode components at the display; a letter is not a clinical definition."),
    "ambiguous_antecedent": (r"\bpost\s+hoc\s*:\s*same\b", "Describe the actual post-hoc population/comparison; preserve its timing, not an unexplained 'same'."),
    "software_state": (r"\b(?:NaN|Undefined|Not fitted)\b", "Check missing/not applicable/not fitted/not estimable/unbounded separately; never automatically replace all states with a dash."),
}
FIELDS = {
    "table": ("title_and_labels", "denominators_and_summaries", "footnotes_and_model_states"),
    "figure": ("title_and_labels", "statistic_and_encodings", "population_and_denominators"),
}


def enabled(project, layer="science", final=False):
    from .state import State
    state=State(project).load()
    owner="S17_assemble" if layer=="science" else "S23_package" if final else "S22_polish"
    return not state.pin_excludes(owner,"1.15.0")


def visible(path):
    suffix=path.suffix.lower()
    if suffix in {".md",".txt",".csv"}: return path.read_text(encoding="utf-8")
    if suffix==".docx":
        from .packagecontent import visible_text
        return visible_text(path)
    if suffix==".xlsx":
        from openpyxl import load_workbook
        book=load_workbook(path,read_only=True,data_only=False)
        try:
            return "\n".join(f"{sheet.title}!{index}: "+" | ".join(str(c.value) for c in row if c.value is not None)
                             for sheet in book for index,row in enumerate(sheet.iter_rows(),1) if any(c.value is not None for c in row))
        finally: book.close()
    if suffix==".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix==".svg":
        import xml.etree.ElementTree as ET
        root=ET.fromstring(path.read_bytes())
        return "\n".join("".join(node.itertext()) for node in root.iter() if node.tag.endswith("}text") or node.tag=="text")
    return ""  # no OCR inference or substituted code labels for raster figures


def diagnose(text, rel):
    findings=[]
    for line, value in enumerate(text.splitlines(),1):
        for kind,(pattern,message) in RULES.items():
            for match in re.finditer(pattern,value,re.I):
                excerpt=value.strip()[:240]
                identity=hashlib.sha256(f"{rel}\0{kind}\0{excerpt}".encode()).hexdigest()[:16]
                findings.append({"id":identity,"path":rel,"locator":f"extracted line {line}","kind":kind,"excerpt":excerpt,"message":message})
    # A blanket n(%) footnote can contradict median/IQR summaries in the same table.
    if re.search(r"median|IQR|interquartile",text,re.I) and re.search(r"values are (?:numbers|counts) of",text,re.I) and not re.search(r"unless otherwise|except",text,re.I):
        identity=hashlib.sha256((rel+"summary_footnote").encode()).hexdigest()[:16]
        findings.append({"id":identity,"path":rel,"locator":"table summary footnote","kind":"summary_footnote","excerpt":"mixed statistical summaries","message":"Footnote must describe the actual row summaries and available-case denominators, not claim every row is a count."})
    return findings


def scan(project,layer="science",final=False):
    from .benchmark import display_source
    plan=load(project,"01_protocol/artifact_plan.json" if layer=="science" else "08_submission/integration/artifact_plan.json")
    folder="07_manuscript" if layer=="science" else "08_submission/integration"
    files={f"{folder}/full_manuscript.md"}
    for rel in (("05_figures/legends.md","04_tables/table_captions.md") if layer=="science" else
                (f"{folder}/figure_legends.md",f"{folder}/table_captions.md")):
        if (project/rel).is_file(): files.add(rel)
    for group in ("main_figures","supp_figures","main_tables","supp_tables"):
        for entry in plan.get(group,[]): files.add(display_source(project,entry,layer,final))
    if final:
        for row in load(project,"08_submission/bundle/manifest.json")["items"]:
            if row.get("upload",True) and row.get("role") in {"manuscript","tables","figure_legends"}: files.add(row["file"])
    issues=[]
    for rel in sorted(files):
        _,file=_safe_path(project,rel)
        if file.is_file(): issues.extend(diagnose(visible(file),rel))
    return issues


def layout_inputs(project, report):
    files={}
    for row in report.get("document_layout",[]):
        rel,file=_safe_path(project,row.get("render",""))
        if not rel.startswith("08_submission/evidence/") or file.suffix.lower() not in {".png",".pdf"} or not file.is_file():
            raise ValueError("Final layout observation must reference an actual existing Word-rendered PNG/PDF under evidence/")
        if file.suffix.lower()==".png":
            from PIL import Image
            with Image.open(file) as image: image.verify()
        else:
            from pypdf import PdfReader
            if not PdfReader(file).pages: raise ValueError("Layout PDF has no actual pages")
        files[rel]=_sha256(file)
    return files


def verify(project, report, layer="science", final=False):
    if not enabled(project,layer,final): return []
    from .benchmark import substantive
    problems=[]
    if report.get("medical_style_version")!=1: problems.append("Complete current medical presentation checks using reference/medical-reader-presentation.md; do not auto-upgrade old evidence")
    plan=load(project,"01_protocol/artifact_plan.json" if layer=="science" else "08_submission/integration/artifact_plan.json")
    for group in ("main_figures","supp_figures","main_tables","supp_tables"):
        kind="table" if "tables" in group else "figure"
        for entry in plan.get(group,[]):
            checks=report.get("display_findings",{}).get(entry["id"],{}).get("medical_checks",{})
            for field in FIELDS[kind]:
                if not substantive(checks.get(field)): problems.append(f"{entry['id']}: describe actual {field}, not generic PASS")
    for issue in scan(project,layer,final):
        decision=report.get("style_resolutions",{}).get(issue["id"],{})
        if decision.get("action")!="retained" or not substantive(decision.get("reason")) or not str(decision.get("evidence_location","")).strip():
            problems.append(f"{issue['path']} {issue['locator']}: {issue['kind']}; fix at source or justify its actual medical use against this issue ID")
    if final:
        documents={row["file"] for row in load(project,"08_submission/bundle/manifest.json")["items"]
                   if row.get("upload",True) and row.get("role") in {"manuscript","tables","figure_legends","supplementary"}
                   and Path(row["file"]).suffix.lower()==".docx"}
        rows=report.get("document_layout",[])
        if len(rows)!=len({r.get("upload") for r in rows}) or {r.get("upload") for r in rows}!=documents:
            problems.append("Inspect each actual figure/table/manuscript/supplement DOCX layout; no assumed coverage of absent supplements")
        renders=layout_inputs(project,report)
        for row in rows:
            _,source=_safe_path(project,row.get("upload",""))
            if (not source.is_file() or row.get("source_sha256")!=_sha256(source)
                    or row.get("render_sha256")!=renders.get(row.get("render"))
                    or not str(row.get("locator","")).strip() or not substantive(row.get("observation"))):
                problems.append("Layout reading must bind current upload/render bytes and concrete page/figure/table observations")
    return problems
