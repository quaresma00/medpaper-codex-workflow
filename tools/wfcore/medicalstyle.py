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
    "assistant_voice": (r"\b(?:as an AI(?: language)? model|as requested by (?:the |our )?user|I (?:can|will) (?:help|generate|provide)|here (?:is|are) (?:the |your )?(?:requested |revised )?(?:manuscript|analysis|table|figure)|let(?:'s| us) (?:delve|explore))\b", "Remove executor-to-user conversation from the medical article; retain scientific content and uncertainty, not assistant narration."),
    "workflow_metadata": (r"\b(?:source_sha256|render_sha256|rebuild_files|validation_stages|citekeys_resolve|schema_version|engine_pin|medical_style_version)\b|\bS(?:0[1-9]|1[0-9]|2[0-5])_(?:assemble|package|polish|artifacts|human_review|analysis)\b", "Internal engine fields and stage receipts do not explain clinical methods/results. Keep their provenance backstage; review any genuine scientific software terminology in context."),
    "local_artifact_path": (r"(?:\b[A-Za-z]:[\\/](?:workspace|Users)[\\/]|\b(?:project[\\/])?(?:03_analysis[\\/]results|07_manuscript|08_submission[\\/](?:bundle|integration))[\\/])", "A local workflow path is not a clinical explanation or a stable reader-accessible data source. Replace only the presentation, preserving the actual method and authorized availability statement."),
    "draft_placeholder": (r"\b(?:TODO|TBD|INSERT[_ ](?:RESULT|REFERENCE|FIGURE|TABLE)|lorem ipsum)\b", "Resolve accidental drafting placeholders before delivery; a target-required placeholder or a quoted scientific term needs its actual contextual reason."),
    "internal_plan_history": (r"\b(?:unregistered protocol|archived.{0,15}protocol|protocol.{0,25}(?:archived|not registered|unregistered)|departures from (?:the |our )?protocol|protocol deviations? (?:are|were) (?:reported|listed)|initial (?:analysis )?plan (?:changed|was revised))\b", "Ordinary retrospective mining does not need internal plan/registration history in the paper. Keep the backstage log; preserve actual exploratory/post-hoc status and any genuinely required protocol reporting."),
    "revision_history": (r"\b(?:after internal review|added after review|review round\s+[MP]\d+|after rerunning the pipeline)\b", "Keep orchestration/revision history backstage, but preserve actual post-hoc status and scientific timing."),
    "runtime_count": (r"\b[\d,]+\s+(?:[A-Za-z-]+\s+){0,3}lines?\s+read\b", "Reading-log count: establish clinical counting unit; never relabel file lines as patients/reports."),
    "implementation_detail": (r"\b(?:Unicode normalization|concatenated legacy records|first\s+\d+\s+alphanumeric characters|vocabulary frozen)\b", "Assess scientific necessity in main Methods; move implementation detail, not validity-critical definitions, to supplement when appropriate."),
    "processing_label": (r"\b(?:collapse step|strict(?:\s+[A-Za-z-]+){0,4}\s+contrasts?|publications collapsed|near-duplicates and clusters removed)\b", "Replace/define internal processing labels in clinical terms without changing the procedure or source-specific model."),
    "opaque_endpoint": (r"\bComposite\s+[A-Z]\b", "Use the clinical endpoint name or decode components at the display; a letter is not a clinical definition."),
    "opaque_procedure": (r"\b(?:same-transmitter screen|first-author keys|first receipt|original rule|second rule|record review)\b", "Explain the actual clinical purpose, source unit and population at point of use; a coined processing label is not an explanation. Update the shared clinical vocabulary when appropriate."),
    "ambiguous_antecedent": (r"\bpost\s+hoc\s*:\s*same\b", "Describe the actual post-hoc population/comparison; preserve its timing, not an unexplained 'same'."),
    "software_state": (r"\b(?:NaN|Undefined|Not fitted)\b", "Check missing/not applicable/not fitted/not estimable/unbounded separately; never automatically replace all states with a dash."),
}
FIELDS = {
    "table": ("title_and_labels", "denominators_and_summaries", "footnotes_and_model_states"),
    "figure": ("title_and_labels", "statistic_and_encodings", "population_and_denominators"),
}

