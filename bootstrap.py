#!/usr/bin/env python3
"""Create and verify the local medpaper-codex environment."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
MIN_SCIENCE_PYTHON = (3, 12)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd: list[str], label: str) -> bool:
    print(f"\n>>> {label}\n    {' '.join(map(str, cmd))}")
    try:
        proc = subprocess.run(cmd, cwd=ROOT)
    except FileNotFoundError:
        print(f"    !! command not found: {cmd[0]}")
        return False
    if proc.returncode:
        print(f"    !! exited {proc.returncode}")
        return False
    return True


def create_venv(uv: str | None) -> bool:
    if venv_python().exists():
        try:
            probe = subprocess.run([str(venv_python()), "-c", "import json,sys;print(json.dumps(list(sys.version_info[:2])))"],
                                   capture_output=True, text=True, timeout=15)
            version = tuple(json.loads(probe.stdout)) if probe.returncode == 0 else ()
        except (OSError, ValueError, subprocess.TimeoutExpired):
            version = ()
        if len(version) != 2 or version < MIN_SCIENCE_PYTHON:
            print("Existing .venv does not provide Python 3.12+ required by pinned NumPy/SciPy; restore the workspace's Python 3.13 environment. Study data/state were not changed.")
            return False
        print(f"\n>>> virtual environment already exists: {VENV.name}")
        return True
    if uv:
        return run([uv, "venv", "--python", "3.13", str(VENV)], "create Python 3.13 environment")
    if sys.version_info < MIN_SCIENCE_PYTHON:
        print(f"Python 3.12+ required by pinned science dependencies; found {sys.version.split()[0]}. Prefer uv with Python 3.13.")
        return False
    return run([sys.executable, "-m", "venv", str(VENV)], "create virtual environment")


def install_dependencies(uv: str | None) -> bool:
    req = ROOT / "requirements.txt"
    if not req.exists():
        print("requirements.txt is missing")
        return False
    if uv:
        cmd = [uv, "pip", "install", "--python", str(venv_python()), "-r", str(req)]
    else:
        cmd = [str(venv_python()), "-m", "pip", "install", "-r", str(req)]
    return run(cmd, "install pinned science dependencies")


def main() -> int:
    ap = argparse.ArgumentParser(description="set up and verify medpaper-codex")
    ap.add_argument("--skip-selftest", action="store_true")
    args = ap.parse_args()

    uv = shutil.which("uv")
    if not uv and sys.version_info < MIN_SCIENCE_PYTHON:
        print(f"Python 3.12+ required by pinned science dependencies; found {sys.version.split()[0]}. Prefer uv with Python 3.13.")
        return 1

    print("=" * 72)
    print("medpaper-codex bootstrap")
    print(f"root:   {ROOT}")
    print(f"runner: {sys.executable} ({sys.version.split()[0]})")
    print(f"uv:     {uv or 'not found; using stdlib venv/pip'}")
    print("=" * 72)

    if not create_venv(uv) or not install_dependencies(uv):
        return 1
    py = str(venv_python())
    required = [
        ([py, "tools/wf.py", "init"], "initialize project state"),
        ([py, "tools/wf.py", "doctor"], "validate workflow and environment"),
    ]
    if not args.skip_selftest:
        required.append(([py, "tools/selftest.py"], "run offline regression suite"))
    for cmd, label in required:
        if not run(cmd, label):
            return 1

    print("\nSetup complete. Open this directory in Codex and start with:")
    print(f"    {venv_python()} tools/wf.py status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
