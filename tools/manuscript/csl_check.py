#!/usr/bin/env python3
"""Compare a rendered REAL-example bibliography with sourced official examples."""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docx import Document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", type=Path, required=True); parser.add_argument("--examples", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.examples.read_text(encoding="utf-8"))
        if not data.get("source") or not data.get("examples"): raise ValueError("official source and nonempty real examples required")
        entries = [p.text for p in Document(args.docx).paragraphs if p.style and p.style.name == "Bibliography"]
        errors = []
        norm = lambda value: re.sub(r"\s+", " ", value).strip()
        for row in data["examples"]:
            number = row["number"]
            if type(number) is not int or number < 1 or number > len(entries): errors.append("rendered example reference missing"); continue
            if norm(entries[number-1]) != norm(row["expected"]): errors.append(f"example {number}: actual reference differs from the sourced expected rendering")
        print("\n".join(errors) if errors else "sourced CSL example comparison: PASS (not bibliographic identity verification)")
        return 2 if errors else 0
    except (OSError, ValueError, KeyError) as exc: print(str(exc)); return 2


if __name__ == "__main__": raise SystemExit(main())