DISPLAY_CODES = re.compile(r"\b(?:n_cases|n_controls|n_obs|row_id|analysis_id|source_id|variable_name|group_code|cohort_code|estimate_raw|p_value|ci_lower|ci_upper|log_or|log_rr|log_hr|unknown_source|model_\d+|source_[a-z0-9]+)\b",re.I)


def display_language_enabled(project, report=None):
    from .state import State, version_tuple
    state=State(project).load().data
    return (version_tuple(str(state.get("engine_pin",state.get("pipeline_version","0")))) >= (1,27,0)
            or (report or {}).get("display_language_version")==1)


def _figure_text_inputs(project,entry,rel):
    """Use a managed R text layer only when it belongs to this exact plotted finding.

    A similarly named neighbouring SVG or script label is never a substitute for the
    submitted raster. No text layer remains a visual-reading task, not an OCR PASS.
    """
    _,image=_safe_path(project,rel)
    if image.suffix.lower() not in {".png",".tif",".tiff",".jpg",".jpeg"}: return {}
    folder="08_submission/integration/figure_qc" if rel.startswith("08_submission/") else "05_figures/qc"
    audit_rel=f"{folder}/{image.stem}.artist.json"
    if not (project/audit_rel).is_file(): return {}
    audit=load(project,audit_rel)
    if audit.get("engine")!="R": return {}
    svg_rel=f"{folder}/{image.stem}.render.svg"
    hashes=audit.get("render_hashes",{})
    if rel not in hashes or svg_rel not in hashes:
        raise ValueError(f"{entry['id']}: readable R text layer is not bound to the actual figure")
    result={audit_rel:_sha256(project/audit_rel)}
    for path in (rel,svg_rel):
        _,file=_safe_path(project,path)
        if not file.is_file() or _sha256(file)!=hashes[path]:
            raise ValueError(f"{entry['id']}: figure/text layer changed since actual rendering")
        result[path]=hashes[path]
    script=entry.get("script")
    if not script or audit.get("script")!=script:
        raise ValueError(f"{entry['id']}: figure text layer's producing script differs from the plan")
    _,file=_safe_path(project,script)
    if not file.is_file() or _sha256(file)!=audit.get("script_sha256"):
        raise ValueError(f"{entry['id']}: producing script changed since figure-text extraction")
    result[script]=audit["script_sha256"]
    sources=audit.get("source_hashes",{})
    if not sources or set(sources)!=set(entry.get("source_results",[])):
        raise ValueError(f"{entry['id']}: figure text layer does not identify the current result sources")
    for path,expected in sources.items():
        _,file=_safe_path(project,path)
        if not file.is_file() or _sha256(file)!=expected:
            raise ValueError(f"{entry['id']}: result source changed since figure-text extraction")
        result[path]=expected
    return result


def display_language_inputs(project,layer="science",final=False,report=None):
    if not display_language_enabled(project,report): return {}
    from .benchmark import display_source
    plan=load(project,"01_protocol/artifact_plan.json" if layer=="science" else "08_submission/integration/artifact_plan.json")
    result={}
    for group in ("main_figures","supp_figures"):
        for entry in plan.get(group,[]):
            result.update(_figure_text_inputs(project,entry,display_source(project,entry,layer,final)))
    return result


def display_surfaces(project,entry,layer="science",final=False):
    """Actual visible cell/text locations, including all supplementary display items."""
    from .benchmark import display_source
    rel=display_source(project,entry,layer,final)
    _,file=_safe_path(project,rel)
    if file.suffix.lower()==".xlsx":
        from openpyxl import load_workbook
        book=load_workbook(file,read_only=True,data_only=False)
        try:
            return rel,[(f"{sheet.title}!{cell.coordinate}",str(cell.value)) for sheet in book
                        for row in sheet for cell in row if cell.value is not None]
        finally: book.close()
    if file.suffix.lower() in {".png",".tif",".tiff",".jpg",".jpeg"}:
        evidence=_figure_text_inputs(project,entry,rel)
        candidates=[path for path in evidence if path.endswith(".render.svg")]
        if not candidates: return rel,[]
        file=project/candidates[0];rel=candidates[0]
    if file.suffix.lower()==".svg":
        return rel,_svg_surfaces(file)
    text=visible(file)
    return rel,[(f"extracted line {i}",line) for i,line in enumerate(text.splitlines(),1) if line.strip()]


