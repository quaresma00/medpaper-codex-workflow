"""Selected-journal presentation settings. No unsourced numeric caps or global CSL edits."""
from __future__ import annotations
import json
import re
from pathlib import Path

SPELLINGS = {"colour": "color", "colours": "colors", "centre": "center", "centres": "centers",
             "analyse": "analyze", "analysed": "analyzed", "analyses": "analyses", "analysing": "analyzing",
             "randomised": "randomized", "randomisation": "randomization", "tumour": "tumor",
             "haemoglobin": "hemoglobin", "modelling": "modeling", "modelled": "modeled"}


def load(project: Path) -> dict:
    path = project / "08_submission/target_journal.json"
    if not path.is_file(): return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError("target_journal.json must be an object")
    return value


def aliases(target: dict) -> dict:
    value = target.get("main_text_headings", {})
    if not isinstance(value, dict) or any(key not in {"Abstract", "Introduction", "Methods", "Results", "Discussion", "Conclusion", "Declarations and Statements", "References", "Figure legends"}
                                         or not isinstance(label, str) or not label.strip() for key, label in value.items()):
        raise ValueError("main_text_headings must map canonical body sections to actual journal labels")
    if len({label.casefold() for label in value.values()}) != len(value):
        raise ValueError("journal heading labels must be unique")
    return value


def spelling(text: str, system: str) -> str:
    if not system: return text
    system = system.casefold().strip()
    if system.startswith(("american", "us ")) or system in {"us", "en-us"}: system = "american"
    elif system.startswith(("british", "uk ")) or system in {"uk", "en-gb"}: system = "british"
    if system not in {"american", "british"}: raise ValueError("spelling must be american or british")
    mapping = SPELLINGS if system == "american" else {v: k for k, v in SPELLINGS.items() if k != v}
    def replace(match):
        word = match.group(); replacement = mapping.get(word.casefold(), word)
        return replacement.upper() if word.isupper() else replacement.capitalize() if word.istitle() else replacement
    return re.sub(r"\b(?:" + "|".join(re.escape(word) for word in mapping) + r")\b", replace, text, flags=re.I)


def number_text(text: str, config: dict) -> str:
    # No rounding. Separators/leading-zero only, never IDs, DOI, version strings or dates.
    if not config: return text
    separator = config.get("thousands")
    if separator == "thin": separator = "\u2009"
    if separator not in {None, "", ",", " ", "\u2009", "\u202f"}: raise ValueError("unsupported thousands separator")
    if config.get("decimal", ".") != ".": raise ValueError("medical decimal point must remain '.'; resolve an explicit journal exception first")
    pattern = r"(?<![\w./\-])([+\-−]?)(\d{1,3}(?:,\d{3})+|\d{4,})(\.\d+)?(?![\w./\-])"
    def format_number(match):
        if separator is None: return match[0]
        digits = match[2].replace(",", "")
        if not match[3] and 1900 <= int(digits) <= 2100 and not re.search(r"[nN]\s*=\s*$", text[:match.start()]): return match[0]
        grouped = separator.join([digits[:len(digits)%3]] + [digits[i:i+3] for i in range(len(digits)%3, len(digits), 3)]).lstrip(separator) if separator else digits
        return match[1] + grouped + (match[3] or "")
    text = re.sub(pattern, format_number, text)
    if config.get("leading_zero", True): text = re.sub(r"(?<![\w.])([+\-−]?)\.(\d+)", r"\g<1>0.\2", text)
    if config.get("p_space") is not None:
        text = re.sub(r"([<≤>≥])\s*(?=\d)", lambda match: match[1] + (" " if config["p_space"] else ""), text)
    if config.get("minus") == "unicode": text = re.sub(r"(?<!\w)-(?=\d)", "−", text)
    elif config.get("minus") == "hyphen": text = text.replace("−", "-")
    elif config.get("minus") is not None: raise ValueError("minus must be unicode or hyphen")
    if config.get("interval") is not None:
        interval = config["interval"]
        if interval not in {" to ", "–", " – "}: raise ValueError("interval must be ' to ' or an en-dash")
        text = re.sub(r"(?<=\d)\s*(?:to|–)\s*(?=[+\-−]?\d)", interval, text)
    return text


def label_text(text: str, project: Path, *, format_numbers=True) -> str:
    target = load(project)
    from .state import State
    state = State(project)
    system = target.get("spelling") or state.config().get("targets", {}).get("spelling", "")
    from .clinicalpresentation import label,profile
    journal=(project/"08_submission/integration/artifact_plan.json").is_file() and state.exists() and state.load().current.startswith(("S20_","S21_","S22_","S23_","S24_","S25_"))
    text=label(text,project,journal=journal)
    text=spelling(text,system)
    return number_text(text,target.get("number_format") or profile(project,journal).get("number_format", {})) if format_numbers else text


def admin_scrub(text: str, project: Path, rel: str) -> str:
    path = project / "00_input/author_info.json"
    if not path.is_file(): return text
    identifiers = []
    def collect(value, key=""):
        if isinstance(value, dict):
            for name, item in value.items(): collect(item, key + "." + name)
        elif isinstance(value, list):
            for item in value: collect(item, key)
        elif isinstance(value, str) and re.search(r"ethic|irb|approval|grant|registration", key, re.I) and re.search(r"\d", value): identifiers.append(value)
    collect(json.loads(path.read_text(encoding="utf-8")))
    def clean(block):
        for identifier in sorted(identifiers, key=len, reverse=True): block = block.replace(identifier, " ")
        return block
    if Path(rel).name in {"title_page.md", "statements.md"}: return clean(text)
    return re.sub(r"(?ms)^#{1,3}\s+(?:Declarations(?: and Statements)?|Ethics(?: approval| statement)?)\s*\n.*?(?=^#{1,3}\s|\Z)",
                  lambda match: clean(match.group()), text)


