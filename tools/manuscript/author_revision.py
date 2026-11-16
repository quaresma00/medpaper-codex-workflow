#!/usr/bin/env python3
"""Inspect author DOCX revisions; import only source-equivalent layout in a scoped round."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wfcore import authorrevision, paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inspect", "adopt-layout"])
    parser.add_argument("--project", type=Path)
    parser.add_argument("--managed", type=Path, required=True, help="managed DOCX; relative paths use --project")
    parser.add_argument("--author", type=Path, required=True, help="author DOCX; relative paths also use --project")
    parser.add_argument("--managed-sha256", help="exact hash from current inspect (adopt-layout only)")
    parser.add_argument("--author-sha256", help="exact hash from current inspect (adopt-layout only)")
    parser.add_argument("--max-changes", type=int, default=8)
    parser.add_argument("--report", type=Path, help="optional local JSON diff file; never overwrites an existing file")
    args = parser.parse_args()
    project = (args.project or paths.project_dir()).resolve()
    resolved = lambda p: p.resolve() if p.is_absolute() else (project / p).resolve()
    try:
        managed, author = resolved(args.managed), resolved(args.author)
        if args.command == "adopt-layout":
            if args.report:
                parser.error("--report is an inspect-only diff output; adoption prints its own pending-QA result")
            if not args.managed_sha256 or not args.author_sha256:
                parser.error("adopt-layout requires both exact hashes from inspect")
            report = authorrevision.adopt_layout(project, managed, author,
                        managed_sha256=args.managed_sha256, author_sha256=args.author_sha256)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            report = authorrevision.compare(managed, author, max_changes=args.max_changes)
            for key in ("classification", "managed_sha256", "author_sha256", "changed_categories", "numbers_changed", "citations_or_identifiers_changed", "clinical_qualifiers_changed", "change_count"):
                print(f"{key}: {report[key]}")
            for change in report["shown_changes"]:
                print(f"{change['part']} managed paragraphs {change['managed_paragraphs']} -> author {change['author_paragraphs']}")
                print("  before: " + change["before"])
                print("  after: " + change["after"])
            for change in report["table_changes"]:
                print(f"{change['part']} table {change['table']}, row {change['row']}, cell {change['cell']}: {change['before']} -> {change['after']}")
            for change in report["member_changes"]:
                print(f"{change['category']} {change['member']}: {change['before_sha256']} -> {change['after_sha256']}")
            if report["section_properties"]:
                print("Section/page properties changed; see actual Word pages and optional JSON diff.")
            if report["truncated"]:
                print("Further changes omitted from this bounded summary; inspect the actual files and use --report if needed.")
            print(report["next_action"])
        if args.report:
            output = resolved(args.report)
            from wfcore.revision import guard_outputs
            try:
                output.relative_to(project)
            except ValueError:
                pass  # Explicit user-selected external report; originals are never overwritten.
            else:
                guard_outputs(project, [output])
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
            print(f"JSON diff: {output}")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"author Word revision: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
