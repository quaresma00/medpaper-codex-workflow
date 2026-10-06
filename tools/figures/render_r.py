#!/usr/bin/env python3
"""Run one declared R figure in staging, inspect real output, then publish atomically."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from figures.r_audit import audit_svg
from wfcore.packagefreeze import _safe_path, _sha256
from wfcore.readiness import atomic_json
from wfcore.revision import guard_outputs, record_build, permits
from wfcore.dependencies import guard_build
from wfcore.state import State


def render(project, figure_id, timeout=180):
    project = project.resolve()
    guard_build(project)
    state = State(project).load()
    if state.current != "S11_figures" and not permits(project, "S11_figures"):
        raise ValueError("Publication R figures run at S11 or an explicitly scoped S11 revision")
    plan_path = project / "01_protocol/artifact_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    matches = [e for g in ("main_figures", "supp_figures") for e in plan.get(g, []) if e.get("id") == figure_id]
    if len(matches) != 1:
        raise ValueError("Figure must occur exactly once in the artifact plan")
    entry = matches[0]
    script_rel, script = _safe_path(project, entry["script"])
    if script.suffix.casefold() != ".r" or not script.is_file():
        raise ValueError("The declared R plotting script is missing or has no .R extension")
    sources = {r: _safe_path(project, r)[1] for r in entry.get("source_results", [])}
    if not sources or any(not r.startswith("03_analysis/results/") or not p.is_file() for r, p in sources.items()):
        raise ValueError("Declare every actual executed result JSON input")
    rscript = shutil.which("Rscript")
    if not rscript:
        raise ValueError("Rscript is unavailable; restore R, do not silently substitute Python")
    png_rel, png = _safe_path(project, entry["file"])
    pdf_rel, pdf = _safe_path(project, entry.get("pdf", ""))
    if png.suffix.lower() != ".png" or pdf.suffix.lower() != ".pdf":
        raise ValueError("R publication entries must declare PNG and vector PDF")
    qc = project / "05_figures/qc"
    extra = {".svg": qc / (png.stem + ".render.svg"), ".rmeta.json": qc / (png.stem + ".rmeta.json")}
    sidecar = qc / (png.stem + ".artist.json")
    destinations = {".png": png, ".pdf": pdf, **extra}
    if entry.get("tiff"):
        destinations[".tiff"] = _safe_path(project, entry["tiff"])[1]
    guard_outputs(project, list(destinations.values()) + [sidecar])
    helper = ROOT / "tools/figures/r_style.R"
    before = {str(p): _sha256(p) for p in [script, helper, plan_path, *sources.values()]}
    (project / "temp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r-figure-", dir=project / "temp") as temporary:
        stem = Path(temporary) / png.stem
        env = {**os.environ, "MEDPAPER_ROOT": str(ROOT), "MEDPAPER_PROJECT": str(project),
               "MEDPAPER_RENDER_STEM": str(stem), "MEDPAPER_FIGURE_SCRIPT": str(script),
               "MEDPAPER_SOURCE_RESULTS": json.dumps(list(sources))}
        if os.name == "nt":
            env.update({"LC_ALL": "C", "LANG": "C"})
        expression = ("a <- file.path(Sys.getenv('MEDPAPER_ROOT'), 'renv/activate.R'); "
                      "if(file.exists(a)) source(a); options(warn=2); "
                      "sys.source(Sys.getenv('MEDPAPER_FIGURE_SCRIPT'), envir=.GlobalEnv)")
        process = subprocess.run([rscript, "--vanilla", "--encoding=UTF-8", "-e", expression],
                                 cwd=ROOT, env=env, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=timeout)
        if process.returncode:
            raise ValueError("R render failed; prior output preserved: " + (process.stderr or process.stdout)[-2400:])
        if any(not Path(str(stem) + suffix).is_file() for suffix in destinations):
            raise ValueError("R helper did not produce every declared output; prior output preserved")
        metadata = json.loads(Path(str(stem) + ".rmeta.json").read_text(encoding="utf-8"))
        if metadata.get("width_class") != entry.get("width"):
            raise ValueError("R physical width differs from the artifact plan")
        report = audit_svg(Path(str(stem) + ".svg"), metadata)
        if any(not Path(p).is_file() or _sha256(Path(p)) != h for p, h in before.items()):
            raise ValueError("Source changed during rendering; prior output preserved")
        for suffix, destination in destinations.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            Path(str(stem) + suffix).replace(destination)
        report["source_hashes"] = {r: before[str(p)] for r, p in sources.items()}
        report["script"] = script_rel
        report["script_sha256"] = before[str(script)]
        report["render_hashes"] = {p.relative_to(project).as_posix(): _sha256(p) for p in destinations.values()}
        atomic_json(sidecar, report)
        for output in [*destinations.values(), sidecar]:
            record_build(project, output, [script, helper, *sources.values()])
    return {"figure": figure_id, "engine": "R", "png": str(png), "pdf": str(pdf), "audit": str(sidecar)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--project", type=Path, default=ROOT / "project")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    try:
        print(json.dumps(render(args.project, args.figure, args.timeout), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"R figure: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