def identities(project: Path) -> list[str]:
    path = project / "00_input/author_info.json"
    if not path.is_file(): return []
    value = json.loads(path.read_text(encoding="utf-8")); result = []
    for author in value.get("authors", []):
        if isinstance(author, str): result.append(author)
        elif isinstance(author, dict):
            result += [str(author[key]) for key in ("name", "full_name", "email") if author.get(key)]
    corresponding = value.get("corresponding", {})
    if isinstance(corresponding, dict): result += [str(corresponding[key]) for key in ("name", "email") if corresponding.get(key)]
    return sorted({name.strip() for name in result if len(name.strip()) >= 4})


def blind_problems(path: Path, project: Path, role: str) -> list[str]:
    if not load(project).get("blinded_main_manuscript") or role in {"title_page", "cover_letter", "coi_forms", "statements"}: return []
    import zipfile
    from xml.etree import ElementTree as ET
    with zipfile.ZipFile(path) as archive:
        text = "\n".join(" ".join(ET.fromstring(archive.read(name)).itertext()) for name in archive.namelist()
                         if name.endswith(".xml") and (name.startswith("docProps/") or re.fullmatch(r"word/(document|header\d+|footer\d+|comments|footnotes|endnotes)\.xml", name)))
    return [f"{path.name}: review-facing author identity remains ({identity})" for identity in identities(project) if identity.casefold() in text.casefold()]


def apply_docx(doc, target: dict, role: str) -> None:
    if role=="manuscript" and "line_numbers" in target:
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        if type(target["line_numbers"]) is not bool: raise ValueError("line_numbers must be the journal's explicit boolean requirement")
        for section in doc.sections:
            for node in list(section._sectPr.findall(qn("w:lnNumType"))): section._sectPr.remove(node)
            if target["line_numbers"]:
                node=OxmlElement("w:lnNumType"); node.set(qn("w:countBy"),"1"); node.set(qn("w:restart"),"continuous")
                section._sectPr.insert_element_before(node,"w:pgNumType","w:cols","w:formProt","w:vAlign","w:noEndnote","w:titlePg","w:textDirection","w:bidi","w:rtlGutter","w:docGrid","w:printerSettings","w:sectPrChange")
    heads = aliases(target); keywords = target.get("keywords", {})
    separator = keywords.get("separator", ", ")
    if separator not in {",", ", ", ";", "; "}: raise ValueError("keyword separator must be a sourced comma or semicolon")
    if target.get("blinded_main_manuscript") and role not in {"title_page", "cover_letter", "coi_forms", "statements"}:
        doc.core_properties.author = ""; doc.core_properties.last_modified_by = ""
    for paragraph in doc.paragraphs:
        name = paragraph.style.name if paragraph.style else ""
        if re.match(r"Heading [1-9]$", name) and paragraph.text in heads: paragraph.text = heads[paragraph.text]
        if paragraph.text.strip().casefold().startswith("keywords:"):
            terms = [term.strip() for term in re.split(r"[,;]", paragraph.text.split(":", 1)[1]) if term.strip()]
            for key, passes in (("min", lambda count, limit: count >= limit), ("max", lambda count, limit: count <= limit)):
                limit = keywords.get(key)
                if limit is not None and (type(limit) is not int or not passes(len(terms), limit)):
                    raise ValueError(f"actual keywords violate journal keywords.{key}")
            paragraph.text = "Keywords: " + separator.join(terms)
        if role not in {"title_page", "cover_letter", "statements", "coi_forms"} and name != "Bibliography":
            for run in paragraph.runs:
                run.text = number_text(spelling(run.text, target.get("spelling", "")), target.get("number_format", {}))


def docx_problems(path: Path, target: dict, project: Path, role: str) -> list[str]:
    from docx import Document
    doc = Document(path); problems = []
    if role == "manuscript":
        if "line_numbers" in target:
            from docx.oxml.ns import qn
            for section in doc.sections:
                nodes=section._sectPr.findall(qn("w:lnNumType"))
                expected=target["line_numbers"]
                if type(expected) is not bool or (expected and (len(nodes)!=1 or nodes[0].get(qn("w:countBy"))!="1" or nodes[0].get(qn("w:restart"))!="continuous")) or (expected is False and nodes):
                    problems.append("actual Word line numbering differs from explicit journal requirement")
        actual = {paragraph.text.strip() for paragraph in doc.paragraphs}
        for canonical, label in aliases(target).items():
            if canonical not in {"Introduction","Methods","Results","Discussion","Conclusion"}: continue
            if label not in actual: problems.append(f"journal body heading missing: {label}")
        for paragraph in doc.paragraphs:
            if paragraph.text.strip().casefold().startswith("keywords:"):
                value = paragraph.text.split(":", 1)[1].strip(); config = target.get("keywords", {})
                terms = [part.strip() for part in re.split(r"[,;]", value) if part.strip()]
                if any((key == "min" and len(terms) < limit) or (key == "max" and len(terms) > limit)
                       for key, limit in config.items() if key in {"min", "max"} and limit is not None):
                    problems.append("actual Word keyword count violates selected journal")
                separator = config.get("separator", ", ").strip()
                if (separator == ";" and "," in value) or (separator == "," and ";" in value): problems.append("actual Word keyword separator differs from journal")
    problems += blind_problems(path, project, role)
    return problems
