#!/usr/bin/env python3
"""Show, synchronize, or check the title-page reference count against actual citations."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from wfcore.checks.refs import (  # noqa: E402
    actual_reference_count,
    declared_reference_counts,
    synchronize_reference_count,
)


def project_root() -> Path:
    raw = os.environ.get("MEDPAPER_PROJECT")
    return Path(raw).resolve() if raw else ROOT / "project"


def paths(project: Path) -> tuple[Path, Path]:
    return (project / "07_manuscript/full_manuscript.md",
            project / "07_manuscript/title_page.md")


def load(project: Path) -> tuple[Path, Path, str, str, int]:
    manuscript, title_page = paths(project)
    for path in (manuscript, title_page):
        if not path.is_file():
            raise FileNotFoundError(path)
    manuscript_text = manuscript.read_text(encoding="utf-8", errors="replace")
    title_text = title_page.read_text(encoding="utf-8", errors="replace")
    return manuscript, title_page, manuscript_text, title_text, actual_reference_count(manuscript_text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="bind an optional title-page reference count to citekeys actually used")
    parser.add_argument("command", choices=["show", "sync", "check"])
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument(
        "--add", action="store_true",
        help="with sync, add 'Number of references' when the title page lacks it; use only if required")
    args = parser.parse_args()
    project = args.project.resolve() if args.project else project_root()
    try:
        _, title_page, _, title_text, actual = load(project)
    except (FileNotFoundError, OSError) as exc:
        print(f"reference count: missing or unreadable input: {exc}", file=sys.stderr)
        return 2

    values = declared_reference_counts(title_text)
    if args.command == "show":
        print(f"actual distinct citations: {actual}")
        print("title-page field: " + (str(values[0]) if len(values) == 1 else
                                      "absent" if not values else "duplicate"))
        return 0 if len(values) <= 1 else 2

    if args.command == "check":
        if len(values) > 1:
            print("reference count: title page contains more than one count field", file=sys.stderr)
            return 2
        if not values:
            print(f"reference count: {actual} actual; no title-page field (permitted)")
            return 0
        if values[0] != actual:
            print(f"reference count mismatch: title page {values[0]}, actual {actual}", file=sys.stderr)
            return 2
        print(f"reference count: title page matches {actual} actual distinct citation(s)")
        return 0

    try:
        updated, changed = synchronize_reference_count(title_text, actual, add=args.add)
    except ValueError as exc:
        print(f"reference count: {exc}", file=sys.stderr)
        return 2
    if changed:
        title_page.write_text(updated, encoding="utf-8")
        print(f"reference count: synchronized title page to {actual}")
    elif values:
        print(f"reference count: already synchronized at {actual}")
    else:
        print(f"reference count: {actual} actual; no field added because the journal did not require one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
