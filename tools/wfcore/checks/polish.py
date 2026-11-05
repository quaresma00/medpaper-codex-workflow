"""Polish-stage checks: contextual language, house style, and fact preservation.

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
                                  "title_page.md", "statements.md","figure_legends.md","supplementary_figure_legends.md")
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
    struct = [x for x in rep.get("structure", []) if x.get("severity") == "blocking"]
    if struct:
        return Result(
            False,
            "ai_tells_clean",
            f"{len(struct)} prose structure finding(s): "
            + "; ".join(f"{x['kind']} in {Path(x['file']).name}" for x in struct[:4]),
            ["Full detail: .venv/Scripts/python.exe tools/text/polish.py lint",
             "Correct the actual structure while preserving scientific content and explicit journal requirements."],
        )
    prompts = rep.get("ai_tells", [])
    if prompts:
        return Result(True, "ai_tells_clean",
                      f"{len(prompts)} advisory wording prompt(s); assess medical meaning, redundancy and claim support before acceptance")
    return Result(True, "ai_tells_clean", "no wording prompts; medical semantic acceptance remains required")


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
    """Use explicitly sourced, article-specific fields; unknown limits remain null."""
    from ..journalrules import limits, compare
    from ..submission import docx_sections, word_count
    try:
        requirements,rules = limits(ctx.project)
        include = requirements["word_count"]["include_sections"]
        if not isinstance(include,list) or not include:
            raise ValueError("Explicit journal main-text section scope is missing")
        manifest = ctx.read_json("08_submission/bundle/manifest.json") if ctx.exists("08_submission/bundle/manifest.json") else {}
        final = [r for r in manifest.get("items",[]) if r.get("role") == "manuscript"]
        if ctx.stage.index >= ctx.pipeline.stage("S23_package").index and len(final) == 1:
            from ..journalspec import aliases, load
            mapping = {label.casefold(): key for key,label in aliases(load(ctx.project)).items()}
            mapping.update(requirements.get("section_aliases", {}))
            _,parts,_ = docx_sections(ctx.p(final[0]["file"]),mapping)
            counts = {k:word_count(v) for k,v in parts.items()}
        else:
            rel = "08_submission/integration/full_manuscript.md"
            if ctx.exists(rel):
                counts = _canonical_section_counts(ctx.read(rel))
                counts = {k.title():v for k,v in counts.items()}
            else:
                counts = {name:word_count(ctx.read(f"07_manuscript/{name.lower()}.md"))
                          for name in [*include,"Abstract"] if ctx.exists(f"07_manuscript/{name.lower()}.md")}
        missing = [name for name in [*include,"Abstract"] if name not in counts]
        if missing:
            raise ValueError("Journal-count sections missing: "+", ".join(missing))
        actual = {"main":sum(counts[name] for name in include),"abstract":counts["Abstract"],"references":_ref_count(ctx)}
        problems = compare(actual,rules)
        return Result(not problems,"journal_limits_met","; ".join(problems) or "Article-specific structured limits met; unspecified caps not invented")
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return Result(False,"journal_limits_met",str(exc),["Resolve the actual S20 requirement fields, not numbers found by regex in guide prose."])


# ---------------------------------------------------------------------------
def _report(ctx: Ctx):
    p = ctx.p(REPORT)
    if not p.exists():
        return Result(
            False, "polish_report", f"project/{REPORT} missing",
            ["Run: .venv/Scripts/python.exe tools/text/polish.py lint"],
        )
    try:
        report=json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(report,dict): raise ValueError("language report must be an object")
        from ..state import version_tuple
        required=(version_tuple(str(ctx.state.data.get("pipeline_version","0"))) >= (1,23,0)
                  and not ctx.state.pin_excludes(ctx.stage.id,"1.23.0"))
        if required or report.get("lint_policy_version")==2:
            from ..packagefreeze import _sha256, _safe_path
            if report.get("lint_policy_version")!=2: raise ValueError("language report uses an obsolete policy; rerun lint")
            hashes=report.get("input_hashes",{})
            from text.polish import CANONICAL_ORDER, LEGACY_SECTION_ORDER
            order=CANONICAL_ORDER if ctx.p("08_submission/integration/full_manuscript.md").is_file() else LEGACY_SECTION_ORDER
            wanted={rel for rel in order if ctx.p(rel).is_file() and ctx.p(rel).stat().st_size>0}
            if set(hashes)!=wanted: raise ValueError("language report does not cover the current manuscript files")
            for rel,digest in hashes.items():
                _,source=_safe_path(ctx.project,rel)
                if not source.is_file() or _sha256(source)!=digest: raise ValueError(f"language report is stale for {rel}; rerun lint")
            if report.get("linter_sha256")!=_sha256(Path(__file__).resolve().parents[2]/"text/polish.py"):
                raise ValueError("language diagnostics changed; rerun lint")
            allow=ctx.p("08_submission/integration/polish_allowlist.tsv")
            if report.get("allowlist_sha256")!=(_sha256(allow) if allow.is_file() else None):
                raise ValueError("language exceptions changed; rerun lint")
        return report
    except (OSError,ValueError,TypeError) as exc:
        return Result(False, "polish_report", f"{REPORT} missing valid current evidence: {exc}")


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
