"""Markdown / source-text checks."""
from __future__ import annotations

import re

from . import Ctx, Result, check

CITE_RE = re.compile(r"\[(@[^\]]+)\]")
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", re.M)

# Hard stops: text that must never survive into a deliverable.
PLACEHOLDERS = [
    "TODO", "TBD", "FIXME", "XXX", "PLACEHOLDER", "VERIFY:", "[insert",
    "lorem ipsum", "as an ai", "i cannot provide", "<your ", "xx.x", "N.NN",
]

# Soft flags: phrasing that reads as machine-generated. Reported, not blocking.
AI_TELLS = [
    "delve into", "it is worth noting", "it is important to note",
    "plays a crucial role", "plays a vital role", "paves the way",
    "in today's rapidly evolving", "ever-evolving", "landscape of",
    "tapestry", "underscores the importance", "holds immense promise",
    "cutting-edge", "seamlessly", "a testament to", "navigating the complexities",
    "unlock the potential", "revolutionize", "game-changer",
    "it is crucial to understand", "multifaceted approach", "delves",
    "in the realm of", "shedding light upon", "robust and comprehensive",
]

FORBIDDEN_VISIBLE_SYMBOLS = {
    "\u2193": "down arrow (use words such as 'lower' or 'decreased')",
}


def _body(text: str) -> str:
    text = FENCE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    return text


def _wordcount(text: str) -> int:
    t = _body(text)
    t = CITE_RE.sub(" ", t)
    t = HEADING_RE.sub(" ", t)
    t = re.sub(r"^\s*>.*$", " ", t, flags=re.M)          # blockquotes
    t = re.sub(r"[*_#>|`~\[\]()]", " ", t)
    return len([w for w in t.split() if any(ch.isalnum() for ch in w)])


def _headings(text: str) -> list[str]:
    return [h.strip() for h in HEADING_RE.findall(text)]


@check("forbidden_symbols_absent")
def forbidden_symbols_absent(ctx: Ctx) -> Result:
    paths = ctx.spec.get("paths", [])
    present = [rel for rel in paths if ctx.p(rel).is_file()]
    if not present:
        return Result(False, "forbidden_symbols_absent", "none of the target files exist")
    problems = []
    for rel in present:
        value = ctx.read(rel)
        for symbol, description in FORBIDDEN_VISIBLE_SYMBOLS.items():
            if symbol in value:
                problems.append(f"{rel}: contains {description}")
    if problems:
        return Result(False, "forbidden_symbols_absent", "; ".join(problems[:8]))
    return Result(True, "forbidden_symbols_absent",
                  f"{len(present)} source file(s) contain no forbidden visible control symbols")


@check("md_sections")
def md_sections(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    if not ctx.p(rel).exists():
        return Result(False, "md_sections", f"{rel} missing")
    text = ctx.read(rel)
    present = [h.lower() for h in _headings(text)]
    required = ctx.spec.get("headings", [])
    missing = [h for h in required if not any(h.lower() in p for p in present)]
    if missing:
        return Result(
            False,
            "md_sections",
            f"{rel} lacks heading(s): " + "; ".join(missing),
            [f"Required headings for this stage: {', '.join(required)}"],
        )
    return Result(True, "md_sections", f"{rel}: {len(required)} required heading(s) present")


@check("md_wordcount")
def md_wordcount(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    if not ctx.p(rel).exists():
        return Result(False, "md_wordcount", f"{rel} missing")
    n = _wordcount(ctx.read(rel))
    lo = ctx.spec_bound("min")
    hi = ctx.spec_bound("max")
    if lo is not None and n < lo:
        return Result(False, "md_wordcount", f"{rel}: {n} words, target >= {lo}")
    if hi is not None and n > hi:
        return Result(
            False,
            "md_wordcount",
            f"{rel}: {n} words, target <= {hi}",
            ["Cut, do not compress into denser jargon. Adjust the target with `wf config set` if the journal differs."],
        )
    return Result(True, "md_wordcount", f"{rel}: {n} words (target {lo}-{hi})")


@check("notes_populated")
def notes_populated(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    if not ctx.p(rel).exists():
        return Result(False, "notes_populated", f"{rel} missing")
    text = ctx.read(rel)
    required = ctx.spec.get("headings", [])
    min_chars = ctx.spec.get("min_chars_per_section", 120)
    # split on headings and measure each block
    blocks: dict[str, str] = {}
    parts = re.split(r"^\s{0,3}#{1,6}\s+", text, flags=re.M)
    for chunk in parts[1:]:
        head, _, rest = chunk.partition("\n")
        blocks[head.strip().lower()] = rest
    thin, absent = [], []
    for h in required:
        key = next((k for k in blocks if h.lower() in k), None)
        if key is None:
            absent.append(h)
        elif len(blocks[key].strip()) < min_chars:
            thin.append(f"{h} ({len(blocks[key].strip())} chars)")
    if absent or thin:
        bits = []
        if absent:
            bits.append("absent: " + ", ".join(absent))
        if thin:
            bits.append(f"under {min_chars} chars: " + ", ".join(thin))
        return Result(
            False,
            "notes_populated",
            f"{rel} -> " + "; ".join(bits),
            ["notes.md is what Introduction and Discussion are built from. Thin notes now means invented prose later."],
        )
    return Result(True, "notes_populated", f"{rel}: all {len(required)} note section(s) substantive")


@check("no_ai_boilerplate")
def no_ai_boilerplate(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    if not ctx.p(rel).exists():
        if ctx.spec.get("optional", False):
            return Result(True, "no_ai_boilerplate", f"{rel}: optional file absent")
        return Result(False, "no_ai_boilerplate", f"{rel} missing")
    raw = ctx.read(rel)
    low = _body(raw).lower()
    hard = [ph for ph in PLACEHOLDERS if ph.lower() in low]
    if hard:
        return Result(
            False,
            "no_ai_boilerplate",
            f"{rel} still contains placeholder text: " + ", ".join(sorted(set(hard))),
            ["Resolve every placeholder from real data or delete the sentence."],
        )
    soft = [ph for ph in AI_TELLS if ph in low]
    if soft:
        return Result(
            False,
            "no_ai_boilerplate",
            f"{rel}: machine-sounding phrasing -> " + "; ".join(soft[:8]),
            ["Rewrite these clauses in plain clinical prose. Warning only; it does not block."],
            severity="warn",
        )
    return Result(True, "no_ai_boilerplate", f"{rel}: no placeholders, no stock phrasing")


@check("no_plot_calls")
def no_plot_calls(ctx: Ctx) -> Result:
    """Exploratory analysis must not produce figures."""
    banned = [
        "matplotlib", "seaborn", "plotly", "savefig", "plt.", "ggplot",
        "ggsave", "pyplot", "altair", "bokeh",
    ]
    hits = []
    for p in ctx.glob(ctx.spec["glob"]):
        try:
            src = p.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        found = sorted({b for b in banned if b in src})
        if found:
            hits.append(f"{p.name}: {', '.join(found)}")
    if hits:
        return Result(
            False,
            "no_plot_calls",
            "plotting code in the exploratory stage -> " + "; ".join(hits),
            ["Exploratory analysis is numbers only. Figures are built in S11 from the approved artifact plan."],
        )
    return Result(True, "no_plot_calls", "exploratory code contains no plotting")
