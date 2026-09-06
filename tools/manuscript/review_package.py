#!/usr/bin/env python3
"""Build or verify the current S19 third-party scientific-review ZIP."""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from wfcore import paths, registry  # noqa: E402
from wfcore.reviewpackage import build, verify  # noqa: E402


def _project() -> Path:
    raw = os.environ.get("MEDPAPER_PROJECT")
    return Path(raw).resolve() if raw else paths.project_dir().resolve()


def _current_stage(project: Path) -> str:
    try:
        return str(json.loads((project / ".wf/state.json").read_text(encoding="utf-8"))["current"])
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="versioned S19 scientific-review ZIP")
    parser.add_argument("command", choices=["build", "verify"])
    parser.add_argument("--project", type=Path, default=None)
    args = parser.parse_args()
    project = args.project.resolve() if args.project else _project()
    try:
        if args.command == "build":
            stage = _current_stage(project)
            if stage and stage != "S19_human_review":
                raise ValueError(
                    f"review ZIP may be built only at S19_human_review; current={stage}"
                )
            pipeline = registry.load()
            archive, manifest, created = build(project, str(pipeline.meta["version"]))
            action = "built" if created else "reused unchanged"
            print(f"{action} S19 review ZIP -> {archive}")
            print(f"revision v{manifest['package_revision']:03d}; package_id={manifest['package_id']}")
            return 0
        ok, details, manifest = verify(project)
        if not ok or manifest is None:
            print("S19 review ZIP verification failed:", file=sys.stderr)
            for detail in details:
                print(f"  - {detail}", file=sys.stderr)
            return 2
        print(
            f"verified S19 review ZIP v{manifest['package_revision']:03d} -> "
            f"{project / manifest['archive_path']}"
        )
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"S19 review ZIP error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

