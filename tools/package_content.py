#!/usr/bin/env python3
"""Capture or verify the S23 visible-text baseline for submission DOCX files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wfcore.packagecontent import BASELINE_REL, verify_baseline, write_baseline  # noqa: E402


def _current_stage(project: Path) -> str:
    state = project / ".wf/state.json"
    try:
        return str(json.loads(state.read_text(encoding="utf-8")).get("current", ""))
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="bind submission DOCX visible text to the legitimate S23 build")
    parser.add_argument("command", choices=["capture", "verify"])
    parser.add_argument("--project", type=Path, default=Path("project"))
    parser.add_argument("--replace", action="store_true",
                        help="replace a prior baseline after a legitimate S23 rebuild")
    args = parser.parse_args()
    project = args.project.resolve()
    if args.command == "capture":
        stage = _current_stage(project)
        if stage and stage != "S23_package":
            print(f"package content: capture is allowed only at S23_package, current={stage}",
                  file=sys.stderr)
            return 2
        try:
            output = write_baseline(project, replace=args.replace)
        except (OSError, ValueError) as exc:
            print(f"package content: {exc}", file=sys.stderr)
            return 2
        print(f"captured DOCX visible-text baseline -> {output}")
        return 0
    ok, details, count = verify_baseline(project)
    if not ok:
        print("package content mismatch:", file=sys.stderr)
        for detail in details:
            print(f"  - {detail}", file=sys.stderr)
        return 2
    print(details[0] if details else f"{count} DOCX baseline(s) match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
