"""A small, display-free writing context and targeted Discussion diagnostics.

The executor prepares supported explanations before drafting; these checks do not
invent mechanisms, judge a bias direction, or certify medical argument quality.
"""
from __future__ import annotations

import json
import hashlib
import re
from difflib import SequenceMatcher
from pathlib import Path

from . import buildproof
from .packagefreeze import _safe_path, _sha256
from .readiness import load

MATERIALS = ".wf/discussion_materials.md"
OUTLINE = ".wf/discussion_outline.md"
DISCUSSION = "07_manuscript/discussion.md"
RESULTS = "07_manuscript/results.md"
OUTLINE_ROLES = {
    "Principal finding": {"principal finding", "main finding", "主要发现"},
    "Comparison with prior work and reasons for differences": {
        "comparison with prior work and reasons for differences", "comparison with prior studies",
        "prior comparisons", "既往研究比较及差异原因"},
    "Possible mechanisms": {"possible mechanisms", "mechanisms", "possible explanations", "可能机制"},
    "Clinical implications": {"clinical implications", "clinical meaning", "clinical relevance", "临床意义"},
    "Limitations and direction of bias": {"limitations and direction of bias", "limitations and bias direction", "局限性及偏倚方向"},
    "Conclusion": {"conclusion", "结论"},
}
NARRATIVE_NOTE_TITLES = {
    "discussion points", "comparison with prior work", "comparison with prior studies", "prior comparisons",
    "possible mechanisms", "mechanisms", "possible explanations", "interpretation",
    "limitations and direction of bias", "limitations and bias direction", "limitations",
}
_PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|fill here|insert here|same as above)\b|<(?:TODO|TBD|insert|fill|replace|finding|comparison|mechanism|limitation|conclusion|text)\b[^>]*>|\[\s*\]", re.I)
_CITE = re.compile(r"\[[^\]]*@[^\]]*\]")
_SUPP = re.compile(r"\b(?:(?:supplementary|supplemental)\s+(?:fig(?:ure)?s?|tables?)\.?\s*S?\d+[A-Za-z]?|(?:fig(?:ure)?s?|tables?)\.?\s*S\d+[A-Za-z]?)\b", re.I)


