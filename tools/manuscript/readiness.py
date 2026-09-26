#!/usr/bin/env python3
"""Freeze or verify the analysis contract and clinical story before writing."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wfcore.readiness import freeze_writing, verify_writing, verify_displays, reader_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "verify", "displays", "review-inputs"])
    parser.add_argument("--project", type=Path, default=Path("project"))
    args = parser.parse_args()
    try:
        if args.command == "review-inputs":
            print(json.dumps({"reviewed_artifacts": reader_inputs(args.project)}, indent=2, ensure_ascii=False))
            return 0
        if args.command == "freeze":
            freeze_writing(args.project)
        problems = (verify_displays(args.project) if args.command == "displays"
                    else verify_writing(args.project))
        print("\n".join(problems) if problems else "readiness: PASS")
        return 2 if problems else 0
    except (OSError, ValueError) as exc:
        print(f"readiness: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
