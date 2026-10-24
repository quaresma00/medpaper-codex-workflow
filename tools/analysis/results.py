"""Write full-precision finite results with observed execution provenance."""
from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import sys
from datetime import datetime, timezone

from wfcore import paths
from wfcore.packagefreeze import _safe_path, _sha256
from wfcore.readiness import atomic_json


def is_scientific_input(rel: str) -> bool:
    value=rel.replace("\\","/")
    return not value.startswith(("04_tables/","05_figures/","07_manuscript/","08_submission/","01_protocol/prototypes/")) and value not in {"01_protocol/artifact_plan.json","01_protocol/display_review.json","01_protocol/artifact_benchmark.md"}


def set_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    random.seed(seed)
    if "numpy" in sys.modules:
        sys.modules["numpy"].random.seed(seed)


def baseline_counts(values, groups=None, *, levels=None) -> dict:
    """All category levels, including both binary levels, with explicit denominators."""
    import pandas as pd
    series = pd.Series(values, dtype=object)
    categories = list(levels) if levels is not None else list(pd.unique(series.dropna()))
    if len({str(value) for value in categories}) != len(categories): raise ValueError("ambiguous category labels")
    if any(value not in categories for value in series.dropna()): raise ValueError("declared levels omit observed values")
    def count(part):
        return {"n_total": int(len(part)), "n_nonmissing": int(part.notna().sum()), "missing": int(part.isna().sum()),
                "counts": {str(level): int((part == level).sum()) for level in categories}}
    result = {"levels": [str(level) for level in categories], "overall": count(series), "groups": []}
    if groups is not None:
        grouping = pd.Series(groups, dtype=object)
        if len(grouping) != len(series): raise ValueError("groups must align with every observation")
        for group in pd.unique(grouping.dropna()): result["groups"].append({"group": str(group), **count(series[grouping == group])})
        result["missing_group"] = count(series[grouping.isna()])
    return result


def write_results(name: str, payload: dict, *, seed: int, inputs: list[str]) -> Path:
    """Call from the real producer, not from a receipt-repair script.

    inputs names every scientific input and project helper, not a sample thereof.
    A receipt documents execution; it does not prove statistical validity.
    """
    project = paths.project_dir().resolve()
    script = Path(sys.argv[0]).resolve()
    script_rel = script.relative_to(project).as_posix()
    if not script_rel.startswith("03_analysis/code/") or script.suffix.lower() != ".py":
        raise ValueError("write_results must run inside the actual analysis producer")
    if len(sys.argv) != 1:
        raise ValueError("Move scientific arguments into declared input/config files for replay")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer; call set_seed before stochastic work")
    if not name or Path(name).name != name or not name.endswith(".json"):
        raise ValueError("name must be a single .json filename")
    if not isinstance(payload, dict) or "environment" in payload:
        raise ValueError("result must be an object without hand-written environment metadata")
    if not inputs or len(inputs) != len(set(inputs)):
        raise ValueError("Declare all actual inputs once")
    hashes = {}
    for rel in inputs:
        normalized, file = _safe_path(project, rel)
        if not file.is_file() or normalized == script_rel or not is_scientific_input(normalized):
            raise ValueError(f"Missing or invalid scientific input: {rel}")
        hashes[normalized] = _sha256(file)
    # No permissive stringification: NaN/Infinity/unsupported values are errors.
    json.dumps(payload, allow_nan=False)
    loaded = {key.split('.')[0] for key in sys.modules}
    packages = {}
    for module, distributions in importlib.metadata.packages_distributions().items():
        if module in loaded:
            for distribution in distributions:
                packages[distribution] = importlib.metadata.version(distribution)
    environment = {"schema_version": 1, "language": "Python", "version": platform.python_version(),
                   "packages": packages, "seed": seed, "script": script_rel,
                   "script_sha256": _sha256(script), "inputs": hashes,
                   "written_at": datetime.now(timezone.utc).isoformat(), "writer": "medpaper-results-v1"}
    out = project / "03_analysis/results" / name
    if (project / ".wf/state.json").exists():
        from wfcore.revision import guard_outputs, record_build
        guard_outputs(project, [out])
    atomic_json(out, {**payload, "environment": environment})
    if (project / ".wf/state.json").exists():
        record_build(project, out, [script, *(_safe_path(project, r)[1] for r in inputs)])
    return out
