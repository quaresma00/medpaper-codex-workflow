#!/usr/bin/env python3
"""Freeze or verify the submission package approved for independent review."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wfcore.packagefreeze import FREEZE_REL, verify_freeze, write_freeze  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="freeze and verify final submission-review inputs")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--project", type=Path, default=Path("project"))
        command.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    freeze = args.freeze.resolve() if args.freeze else project / Path(FREEZE_REL)
    try:
        if args.command == "freeze":
            output = write_freeze(project, freeze)
            ok, problems, count = verify_freeze(project, output)
            if not ok:
                raise ValueError("; ".join(problems))
            print(f"froze {count} final-review file(s) -> {output}")
            return 0
        ok, problems, count = verify_freeze(project, freeze)
        if not ok:
            print("submission package changed after user confirmation:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 2
        print(f"verified {count} frozen final-review file(s); no changes detected")
        return 0
    except (OSError, ValueError) as exc:
        print(f"package review error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
