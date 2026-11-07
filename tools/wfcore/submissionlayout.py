"""Current journal upload organization, derived from one administrative source.

Defaults reflect the user's submission convention, not a claim that every journal uses it.
Only current captured guide evidence may override them. No scientific source is edited.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .packagefreeze import _safe_path, _sha256

AUTHOR_FACTS = "00_input/author_info.json"
TARGET = "08_submission/target_journal.json"
PLAN = "08_submission/integration/artifact_plan.json"


def enabled(project: Path, target=None) -> bool:
    from .state import State, version_tuple
    target = target if target is not None else _load(project, TARGET, {})
    if "submission_layout" in target:
        return True
    state = State(project)
    return bool(target and state.exists() and version_tuple(str(state.load().data.get("engine_pin", "0"))) >= (1, 27, 0))


def _load(project, rel, default=None):
    path = project / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _evidence(project, settings, key):
    from .journalcontext import current
    from .guides import normalize
    proof = settings.get("evidence", {}).get(key)
    if not isinstance(proof, dict) or proof.get("status") != "required":
        raise ValueError(f"submission_layout.{key}: a nondefault arrangement needs an explicit required guide clause")
    context = current(project)
    try:
        source = context["sources"][proof["source_id"]]
        text = _safe_path(project, source["text"])[1]
        quote = normalize(proof["quote"])
        if (source.get("context_id") != context["context_id"] or _sha256(text) != source["text_sha256"] or
                len(quote) < 20 or quote.casefold() not in normalize(text.read_text(encoding="utf-8")).casefold() or
                len(str(proof.get("locator", "")).strip()) < 3):
            raise ValueError("missing/stale exact guide passage")
    except (KeyError, TypeError) as exc:
        raise ValueError(f"submission_layout.{key}: cite the current captured official guide") from exc
    return proof


def policy(project: Path, target=None) -> dict:
    target = target if target is not None else _load(project, TARGET, {})
    settings = target.get("submission_layout", {})
    if not isinstance(settings, dict):
        raise ValueError("submission_layout must be an object")
    figures = settings.get("figures", "separate")
    figure_legends = settings.get("figure_legends", "end")
    tables = settings.get("tables", "after_references")
    separate = settings.get("separate_title_page", False)
    if figures not in {"separate", "inline"} or figure_legends not in {"end","inline"} or tables not in {"after_references", "inline"} or type(separate) is not bool:
        raise ValueError("Use figures separate/inline, tables after_references/inline and boolean separate_title_page")
    if figures == "inline": _evidence(project, settings, "figures")
    if figure_legends == "inline": _evidence(project, settings, "figure_legends")
    if tables == "inline": _evidence(project, settings, "tables")
    if separate: _evidence(project, settings, "separate_title_page")
    filenames = settings.get("supplement_filenames", {})
    if not isinstance(filenames, dict) or any(not isinstance(k, str) or not isinstance(v, str) or Path(v).name != v for k, v in filenames.items()):
        raise ValueError("supplement_filenames must map actual item IDs/roles to safe exact filenames")
    if filenames: _evidence(project, settings, "supplement_filenames")
    return {"figures": figures, "figure_legends":figure_legends, "tables": tables,
            "separate_title_page": bool(target.get("blinded_main_manuscript")) or separate,
            "blinded": bool(target.get("blinded_main_manuscript")), "supplement_filenames": filenames}


def admin_lines(project: Path) -> list[str]:
    facts = _load(project, AUTHOR_FACTS)
    if not isinstance(facts, dict): raise ValueError("Actual author_info.json is required before submission builds")
    authors, affiliations, corresponding = facts.get("authors"), facts.get("affiliations"), facts.get("corresponding")
    if not isinstance(authors, list) or not authors or not affiliations or not isinstance(corresponding, dict):
        raise ValueError("Complete ordered authors, affiliations and corresponding-author facts at S21")
    names, orcids = [], []
    for author in authors:
        if not isinstance(author, dict): raise ValueError("Each author needs actual name and affiliation links in author_info.json")
        name = str(author.get("name") or author.get("full_name") or "").strip()
        if not name: raise ValueError("Author name missing")
        links = author.get("affiliations", author.get("affiliation_ids", []))
        if isinstance(links, (str, int)): links = [links]
        if not isinstance(links, list) or not links: raise ValueError(f"{name}: actual affiliation links required")
        names.append(name + " (" + ", ".join(map(str, links)) + ")")
        orcid = str(author.get("orcid") or author.get("ORCID") or "").strip()
        if orcid:
            orcid = re.sub(r"^https?://orcid\.org/", "", orcid)
            if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", orcid): raise ValueError(f"{name}: invalid ORCID format")
            orcids.append(f"{name}: {orcid}")
    lines = [", ".join(names)]
    if isinstance(affiliations, dict):
        rows = [(key, value) for key, value in affiliations.items()]
    elif isinstance(affiliations, list):
        rows = [(row.get("id", str(i + 1)), row) if isinstance(row, dict) else (str(i + 1), row)
                for i, row in enumerate(affiliations)]
    else: raise ValueError("affiliations must be an ordered list or ID mapping")
    ids = set()
    for key, row in rows:
        ids.add(str(key))
        if isinstance(row, dict):
            value = row.get("name") or row.get("text") or row.get("affiliation")
            if not value: value = ", ".join(str(row[k]) for k in ("department", "institution", "city", "country") if row.get(k))
        else: value = str(row)
        if not str(value).strip(): raise ValueError("Empty author affiliation")
        lines.append(str(key) + ". " + str(value))
    for author in authors:
        links = author.get("affiliations", author.get("affiliation_ids", []))
        if isinstance(links, (str, int)): links = [links]
        if any(str(link) not in ids for link in links): raise ValueError("Author links to an unknown affiliation ID")
    name = str(corresponding.get("name") or corresponding.get("full_name") or "").strip()
    email = str(corresponding.get("email") or "").strip()
    if not name or not email or "@" not in email: raise ValueError("Actual corresponding-author name and email required")
    contact = [name, *[str(corresponding[k]) for k in ("address", "phone", "telephone") if corresponding.get(k)], email]
    lines.append("Correspondence: " + "; ".join(contact))
    if orcids: lines.append("ORCID: " + "; ".join(orcids))
    extra=facts.get("title_page_fields",{})
    if not isinstance(extra,dict): raise ValueError("title_page_fields must be a map of actual required administrative fields")
    for label,value in extra.items():
        if not isinstance(label,str) or not isinstance(value,(str,int,float)) or not str(value).strip():
            raise ValueError("Title-page extra fields need actual labels/values")
        lines.append(label.rstrip(":")+": "+str(value))
    # Retain the already-supported optional reference-count field, deriving it from
    # actual citations rather than the candidate library or a second hand-entered count.
    title_source=project/"08_submission/integration/title_page.md"
    if title_source.is_file():
        from .checks.refs import declared_reference_counts,actual_reference_count
        declared=declared_reference_counts(title_source.read_text(encoding="utf-8"))
        if declared:
            if len(declared)!=1: raise ValueError("Duplicate title-page reference count")
            if not any(re.search(r"reference",label,re.I) for label in extra):
                manuscript=(project/"08_submission/integration/full_manuscript.md").read_text(encoding="utf-8")
                lines.append("Number of references: "+str(actual_reference_count(manuscript)))
    return [re.sub(r"\s+", " ", line).strip() for line in lines]


def manuscript_title(project):
    path = project/"08_submission/integration/full_manuscript.md"
    if not path.is_file(): raise ValueError("Current integration manuscript is required as the single title source")
    match=re.search(r"^#\s+(.+?)\s*$",path.read_text(encoding="utf-8"),re.M)
    if not match: raise ValueError("Current integration manuscript has no selected title")
    return match[1].strip()


def main_plan(project):
    plan = _load(project, PLAN)
    return plan if isinstance(plan, dict) else _load(project, "01_protocol/artifact_plan.json", {})


def table_entries(project):
    from openpyxl import load_workbook
    result, inputs = [], []
    plan_path = project / (PLAN if (project / PLAN).is_file() else "01_protocol/artifact_plan.json")
    if plan_path.is_file(): inputs.append(plan_path)
    for item in main_plan(project).get("main_tables", []):
        rel, path = _safe_path(project, item.get("file", ""))
        if path.suffix.lower() != ".xlsx" or not path.is_file(): raise ValueError("Each main table needs its actual XLSX source")
        sheet = item.get("sheet")
        if not sheet:
            book = load_workbook(path, read_only=True)
            try:
                if len(book.sheetnames) != 1: raise ValueError("Main table has multiple sheets; declare the actual sheet/range in --tables-json")
                sheet = book.sheetnames[0]
            finally: book.close()
        result.append({**{k: item[k] for k in ("id", "orientation", "header_start", "header_end", "body_end", "columns", "caption", "anchor") if k in item},
                       "file": rel, "sheet": sheet})
        inputs.append(path)
    return result, inputs


def _insert_before(parent, elements, anchor):
    for element in elements:
        parent.remove(element)
        anchor.addprevious(element)


def apply_front(doc, project, role, settings):
    if role not in {"manuscript", "title_page"}: return
    if role == "title_page" and not settings["separate_title_page"]:
        raise ValueError("No separate title-page upload is requested; author details belong at the start of the nonblinded manuscript")
    if role == "manuscript" and settings["blinded"]: return
    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    if not paragraphs: raise ValueError("Submission source has no title")
    title = paragraphs[0]
    if role == "title_page":
        title.text=manuscript_title(project)
        # Derived title-page prose is never another source of author identities.
        body = doc.element.body
        for node in list(body):
            if node is not title._p and node.tag.rsplit("}", 1)[-1] != "sectPr": body.remove(node)
    after = title._p
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    for index,line in enumerate(admin_lines(project)):
        p = doc.add_paragraph(line)
        marker=OxmlElement("w:bookmarkStart");marker.set(qn("w:id"),str(50000+index));marker.set(qn("w:name"),f"medpaper_admin_{index}")
        p._p.insert(0,marker)
        end=OxmlElement("w:bookmarkEnd");end.set(qn("w:id"),str(50000+index));p._p.append(end)
        after.addnext(p._p); after = p._p
    if role == "manuscript":
        # A real page break (not Shift+Enter or paragraph pageBreakBefore) keeps the
        # complete author information before the abstract without tiny fonts/truncation.
        p = doc.add_paragraph(); p.add_run().add_break(__import__("docx.enum.text", fromlist=["WD_BREAK"]).WD_BREAK.PAGE)
        after.addnext(p._p)


def place_tables(doc, project, entries, style, settings):
    from .wordtables import append_tables
    from docx.oxml.ns import qn
    body = doc.element.body
    if settings["tables"] == "after_references":
        legend = next((p._p for p in doc.paragraphs if p.text.strip().casefold() == "figure legends"), None)
        if legend is None: raise ValueError("Main tables need the final Figure legends boundary")
        before = set(body)
        append_tables(doc, project, entries, style)
        from docx.enum.section import WD_SECTION_START
        from .wordtables import _geometry
        if settings["figure_legends"]=="end":
            final=doc.add_section(WD_SECTION_START.NEW_PAGE)
            _geometry(final,"portrait",style)
        added = [node for node in body if node not in before and node.tag != qn("w:sectPr")]
        _insert_before(body, added, legend)
        # Invisible section identity stops reference/word counts before table captions.
        # A visible generic "Tables" heading is unnecessary to read these medical tables.
        caption_text=str(entries[0].get("caption") or "").strip()
        caption=next((p for p in doc.paragraphs if caption_text and p.text.strip()==caption_text),None)
        if caption is None:
            caption=next((p for p in doc.paragraphs if p.text.strip().casefold().startswith(str(entries[0]["id"]).casefold()+".")),None)
        if caption is None: raise ValueError("Actual main-table caption boundary missing")
        marker=__import__("docx.oxml",fromlist=["OxmlElement"]).OxmlElement("w:bookmarkStart")
        marker.set(qn("w:id"),"59000");marker.set(qn("w:name"),"medpaper_section_tables")
        caption._p.insert(0,marker)
        end=__import__("docx.oxml",fromlist=["OxmlElement"]).OxmlElement("w:bookmarkEnd");end.set(qn("w:id"),"59000");caption._p.append(end)
    else:
        tails={}
        for entry in entries:
            anchor_text = entry.get("anchor")
            matches = [p for p in doc.paragraphs if anchor_text and p.text.strip() == anchor_text]
            if len(matches) != 1: raise ValueError("Inline tables need one exact prose anchor per table in --tables-json")
            anchor = matches[0]._p
            before = set(body); count=len(doc.sections)
            append_tables(doc, project, [entry], style,inline=True)
            from docx.enum.section import WD_SECTION_START
            from .wordtables import _geometry
            if len(doc.sections)>count:
                final=doc.add_section(WD_SECTION_START.CONTINUOUS);_geometry(final,"portrait",style)
            added = [node for node in body if node not in before and node.tag != qn("w:sectPr")]
            # A required orientation change may still paginate in Word, but a
            # journal's inline table rule must not force empty next-page sections.
            for node in added:
                for props in node.iter(qn("w:sectPr")):
                    from docx.oxml import OxmlElement
                    kind=props.find(qn("w:type"))
                    if kind is None:kind=OxmlElement("w:type");props.append(kind)
                    kind.set(qn("w:val"),"continuous")
            after = tails.get(anchor,anchor)
            for node in added:
                body.remove(node); after.addnext(node); after = node
            tails[anchor]=after
        if settings["figure_legends"]=="end":
            # Flat headings cannot use keepNext/pageBreakBefore. A real page break
            # keeps the final caption section from stranding its heading after
            # an inline table, without inserting blank table sections.
            legend=next((p._p for p in doc.paragraphs if p.text.strip().casefold()=="figure legends"),None)
            if legend is not None:
                from docx.enum.text import WD_BREAK
                boundary=doc.add_paragraph();boundary.add_run().add_break(WD_BREAK.PAGE)
                legend.addprevious(boundary._p)


def place_figures(doc, project, settings,style):
    if settings["figures"] != "inline": return []
    from docx.shared import Inches
    inputs = []
    for entry in main_plan(project).get("main_figures", []):
        rel, path = _safe_path(project, entry.get("file", ""))
        anchor_text = entry.get("anchor")
        matches = [p for p in doc.paragraphs if anchor_text and p.text.strip() == anchor_text]
        if len(matches) != 1: raise ValueError("Inline figures need one exact prose anchor per figure in the journal artifact plan")
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}: raise ValueError("Inline Word figure needs the actual raster preview; retain its separate publication master")
        width = (8.5 if str(style["paper_size"]).upper()=="LETTER" else 8.2677)-2*float(style["margins_in"])
        p = doc.add_paragraph(); p.add_run().add_picture(str(path), width=Inches(width))
        matches[0]._p.addnext(p._p); inputs.append(path)
    return inputs


def place_legends(doc,project,settings):
    """Move captions, not image files; explicit caption instructions are independent."""
    if settings["figure_legends"]!="inline": return
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    paragraphs=list(doc.paragraphs)
    start=next((i for i,p in enumerate(paragraphs) if p.text.strip().casefold()=="figure legends"),None)
    if start is None: raise ValueError("Canonical Figure legends source is missing")
    blocks=[];current=None
    for p in paragraphs[start+1:]:
        match=re.match(r"^(Figure\s+S?\d+)\.?\s*(.*)$",p.text.strip(),re.I)
        if match:
            current={"id":re.sub(r"\s+"," ",match[1]),"paragraphs":[]};blocks.append(current)
        if current: current["paragraphs"].append(p)
        elif p.text.strip(): raise ValueError("Cannot identify actual figure caption boundary")
    if not blocks: raise ValueError("No actual figure captions to place")
    plan=main_plan(project)
    entries={e["id"].casefold():e for group in ("main_figures","supp_figures") for e in plan.get(group,[])}
    tails={}
    for index,block in enumerate(blocks):
        entry=entries.get(block["id"].casefold())
        if entry is None: raise ValueError("Inline caption has no corresponding actual planned figure")
        anchor=entry.get("legend_anchor")
        candidates=[p for p in paragraphs[:start] if anchor and p.text.strip()==anchor]
        if len(candidates)!=1: raise ValueError("Inline captions need one exact first-citation paragraph as legend_anchor in the journal artifact plan")
        # Each caption paragraph is tagged structurally; no hidden/white text or
        # machine tokens are inserted into the actual manuscript's visible content.
        anchor_node=candidates[0]._p
        after=tails.get(anchor_node,anchor_node)
        for j,p in enumerate(block["paragraphs"]):
            marker=OxmlElement("w:bookmarkStart");marker.set(qn("w:id"),str(60000+index*100+j))
            marker.set(qn("w:name"),f"medpaper_caption_{index}_{j}")
            p._p.insert(0,marker)
            end=OxmlElement("w:bookmarkEnd");end.set(qn("w:id"),str(60000+index*100+j));p._p.append(end)
            after.addnext(p._p);after=p._p
        tails[anchor_node]=after
    paragraphs[start]._p.getparent().remove(paragraphs[start]._p)


def inline_legends(project):
    return enabled(project) and policy(project)["figure_legends"]=="inline"


def caption_problems(doc,expected,cap=None):
    from docx.oxml.ns import qn
    blocks=[];current=[]
    for p in doc.paragraphs:
        markers=[n.get(qn("w:name"),"") for n in p._p.iter(qn("w:bookmarkStart"))]
        marker=next((m for m in markers if m.startswith("medpaper_caption_")),None)
        if not marker: continue
        if marker.endswith("_0"):
            if current: blocks.append(current)
            current=[]
        current.append(p.text.strip())
    if current: blocks.append(current)
    ids=[];problems=[]
    for block in blocks:
        match=re.match(r"^(Figure\s+S?\d+)\b",block[0],re.I)
        if not match: problems.append("Inline caption lacks a figure identifier");continue
        ids.append(re.sub(r"\s+"," ",match[1]).casefold())
        content=" ".join(block)
        if len(content)<40: problems.append("Inline figure caption lacks sufficient decoding text")
        if cap is not None and len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b",content))>cap:
            problems.append("Inline figure caption exceeds the actual journal word limit")
    wanted=[re.sub(r"\s+"," ",x).casefold() for x in expected]
    if sorted(ids)!=sorted(wanted): problems.append("Inline caption inventory differs from planned figure identifiers")
    return problems


def docx_problems(path, project, role):
    if not enabled(project): return []
    from docx import Document
    from docx.oxml.ns import qn
    doc = Document(path); settings = policy(project); problems = []
    if role in {"manuscript", "title_page"}:
        texts = [p.text.strip() for p in doc.paragraphs]
        from .journalspec import aliases, load as journal_profile
        labels=aliases(journal_profile(project))
        if role == "title_page" and not settings["separate_title_page"]: problems.append("unexpected separate title-page upload")
        if role == "title_page" or not settings["blinded"]:
            try:
                expected = admin_lines(project)
                front = texts[:next((i for i, t in enumerate(texts) if t.casefold() == labels.get("Abstract","Abstract").casefold()),len(texts))]
                if any(front.count(line) != 1 for line in expected): problems.append("author information is missing, duplicated or differs from author_info.json")
            except (OSError, ValueError) as exc: problems.append(str(exc))
        if role == "manuscript":
            if settings["figures"] == "separate" and doc.inline_shapes: problems.append("figures are embedded although the current guide does not require inline figures")
            body = list(doc.element.body)
            refs_p = next((p._p for p in doc.paragraphs if p.text.strip().casefold()==labels.get("References","References").casefold()),None)
            legend_p = next((p._p for p in doc.paragraphs if p.text.strip().casefold()==labels.get("Figure legends","Figure legends").casefold()),None)
            references=body.index(refs_p) if refs_p is not None else None
            legends=body.index(legend_p) if legend_p is not None else None
            if settings["tables"] == "after_references":
                tables=[i for i,n in enumerate(body) if n.tag==qn("w:tbl")]
                end=legends if settings["figure_legends"]=="end" else len(body)
                if tables and (references is None or end is None or any(not references<i<end for i in tables)):
                    problems.append("main tables must follow References and precede final Figure legends")
                expected_ids={str(e.get("id")) for e in main_plan(project).get("main_tables",[])}
                actual_ids={t._tbl.tblPr.find(qn("w:tblCaption")).get(qn("w:val")).removeprefix("medpaper-threeline:")
                            for t in doc.tables if t._tbl.tblPr.find(qn("w:tblCaption")) is not None}
                if expected_ids != actual_ids: problems.append("main table inventory differs from the current journal artifact plan")
    return problems


def supplemental_name(sequence, description, suffix):
    if type(sequence) is not int or sequence < 1: raise ValueError("Positive supplemental sequence required")
    description = re.sub(r"[^A-Za-z0-9]+", "_", description).strip("_")
    if not description or not re.search(r"[A-Za-z]", description): raise ValueError("A meaningful supplemental description is required")
    return f"Supplemental_File_{sequence}_{description}.{suffix.lstrip('.')}"


def _supplement(item):
    return bool(str(item.get("role", "")).startswith(("supplement", "supp_")) or item.get("supplemental") is True or
                re.search(r"\b(?:Figure|Table)\s+S\d+", str(item.get("id", item.get("artifact_id",""))), re.I) or
                any(str(p).startswith("04_tables/supplementary/") for p in item.get("source_files",[])) or
                Path(str(item.get("file",""))).name.startswith("Supplemental_File_"))


def manifest_problems(project, manifest):
    if not enabled(project): return []
    settings=policy(project); items=[i for i in manifest.get("items",[]) if i.get("upload",True) is not False]
    problems=[]
    manuscripts=[i for i in items if i.get("role")=="manuscript"]
    if manuscripts:
        titlepages=[i for i in items if i.get("role")=="title_page"]
        if len(titlepages)!=(1 if settings["separate_title_page"] else 0): problems.append("title-page upload count differs from current blinding/explicit guide requirement")
        if len(manuscripts)==1 and len(titlepages)==1:
            from docx import Document
            main_path=_safe_path(project,manuscripts[0]["file"])[1]
            page_path=_safe_path(project,titlepages[0]["file"])[1]
            if main_path.is_file() and page_path.is_file():
                main_title=next((p.text.strip() for p in Document(main_path).paragraphs if p.text.strip()),"")
                page_title=next((p.text.strip() for p in Document(page_path).paragraphs if p.text.strip()),"")
                if main_title!=page_title: problems.append("main manuscript and separate title page have different titles")
        expected_figures={str(i.get("id")) for i in main_plan(project).get("main_figures",[])}
        uploaded={str(i.get("id",i.get("artifact_id"))) for i in items if i.get("role") in {"figure","main_figure"}}
        if settings["figures"]=="separate" and not expected_figures<=uploaded:
            problems.append("separate main figure upload missing; declare each actual planned figure ID in manifest")
    numbers=[]
    for item in items:
        if not _supplement(item): continue
        name=Path(item.get("file","")).name; key=item.get("id") or item.get("role")
        mandated=settings["supplement_filenames"].get(key)
        if mandated:
            if name!=mandated: problems.append(f"{name}: filename differs from explicit guide requirement")
            continue
        match=re.fullmatch(r"Supplemental_File_([1-9]\d*)_([A-Za-z][A-Za-z0-9_]+)\.[A-Za-z0-9]+",name)
        if not match: problems.append(f"{name}: use numbered descriptive Supplemental_File_<n>_<description> naming")
        else: numbers.append(int(match[1]))
    if len(numbers)!=len(set(numbers)) or (numbers and sorted(numbers)!=list(range(1,len(numbers)+1))):
        problems.append("supplemental file sequence must be unique and consecutive")
    return problems


def required_roles(project):
    requirements=_load(project,"08_submission/submission_requirements.json",{})
    if not enabled(project): return requirements.get("required_upload_roles",["manuscript","title_page","cover_letter"])
    settings=policy(project)
    roles=requirements.get("required_upload_roles",["manuscript","cover_letter"])
    if "title_page" in roles and not settings["separate_title_page"]:
        raise ValueError("A separate title-page upload needs actual blinding or an explicit current-guide layout requirement")
    return list(dict.fromkeys([*roles,*(["title_page"] if settings["separate_title_page"] else [])]))
