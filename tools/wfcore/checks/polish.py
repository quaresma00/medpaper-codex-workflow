"""Polish-stage checks: de-AI, house style, and fact preservation.

The last one matters most. A language pass rewrites sentences wholesale, which is the
easiest place in the whole pipeline to silently lose a number or a citation. The gate
compares the polished text against a pre-polish snapshot and requires the multiset of
numbers, the set of citekeys and the set of figure/table references to be identical.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import Ctx, Result, check

SNAPSHOT = "08_submission/integration/prepolish"
REPORT = "08_submission/integration/polish_report.json"
LEGACY_SECTIONS = ["introduction.md", "methods.md", "supplementary_methods.md", "results.md", "discussion.md", "abstract.md"]


def _wanted_sections(ctx: Ctx) -> set[str]:
    if ctx.p("08_submission/integration/full_manuscript.md").exists():
        return {name for name in ("full_manuscript.md", "supplementary_methods.md",
                                  "title_page.md", "statements.md")
                if ctx.p(f"08_submission/integration/{name}").exists()}
    return {name for name in LEGACY_SECTIONS if ctx.p(f"07_manuscript/{name}").exists()}


def _polish_tool(ctx: Ctx) -> Path:
    return ctx.pipeline.raw and Path(__file__).resolve().parents[2] / "text" / "polish.py"


@check("polish_snapshot_exists")
def polish_snapshot_exists(ctx: Ctx) -> Result:
    facts = ctx.p(f"{SNAPSHOT}/facts.json")
    if not facts.exists():
        return Result(
            False,
            "polish_snapshot_exists",
            f"no pre-polish snapshot at project/{SNAPSHOT}/facts.json",
            ["Take it BEFORE editing: .venv/Scripts/python.exe tools/text/polish.py snapshot",
             "Without it there is no way to prove the polish pass did not alter the data."],
        )
    try:
        data = json.loads(facts.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Result(False, "polish_snapshot_exists", f"facts.json unreadable: {exc}")
    files = data.get("files", {})
    missing = [rel for rel in files if not ctx.p(rel).exists()]
    if missing:
        return Result(False, "polish_snapshot_exists",
                      "snapshotted section(s) no longer present: " + ", ".join(missing))
    have = {Path(r).name for r in files}
    wanted = _wanted_sections(ctx)
    gap = sorted(wanted - have)
    if gap:
        return Result(
            False, "polish_snapshot_exists",
            "snapshot predates these sections: " + ", ".join(gap),
            ["Re-take it: .venv/Scripts/python.exe tools/text/polish.py snapshot --force"],
        )
    return Result(True, "polish_snapshot_exists",
                  f"{len(files)} section(s) snapshotted at {data.get('snapshot_at', '?')}")


@check("polish_preserves_facts")
def polish_preserves_facts(ctx: Ctx) -> Result:
    """Delegates to the tool so the CLI and the gate can never disagree."""
    tool = Path(__file__).resolve().parents[2] / "text" / "polish.py"
    if not tool.exists():
        return Result(False, "polish_preserves_facts", f"tool missing: {tool}")
    try:
        proc = subprocess.run(
            [sys.executable, str(tool), "diff"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
            env={**_env(ctx)},
        )
    except Exception as exc:  # noqa: BLE001
        return Result(False, "polish_preserves_facts", f"could not run polish.py diff: {exc}")
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        return Result(True, "polish_preserves_facts",
                      "every number, citekey and figure/table reference survived the polish")
    fails = [ln.strip() for ln in out.splitlines()
             if ": number(s)" in ln or ": citekey(s)" in ln or ": artifact ref(s)" in ln
             or "disappeared after" in ln]
    if not fails:
        fails = [ln.strip() for ln in out.splitlines() if "no snapshot" in ln or "run `" in ln]
    return Result(
        False,
        "polish_preserves_facts",
        "; ".join(fails[:6]) or out.strip()[:300],
        [f"Restore the affected text from project/{SNAPSHOT}/ and redo those sentences.",
         "Polishing changes wording only. Never a value, never a citation."],
    )


@check("ai_tells_clean")
def ai_tells_clean(ctx: Ctx) -> Result:
    rep = _report(ctx)
    if isinstance(rep, Result):
        return rep
    tier_a = [x for x in rep.get("ai_tells", []) if x.get("tier") == "A"]
    struct = [x for x in rep.get("structure", []) if x.get("severity") == "blocking"]
    if tier_a or struct:
        bits = []
        if tier_a:
            labels = Counter(x["label"] for x in tier_a)
            bits.append(f"{len(tier_a)} tier-A phrase(s): "
                        + ", ".join(f"{k} x{v}" for k, v in labels.most_common(6)))
        if struct:
            bits.append(f"{len(struct)} structural tell(s): "
                        + "; ".join(f"{x['kind']} in {Path(x['file']).name}" for x in struct[:4]))
        return Result(
            False,
            "ai_tells_clean",
            "; ".join(bits),
            ["Full detail: .venv/Scripts/python.exe tools/text/polish.py lint",
             "Rewrite the clause. Do not delete the sentence to make the check pass.",
             f"A genuine exception goes in project/08_submission/integration/polish_allowlist.tsv."],
        )
    tier_b = [x for x in rep.get("ai_tells", []) if x.get("tier") == "B"]
    if tier_b:
        return Result(True, "ai_tells_clean",
                      f"no tier-A tells; {len(tier_b)} tier-B phrase(s) left for your judgement")
    return Result(True, "ai_tells_clean", "no machine-generated phrasing detected")


@check("style_consistent")
def style_consistent(ctx: Ctx) -> Result:
    rep = _report(ctx)
    if isinstance(rep, Result):
        return rep
    blocking = [x for x in rep.get("style", []) if x.get("severity") == "blocking"]
    if blocking:
        kinds = Counter(x["kind"] for x in blocking)
        return Result(
            False,
            "style_consistent",
            f"{len(blocking)} house-style defect(s): "
            + "; ".join(f"{k} x{v}" for k, v in kinds.most_common(8)),
            ["Full detail: .venv/Scripts/python.exe tools/text/polish.py lint",
             "These are settled by convention, not taste: fix them all."],
        )
    advisory = [x for x in rep.get("style", []) if x.get("severity") != "blocking"]
    return Result(True, "style_consistent",
                  f"house style consistent"
                  + (f"; {len(advisory)} advisory note(s)" if advisory else ""))


@check("journal_limits_met")
def journal_limits_met(ctx: Ctx) -> Result:
    """Word and reference counts against the guidelines fetched at S20."""
    gx = "08_submission/guidelines_extract.md"
    if not ctx.p(gx).exists():
        return Result(False, "journal_limits_met", f"{gx} missing - fetch the guidelines first")
    text = ctx.read(gx)
    rep = _report(ctx)
    if isinstance(rep, Result):
        return rep
    counts = {Path(r["file"]).name: r["words"] for r in rep.get("readability", [])}

    limits = _declared_limits(text)
    if not limits:
        return Result(
            False,
            "journal_limits_met",
            "no word or reference limit could be found in guidelines_extract.md",
            ["Quote the journal's actual limits under 'Word limits', e.g. "
             "'Abstract: 250 words', 'Main text: 3500 words', 'References: max 50'.",
             "If the journal states no limit, write 'no stated limit' explicitly."],
        )

    if ctx.p("08_submission/integration/full_manuscript.md").exists():
        sections = _canonical_section_counts(ctx.read("08_submission/integration/full_manuscript.md"))
        abstract_words = sections.get("abstract", 0)
        body_words = sum(sections.get(k, 0) for k in
                         ("introduction", "methods", "results", "discussion"))
    else:
        abstract_words = counts.get("abstract.md", 0)
        body_words = sum(v for k, v in counts.items()
                         if k in ("introduction.md", "methods.md", "results.md", "discussion.md"))
    problems, notes = [], []
    for kind, cap in limits.items():
        if kind == "abstract" and abstract_words:
            got = abstract_words
            (problems if got > cap else notes).append(f"abstract {got}/{cap} words")
        elif kind == "main":
            (problems if body_words > cap else notes).append(f"main text {body_words}/{cap} words")
        elif kind == "references":
            n = _ref_count(ctx)
            (problems if n and n > cap else notes).append(f"references {n}/{cap}")
    if problems:
        return Result(
            False,
            "journal_limits_met",
            "over the journal's limit: " + "; ".join(problems),
            ["Cut content, do not compress into denser jargon.",
             "If cutting would remove something a reviewer needs, move it to the supplement."],
        )
    return Result(True, "journal_limits_met", "within journal limits: " + "; ".join(notes))


# ---------------------------------------------------------------------------
def _report(ctx: Ctx):
    p = ctx.p(REPORT)
    if not p.exists():
        return Result(
            False, "polish_report", f"project/{REPORT} missing",
            ["Run: .venv/Scripts/python.exe tools/text/polish.py lint"],
        )
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Result(False, "polish_report", f"{REPORT} invalid JSON: {exc}")


def _env(ctx: Ctx) -> dict:
    import os
    return {**os.environ,
            "MEDPAPER_PROJECT": str(ctx.project),
            "MEDPAPER_ROOT": str(Path(__file__).resolve().parents[3]),
            "PYTHONIOENCODING": "utf-8"}


def _declared_limits(text: str) -> dict[str, int]:
    """Pull numeric caps out of the quoted guidelines."""
    out: dict[str, int] = {}
    patterns = [
        (r"abstract[^.\n]{0,60}?(\d{2,4})\s*words", "abstract"),
        (r"(\d{2,4})\s*words[^.\n]{0,30}?abstract", "abstract"),
        (r"(?:main\s+text|manuscript|body|article)[^.\n]{0,60}?(\d{3,5})\s*words", "main"),
        (r"(\d{3,5})\s*words[^.\n]{0,40}?(?:main\s+text|manuscript|body|excluding)", "main"),
        (r"references?[^.\n]{0,40}?(?:max(?:imum)?|limit(?:ed)?\s*to|up\s+to|no\s+more\s+than)"
         r"[^.\n]{0,20}?(\d{1,3})", "references"),
        (r"(?:max(?:imum)?|up\s+to|no\s+more\s+than)\s*(\d{1,3})\s*references?", "references"),
    ]
    low = text.lower()
    for rx, kind in patterns:
        m = re.search(rx, low)
        if m and kind not in out:
            out[kind] = int(m.group(1))
    return out


def _ref_count(ctx: Ctx) -> int:
    keys: set[str] = set()
    names = (("full_manuscript.md",) if ctx.p("08_submission/integration/full_manuscript.md").exists()
             else ("introduction.md", "methods.md", "results.md", "discussion.md"))
    for name in names:
        base = "08_submission/integration" if name == "full_manuscript.md" else "07_manuscript"
        p = ctx.p(f"{base}/{name}")
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            for grp in re.findall(r"\[([^\]]*@[^\]]*)\]", text):
                keys.update(re.findall(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)", grp))
    return len(keys)


def _canonical_section_counts(text: str) -> dict[str, int]:
    """Count journal-limited sections without counting title, keywords, refs or legends."""
    matches = list(re.finditer(r"(?m)^#\s+([^#\n].*)$", text))
    out: dict[str, int] = {}
    wanted = {"abstract", "introduction", "methods", "results", "discussion"}
    for i, match in enumerate(matches):
        name = match.group(1).strip().casefold()
        if name not in wanted:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[match.end():end]
        block = re.sub(r"(?m)^Keywords\s*:.*$", "", block, flags=re.I)
        out[name] = len(re.findall(r"[A-Za-z][A-Za-z'-]*", block))
    return out

