"""Rebuild actual stale DOCX consumers, then measure; never approve or reset a freeze."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from . import buildproof
from .packagefreeze import _safe_path, _sha256, expected_files


def _path(project: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        value = path.resolve().relative_to(project.resolve()).as_posix()
    return _safe_path(project, value)[1]


def command(project: Path, rel: str, receipt: dict) -> list[str]:
    if receipt.get("tool") != "tools/manuscript/build_docx.py":
        raise ValueError(f"{rel}: no supported recorded builder; run its real producer explicitly")
    params = receipt.get("parameters", {})
    inputs = params.get("inputs")
    if not inputs:
        # Exact historic entrypoints, excluding the explicitly recorded table specification.
        table = _path(project, params["tables_json"]) if params.get("tables_json") else None
        inputs = [p for p in receipt.get("entrypoints", []) if _path(project, p) != table]
    if not inputs or not params.get("kind") or not params.get("style"):
        raise ValueError(f"{rel}: incomplete build arguments; do not guess a source by file role")
    tools = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, str(tools / "manuscript/build_docx.py"), "build", "--kind", params["kind"],
           "--output", str(_path(project, rel)), "--style-config", str(_path(project, params["style"]))]
    for src in inputs:
        cmd += ["--input", str(_path(project, src))]
    for field, flag in (("bibliography", "--bibliography"), ("csl", "--csl"),
                        ("tables_json", "--tables-json"), ("csl_patch", "--csl-patch"), ("reference_doc", "--reference-doc")):
        if params.get(field):
            cmd += [flag, str(_path(project, params[field]))]
    if params.get("legend_scope"):
        cmd += ["--legend-scope", params["legend_scope"]]
    return cmd


def plan(project: Path) -> list[dict]:
    from .revision import guard_outputs
    from .journalcontext import guard,build_identity
    guard(project); current_identity=build_identity(project)
    uploads = expected_files(project, require_exists=False)
    receipts = buildproof.load(project)
    pending = []
    for rel, output in uploads.items():
        rec = receipts.get(rel)
        if not rec:
            if output.suffix.lower() == ".docx" or not output.is_file():
                raise ValueError(f"{rel}: no real build receipt; preserve the file and register its actual producer")
            continue  # Images/PDFs/workbooks stay with their own producer and scoped QA.
        if output.is_file() and _sha256(output) != rec.get("sha256"):
            raise ValueError(f"{rel}: changed outside its recorded build; preserve author edits and resolve them first")
        if output.is_file() and buildproof.inputs_current(rec) and all(rec.get(k)==v for k,v in current_identity.items()):
            continue
        cmd = command(project, rel, rec)
        guard_outputs(project, [output])
        pending.append({"output": rel, "command": cmd})
    affected = {r["output"] for r in pending}
    while True:
        consumers = [rel for rel in uploads if rel not in affected and receipts.get(rel) and any(
            str(_path(project, source)) in receipts[rel].get("sources", {}) for source in affected)]
        if not consumers:
            break
        for rel in consumers:
            guard_outputs(project, [uploads[rel]])
            pending.append({"output": rel, "command": command(project, rel, receipts[rel])})
            affected.add(rel)
    # Topological order from the real receipt sources, not an assumed manuscript-first order.
    ordered, remaining = [], {row["output"]: row for row in pending}
    while remaining:
        ready = [rel for rel in remaining if not any(
            str(_path(project, other)) in receipts[rel].get("sources", {})
            for other in remaining if other != rel)]
        if not ready:
            raise ValueError("Cyclic build receipts; resolve the actual producer dependencies before rebuilding")
        for rel in ready:
            ordered.append(remaining.pop(rel))
    return ordered


def run(project: Path, *, dry: bool = False, execute=None) -> int:
    from .dependencies import guard_build
    from .revision import active, baseline_capture_allowed
    from .state import State
    project = project.resolve()
    state = State(project).load()
    if state.current not in {"S23_package", "S24_package_human_review"}:
        raise ValueError("Package rebuilding belongs to S23 or a scoped S24 revision")
    guard_build(project)
    round_record = active(project)
    if round_record:
        from .revision import scope_problems
        problems = scope_problems(project, round_record)
        if problems:
            raise ValueError("Resolve revision scope before building: " + "; ".join(problems[:5]))
        if round_record.get("presentation_candidate"):
            from .presentationdelta import classify
            result = classify(project, round_record)
            if result["class"] != "presentation":
                raise ValueError("Resolve source meaning/science classification before an expensive rebuild; use rework.py preview and the existing owner rules")
    jobs = plan(project)  # Preflight every output before the first expensive build.
    if dry:
        print(json.dumps({"affected_uploads": [r["output"] for r in jobs], "commands": jobs}, ensure_ascii=False, indent=2))
        return 0
    if state.current == "S24_package_human_review" and jobs and not active(project):
        raise ValueError("Open and seal the source revision before rebuilding an approved package")
    if not jobs:
        print("No stale managed DOCX uploads; no build or repeated QA was run")
        return 0
    tools = Path(__file__).resolve().parents[1]
    log = project / ".wf/logs/rebuild.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MEDPAPER_PROJECT": str(project), "MEDPAPER_ROOT": str(tools.parent),
           "PYTHONIOENCODING": "utf-8"}
    execute = execute or subprocess.run
    with log.open("w", encoding="utf-8") as out:
        def step(label, cmd):
            out.write(f"{label}\n{json.dumps(cmd, ensure_ascii=False)}\n"); out.flush()
            result = execute(cmd, cwd=tools.parent, env=env, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=1800)
            output = (result.stdout or "") + (result.stderr or "")
            out.write(output + f"\nexit={result.returncode}\n"); out.flush()
            if result.returncode:
                raise ValueError(f"{label} failed ({result.returncode}); stopped before downstream evidence updates; details: {log}")
        for row in jobs:
            step(row["output"], row["command"])
        step("DOCX audit", [sys.executable, str(tools/"manuscript/build_docx.py"), "audit",
             "--manifest", str(project/"08_submission/bundle/manifest.json"),
             "--style-config", str(project/"08_submission/docx_style.json")])
        step("Final DOCX portal counts", [sys.executable, str(tools/"manuscript/submission_fields.py"), "--project", str(project)])
        step("Actual upload measurements", [sys.executable, str(tools/"submission_qc.py"), "measure", "--project", str(project)])
        # Classification and genuine builder receipts control recapture. Never bless Word edits.
        if state.current == "S23_package" or baseline_capture_allowed(project):
            args = ["--replace"] if (project/"08_submission/package_content_baseline.json").is_file() else []
            step("Content baseline", [sys.executable, str(tools/"package_content.py"), "capture", "--project", str(project), *args])
        elif (project/"08_submission/package_content_baseline.json").is_file():
            step("Content baseline", [sys.executable, str(tools/"package_content.py"), "verify", "--project", str(project)])
        if active(project):
            step("Scoped content checks", [sys.executable, str(tools/"rework.py"), "check", "--project", str(project)])
    print(f"Rebuilt {len(jobs)} affected DOCX upload(s), measured and checked; visual QA remains required: {log}")
    return 0
