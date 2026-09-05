"""Filesystem / structural checks: existence, placement, discipline."""
from __future__ import annotations

import fnmatch
import json

from . import Ctx, Result, check


@check("outputs_exist")
def outputs_exist(ctx: Ctx) -> Result:
    optional = set(ctx.spec.get("optional", []))
    missing, empty, optional_present = [], [], 0
    for rel in ctx.stage.outputs:
        p = ctx.p(rel)
        if not p.exists():
            if rel not in optional:
                missing.append(rel)
        elif p.is_file() and p.stat().st_size == 0:
            empty.append(rel)
        elif rel in optional:
            optional_present += 1
    if missing or empty:
        bits = []
        if missing:
            bits.append("missing: " + ", ".join(missing))
        if empty:
            bits.append("empty: " + ", ".join(empty))
        return Result(
            False,
            "outputs_exist",
            "; ".join(bits),
            [f"Create each declared output under project/. Stage {ctx.stage.id} declares {len(ctx.stage.outputs)}."],
        )
    required = len(ctx.stage.outputs) - len(optional)
    detail = f"{required} required output(s) present"
    if optional:
        detail += f"; {optional_present}/{len(optional)} optional output(s) present"
    return Result(True, "outputs_exist", detail)


@check("no_future_artifacts")
def no_future_artifacts(ctx: Ctx) -> Result:
    """Enforce 'one thing at a time': later stages' outputs must not exist yet."""
    offenders = []
    for st in ctx.pipeline.stages_after(ctx.stage.id):
        if ctx.state.is_done(st.id):
            continue
        for rel in st.outputs:
            if ctx.p(rel).exists():
                offenders.append(f"{rel} (belongs to {st.id})")
    if offenders:
        return Result(
            False,
            "no_future_artifacts",
            "produced ahead of schedule: " + "; ".join(offenders[:8]),
            ["Delete these and produce them in their own stage. Running ahead is how the workflow drifts."],
        )
    return Result(True, "no_future_artifacts", "nothing produced ahead of schedule")


@check("single_section_written")
def single_section_written(ctx: Ctx) -> Result:
    """A manuscript stage may add only its own declared manuscript file(s)."""
    manuscript_stages = [
        s for s in ctx.pipeline.stages
        if any(o.startswith("07_manuscript/") and o.endswith(".md") for o in s.outputs)
    ]
    unexpected = []
    for st in manuscript_stages:
        if st.index <= ctx.stage.index or ctx.state.is_done(st.id):
            continue
        for rel in st.outputs:
            if rel.startswith("07_manuscript/") and ctx.p(rel).exists():
                unexpected.append(f"{rel} (stage {st.id})")
    if unexpected:
        return Result(
            False,
            "single_section_written",
            "manuscript file(s) from a future stage exist: " + "; ".join(unexpected),
            ["Write only the active stage's manuscript file(s). Remove the premature file(s)."],
        )
    return Result(True, "single_section_written", "only active-stage manuscript file(s) were written")


@check("file_count")
def file_count(ctx: Ctx) -> Result:
    pattern = ctx.spec["glob"]
    lo = ctx.spec.get("min")
    hi = ctx.spec.get("max")
    n = len(ctx.glob(pattern))
    if lo is not None and n < lo:
        return Result(False, "file_count", f"{pattern}: found {n}, need >= {lo}")
    if hi is not None and n > hi:
        return Result(False, "file_count", f"{pattern}: found {n}, allowed <= {hi}")
    return Result(True, "file_count", f"{pattern}: {n} file(s)")


@check("temp_clean")
def temp_clean(ctx: Ctx) -> Result:
    tmp = ctx.project / ctx.pipeline.layout.get("temp_dir", "temp")
    if not tmp.exists():
        return Result(True, "temp_clean", "no temp dir")
    leftovers = [p for p in tmp.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    if leftovers:
        names = ", ".join(p.name for p in leftovers[:8])
        return Result(
            False,
            "temp_clean",
            f"{len(leftovers)} leftover scratch file(s): {names}",
            ["Delete scratch files before advancing:  .venv/Scripts/python.exe tools/wf.py clean --apply"],
        )
    return Result(True, "temp_clean", "scratch dir empty")


@check("no_orphans")
def no_orphans(ctx: Ctx) -> Result:
    declared = ctx.pipeline.all_declared_outputs()
    free = ctx.pipeline.freeform
    always = ctx.pipeline.policy.get("always_allowed", [])
    orphans = []
    for p in ctx.project.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ctx.project).as_posix()
        if rel in declared:
            continue
        if any(fnmatch.fnmatch(rel, g) for g in free + always):
            continue
        orphans.append(rel)
    if orphans:
        return Result(
            False,
            "no_orphans",
            f"{len(orphans)} undeclared file(s): " + ", ".join(orphans[:10]),
            [
                "Either delete them, or declare them in pipeline.toml (stage outputs / [freeform].globs).",
                "Run `.venv/Scripts/python.exe tools/wf.py clean` to review.",
            ],
            severity=ctx.spec.get("severity", "fail"),
        )
    return Result(True, "no_orphans", "every file is accounted for")


@check("json_keys")
def json_keys(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    if not ctx.p(rel).exists():
        return Result(False, "json_keys", f"{rel} missing")
    try:
        data = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "json_keys", f"{rel} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        return Result(False, "json_keys", f"{rel} must be a JSON object")
    required = ctx.spec.get("keys", [])
    missing = [k for k in required if k not in data]
    blank = [k for k in required if k in data and data[k] in (None, "", [], {})]
    if missing or blank:
        bits = []
        if missing:
            bits.append("absent: " + ", ".join(missing))
        if blank:
            bits.append("empty: " + ", ".join(blank))
        return Result(False, "json_keys", f"{rel} -> " + "; ".join(bits))
    return Result(True, "json_keys", f"{rel}: {len(required)} required key(s) populated")
