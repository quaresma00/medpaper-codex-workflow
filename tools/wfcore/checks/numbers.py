"""Numeric provenance.

Rule enforced here: a number may appear in the manuscript or in a table only if
executed code already wrote it to 03_analysis/results/*.json. This is what stops
plausible-looking statistics from being invented during writing.
"""
from __future__ import annotations

import json
import re

from .. import xlsxlite
from . import Ctx, Result, check

RESULTS_GLOB = "03_analysis/results/*.json"
ALLOWLIST = "03_analysis/results/number_allowlist.tsv"

# Numbers that are conventions rather than findings.
CONVENTIONS = {
    "95", "99", "90", "100", "0.05", "0.01", "0.001", "0.025", "1.96", "0.5",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "0",
}

CITE_RE = re.compile(r"\[@[^\]]*\]")
FENCE_RE = re.compile(r"```.*?```", re.S)
ARTIFACT_RE = re.compile(
    r"\b(?:supplementary\s+)?(?:fig(?:ure)?s?|tables?|panels?|appendix|eq(?:uation)?s?)\.?\s*"
    r"[A-Za-z]?\d+[A-Za-z]?(?:\s*[-,and]+\s*[A-Za-z]?\d+[A-Za-z]?)*",
    re.I,
)
NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w])")


# ---------------------------------------------------------------------------
# building the pool of legitimate values
# ---------------------------------------------------------------------------
def _walk(obj, sink: set[str]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        sink.add(_norm(obj))
        return
    if isinstance(obj, str):
        for m in NUM_RE.finditer(obj):
            sink.add(_norm(m.group(1)))
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _walk(v, sink)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            _walk(v, sink)


def _norm(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return repr(round(f, 10))


def _pool(ctx: Ctx) -> tuple[set[float], set[str], list[str]]:
    """-> (float pool, raw-string pool, source file names)"""
    strings: set[str] = set()
    sources: list[str] = []
    for p in ctx.glob(RESULTS_GLOB):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sources.append(p.name)
        _walk(data, strings)
    floats: set[float] = set()
    for s in strings:
        try:
            floats.add(float(s))
        except ValueError:
            pass
    return floats, strings, sources


def _allowlist(ctx: Ctx) -> set[str]:
    allowed = set(CONVENTIONS)
    p = ctx.p(ALLOWLIST)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split("\t")[0].strip()
            if token:
                allowed.add(token)
    return allowed


def _matches(token: str, floats: set[float], strings: set[str]) -> bool:
    if token in strings:
        return True
    try:
        val = float(token)
    except ValueError:
        return False
    if val in floats:
        return True
    # Tolerate rounding to the precision the author displayed.
    dp = len(token.split(".")[1]) if "." in token else 0
    for f in floats:
        if round(f, dp) == val:
            return True
        if dp == 0 and abs(f - val) < 0.5 and f != 0:
            return True
    return False


def _scrub(text: str) -> str:
    text = FENCE_RE.sub(" ", text)
    text = CITE_RE.sub(" ", text)
    text = ARTIFACT_RE.sub(" ", text)
    text = re.sub(r"^\s*#{1,6}\s.*$", " ", text, flags=re.M)
    text = re.sub(r"\bp\s*[<>=]\s*0?\.0+\d*\b", " ", text, flags=re.I)  # p<0.001 style
    text = re.sub(r"\b(19|20)\d{2}\s*[-\u2013]\s*(19|20)?\d{2}\b", " ", text)  # not scrubbed values
    return text


def _offenders(text: str, floats, strings, allowed) -> list[tuple[int, str]]:
    bad: list[tuple[int, str]] = []
    for lineno, raw in enumerate(_scrub(text).splitlines(), start=1):
        for m in NUM_RE.finditer(raw):
            tok = m.group(1)
            if tok in allowed:
                continue
            if _matches(tok, floats, strings):
                continue
            bad.append((lineno, tok))
    return bad


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
@check("numbers_have_provenance")
def numbers_have_provenance(ctx: Ctx) -> Result:
    source = ctx.spec.get("source", "markdown")
    if source != "tables":
        rel = ctx.spec["path"]
        if not ctx.p(rel).exists():
            if ctx.spec.get("optional", False):
                return Result(True, "numbers_have_provenance", f"{rel}: optional file absent")
            return Result(False, "numbers_have_provenance", f"{rel} missing")

    floats, strings, sources = _pool(ctx)
    if not sources:
        return Result(
            False,
            "numbers_have_provenance",
            f"no result files under {RESULTS_GLOB}",
            ["Analysis code must dump every reported statistic to JSON before any prose is written."],
        )
    allowed = _allowlist(ctx)
    if source == "tables":
        offenders = []
        for p in ctx.glob("04_tables/main/*.xlsx") + ctx.glob("04_tables/supplementary/*.xlsx"):
            try:
                cells = xlsxlite.numeric_cell_values(p)
            except Exception as exc:  # noqa: BLE001 - report, do not crash the gate
                return Result(False, "numbers_have_provenance", f"cannot read {p.name}: {exc}")
            for sheet, ref, val in cells:
                for m in NUM_RE.finditer(str(val)):
                    tok = m.group(1)
                    if tok in allowed or _matches(tok, floats, strings):
                        continue
                    offenders.append(f"{p.name}[{sheet}]!{ref}={val}")
        if offenders:
            uniq = sorted(set(offenders))
            return Result(
                False,
                "numbers_have_provenance",
                f"{len(uniq)} table value(s) not traceable to results JSON: " + "; ".join(uniq[:8]),
                [
                    "Tables must be generated from 03_analysis/results/*.json, not retyped.",
                    f"If a value is a legitimate constant, add it to {ALLOWLIST} with a reason.",
                ],
            )
        return Result(True, "numbers_have_provenance", f"all table values trace to {len(sources)} result file(s)")

    bad = _offenders(ctx.read(rel), floats, strings, allowed)
    if bad:
        shown = "; ".join(f"line {ln}: {tok}" for ln, tok in bad[:10])
        return Result(
            False,
            "numbers_have_provenance",
            f"{rel}: {len(bad)} number(s) with no provenance -> {shown}",
            [
                "Every statistic must already exist in 03_analysis/results/*.json, written by executed code.",
                f"For genuine constants (thresholds, conventions), add them to {ALLOWLIST} as 'value<TAB>reason'.",
                "Do not fix this by rounding differently. Re-run the analysis and dump the value.",
            ],
        )
    return Result(True, "numbers_have_provenance", f"{rel}: every number traces to results JSON")


@check("numbers_cross_match")
def numbers_cross_match(ctx: Ctx) -> Result:
    """Numbers attributed to 'Table N' in Results must actually appear in Table N."""
    rel = "07_manuscript/results.md"
    if not ctx.p(rel).exists():
        return Result(False, "numbers_cross_match", f"{rel} missing")
    try:
        plan = ctx.read_json("01_protocol/artifact_plan.json")
    except Exception:  # noqa: BLE001
        return Result(False, "numbers_cross_match", "artifact_plan.json unreadable")

    table_files: dict[str, list] = {}
    for entry in plan.get("main_tables", []) + plan.get("supp_tables", []):
        label = str(entry.get("id", "")).strip()
        fp = entry.get("file")
        if not label or not fp:
            continue
        p = ctx.p(fp)
        if p.exists():
            try:
                table_files[label.lower()] = [v for _, _, v in xlsxlite.numeric_cell_values(p)]
            except Exception:  # noqa: BLE001
                table_files[label.lower()] = []

    if not table_files:
        return Result(False, "numbers_cross_match", "no rendered tables found to cross-match against")

    allowed = _allowlist(ctx)
    text = FENCE_RE.sub(" ", ctx.read(rel))
    sentences = re.split(r"(?<=[.;])\s+", text)
    problems: list[str] = []
    checked = 0
    for sent in sentences:
        refs = re.findall(r"\b((?:supplementary\s+)?table\s*S?\d+)\b", sent, re.I)
        if not refs:
            continue
        pool: set[str] = set()
        matched_label = None
        for r in refs:
            key = re.sub(r"\s+", " ", r.strip().lower())
            for label, vals in table_files.items():
                if key.endswith(label.split()[-1]) or label in key:
                    matched_label = label
                    for v in vals:
                        for m in NUM_RE.finditer(str(v)):
                            pool.add(m.group(1))
        if not pool:
            continue
        checked += 1
        body = ARTIFACT_RE.sub(" ", CITE_RE.sub(" ", sent))
        for m in NUM_RE.finditer(body):
            tok = m.group(1)
            if tok in allowed or tok in pool:
                continue
            if any(abs(float(tok) - float(v)) < 10 ** -max(0, len(tok.split(".")[1]) if "." in tok else 0)
                   for v in pool if _is_num(v)):
                continue
            problems.append(f"{tok} cited to {matched_label} but absent from it")
    if problems:
        uniq = sorted(set(problems))
        return Result(
            False,
            "numbers_cross_match",
            f"{len(uniq)} mismatch(es): " + "; ".join(uniq[:8]),
            ["Either the sentence cites the wrong table or the table was built from different values."],
        )
    return Result(
        True,
        "numbers_cross_match",
        f"{checked} table-citing sentence(s) agree with the rendered tables",
    )


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False
