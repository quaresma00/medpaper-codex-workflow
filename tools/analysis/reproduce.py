#!/usr/bin/env python3
"""Run one producer, or replay only stale/missing result proofs in isolated copies."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from wfcore import paths
from wfcore.packagefreeze import _safe_path, _sha256
from wfcore.readiness import atomic_json
from wfcore.datasources import input_path,REGISTRY

PROOFS = ".wf/analysis_reproduction.json"


def results(project):
    return {p.relative_to(project).as_posix(): json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((project / "03_analysis/results").glob("*.json"))}


def canonical(value):
    value = copy.deepcopy(value)
    if isinstance(value.get("environment"), dict):
        value["environment"].pop("written_at", None)  # NOT scientific date/time fields.
    return value


def identity(project, rel, value):
    env = value.get("environment", {})
    if env.get("writer") != "medpaper-results-v1":
        raise ValueError(f"{rel}: no executed writer receipt; rerun the actual producer, never backfill")
    script, file = _safe_path(project, env["script"])
    if not script.startswith("03_analysis/code/") or _sha256(file) != env.get("script_sha256"):
        raise ValueError(f"{rel}: producer is missing or changed")
    inputs = env.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError(f"{rel}: no scientific inputs declared")
    from analysis.results import is_scientific_input
    if any(not is_scientific_input(source) for source in inputs):
        raise ValueError(f"{rel}: downstream manuscript/display was incorrectly declared as analysis input; correct the actual producer dependency instead of replaying prose changes")
    hashes = {r: _sha256(input_path(project,r)) for r in inputs}
    if hashes != inputs:
        raise ValueError(f"{rel}: input changed; run only the affected producer and true dependents")
    return {"output": _sha256(_safe_path(project, rel)[1]), "script": env["script_sha256"], "inputs": hashes}


def run(project, script, timeout=3600, *, log_project=None):
    project = project.resolve()
    from wfcore.engineintegrity import verify_engine
    verify_engine(ROOT)
    if (project / ".wf/state.json").exists():
        from wfcore.state import State
        from wfcore.revision import permits
        from wfcore.dependencies import guard_build
        guard_build(project)
        if State(project).load().current != "S05_analysis" and not permits(project, "S05_analysis"):
            raise ValueError("Execute analysis only at S05 or its explicitly scoped revision")
    rel, file = _safe_path(project, script)
    if not rel.startswith("03_analysis/code/") or file.suffix.lower() not in {".py", ".r"}:
        raise ValueError("Only a declared project analysis producer is executable")
    exe = sys.executable if file.suffix.lower() == ".py" else shutil.which("Rscript")
    if not exe:
        raise ValueError("Rscript missing; restore R rather than substituting an analysis")
    env = {**os.environ, "MEDPAPER_PROJECT": str(project), "MEDPAPER_ROOT": str(ROOT),
           "MEDPAPER_PYTHON": sys.executable, "PYTHONPATH": str(ROOT / "tools") + os.pathsep + os.environ.get("PYTHONPATH", ""),
           "PYTHONDONTWRITEBYTECODE": "1"}
    args = [exe, str(file)] if file.suffix.lower() == ".py" else [exe, "--vanilla", "--encoding=UTF-8", str(file)]
    from wfcore.execution import run_logged
    process = run_logged(args, project=log_project or project,cwd=project,env=env,timeout=timeout)
    log=process.log_path
    if process.returncode:
        raise ValueError(f"Producer failed ({process.returncode}); full log: {log}")
    return process


def verify(project):
    try:
        report = json.loads((project / PROOFS).read_text(encoding="utf-8")) if (project / PROOFS).exists() else {}
        state = project / ".wf/state.json"
        required = json.loads(state.read_text(encoding="utf-8")).get("analysis_receipts_required", False) if state.exists() else False
        defects = []
        for rel, value in results(project).items():
            if not value.get("environment", {}).get("writer"):
                if required or rel in report:
                    defects.append(f"{rel}: executed receipt missing; run the real producer, do not hand-write verification")
                continue  # Explicit legacy compatibility; no claim that it was reproduced.
            current = identity(project, rel, value)
            proof = report.get(rel, {})
            retained = _safe_path(project, proof.get("replayed", "missing"))[1]
            if proof.get("identity") != current or not retained.is_file() or _sha256(retained) != proof.get("replay_sha256"):
                defects.append(f"{rel}: missing/stale replay proof")
            elif canonical(json.loads(retained.read_text(encoding="utf-8"))) != canonical(value):
                defects.append(f"{rel}: retained replay disagrees with actual scientific results/environment")
        return defects
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [str(exc)]


def replay(project, only=None, timeout=3600, copy_limit_bytes=200*1024*1024):
    project = project.resolve()
    from wfcore.engineintegrity import verify_engine
    verify_engine(ROOT)
    original = results(project)
    report_path = project / PROOFS
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    selected = set(only or original)
    if selected - original.keys():
        raise ValueError("Requested output does not exist")
    executed = []
    copied=0
    by_script = {}
    for rel in sorted(selected):
        value = original[rel]
        current = identity(project, rel, value)
        prior = report.get(rel, {})
        retained = _safe_path(project, prior.get("replayed", "missing"))[1]
        if (prior.get("identity") == current and retained.is_file() and _sha256(retained) == prior.get("replay_sha256")
                and canonical(json.loads(retained.read_text(encoding="utf-8"))) == canonical(value)):
            continue
        by_script.setdefault(value["environment"]["script"], []).append(rel)
    for script, outputs in by_script.items():
        # Use immutable, complete declared inputs. No filename-order execution, reacquisition,
        # result truncation, broad folder reruns, or writes to the real study outputs.
        declared = set().union(*(original[r]["environment"]["inputs"] for r in outputs))
        before = {r: _sha256(input_path(project,r)) for r in [script, *declared, *outputs]}
        local=[script,*sorted(r for r in declared if not r.startswith("data:"))]
        required=sum(input_path(project,r).stat().st_size for r in local)
        if copy_limit_bytes<0 or copied+required>copy_limit_bytes:
            raise ValueError("Replay input-copy budget exceeded before copying. Register the full original dataset with data_sources.py and read its data: reference; never truncate, hard-link, overwrite originals or silently fall back to a large copy.")
        from wfcore.replayjobs import sandbox as owned_sandbox
        with owned_sandbox(project) as temporary:
            sandbox = Path(temporary)
            if any(r.startswith("data:") for r in declared):
                registry=_safe_path(sandbox,REGISTRY)[1]; registry.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(project/REGISTRY,registry)
            for rel in local:
                source = input_path(project,rel)
                dest = _safe_path(sandbox, rel)[1]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            copied+=required
            run(sandbox, script, timeout,log_project=project)
            replayed = results(sandbox)
            if any(not input_path(project,r).is_file() or _sha256(input_path(project,r)) != h for r, h in before.items()):
                raise ValueError("Real study changed during replay; evidence not accepted")
            for rel in outputs:
                if rel not in replayed or canonical(replayed[rel]) != canonical(original[rel]):
                    raise ValueError(f"{rel}: replay differs (including exact counts); inspect nondeterminism or undeclared inputs")
                # A later producer failure must not overwrite an earlier proof's replay.
                digest=_sha256(sandbox/rel)
                kept = project / ".wf/reproduction" / (Path(rel).stem+"-"+digest[:16]+".json")
                kept.parent.mkdir(parents=True, exist_ok=True)
                atomic_json(kept, replayed[rel])
                report[rel] = {"identity": identity(project, rel, original[rel]),
                               "replayed": kept.relative_to(project).as_posix(), "replay_sha256": _sha256(kept)}
            executed.append(script)
    atomic_json(report_path, report)
    return executed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["run", "replay", "check", "cleanup"])
    ap.add_argument("--script")
    ap.add_argument("--output", action="append")
    ap.add_argument("--project", type=Path, default=paths.project_dir())
    ap.add_argument("--timeout", type=int, default=3600,help="explicit producer deadline; long tasks use managed waits and heartbeat, not shell polling")
    ap.add_argument("--copy-limit-mb",type=int,default=200,help="local sandbox-copy budget; data: references copy zero dataset bytes")
    ap.add_argument("--apply",action="store_true",help="cleanup only owned sandboxes whose parent/recorded child are no longer alive")
    args = ap.parse_args()
    try:
        if args.command == "run":
            if not args.script:
                raise ValueError("run requires --script")
            run(args.project, args.script, args.timeout)
            print("Producer executed; validate scientific outputs before replay")
        elif args.command == "replay":
            print(json.dumps({"executed": replay(args.project, args.output, args.timeout,copy_limit_bytes=args.copy_limit_mb*1024*1024)}))
        elif args.command=="cleanup":
            from wfcore.replayjobs import cleanup
            print(json.dumps(cleanup(args.project,args.apply)))
        else:
            defects = verify(args.project)
            legacy = [r for r,v in results(args.project).items() if not v.get("environment",{}).get("writer")]
            print("\n".join(defects) if defects else "Receipted result proofs are current")
            if legacy:
                print(f"Legacy results not replayed: {len(legacy)}; rerun real producers on their next scientific revision")
            return 2 if defects else 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
