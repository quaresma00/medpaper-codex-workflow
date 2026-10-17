#!/usr/bin/env python3
"""Measure actual uploads once; verify unchanged measurements without rebuilding."""
import argparse
from pathlib import Path
from wfcore import paths
from wfcore.submissionqc import write, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["measure", "verify"])
    parser.add_argument("--project", type=Path)
    args = parser.parse_args()
    project = (args.project or paths.project_dir()).resolve()
    try:
        if args.command == "measure":
            receipt = write(project)
            print(f"measured {len(receipt['rows'])} final-file rows; visual QA remains a separate real inspection")
        problems = verify(project)
        print("\n".join(problems) if problems else "submission measurements current: PASS")
        return 2 if problems else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"submission measurement refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