def _svg_surfaces(path):
    import xml.etree.ElementTree as ET
    result=[]
    def hidden(node):
        tag=node.tag.rsplit("}",1)[-1]
        style=node.get("style","")
        return (tag in {"metadata","defs","clipPath","mask","script","style","title","desc"} or
                node.get("display")=="none" or node.get("visibility") in {"hidden","collapse"} or
                node.get("opacity") in {"0","0.0","0.00"} or node.get("fill-opacity") in {"0","0.0","0.00"} or
                re.search(r"(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)|(?:^|;)\s*(?:fill-)?opacity\s*:\s*0(?:\.0+)?\s*(?:;|$))",style,re.I))
    def content(node):
        if hidden(node): return ""
        return (node.text or "")+"".join(content(child)+(child.tail or "") for child in node)
    def walk(node):
        tag=node.tag.rsplit("}",1)[-1]
        if hidden(node): return
        if tag=="text":
            text=content(node).strip()
            if text: result.append((f"SVG text {len(result)+1}",text))
        else:
            for child in node: walk(child)
    walk(ET.fromstring(path.read_bytes()))
    return result


def _word_table_surfaces(path):
    import zipfile
    import xml.etree.ElementTree as ET
    ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root=ET.fromstring(archive.read("word/document.xml"))
    result=[]
    for index,table in enumerate(root.findall(".//w:tbl",ns),1):
        for row_index,row in enumerate(table.findall("w:tr",ns),1):
            for column,cell in enumerate(row.findall("w:tc",ns),1):
                text=" ".join("".join(t.text or "" for t in p.findall(".//w:t",ns)) for p in cell.findall("w:p",ns)).strip()
                if text: result.append((f"Word table {index}, row {row_index}, cell {column}",text))
    return result


def _dictionary_patterns(dictionary):
    groups={}
    for row in dictionary:
        for internal in (row["key"],row["internal"]):
            if (not re.fullmatch(r"[+\-−]?(?:\d+(?:\.\d+)?|\.\d+)",internal) and
                    internal.casefold()!=row["label"].casefold()):
                groups.setdefault(internal,[]).append(row)
    return [(re.compile(r"(?<!\w)"+re.escape(internal)+r"(?!\w)",re.I),internal,rows)
            for internal,rows in groups.items()]


def diagnose_display(text,rel,locator,dictionary,patterns=None):
    findings=diagnose(text,rel)
    for finding in findings: finding["locator"]=locator
    extra=[]
    if DISPLAY_CODES.search(text):
        extra.append(("display_code_label","A code-like export/processing label needs the actual clinical variable, group, statistic or a precise local definition. Do not replace legitimate methods by keyword alone."))
    mapped=[]
    matched=[]
    for pattern,internal,rows in (_dictionary_patterns(dictionary) if patterns is None else patterns):
        if pattern.search(text):
            for row in rows:
                mapped.append(f"{internal!r} -> {row['label']!r} ({row['scope']})")
                matched.append(row)
    if mapped:
        extra.append(("display_dictionary_label","Actual display still contains declared internal wording: "+"; ".join(mapped)+". Resolve its actual source scope and clinical meaning; never guess among different source definitions or rewrite scientific states automatically."))
    for kind,message in extra:
        mapping=json.dumps(sorted(matched,key=lambda row:row["key"]),sort_keys=True) if kind=="display_dictionary_label" else ""
        identity=hashlib.sha256(f"{rel}\0{kind}\0{text.strip()}\0{mapping}".encode()).hexdigest()[:16]
        findings.append({"id":identity,"path":rel,"locator":locator,"kind":kind,"excerpt":text[:240],"message":message})
    return findings


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
        return "\n".join(text for _,text in _svg_surfaces(path))
    return ""  # no OCR inference or substituted code labels for raster figures


