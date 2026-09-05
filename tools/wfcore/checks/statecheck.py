"""Checks that read the run state rather than the filesystem."""
from __future__ import annotations

from . import Ctx, Result, check


@check("decision_recorded")
def decision_recorded(ctx: Ctx) -> Result:
    name = ctx.spec["name"]
    allowed = ctx.spec.get("allowed")
    rec = ctx.state.decision(name)
    if not rec:
        hint = f".venv/Scripts/python.exe tools/wf.py decide {name} <VALUE> --why \"...\""
        if allowed:
            hint = f".venv/Scripts/python.exe tools/wf.py decide {name} {'|'.join(allowed)} --why \"...\""
        return Result(
            False,
            "decision_recorded",
            f"decision '{name}' has not been recorded",
            [hint, "The rationale is written to state and to the handoff log, so it survives a context reset."],
        )
    value = rec.get("value")
    if allowed and value not in allowed:
        return Result(
            False,
            "decision_recorded",
            f"decision '{name}' is '{value}'; this stage requires one of {allowed}",
            ["A STOP or PIVOT verdict means the pipeline should not advance. Talk to the user."],
        )
    why = (rec.get("rationale") or "").strip()
    if len(why) < 40:
        return Result(
            False,
            "decision_recorded",
            f"decision '{name}'={value} has a {len(why)}-char rationale",
            ["Record why, in enough detail that a reviewer could challenge it. At least 40 characters."],
        )
    return Result(True, "decision_recorded", f"{name} = {value} (rationale on record)")
