#!/usr/bin/env python3
"""Generate author-facing portal fields and actual final-DOCX text counts."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wfcore.submission import write_portal, verify_portal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("project"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if not args.check:
            doc = write_portal(args.project)
            print(f"final DOCX: main={doc['word_counts']['main']}, abstract={doc['word_counts']['abstract']}")
            print(args.project.resolve() / "08_submission/portal_fields.json")
        problems = verify_portal(args.project)
        print("\n".join(problems) if problems else "portal fields: PASS")
        return 2 if problems else 0
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