def _reader_lines(text):
    """Skip bibliographic titles, retaining locators and later legends/supplements."""
    in_references=False
    for line,value in enumerate(text.splitlines(),1):
        if re.fullmatch(r"\s*(?:#{1,6}\s*)?(?:References|Bibliography)\s*[:.]?\s*",value,re.I):
            in_references=True; continue
        if in_references:
            following=(re.match(r"\s*#{1,6}\s+",value) or
                       re.fullmatch(r"\s*(?:Figure legends?|Table captions?|Tables?|Figures?|Supplementary (?:Methods|Materials?|Information|Tables?|Figures?|Figure legends?)|Declarations(?: and Statements)?|Statements(?: and Declarations)?)\s*[:.]?\s*",value,re.I) or
                       re.match(r"\s*(?:Figure|Table)\s+S?\d+[.:]\s+",value,re.I))
            if not following: continue
            in_references=False
        yield line,value


def _summary_surfaces(text,rel):
    # A count note in Table 2 must not be judged against a median in Table 1 or prose.
    suffix=Path(rel).suffix.lower()
    if suffix==".xlsx":
        sheets={}
        for line in text.splitlines():
            match=re.match(r"^(.*?)!\d+: (.*)$",line)
            if match: sheets.setdefault(match[1],[]).append(match[2])
        return [(f"worksheet {name}","\n".join(lines)) for name,lines in sheets.items()]
    if suffix==".csv": return [("table summary footnote",text)]
    return []  # No reliable table boundary in flattened DOCX/PDF/manuscript text.


def diagnose(text, rel):
    findings=[]
    for line,value in _reader_lines(text):
        for kind,(pattern,message) in RULES.items():
            match=re.search(pattern,value,re.I)
            if match:
                # Hash the complete context, not the display-truncated excerpt. A change
                # late in a long paragraph must not inherit an obsolete retained reason.
                context=value.strip()
                identity=hashlib.sha256(f"{rel}\0{kind}\0{context}".encode()).hexdigest()[:16]
                start=max(0,match.start()-60); end=min(len(value),start+240)
                excerpt=("…" if start else "")+value[start:end].strip()+("…" if end<len(value) else "")
                findings.append({"id":identity,"path":rel,"locator":f"extracted line {line}","kind":kind,"excerpt":excerpt,"message":message})
    for locator,surface in _summary_surfaces(text,rel):
        if re.search(r"median|IQR|interquartile",surface,re.I) and re.search(r"values are (?:numbers|counts) of",surface,re.I) and not re.search(r"unless otherwise|except",surface,re.I):
            identity=hashlib.sha256(f"{rel}\0summary_footnote\0{locator}\0{surface}".encode()).hexdigest()[:16]
            findings.append({"id":identity,"path":rel,"locator":locator,"kind":"summary_footnote","excerpt":"mixed statistical summaries","message":"Footnote must describe the actual row summaries and available-case denominators, not claim every row is a count."})
    # One retained decision covers repeated identical risk in the same surface; locations
    # remain available without asking for duplicate justifications for the same wording.
    unique={}
    for finding in findings:
        if finding["id"] in unique:
            unique[finding["id"]].setdefault("also_at",[]).append(finding["locator"])
        else: unique[finding["id"]]=finding
    return list(unique.values())


