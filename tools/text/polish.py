#!/usr/bin/env python3
"""Manuscript de-AI and academic-English linter. Stdlib only.

    .venv/Scripts/python.exe tools/text/polish.py snapshot      # freeze the pre-polish text (do this first)
    .venv/Scripts/python.exe tools/text/polish.py lint          # full report -> 07_manuscript/polish_report.json
    .venv/Scripts/python.exe tools/text/polish.py lint --file 07_manuscript/discussion.md
    .venv/Scripts/python.exe tools/text/polish.py diff          # what polishing changed, and what it must not have

Three jobs, deliberately separated:

  ai_tells    machine-generated writing patterns. Tier A blocks, Tier B is advisory.
  style       journal-house-style consistency that code can settle definitively.
  readability advisory metrics that need a human call.

`diff` is the safety net. Polishing rewrites sentences, which is the single most likely
place for a number or a citation to be silently mangled. It compares the polished text
against the snapshot and requires the multiset of numbers, the set of citekeys and the set
of figure/table references to be unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Fallback order for legacy workspaces. Once full_manuscript.md exists it is the canonical
# main source and the component drafts are deliberately not polished in parallel.
LEGACY_SECTION_ORDER = [
    "07_manuscript/title_page.md",
    "07_manuscript/abstract.md",
    "07_manuscript/introduction.md",
    "07_manuscript/methods.md",
    "07_manuscript/supplementary_methods.md",
    "07_manuscript/results.md",
    "07_manuscript/discussion.md",
    "07_manuscript/statements.md",
]
CANONICAL_ORDER = [
    "07_manuscript/full_manuscript.md",
    "07_manuscript/supplementary_methods.md",
    "07_manuscript/title_page.md",
    "07_manuscript/statements.md",
]
SNAPSHOT_DIR = "07_manuscript/prepolish"
REPORT = "07_manuscript/polish_report.json"
ALLOWLIST = "07_manuscript/polish_allowlist.tsv"

FENCE_RE = re.compile(r"```.*?```", re.S)
CITE_RE = re.compile(r"\[[^\]]*@[^\]]*\]")
KEY_RE = re.compile(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)")
ART_RE = re.compile(r"\b(?:supplementary\s+)?(?:figure|fig\.?|table)\s*S?\d+", re.I)
NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w])")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+.*$", re.M)
# P-value notation is a style matter this stage is meant to normalize
# (P = 0.000 -> P < 0.001), so its digits are excluded from fact comparison.
PVAL_RE = re.compile(r"\b[Pp]\s*[<>=]\s*\.?\d*\.?\d+", re.I)


# ===========================================================================
# pattern tables
# ===========================================================================
# Tier A: phrasing that reads as machine-generated in a clinical paper. Blocking.
AI_TIER_A = [
    (r"\bdelve[sd]?\s+(?:in)?to\b", "delve into"),
    (r"\bit\s+is\s+worth\s+noting\b", "it is worth noting"),
    (r"\bplays?\s+(?:a\s+)?(?:crucial|vital|pivotal|key|significant|critical)\s+role\b",
     "plays a crucial role"),
    (r"\bpave[sd]?\s+the\s+way\b", "paves the way"),
    (r"\bin\s+today'?s\s+(?:rapidly\s+)?(?:evolving|changing)\b", "in today's rapidly evolving"),
    (r"\bever[- ]evolving\b", "ever-evolving"),
    (r"\bin\s+the\s+realm\s+of\b", "in the realm of"),
    (r"\b(?:the\s+)?landscape\s+of\s+(?:modern|contemporary|current)\b", "landscape of"),
    (r"\btapestry\b", "tapestry"),
    (r"\ba\s+testament\s+to\b", "a testament to"),
    (r"\bnavigat\w*\s+the\s+complexit\w+\b", "navigating the complexities"),
    (r"\bunderscore[sd]?\s+the\s+(?:importance|need|critical)\b", "underscores the importance"),
    (r"\bhold[sd]?\s+(?:immense\s+|great\s+|significant\s+)?promise\b", "holds promise"),
    (r"\bcutting[- ]edge\b", "cutting-edge"),
    (r"\bseamless(?:ly)?\b", "seamlessly"),
    (r"\brevolutioni[sz]\w+\b", "revolutionize"),
    (r"\bgame[- ]chang\w+\b", "game-changer"),
    (r"\bunlock\w*\s+the\s+(?:potential|power)\b", "unlock the potential"),
    (r"\bmultifaceted\b", "multifaceted"),
    (r"\b(?:a\s+)?myriad\s+of\b", "myriad of"),
    (r"\b(?:a\s+)?plethora\s+of\b", "plethora of"),
    (r"\bintricate\s+(?:interplay|balance|relationship|mechanism)\b", "intricate interplay"),
    (r"\brobust\s+and\s+comprehensive\b", "robust and comprehensive"),
    (r"\bcomprehensive\s+understanding\b", "comprehensive understanding"),
    (r"\bit\s+is\s+(?:crucial|essential|imperative|vital)\s+to\s+(?:note|understand|recognize|recognise)\b",
     "it is crucial to note"),
    (r"\bleverag\w+\b", "leverage (use 'use')"),
    (r"\butili[sz]\w+\b", "utilize (use 'use')"),
    (r"\bbridg\w*\s+(?:this\s+|the\s+)?gap\b", "bridge the gap"),
    (r"\bnot\s+only\s+\w[^.;]{0,60}?\s+but\s+also\b", "not only ... but also"),
    (r"\bdeep\s+dive\b", "deep dive"),
    (r"\bat\s+the\s+forefront\s+of\b", "at the forefront of"),
    (r"\bgrowing\s+body\s+of\s+(?:evidence|literature)\s+suggests\b",
     "a growing body of evidence suggests"),
    (r"\bin\s+an\s+era\s+(?:of|where)\b", "in an era of"),
    (r"\bpaint\w*\s+a\s+(?:clear|complete)\s+picture\b", "paints a picture"),
]

# Tier B: conventional in real papers but overused by generators. Advisory.
AI_TIER_B = [
    (r"\bit\s+(?:is|should\s+be)\s+(?:important|noted|noteworthy)\s+(?:to\s+note\s+)?that\b",
     "it should be noted that"),
    (r"\bshed(?:ding)?\s+light\s+(?:on|upon)\b", "shed light on"),
    (r"\bstate[- ]of[- ]the[- ]art\b", "state-of-the-art"),
    (r"\bwarrants?\s+further\s+(?:investigation|study|research)\b", "warrants further investigation"),
    (r"\bfurther\s+studies\s+are\s+(?:warranted|needed|required)\b", "further studies are warranted"),
    (r"\b(?:First|Second|Third|Fourth|Last)ly,", "Firstly/Secondly ordinal chain"),
    (r"\btaken\s+together\b", "taken together"),
    (r"\bthese\s+findings\s+highlight\b", "these findings highlight"),
    (r"\balign\w*\s+with\s+(?:previous|prior|our)\b", "align with previous work"),
    (r"\bto\s+the\s+best\s+of\s+our\s+knowledge\b", "to the best of our knowledge"),
    (r"\bhas\s+(?:attracted|garnered|received)\s+(?:increasing|growing)\s+attention\b",
     "has attracted increasing attention"),
    (r"\bin\s+recent\s+years\b", "in recent years"),
    (r"\bplays?\s+an\s+important\s+role\b", "plays an important role"),
]

# US -> UK spelling pairs. The linter reports drift, not a preference.
SPELLING_PAIRS = [
    (r"\btumor(s|al)?\b", r"\btumour(s|al)?\b", "tumor/tumour"),
    (r"\banemia?\b|\banemic\b", r"\banaemia?\b|\banaemic\b", "anemia/anaemia"),
    (r"\bhemo(\w+)\b", r"\bhaemo(\w+)\b", "hemo-/haemo-"),
    (r"\besophag(\w+)\b", r"\boesophag(\w+)\b", "esophag-/oesophag-"),
    (r"\bpediatric(s)?\b", r"\bpaediatric(s)?\b", "pediatric/paediatric"),
    (r"\bfetal\b|\bfetus(es)?\b", r"\bfoetal\b|\bfoetus(es)?\b", "fetal/foetal"),
    (r"\bcenter(s|ed|ing)?\b", r"\bcentre(s|d)?\b", "center/centre"),
    (r"\blabel(ed|ing)\b", r"\blabell(ed|ing)\b", "labeled/labelled"),
    (r"\bmodel(ed|ing)\b", r"\bmodell(ed|ing)\b", "modeling/modelling"),
    (r"\bag(e)?ing\b", r"\bageing\b", "aging/ageing"),
    (r"\brandomi[z]\w+\b", r"\brandomi[s]\w+\b", "randomize/randomise"),
    (r"\banaly[z]\w+\b", r"\banaly[s]e\w*\b", "analyze/analyse"),
    (r"\bcharacteri[z]\w+\b", r"\bcharacteri[s]\w+\b", "characterize/characterise"),
    (r"\bhospitali[z]\w+\b", r"\bhospitali[s]\w+\b", "hospitalize/hospitalise"),
    (r"\bfavor(able|ably)?\b", r"\bfavour(able|ably)?\b", "favor/favour"),
    (r"\bbehavior(al)?\b", r"\bbehaviour(al)?\b", "behavior/behaviour"),
]

# Abbreviations that journals accept without definition.
NO_DEF_NEEDED = {
    "CI", "SD", "SE", "SEM", "IQR", "OR", "HR", "RR", "AUC", "ROC", "BMI", "DNA", "RNA",
    "HIV", "AIDS", "WHO", "USA", "US", "UK", "CT", "MRI", "PET", "ECG", "EKG", "ICU",
    "BP", "HDL", "LDL", "GFR", "eGFR", "CRP", "TNF", "IL", "PCR", "ELISA", "FDA", "EMA",
    "NHS", "NA", "SD", "ANOVA", "ROC", "APC", "AI", "ML",
}
STAT_SYMBOLS = ["n", "P", "r", "t", "F", "z", "df"]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def project_root() -> Path:
    env = os.environ.get("MEDPAPER_PROJECT")
    if env:
        return Path(env).resolve()
    root = Path(os.environ.get("MEDPAPER_ROOT") or Path(__file__).resolve().parents[2])
    return root / "project"


def body(text: str) -> str:
    """Prose only: no code fences, no headings."""
    return HEADING_RE.sub(" ", FENCE_RE.sub(" ", text))


def flow(text: str) -> str:
    """Undo markdown soft wrapping so sentence-level checks see real sentences.

    Without this, a line that happens to begin with '5 mg dose.' looks like a sentence
    starting with a numeral, and any check anchored to ^ misfires on wrapped prose.
    """
    return re.sub(r"(?<!\n)\n(?!\n)", " ", body(text))


def allowlist() -> dict[str, str]:
    p = project_root() / ALLOWLIST
    out: dict[str, str] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                bits = line.split("\t")
                out[bits[0].strip().lower()] = bits[1].strip() if len(bits) > 1 else ""
    return out


def sections(only: str | None = None) -> list[tuple[str, str]]:
    proj = project_root()
    if only:
        rels = [only]
    elif (proj / "07_manuscript/full_manuscript.md").exists():
        rels = CANONICAL_ORDER
    else:
        rels = LEGACY_SECTION_ORDER
    out = []
    for rel in rels:
        p = proj / rel
        if p.exists() and p.stat().st_size > 0:
            out.append((rel, p.read_text(encoding="utf-8", errors="replace")))
    return out


# ===========================================================================
# fact extraction - the invariants polishing must preserve
# ===========================================================================
def _normalize_for_facts(s: str) -> str:
    """Make number extraction invariant to the formatting fixes this stage requires.

    Without this, three legitimate polish edits look like data corruption:
      '5mg'   -> '5 mg'    unit spacing: the digit only becomes visible after the fix
      '1,284' -> '1284'    thousands separator: splits into two tokens before the fix
      'P=0.000' -> 'P<0.001'  handled separately by PVAL_RE
    The magnitude of every reported value is still compared exactly.
    """
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)     # 1,284 -> 1284
    s = re.sub(r"(\d)(?=[A-Za-z])", r"\1 ", s)    # 5mg   -> 5 mg
    return s


def facts(text: str) -> dict:
    b = FENCE_RE.sub(" ", text)
    keys = sorted({k for grp in CITE_RE.findall(b) for k in KEY_RE.findall(grp)})
    arts = sorted({re.sub(r"\s+", " ", a).lower().replace("fig.", "figure").replace("fig ", "figure ")
                   for a in ART_RE.findall(b)})
    stripped = PVAL_RE.sub(" ", ART_RE.sub(" ", CITE_RE.sub(" ", b)))
    nums = sorted(NUM_RE.findall(_normalize_for_facts(stripped)))
    return {"numbers": nums, "citekeys": keys, "artifacts": arts}


# ===========================================================================
# linters
# ===========================================================================
def lint_ai(rel: str, text: str, allow: dict) -> list[dict]:
    """Line numbers refer to the file as written, so keep the original line breaks here."""
    out = []
    lines = body(text).splitlines()
    for tier, table in (("A", AI_TIER_A), ("B", AI_TIER_B)):
        for pattern, label in table:
            if label.lower() in allow:
                continue
            rx = re.compile(pattern, re.I)
            for i, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    out.append({"file": rel, "line": i, "tier": tier, "label": label,
                                "match": m.group(0)[:60],
                                "context": line.strip()[max(0, m.start() - 30):m.end() + 30][:120]})
    return out


def lint_structure(rel: str, text: str) -> list[dict]:
    """Structural tells: rhythm and formatting that give away generated prose."""
    out = []
    raw = body(text)
    b = flow(text)
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", b)]
    nwords = len(words) or 1

    def flag(kind: str, detail: str, severity: str = "advisory") -> None:
        out.append({"file": rel, "kind": kind, "detail": detail, "severity": severity})

    em = len(re.findall(r"\u2014|\s--\s", b))
    if em / nwords * 1000 > 4:
        flag("em_dash_density", f"{em} em dashes in {nwords} words "
                               f"({em / nwords * 1000:.1f} per 1000; > 4 reads as generated)", "blocking")

    transitions = re.findall(
        r"(?:(?<=[.!?])\s+|(?<=\n\n)|\A)(Furthermore|Moreover|Additionally|Notably|"
        r"Importantly|Consequently|Nevertheless|Nonetheless|Overall|Indeed|Crucially|"
        r"Interestingly)\b", b)
    if transitions:
        c = Counter(transitions)
        rate = len(transitions) / nwords * 1000
        if rate > 6:
            flag("transition_density",
                 f"{len(transitions)} paragraph-initial transitions ({rate:.1f} per 1000 words): "
                 + ", ".join(f"{k}x{v}" for k, v in c.most_common(5)), "blocking")
        for word, n in c.items():
            if n >= 3:
                flag("transition_repeat", f"'{word}' opens {n} sentences", "advisory")

    paras = [p.strip() for p in re.split(r"\n\s*\n", b) if len(p.strip()) > 80]
    if len(paras) >= 4:
        lens = [len(p.split()) for p in paras]
        cv = statistics.pstdev(lens) / (statistics.fmean(lens) or 1)
        if cv < 0.16:
            flag("uniform_paragraphs",
                 f"{len(paras)} paragraphs of {min(lens)}-{max(lens)} words, "
                 f"coefficient of variation {cv:.2f} (< 0.16 is suspiciously even)", "advisory")

    tricolon = re.findall(r"\b\w+,\s+\w[\w\s]{0,20},\s+and\s+\w+\b", b)
    if len(tricolon) / nwords * 1000 > 5:
        flag("tricolon_density",
             f"{len(tricolon)} three-item lists per {nwords} words - vary the sentence shape",
             "advisory")

    if re.search(r"(?m)^\s*[-*+]\s+\S", raw) and any(
            s in rel for s in ("results", "discussion", "introduction")):
        flag("bullets_in_prose",
             "bullet list in a narrative section - journals want continuous prose", "blocking")
    if re.search(r"(?<!\*)\*\*[^*\n]{1,60}\*\*(?!\*)", b) and "title_page" not in rel:
        flag("inline_bold", "bold text inside prose - remove it unless the journal asks for it",
             "blocking")
    if re.search(r"\?\s*$", b, re.M) and "abstract" not in rel:
        flag("rhetorical_question", "a question mark in narrative prose", "advisory")

    hedges = re.findall(
        r"\b(?:may|might|could|possibly|potentially|perhaps|suggest\w*|appear\w*|seem\w*)\b", b, re.I)
    for m in re.finditer(
            r"\b(?:may|might|could)\s+(?:possibly|potentially|perhaps)\b|"
            r"\b(?:suggests?|indicates?)\s+that\s+\w+\s+(?:may|might|could)\s+(?:possibly|potentially)\b",
            b, re.I):
        flag("hedge_stacking", f"stacked hedges: {m.group(0)!r}", "blocking")
    if len(hedges) / nwords * 1000 > 28:
        flag("hedge_density",
             f"{len(hedges)} hedge words per {nwords} words ({len(hedges) / nwords * 1000:.0f} "
             "per 1000) - commit to what the data shows", "advisory")

    long_sents = [s for s in re.split(r"(?<=[.!?])\s+", b) if len(s.split()) > 45]
    if long_sents:
        flag("long_sentences",
             f"{len(long_sents)} sentence(s) over 45 words, longest {max(len(s.split()) for s in long_sents)}",
             "advisory")
    return out


def lint_style(rel: str, text: str) -> list[dict]:
    out = []
    b = flow(text)

    def flag(kind: str, detail: str, severity: str = "blocking") -> None:
        out.append({"file": rel, "kind": kind, "detail": detail, "severity": severity})

    # numeric ranges: en dash, not hyphen
    bad_ranges = re.findall(r"(?<![\w-])(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?![\w-])", b)
    if bad_ranges:
        flag("range_dash",
             f"{len(bad_ranges)} numeric range(s) with a hyphen; use an en dash (\u2013) or 'to': "
             + ", ".join(f"{a}-{b_}" for a, b_ in bad_ranges[:5]))

    # P value styling must be internally consistent
    variants = Counter()
    for rx, name in ((r"\bP\s*[<>=]", "P"), (r"\bp\s*[<>=]", "p"),
                     (r"\bP[- ]values?\b", "P value"), (r"\bp[- ]values?\b", "p value")):
        n = len(re.findall(rx, b))
        if n:
            variants[name] = n
    if {"P", "p"} <= set(variants):
        flag("p_case", f"mixed P/p for the test statistic: {dict(variants)}")
    if {"P value", "p value"} <= set(variants):
        flag("p_value_style", f"mixed 'P value' spellings: {dict(variants)}")
    hyph = len(re.findall(r"\b[Pp]-values?\b", b))
    plain = len(re.findall(r"\b[Pp] values?\b", b))
    if hyph and plain:
        flag("p_value_hyphen", f"'P-value' ({hyph}) and 'P value' ({plain}) both used")

    # units
    glued = re.findall(r"\b\d+(?:\.\d+)?(mg|kg|ml|mL|mmHg|cm|mm|kPa|mmol|umol|IU|years?|mo)\b", b)
    if glued:
        flag("unit_spacing", f"{len(glued)} value(s) glued to a unit (write '5 mg'): "
                             + ", ".join(sorted(set(glued))[:6]))
    spaced_pct = len(re.findall(r"\d\s+%", b))
    tight_pct = len(re.findall(r"\d%", b))
    if spaced_pct and tight_pct:
        flag("percent_spacing", f"'5 %' ({spaced_pct}) and '5%' ({tight_pct}) both used")

    m = re.search(r"(?:(?<=[.!?])\s+|(?<=\n\n))(\d[\w.,]*(?:\s+\S+){0,3})", b)
    if m:
        flag("sentence_starts_with_numeral",
             f"a sentence begins with a numeral ({m.group(1)[:30]!r}) - spell it out or restructure")
    if re.search(r"\bdata\s+(?:was|is|has\s+been)\b", b, re.I):
        flag("data_agreement", "'data was/is' - data is plural in formal medical writing")
    # 0 or an all-zero decimal only: P=0.62 must not match on its leading zero.
    if re.search(r"\b[Pp]\s*=\s*0(?:\.0+)?(?![\d.])", b):
        flag("p_zero", "P = 0 / P = 0.000 is not a value; report P < 0.001")
    if re.search(r"\b(?:proves?|proven|demonstrates?\s+causation|causes?\s+the\s+outcome)\b", b, re.I):
        flag("causal_overclaim",
             "causal language - use 'associated with' unless the design supports causation")
    if re.search(r"[ \t]+$", b, re.M):
        flag("trailing_whitespace", "trailing whitespace on one or more lines", "advisory")
    if "  " in re.sub(r"^\s+", "", b, flags=re.M):
        flag("double_space", "double spaces inside prose", "advisory")
    if re.search(r"[\u201c\u201d]", b) and '"' in b:
        flag("mixed_quotes", "curly and straight quotes mixed", "advisory")

    for rx in STAT_SYMBOLS:
        ital = len(re.findall(rf"\*{re.escape(rx)}\*\s*[=<>]", b))
        plainv = len(re.findall(rf"(?<![\w*]){re.escape(rx)}\s*[=<>]", b))
        if ital and plainv:
            flag("stat_symbol_italics",
                 f"'{rx}' appears both italic ({ital}) and roman ({plainv}) before an operator",
                 "advisory")
    return out


def lint_spelling(docs: list[tuple[str, str]]) -> list[dict]:
    """Spelling-variant drift across the whole manuscript, not per file."""
    joined = " ".join(body(t) for _, t in docs)
    out = []
    us_total = uk_total = 0
    details = []
    for us_rx, uk_rx, label in SPELLING_PAIRS:
        us = len(re.findall(us_rx, joined, re.I))
        uk = len(re.findall(uk_rx, joined, re.I))
        us_total += us
        uk_total += uk
        if us and uk:
            details.append(f"{label} ({us} US / {uk} UK)")
    if details:
        out.append({"file": "(manuscript)", "kind": "spelling_variant_mixed",
                    "severity": "blocking",
                    "detail": f"US and UK spellings both used: {'; '.join(details[:6])}. "
                              f"Overall {us_total} US vs {uk_total} UK - pick the journal's variant."})
    elif us_total and uk_total:
        out.append({"file": "(manuscript)", "kind": "spelling_variant",
                    "severity": "advisory",
                    "detail": f"{us_total} US-leaning vs {uk_total} UK-leaning tokens"})
    return out


def lint_abbreviations(docs: list[tuple[str, str]]) -> list[dict]:
    """Define once, on first use, then use consistently. Abstract has its own scope."""
    out = []
    for scope, files in (("abstract", ["07_manuscript/abstract.md"]),
                         ("body", [f for f, _ in docs if "abstract" not in f])):
        text = "\n".join(body(t) for f, t in docs if f in files)
        if not text.strip():
            continue
        defined: dict[str, int] = {}
        for m in re.finditer(r"\(([A-Z][A-Za-z0-9]{1,7})s?\)", text):
            abbr = m.group(1)
            defined.setdefault(abbr, m.start())
            if len(re.findall(rf"\({re.escape(abbr)}s?\)", text)) > 1:
                out.append({"file": f"({scope})", "kind": "abbrev_redefined",
                            "severity": "blocking",
                            "detail": f"'{abbr}' is defined more than once in the {scope}"})
        for abbr, pos in defined.items():
            uses = [m.start() for m in re.finditer(rf"(?<![\w]){re.escape(abbr)}(?![\w])", text)]
            before = [u for u in uses if u < pos - 1]
            if before:
                out.append({"file": f"({scope})", "kind": "abbrev_used_before_defined",
                            "severity": "blocking",
                            "detail": f"'{abbr}' is used before it is defined in the {scope}"})
            if len(uses) <= 2 and abbr not in NO_DEF_NEEDED:
                out.append({"file": f"({scope})", "kind": "abbrev_barely_used",
                            "severity": "advisory",
                            "detail": f"'{abbr}' is defined but used only "
                                      f"{max(0, len(uses) - 1)}x afterwards - spell it out instead"})
        for m in re.finditer(r"(?<![\w(])([A-Z]{2,7})(?![\w)])", text):
            abbr = m.group(1)
            if abbr in defined or abbr in NO_DEF_NEEDED or abbr.isdigit():
                continue
            out.append({"file": f"({scope})", "kind": "abbrev_undefined",
                        "severity": "blocking",
                        "detail": f"'{abbr}' is used in the {scope} but never defined there"})
    seen = set()
    uniq = []
    for item in out:
        k = (item["kind"], item["detail"])
        if k not in seen:
            seen.add(k)
            uniq.append(item)
    return uniq


def readability(rel: str, text: str) -> dict:
    b = flow(text)
    sents = [s for s in re.split(r"(?<=[.!?])\s+", b) if s.strip()]
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", b)
    lens = [len(s.split()) for s in sents] or [0]
    passive = len(re.findall(
        r"\b(?:was|were|is|are|been|being)\s+\w+(?:ed|en)\b(?:\s+by\b)?", b, re.I))
    past = len(re.findall(r"\b\w+ed\b", b))
    present = len(re.findall(r"\b(?:is|are|shows?|demonstrates?|indicates?|remains?)\b", b, re.I))
    return {
        "file": rel,
        "words": len(words),
        "sentences": len(sents),
        "mean_sentence_words": round(statistics.fmean(lens), 1),
        "max_sentence_words": max(lens),
        "passive_constructions": passive,
        "past_tense_markers": past,
        "present_tense_markers": present,
        "first_person": len(re.findall(r"\bwe\b|\bour\b", b, re.I)),
    }


# ===========================================================================
# commands
# ===========================================================================
def cmd_snapshot(args) -> int:
    proj = project_root()
    dest = proj / SNAPSHOT_DIR
    docs = sections()
    if not docs:
        print("nothing to snapshot: no manuscript section files exist yet")
        return 1
    if dest.exists() and not args.force:
        print(f"snapshot already exists at project/{SNAPSHOT_DIR}/")
        print("that is the pre-polish reference; do not overwrite it unless you are "
              "restarting the polish pass (--force)")
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    facts_index = {}
    for rel, text in docs:
        name = Path(rel).name
        shutil.copy2(proj / rel, dest / name)
        facts_index[rel] = facts(text)
    (dest / "facts.json").write_text(
        json.dumps({"snapshot_at": now(), "files": facts_index}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"snapshotted {len(docs)} section(s) -> project/{SNAPSHOT_DIR}/")
    for rel, f in facts_index.items():
        print(f"  {Path(rel).name:<20} {len(f['numbers']):>4} numbers  "
              f"{len(f['citekeys']):>3} citekeys  {len(f['artifacts']):>2} artifact refs")
    print("\nPolishing must leave all three of those unchanged. `polish.py diff` checks it.")
    return 0


def cmd_lint(args) -> int:
    proj = project_root()
    docs = sections(args.file)
    if not docs:
        print("no manuscript sections found" + (f" at {args.file}" if args.file else ""))
        return 1
    allow = allowlist()

    ai, struct, style, read = [], [], [], []
    for rel, text in docs:
        ai += lint_ai(rel, text, allow)
        struct += lint_structure(rel, text)
        style += lint_style(rel, text)
        read.append(readability(rel, text))
    style += lint_spelling(docs)
    if not args.file:
        style += lint_abbreviations(docs)

    tier_a = [x for x in ai if x["tier"] == "A"]
    tier_b = [x for x in ai if x["tier"] == "B"]
    blocking_struct = [x for x in struct if x["severity"] == "blocking"]
    blocking_style = [x for x in style if x["severity"] == "blocking"]

    report = {
        "linted_at": now(),
        "files": [rel for rel, _ in docs],
        "counts": {
            "ai_tier_a": len(tier_a), "ai_tier_b": len(tier_b),
            "structure_blocking": len(blocking_struct),
            "structure_advisory": len(struct) - len(blocking_struct),
            "style_blocking": len(blocking_style),
            "style_advisory": len(style) - len(blocking_style),
        },
        "blocking_total": len(tier_a) + len(blocking_struct) + len(blocking_style),
        "ai_tells": ai, "structure": struct, "style": style, "readability": read,
        "allowlisted": sorted(allow),
    }
    if not args.file:
        (proj / REPORT).parent.mkdir(parents=True, exist_ok=True)
        (proj / REPORT).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["blocking_total"] == 0 else 2

    def block(title: str, items, fmt) -> None:
        print(f"\n{title} ({len(items)})")
        print("-" * len(f"{title} ({len(items)})"))
        if not items:
            print("  none")
        for x in items[:40]:
            print("  " + fmt(x))
        if len(items) > 40:
            print(f"  ... {len(items) - 40} more (see project/{REPORT})")

    block("AI TELLS - tier A (blocking)", tier_a,
          lambda x: f"{Path(x['file']).name}:{x['line']}  {x['label']}  -> {x['match']!r}")
    block("AI TELLS - tier B (advisory: conventional but overused)", tier_b,
          lambda x: f"{Path(x['file']).name}:{x['line']}  {x['label']}  -> {x['match']!r}")
    block("STRUCTURE", struct,
          lambda x: f"[{x['severity']:<9}] {Path(x['file']).name}  {x['kind']}: {x['detail']}")
    block("STYLE / HOUSE CONSISTENCY", style,
          lambda x: f"[{x['severity']:<9}] {Path(x['file']).name}  {x['kind']}: {x['detail']}")

    print("\nREADABILITY (advisory)")
    print("-" * 21)
    print(f"  {'file':<20} {'words':>6} {'sents':>6} {'mean':>6} {'max':>5} "
          f"{'passive':>8} {'we/our':>7}")
    for r in read:
        print(f"  {Path(r['file']).name:<20} {r['words']:>6} {r['sentences']:>6} "
              f"{r['mean_sentence_words']:>6} {r['max_sentence_words']:>5} "
              f"{r['passive_constructions']:>8} {r['first_person']:>7}")

    print("\n" + "=" * 70)
    n = report["blocking_total"]
    if n == 0:
        print("no blocking findings. Tier B and advisory items are yours to judge.")
    else:
        print(f"{n} blocking finding(s): {len(tier_a)} tier-A phrase(s), "
              f"{len(blocking_struct)} structural, {len(blocking_style)} style.")
        print("Rewrite them. Do not change a number, a citation, or a figure/table reference")
        print("while doing it - `polish.py diff` will catch it if you do.")
        print(f"A genuine exception goes in project/{ALLOWLIST} as 'pattern<TAB>reason'.")
    return 0 if n == 0 else 2


def cmd_diff(args) -> int:
    proj = project_root()
    snap = proj / SNAPSHOT_DIR
    if not (snap / "facts.json").exists():
        print(f"no snapshot at project/{SNAPSHOT_DIR}/facts.json")
        print("run `.venv/Scripts/python.exe tools/text/polish.py snapshot` BEFORE polishing")
        return 1
    before = json.loads((snap / "facts.json").read_text(encoding="utf-8"))["files"]

    problems, rows = [], []
    for rel, expect in before.items():
        p = proj / rel
        if not p.exists():
            problems.append(f"{rel}: disappeared after polishing")
            continue
        got = facts(p.read_text(encoding="utf-8", errors="replace"))
        old_words = len(body((snap / Path(rel).name).read_text(encoding="utf-8", errors="replace")).split())
        new_words = len(body(p.read_text(encoding="utf-8", errors="replace")).split())
        for field, label in (("numbers", "number"), ("citekeys", "citekey"), ("artifacts", "artifact ref")):
            lost = sorted(Counter(expect[field]) - Counter(got[field]))
            added = sorted(Counter(got[field]) - Counter(expect[field]))
            if lost:
                problems.append(f"{Path(rel).name}: {label}(s) LOST: {', '.join(map(str, lost[:8]))}")
            if added:
                problems.append(f"{Path(rel).name}: {label}(s) APPEARED: {', '.join(map(str, added[:8]))}")
        rows.append((Path(rel).name, old_words, new_words,
                     len(expect["numbers"]), len(got["numbers"]),
                     len(expect["citekeys"]), len(got["citekeys"])))

    print(f"{'file':<20} {'words':>13} {'numbers':>11} {'citekeys':>11}")
    print(f"{'':<20} {'before/after':>13} {'before/after':>11} {'before/after':>11}")
    for name, ow, nw, on_, nn, ok_, nk in rows:
        delta = f"{ow}/{nw}"
        print(f"{name:<20} {delta:>13} {f'{on_}/{nn}':>11} {f'{ok_}/{nk}':>11}")

    print()
    if problems:
        print(f"{len(problems)} FACT-PRESERVATION FAILURE(S):")
        for p_ in problems:
            print(f"  {p_}")
        print("\nPolishing may change wording only. Restore the lost content from")
        print(f"project/{SNAPSHOT_DIR}/ and redo the affected sentences.")
        return 2
    print("every number, citekey and figure/table reference survived the polish pass.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="de-AI and academic-English linting")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("snapshot", help="freeze the pre-polish manuscript (run first)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_snapshot)

    p = sub.add_parser("lint", help="report AI tells, structure and house style")
    p.add_argument("--file", help="lint one file instead of the whole manuscript")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_lint)

    p = sub.add_parser("diff", help="verify polishing preserved every fact")
    p.set_defaults(fn=cmd_diff)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
