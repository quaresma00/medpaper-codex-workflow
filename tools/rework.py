#!/usr/bin/env python3
"""Route a user-requested revision to its earliest owning workflow stage."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wfcore import paths, registry  # noqa: E402
from wfcore.state import State  # noqa: E402


ROUTES = {
    "study-design": "S03_protocol",
    "data": "S04_data",
    "analysis": "S05_analysis",
    "final-protocol": "S06_protocol_final",
    "artifact-plan-or-legend": "S07_artifacts",
    "methods": "S08_methods",
    "results-wording": "S09_results",
    "tables": "S10_tables",
    "figures": "S11_figures",
    "introduction": "S14_introduction",
    "discussion": "S16_discussion",
    "title-abstract-keywords": "S17_assemble",
    "journal": "S20_journal",
    "title-page-or-statements": "S21_authors",
    "cover-letter-or-package-structure": "S23_package",
}


def resolve_route(kind: str, current: str, pipe) -> str:
    if kind == "manuscript-copyedit":
        current_index = pipe.stage(current).index
        if current_index < pipe.stage("S19_human_review").index:
            raise ValueError("manuscript-copyedit routing is available from S19 onward")
        return ("S22_polish" if current_index >= pipe.stage("S22_polish").index
                else "S19_human_review")
    if kind == "word-format-only":
        current_index = pipe.stage(current).index
        if current_index < pipe.stage("S23_package").index:
            raise ValueError("word-format-only routing is available after the package is built")
        return ("S23_package" if current == "S23_package"
                else "S24_package_human_review")
    return ROUTES[kind]


def main() -> int:
    kinds = sorted([*ROUTES, "manuscript-copyedit", "word-format-only"])
    parser = argparse.ArgumentParser(
        description="rewind medpaper to the source-owning stage before applying a revision")
    parser.add_argument("command", choices=["plan", "start"])
    parser.add_argument("--kind", choices=kinds, required=True)
    parser.add_argument("--why", required=True,
                        help="specific user-requested change and why this route owns it")
    parser.add_argument("--project", type=Path, default=None)
    args = parser.parse_args()
    if len(args.why.strip()) < 20:
        print("rework reason is too short; name the requested change and affected artifact",
              file=sys.stderr)
        return 2
    project = args.project.resolve() if args.project else paths.project_dir().resolve()
    try:
        pipe = registry.load()
        state = State(project, pipe.layout.get("state_dir", ".wf")).load()
        current = state.current
        target = resolve_route(args.kind, current, pipe)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"rework route error: {exc}", file=sys.stderr)
        return 2
    if pipe.stage(target).index > pipe.stage(current).index:
        print(f"rework route error: {target} is ahead of current stage {current}", file=sys.stderr)
        return 2
    print(f"revision route: {args.kind}: {current} -> {target}")
    if args.command == "plan":
        return 0
    tool = paths.tools_dir() / "wf.py"
    env = {**os.environ, "MEDPAPER_PROJECT": str(project),
           "MEDPAPER_ROOT": str(paths.repo_root()), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(tool), "loop", "--to", target, "--why",
         f"user-requested {args.kind} revision: {args.why.strip()}"],
        text=True, env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
