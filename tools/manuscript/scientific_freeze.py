#!/usr/bin/env python3
"""Create or verify the S19 journal-independent scientific-master freeze."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from wfcore import paths, registry  # noqa: E402
from wfcore.scientificfreeze import verify, write  # noqa: E402


def _project() -> Path:
    raw = os.environ.get("MEDPAPER_PROJECT")
    return Path(raw).resolve() if raw else paths.project_dir().resolve()


def _state(project: Path) -> dict:
    try:
        return json.loads((project / ".wf/state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(f"workflow state is unavailable: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="freeze the user-approved S19 scientific master")
    parser.add_argument("command", choices=["freeze", "verify"])
    parser.add_argument("--project", type=Path)
    args = parser.parse_args()
    project = args.project.resolve() if args.project else _project()
    try:
        if args.command == "freeze":
            state = _state(project)
            if state.get("current") != "S19_human_review":
                raise ValueError("the scientific master may be frozen only at S19_human_review")
            decision = state.get("decisions", {}).get("manuscript_human_reviewed", {})
            if decision.get("value") != "NO_FURTHER_REVIEW":
                raise ValueError("explicit NO_FURTHER_REVIEW approval is required before freezing")
            pipeline = registry.load()
            output, payload, created = write(project, str(pipeline.meta["version"]))
            action = "created" if created else "reused unchanged"
            print(f"{action} scientific-master freeze -> {output}")
            print(f"freeze_id={payload['freeze_id']}; review_package_id={payload['review_package_id']}")
            return 0
        ok, problems, payload = verify(project)
        if not ok or payload is None:
            print("scientific-master freeze verification failed:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 2
        print(f"verified scientific master {payload['freeze_id']} ({len(payload['files'])} files)")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"scientific freeze error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

