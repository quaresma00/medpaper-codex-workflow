#!/usr/bin/env python3
"""Assemble the canonical medical manuscript in a fixed, testable order."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def project_root() -> Path:
    raw = os.environ.get("MEDPAPER_PROJECT")
    return Path(raw).resolve() if raw else ROOT / "project"


def read_required(project: Path, rel: str) -> str:
    path = project / rel
    if not path.is_file() or not path.read_text(encoding="utf-8", errors="replace").strip():
        raise ValueError(f"missing or empty: project/{rel}")
    return path.read_text(encoding="utf-8", errors="replace").strip()


def normalize_h1(text: str, expected: str) -> str:
    lines = text.strip().splitlines()
    if lines and re.fullmatch(r"#\s+.+", lines[0].strip()):
        lines[0] = f"# {expected}"
    else:
        lines.insert(0, f"# {expected}")
    return "\n".join(lines).strip()


def selected_title(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) != 1 or not lines[0].startswith("# ") or lines[0].startswith("## "):
        raise ValueError("project/07_manuscript/title.md must contain exactly one level-1 heading")
    title = re.sub(r"^#\s+", "", lines[0]).strip()
    if len(re.findall(r"[A-Za-z][A-Za-z'-]*", title)) < 5:
        raise ValueError("selected title is too short to identify the study")
    if re.search(r"\b(?:untitled|working title|title here|todo|tbd)\b", title, re.I):
        raise ValueError("selected title contains placeholder text")
    return title


def validate_keywords(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) != 1 or not re.match(r"^keywords\s*:", lines[0], re.I):
        raise ValueError("keywords.md must be one line beginning 'Keywords:'")
    payload = re.sub(r"^keywords\s*:\s*", "", lines[0], flags=re.I)
    if any(ch in payload for ch in "/;&"):
        raise ValueError("keywords must use commas only; '/', ';' and '&' are forbidden")
    items = [x.strip() for x in payload.split(",") if x.strip()]
    if len(items) < 3 or len(items) > 6:
        raise ValueError(f"keywords must contain 3-6 comma-separated terms, found {len(items)}")
    if len({x.casefold() for x in items}) != len(items):
        raise ValueError("keywords contain duplicates")
    return "Keywords: " + ", ".join(items)


def assemble(project: Path) -> str:
    title = selected_title(read_required(project, "07_manuscript/title.md"))
    abstract = normalize_h1(read_required(project, "07_manuscript/abstract.md"), "Abstract")
    keywords = validate_keywords(read_required(project, "07_manuscript/keywords.md"))
    sections = [
        normalize_h1(read_required(project, "07_manuscript/introduction.md"), "Introduction"),
        normalize_h1(read_required(project, "07_manuscript/methods.md"), "Methods"),
        normalize_h1(read_required(project, "07_manuscript/results.md"), "Results"),
        normalize_h1(read_required(project, "07_manuscript/discussion.md"), "Discussion"),
    ]
    statements_path = project / "07_manuscript/statements.md"
    if statements_path.is_file():
        statements = read_required(project, "07_manuscript/statements.md")
        sections.append(normalize_h1(statements, "Declarations and Statements"))
    legends = normalize_h1(read_required(project, "05_figures/legends.md"), "Figure legends")
    parts = [f"# {title}", abstract, keywords, *sections,
             "# References\n\n::: {#refs}\n:::", legends]
    return "\n\n".join(p.strip() for p in parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="assemble project/07_manuscript/full_manuscript.md")
    ap.add_argument("--check", action="store_true", help="fail if the current file differs")
    args = ap.parse_args()
    project = project_root()
    try:
        expected = assemble(project)
    except ValueError as exc:
        print(f"assemble: {exc}", file=sys.stderr)
        return 2
    output = project / "07_manuscript/full_manuscript.md"
    if args.check:
        if not output.is_file():
            print(f"assemble: missing {output}", file=sys.stderr)
            return 2
        if output.read_text(encoding="utf-8", errors="replace") != expected:
            print("assemble: full_manuscript.md differs from its gated source sections", file=sys.stderr)
            return 2
        print("canonical manuscript matches its source sections")
        return 0
    from wfcore.revision import guard_outputs
    guard_outputs(project, [output])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8")
    print(f"assembled canonical manuscript -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