def scan(project,layer="science",final=False,report=None):
    from .benchmark import display_source
    plan=load(project,"01_protocol/artifact_plan.json" if layer=="science" else "08_submission/integration/artifact_plan.json")
    folder="07_manuscript" if layer=="science" else "08_submission/integration"
    files=set() if final else {f"{folder}/full_manuscript.md"}
    for name in ("methods.md","results.md","discussion.md","supplementary_methods.md"):
        if not final and (project/folder/name).is_file(): files.add(f"{folder}/{name}")
    for rel in (("05_figures/legends.md","04_tables/table_captions.md") if layer=="science" else
                (f"{folder}/figure_legends.md",f"{folder}/table_captions.md")):
        if not final and (project/rel).is_file(): files.add(rel)
    extended=display_language_enabled(project,report)
    issues=[]
    dictionary=[]
    if extended:
        from .clinicalpresentation import vocabulary
        dictionary=vocabulary(project,journal=layer=="journal")
    patterns=_dictionary_patterns(dictionary)
    for group in ("main_figures","supp_figures","main_tables","supp_tables"):
        for entry in plan.get(group,[]):
            rel=display_source(project,entry,layer,final)
            if not extended:
                files.add(rel);continue
            source,surfaces=display_surfaces(project,entry,layer,final)
            for locator,text in surfaces:
                issues.extend(diagnose_display(text,source,locator,dictionary,patterns))
            if Path(rel).suffix.lower()==".xlsx":
                issues.extend(row for row in diagnose(visible(project/rel),rel) if row["kind"]=="summary_footnote")
    if final:
        for row in load(project,"08_submission/bundle/manifest.json")["items"]:
            if row.get("upload",True) and row.get("role") in {"manuscript","tables","figure_legends","supplementary"}:
                files.add(row["file"])
                if extended and Path(row["file"]).suffix.lower()==".docx":
                    _,file=_safe_path(project,row["file"])
                    for locator,text in _word_table_surfaces(file):
                        issues.extend(diagnose_display(text,row["file"],locator,dictionary,patterns))
    for rel in sorted(files):
        _,file=_safe_path(project,rel)
        if file.is_file(): issues.extend(diagnose(visible(file),rel))
    unique={}
    for issue in issues:
        if issue["id"] in unique and unique[issue["id"]]["locator"]!=issue["locator"]:
            unique[issue["id"]].setdefault("also_at",[]).append(issue["locator"])
        else: unique.setdefault(issue["id"],issue)
    return list(unique.values())


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
    observed_checks={}
    language=display_language_enabled(project,report)
    for group in ("main_figures","supp_figures","main_tables","supp_tables"):
        kind="table" if "tables" in group else "figure"
        for entry in plan.get(group,[]):
            checks=report.get("display_findings",{}).get(entry["id"],{}).get("medical_checks",{})
            for field in FIELDS[kind]:
                if not substantive(checks.get(field)): problems.append(f"{entry['id']}: describe actual {field}, not generic PASS")
            observations=tuple(re.sub(r"\s+"," ",str(checks.get(field,"")).strip()).casefold() for field in FIELDS[kind])
            if all(observations):
                if len(set(observations))==1:
                    problems.append(f"{entry['id']}: distinct medical questions need actual observations, not one copied sentence for every check")
                key=(kind,observations)
                if key in observed_checks:
                    problems.append(f"{entry['id']} and {observed_checks[key]}: all medical observations are copied; inspect each display's actual labels, measures and denominator")
                observed_checks[key]=entry['id']
            if language:
                wording=report.get("display_findings",{}).get(entry["id"],{}).get("visible_wording",{})
                quote=wording.get("quote","") if isinstance(wording,dict) else ""
                locator=wording.get("locator","") if isinstance(wording,dict) else ""
                reading=wording.get("clinical_reading","") if isinstance(wording,dict) else ""
                if not isinstance(quote,str) or len(quote.strip())<3 or not str(locator).strip() or not substantive(reading):
                    problems.append(f"{entry['id']}: quote actual visible wording at its location and state what a medical reader understands; this supplements, not replaces, the three medical checks")
                else:
                    _,surfaces=display_surfaces(project,entry,layer,final)
                    if surfaces:
                        matching=[text for location,text in surfaces if location==locator]
                        normalized=lambda text:re.sub(r"\s+"," ",text).strip()
                        if not matching or not any(normalized(quote) in normalized(text) for text in matching):
                            problems.append(f"{entry['id']}: visible wording quote/location does not match the actual current cell/text layer")
                    else:
                        # Actual raster reading remains human/agent observation. Validate
                        # real image bytes, never infer text from code, filename or metadata.
                        from .benchmark import display_source
                        from PIL import Image
                        _,image=_safe_path(project,display_source(project,entry,layer,final))
                        with Image.open(image) as opened: opened.verify()
    for issue in scan(project,layer,final,report):
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