def _sections(text):
    matches = list(re.finditer(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", text, re.M))
    out = []
    for i, match in enumerate(matches):
        end = next((m.start() for m in matches[i+1:] if len(m[1]) <= len(match[1])), len(text))
        out.append((match[2].casefold(), text[match.end():end].strip()))
    return out


def notes_outside_discussion_hash(text):
    """Bind every other note section before a scoped narrative-only revision."""
    headings = list(re.finditer(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", text, re.M))
    covered = []
    for i, heading in enumerate(headings):
        if heading[2].casefold() not in NARRATIVE_NOTE_TITLES: continue
        end = next((m.start() for m in headings[i+1:] if len(m[1]) <= len(heading[1])), len(text))
        covered.append((heading.start(), end))
    kept, cursor = [], 0
    for start, end in covered:
        if start > cursor: kept.append(text[cursor:start])
        cursor = max(cursor, end)
    kept.append(text[cursor:])
    outside = "".join(kept)
    return hashlib.sha256(outside.encode("utf-8")).hexdigest()


def _part(text, titles):
    sections = _sections(text)
    for title in titles:
        value = next((value for name, value in sections if name == title.casefold()), "")
        if value:
            # The generic parent is a fallback, not permission to duplicate all its
            # mechanism/limitations child sections in the comparison material.
            if title.casefold() == "discussion points":
                value = re.split(r"(?m)^\s{0,3}#{1,6}\s+", value, maxsplit=1)[0]
            if value.strip(): return value
    return ""


def clean_material(text):
    """Remove display payload and identifiers, never recalculate or rewrite findings."""
    from .checks.numbers import ARTIFACT_RE
    text = re.sub(r"```.*?```", "", str(text), flags=re.S)
    text = re.sub(r"<table\b.*?</table\s*>", "", text, flags=re.I | re.S)
    lines = text.splitlines(); removed = set()
    for i, line in enumerate(lines):
        if re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*", line):
            j = max(0, i-1)
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                removed.add(j); j += 1
    text = "\n".join(line for i, line in enumerate(lines) if i not in removed)
    text = ARTIFACT_RE.sub("", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+.*$", "", text)
    text = re.sub(r"\(\s*\)|\[\s*\]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", text).strip()
    return text


def _populated(value):
    plain = re.sub(r"^[\s>*+-]+", "", str(value)).strip()
    return bool(plain and not _PLACEHOLDER.search(plain) and plain.casefold() not in {
        "n/a", "na", "not applicable", "discuss findings", "compare studies", "explain mechanisms",
        "discuss limitations", "write conclusion", "unknown", "pending"})


def enabled(project):
    from .state import State, version_tuple
    state = State(project)
    version = state.load().data if state.exists() else {}
    return (version_tuple(str(version.get("engine_pin", version.get("pipeline_version", "0")))) >= (1, 27, 0)
            or (project / MATERIALS).exists() or (project / OUTLINE).exists())


def prepare(project):
    """Create the writer's plain-language packet from actual existing notes.

    Missing interpretations stay missing; the executor must prepare them from evidence.
    No Results file, workbook, figure, artifact plan or internal revision log is included.
    """
    project = Path(project).resolve()
    notes_path = _safe_path(project, "03_analysis/notes.md")[1]
    facts_path = _safe_path(project, "01_protocol/study_facts.json")[1]
    index_path = _safe_path(project, "06_refs/deepread/deepread_index.json")[1]
    results_path = _safe_path(project, RESULTS)[1]
    notes = notes_path.read_text(encoding="utf-8")
    facts = load(project, "01_protocol/study_facts.json")
    for field in ("main_finding", "clinical_relevance", "cannot_claim"):
        if not isinstance(facts.get(field), str):
            raise ValueError(f"study_facts.{field} must be the actual plain-language narrative, not a JSON result/metadata dump")
    selected = load(project, "06_refs/deepread/deepread_index.json").get("selected", [])
    # Current Results is a backstage identity dependency, never writer payload.
    sources = [notes_path, facts_path, index_path, results_path, Path(__file__)]
    comparisons = [_part(notes, ("Comparison with prior work", "Comparison with prior studies", "Prior comparisons", "Discussion points"))]
    for row in selected:
        key = row.get("citekey", "")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Deep-read selection needs its actual citekey")
        rel, note = _safe_path(project, row.get("notes", ""))
        if not rel.startswith("06_refs/deepread/") or not note.is_file():
            raise ValueError(f"{key}: actual registered deep-read notes are missing")
        comparison = _part(note.read_text(encoding="utf-8"), (
            "How this supports or contradicts our finding", "Discussion use", "Comparison with our study"))
        if not _populated(clean_material(comparison)):
            raise ValueError(f"{key}: write an actual comparison point in the existing deep-read notes")
        comparisons.append(f"[@{key}] {comparison}")
        sources.append(note)
    data = {
        "Principal finding": facts["main_finding"],
        "Comparison with prior studies": "\n\n".join(x for x in comparisons if x),
        "Possible explanations": _part(notes, ("Possible mechanisms", "Mechanisms", "Possible explanations", "Interpretation")),
        "Clinical meaning": facts["clinical_relevance"],
        "Limitations and direction of bias": _part(notes, ("Limitations and direction of bias", "Limitations and bias direction", "Limitations")),
        "Limits on conclusion": facts["cannot_claim"],
    }
    data = {key: clean_material(value) for key, value in data.items()}
    missing = [key for key, value in data.items() if not _populated(value)]
    if missing:
        raise ValueError("Prepare supported narrative material in existing study_facts/notes first: " + "; ".join(missing) +
                         ". A scientifically supported explanation that mechanism/bias direction cannot be determined is valid; do not invent one.")
    packet = "# Discussion writing materials\n\n" + "\n\n".join(f"## {key}\n\n{value}" for key, value in data.items()) + "\n"
    defects = material_problems(packet)
    if defects: raise ValueError("; ".join(defects))
    output = project / MATERIALS; output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    try:
        temporary.write_text(packet, encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    buildproof.record(project, output, sources, entrypoints=[notes_path, facts_path, index_path],
                      tool="discussion_materials", parameters={"schema": 1})
    return {"materials": MATERIALS, "outline": OUTLINE, "source_files": len(sources)-1}


def material_problems(text):
    from .checks.numbers import ARTIFACT_RE
    problems = []
    if ARTIFACT_RE.search(text): problems.append("Discussion writer materials must not contain figure/table identifiers")
    if re.search(r"<table\b|^\s*\|.*\|\s*$|```", text, re.I | re.M):
        problems.append("Discussion writer materials contain a table/code payload")
    if re.search(r"(?:03_analysis|04_tables|05_figures|\.wf)[/\\]", text):
        problems.append("Discussion writer materials contain an internal file path")
    if _PLACEHOLDER.search(text): problems.append("Discussion writer materials contain an unresolved placeholder")
    return problems


def outline_problems(text):
    values = {}; current = None; duplicates = set()
    for line in text.splitlines():
        title = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        bullet = re.match(r"^\s*(?:[-*+]\s+)?([^:\n]+):\s*(.*)$", line)
        label = (title[1] if title else bullet[1] if bullet else "").casefold().strip()
        role = next((key for key, aliases in OUTLINE_ROLES.items() if label in aliases), None)
        if role:
            if role in values: duplicates.add(role)
            values.setdefault(role, []); current = role
            if bullet and bullet[2]: values[role].append(bullet[2])
        elif current and line.strip():
            values[current].append(line.strip())
    problems = material_problems(text)
    problems.extend(f"Discussion outline missing a concrete point: {key}" for key in OUTLINE_ROLES
                if not _populated(" ".join(values.get(key, []))))
    problems.extend(f"Discussion outline repeats role: {key}" for key in sorted(duplicates))
    return problems


def _receipt_current(project, rel, tool):
    row = buildproof.load(project).get(rel)
    if not row or row.get("tool") != tool:
        return False
    path = project / rel
    return path.is_file() and row.get("sha256") == _sha256(path) and buildproof.inputs_current(row)


def bind_outline(project):
    project = Path(project).resolve()
    if not _receipt_current(project, MATERIALS, "discussion_materials"):
        raise ValueError("Prepare the actual current Discussion materials first")
    path = project / OUTLINE
    problems = outline_problems(path.read_text(encoding="utf-8"))
    if problems: raise ValueError("; ".join(problems))
    if not _receipt_current(project, OUTLINE, "discussion_outline"):
        buildproof.record(project, path, [project/MATERIALS, Path(__file__)], entrypoints=[project/MATERIALS],
                          tool="discussion_outline", parameters={"schema": 1})
    return {"outline": OUTLINE, "materials": MATERIALS}


def _chapter(text, name, *, alias=None, required=False):
    # Composed manuscripts use actual top-level headings; Abstract's Results is not main Results.
    headings = list(re.finditer(r"^#\s+(.+?)\s*$", text, re.M))
    if not headings and not required: return text, None
    # Markdown can remain canonical while the final Word uses journal aliases.
    for title in (name, alias):
        if not title: continue
        for i, heading in enumerate(headings):
            if heading[1].casefold() == title.casefold():
                end = headings[i+1].start() if i+1 < len(headings) else len(text)
                return text[heading.end():end], heading[1].casefold()
    raise ValueError(f"Current manuscript has no top-level {name} section")


def _sentences(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+.*$", " ", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])|\n\s*\n", text) if s.strip()]


def _words(text):
    from .checks.numbers import ARTIFACT_RE
    text = ARTIFACT_RE.sub(" ", _CITE.sub(" ", text))
    return re.findall(r"[a-z]+(?:[-'][a-z]+)?|\d+(?:\.\d+)?", text.casefold())


def diagnose(discussion, results, *, headings=None, require_sections=False):
    """Conservative structural flags, not an automatic clinical review."""
    names = headings or {}
    discussion, discussion_title = _chapter(discussion, "Discussion", alias=names.get("Discussion"), required=require_sections)
    results, results_title = _chapter(results, "Results", alias=names.get("Results"), required=require_sections)
    if require_sections and discussion_title == results_title:
        raise ValueError("Discussion and Results must resolve to distinct sections; a merged chapter needs an explicit passage mapping, not self-comparison")
    sentences = _sentences(discussion); original = [(s, _words(s)) for s in _sentences(results)]
    errors, warnings = [], []
    for sentence in sentences:
        words = _words(sentence)
        numeric = len(re.findall(r"(?<![\w.])\d+(?:\.\d+)?", sentence))
        # Allow a short nonnumeric principal-finding reminder and shared statistical terms.
        if len(words) < 16 and not (len(words) >= 9 and numeric >= 2): continue
        for raw, source in original:
            if not source or min(len(words), len(source)) / max(len(words), len(source)) < .8: continue
            if SequenceMatcher(None, words, source, autojunk=False).ratio() >= .92:
                errors.append({"kind": "results_repetition", "discussion_sentence": sentence,
                               "results_sentence": raw,
                               "detail": "Near-whole Results sentence repeated; replace transcription with interpretation/comparison, preserving scientific meaning."})
                break
    cited = [s for s in sentences if _SUPP.search(s)]
    mentions = [m.group(0) for s in cited for m in _SUPP.finditer(s)]
    ratio = len(cited) / max(1, len(sentences))
    # Hard-block a clear display inventory, not three genuine interpretive sentences
    # merely because they cite supplementary evidence in a short Discussion.
    explanatory = re.compile(r"\b(?:because|may reflect|could reflect|explain\w*|suggest\w*|consistent with|whereas|unlike|in contrast|bias|confounding|interpret\w*|mechanism\w*|clinical)\b", re.I)
    def walkthrough(sentence):
        if explanatory.search(sentence): return False
        return bool(re.search(r"\b(?:shown|presented|listed|reported|summari[sz]ed|detailed|displayed|provided)\s+(?:in|by)\b", sentence, re.I) or
                    (re.match(r"^\s*(?:Supplementary\s+|Supplemental\s+)?(?:Tables?|Figures?|Figs?\.)\s+S?\d", sentence, re.I) and
                     re.search(r"\b(?:shows?|presents?|lists?|reports?|summari[sz]es?)\b", sentence, re.I)))
    walking = [s for s in cited if walkthrough(s)]
    if len(walking) >= 3 and len(walking) / max(1, len(sentences)) >= .4:
        errors.append({"kind": "supplement_display_walkthrough", "detail": "A large share of this short Discussion walks through supplementary displays; move result detail to Results and develop the actual argument.",
                       "sentences": len(walking), "discussion_sentences": len(sentences)})
    elif len(mentions) > 4 or (len(cited) >= 3 and ratio >= .2):
        warnings.append({"kind": "supplement_reference_density", "detail": "Inspect whether these supplementary references are necessary to the interpretation, rather than a second Results narrative.", "mentions": len(mentions)})
    return errors, warnings


def check(project, *, discussion_path=DISCUSSION, results_path=RESULTS, presentation_only=False):
    project = Path(project).resolve()
    if not enabled(project): return [], []
    errors = []
    if not presentation_only:
        if not _receipt_current(project, MATERIALS, "discussion_materials"):
            errors.append({"kind": "materials_stale", "detail": "Discussion writing materials are missing/changed/stale; update supported notes and run discussion.py prepare in scope."})
        elif material_problems((project/MATERIALS).read_text(encoding="utf-8")):
            errors.append({"kind": "materials_payload", "detail": "; ".join(material_problems((project/MATERIALS).read_text(encoding="utf-8")))})
        if not _receipt_current(project, OUTLINE, "discussion_outline"):
            errors.append({"kind": "outline_stale", "detail": "Write the six-point outline before drafting, then bind the actual current outline with discussion.py outline."})
        elif outline_problems((project/OUTLINE).read_text(encoding="utf-8")):
            errors.append({"kind": "outline_incomplete", "detail": "; ".join(outline_problems((project/OUTLINE).read_text(encoding="utf-8")))})
    discussion_file = _safe_path(project, discussion_path)[1]
    results_file = _safe_path(project, results_path)[1]
    discussion = discussion_file.read_text(encoding="utf-8")
    results = discussion if discussion_file == results_file else results_file.read_text(encoding="utf-8")
    names = {}
    if discussion_path.startswith("08_submission/") or results_path.startswith("08_submission/"):
        from .journalspec import load as journal_target, aliases
        names = aliases(journal_target(project))
    repeated, warnings = diagnose(discussion, results, headings=names, require_sections=discussion_file == results_file)
    return errors + repeated, warnings
