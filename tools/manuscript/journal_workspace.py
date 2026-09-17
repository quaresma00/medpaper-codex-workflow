#!/usr/bin/env python3
"""Initialize or verify the active journal-specific integration workspace."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from wfcore import paths  # noqa: E402
from wfcore.journalworkspace import initialise, verify  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="derive journal integration sources from the S19 freeze")
    parser.add_argument("command", choices=["init", "verify"])
    parser.add_argument("--project", type=Path)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--require-pristine", action="store_true")
    args = parser.parse_args()
    raw = os.environ.get("MEDPAPER_PROJECT")
    project = args.project.resolve() if args.project else (
        Path(raw).resolve() if raw else paths.project_dir().resolve()
    )
    try:
        if args.command == "init":
            path, payload, created = initialise(project, replace=args.replace)
            action = "created" if created else "reused"
            print(f"{action} journal integration workspace -> {path}")
            print(f"journal={payload.get('journal')}; scientific_freeze_id={payload['scientific_freeze_id']}")
            return 0
        ok, problems, payload = verify(project, require_pristine=args.require_pristine)
        if not ok or payload is None:
            print("journal integration verification failed:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 2
        print(f"verified journal integration for {payload.get('journal')} ({len(payload['files'])} derived files)")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"journal workspace error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

