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
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from wfcore import paths
from wfcore.packagefreeze import _safe_path, _sha256
from wfcore.readiness import atomic_json

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
    hashes = {r: _sha256(_safe_path(project, r)[1]) for r in inputs}
    if hashes != inputs:
        raise ValueError(f"{rel}: input changed; run only the affected producer and true dependents")
    return {"output": _sha256(_safe_path(project, rel)[1]), "script": env["script_sha256"], "inputs": hashes}


def run(project, script, timeout=600):
    project = project.resolve()
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
    process = subprocess.run(args, cwd=project, env=env, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout)
    log = project / "temp/analysis_logs" / (file.stem + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    temporary = log.with_suffix(".log.tmp")
    temporary.write_text(process.stdout + process.stderr, encoding="utf-8")
    temporary.replace(log)
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


def replay(project, only=None, timeout=600):
    project = project.resolve()
    original = results(project)
    report_path = project / PROOFS
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    selected = set(only or original)
    if selected - original.keys():
        raise ValueError("Requested output does not exist")
    executed = []
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
        before = {r: _sha256(_safe_path(project, r)[1]) for r in [script, *declared, *outputs]}
        with tempfile.TemporaryDirectory(prefix="medpaper-replay-") as tmp:
            sandbox = Path(tmp)
            for rel in [script, *declared]:
                source = _safe_path(project, rel)[1]
                dest = _safe_path(sandbox, rel)[1]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            run(sandbox, script, timeout)
            replayed = results(sandbox)
            if any(not (project / r).is_file() or _sha256(project / r) != h for r, h in before.items()):
                raise ValueError("Real study changed during replay; evidence not accepted")
            for rel in outputs:
                if rel not in replayed or canonical(replayed[rel]) != canonical(original[rel]):
                    raise ValueError(f"{rel}: replay differs (including exact counts); inspect nondeterminism or undeclared inputs")
                kept = project / ".wf/reproduction" / Path(rel).name
                kept.parent.mkdir(parents=True, exist_ok=True)
                atomic_json(kept, replayed[rel])
                report[rel] = {"identity": identity(project, rel, original[rel]),
                               "replayed": kept.relative_to(project).as_posix(), "replay_sha256": _sha256(kept)}
            executed.append(script)
    atomic_json(report_path, report)
    return executed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["run", "replay", "check"])
    ap.add_argument("--script")
    ap.add_argument("--output", action="append")
    ap.add_argument("--project", type=Path, default=paths.project_dir())
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    try:
        if args.command == "run":
            if not args.script:
                raise ValueError("run requires --script")
            run(args.project, args.script, args.timeout)
            print("Producer executed; validate scientific outputs before replay")
        elif args.command == "replay":
            print(json.dumps({"executed": replay(args.project, args.output, args.timeout)}))
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
