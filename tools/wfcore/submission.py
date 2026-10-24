"""Derive portal text and counts from final DOCX, never from draft Markdown."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json, load

REQUIREMENTS = "08_submission/submission_requirements.json"
PORTAL = "08_submission/portal_fields.json"
MANIFEST = "08_submission/bundle/manifest.json"
AUTHOR_FACTS = "00_input/author_info.json"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SECTIONS = ("Abstract", "Keywords", "Introduction", "Methods", "Results", "Discussion",
            "Conclusion", "Declarations and Statements", "References", "Figure legends")
ALIASES = {"materials and methods": "Methods", "patients and methods": "Methods",
           "statistical methods": "Methods", "conclusions": "Conclusion",
           "declarations": "Declarations and Statements", "statements": "Declarations and Statements",
           "statements and declarations": "Declarations and Statements"}


def word_count(text: str) -> int:
    """Document-text tokenizer; the method is explicit, not claimed as Word's UI count."""
    return len(re.findall(r"\b\w+(?:[’'\-]\w+)*\b", text, re.UNICODE))


def docx_sections(path: Path, aliases: dict | None = None) -> tuple[str, dict[str, str], str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    if root.find(f".//{W}del") is not None or root.find(f".//{W}ins") is not None:
        raise ValueError("final DOCX still contains tracked changes; resolve them before portal extraction")
    headings = {name.casefold(): name for name in SECTIONS}
    headings.update(ALIASES)
    headings.update(aliases or {})
    section, title, collected, all_text = "front", "", {}, []
    explicit = any((n.get(W+"name","").startswith("medpaper_section_") for n in root.iter(W+"bookmarkStart")))
    styled = any(n.get(W+"val","") in {"Heading1","SectionHeading"} for n in root.iter(W+"pStyle"))
    for paragraph in root.iter(W + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(W + "t")).strip()
        if not text:
            continue
        all_text.append(text)
        normalized = re.sub(r"^\d+(?:\.\d+)*[. ]*", "", text).strip().rstrip(":").casefold()
        markers = [n.get(W+"name","") for n in paragraph.iter(W+"bookmarkStart")]
        pstyle = paragraph.find(W+"pPr/"+W+"pStyle")
        style_id = pstyle.get(W+"val","") if pstyle is not None else ""
        structural = (any(n.startswith("medpaper_section_") for n in markers) if explicit else
                      style_id in {"Heading1","SectionHeading"} if styled else True)
        if structural and normalized in headings and (explicit or section!="Abstract" or
                headings[normalized] in ("Keywords","Introduction")):
            section = headings[normalized]
            collected.setdefault(section, [])
            continue
        if not title and section == "front":
            title = text
        if re.match(r"(?i)^key\s*words?\s*:", text):
            collected["Keywords"] = [re.sub(r"(?i)^key\s*words?\s*:\s*", "", text)]
            section = "Keywords"
            continue
        collected.setdefault(section, []).append(text)
    return title, {key: "\n".join(value) for key, value in collected.items()}, "\n".join(all_text)


def build_portal(project: Path) -> dict:
    from .journalrules import limits,compare
    requirements,rules = limits(project)
    manifest = load(project, MANIFEST)
    manuscripts = [row for row in manifest.get("items", []) if row.get("role") == "manuscript"]
    if len(manuscripts) != 1:
        raise ValueError("portal extraction needs exactly one final manuscript DOCX")
    rel, manuscript = _safe_path(project, manuscripts[0]["file"])
    if manuscript.suffix.lower() != ".docx":
        raise ValueError("portal source must be the final DOCX")
    from .journalspec import aliases, load as journal_profile
    section_aliases = {label.casefold(): key for key, label in aliases(journal_profile(project)).items()}
    section_aliases.update(requirements.get("section_aliases", {}))
    title, sections, full_text = docx_sections(manuscript, section_aliases)
    if not title or not sections.get("Abstract"):
        raise ValueError("final manuscript needs a title before an explicit Abstract heading")
    rule = requirements.get("word_count", {})
    include = rule.get("include_sections")
    if not isinstance(include, list) or not include or not rule.get("source"):
        raise ValueError("official word-count scope and source must be set at S20")
    missing = [name for name in include if name not in sections]
    if missing:
        raise ValueError("word-count sections missing from final DOCX: " + ", ".join(missing))
    counts = {name: word_count(text) for name, text in sections.items()}
    main_words = sum(counts[name] for name in include)
    abstract_words = counts.get("Abstract", 0)
    errors = compare({"main":main_words,"abstract":abstract_words},rules)
    if errors:
        raise ValueError("final DOCX: "+"; ".join(errors))
    facts = load(project, AUTHOR_FACTS)
    required_admin = ("authors", "affiliations", "corresponding", "funding", "conflicts",
                      "ethics_approval", "data_availability")
    if any(key not in facts or facts[key] in (None, "", [], {}) for key in required_admin):
        raise ValueError("administrative facts are incomplete; collect them together at S21")
    inputs = {rel: _sha256(manuscript), REQUIREMENTS: _sha256(project / REQUIREMENTS),
              AUTHOR_FACTS: _sha256(project / AUTHOR_FACTS), MANIFEST: _sha256(project / MANIFEST)}
    payload = {
        "schema_version": 1, "source_hashes": inputs,
        "title": title, "abstract": sections["Abstract"],
        "keywords": [part.strip() for part in re.split(r"[,;\n]", sections.get("Keywords", "")) if part.strip()],
        "article_type": requirements.get("article_type"),
        "word_counts": {"method": "final DOCX visible-text Unicode words; hyphenated words count as one; main section headings excluded; structured abstract subheading text included",
                        "main": main_words, "abstract": abstract_words, "all_visible": word_count(full_text),
                        "sections": counts, "included_sections": include, "rule_source": rule["source"]},
        "administrative_facts": {key: facts[key] for key in required_admin},
        "uploads": [{"role": item["role"], "file": item["file"]} for item in manifest["items"]
                    if item.get("upload", True)],
    }
    return payload


def verify_portal(project: Path) -> list[str]:
    try:
        saved, current = load(project, PORTAL), build_portal(project)
        if saved != current:
            return ["portal fields/counts are stale; rerun tools/manuscript/submission_fields.py"]
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        return [str(exc)]
    return []


def write_portal(project: Path) -> dict:
    payload = build_portal(project)
    atomic_json(project / PORTAL, payload)
    return payload
