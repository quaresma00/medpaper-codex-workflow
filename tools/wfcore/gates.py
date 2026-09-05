"""Gate runner: turns declarative gate specs into pass/fail results."""
from __future__ import annotations

from pathlib import Path

from . import checks
from .checks import Ctx, Result


def run_stage(pipeline, state, project: Path, stage) -> list[Result]:
    checks.load_all()
    results: list[Result] = []
    if not stage.gate:
        results.append(Result(True, "-", "stage declares no gate"))
        return results
    for spec in stage.gate:
        name = spec.get("check")
        fn = checks.get(name)
        if fn is None:
            results.append(
                Result(False, name or "<missing>", f"unknown check '{name}' - not in the registry",
                       [f"Known checks: {', '.join(checks.known())}"])
            )
            continue
        ctx = Ctx(pipeline=pipeline, state=state, project=project, stage=stage, spec=spec)
        try:
            res = fn(ctx)
        except Exception as exc:  # noqa: BLE001 - a broken check must not brick the pipeline
            res = Result(False, name, f"check raised {type(exc).__name__}: {exc}")
        if "severity" in spec and not res.ok:
            res.severity = spec["severity"]
        results.append(res)
    return results


def summarize(results: list[Result]) -> tuple[bool, int, int]:
    blocking = sum(1 for r in results if r.blocking)
    warned = sum(1 for r in results if (not r.ok) and r.severity == "warn")
    return blocking == 0, blocking, warned
