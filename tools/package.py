#!/usr/bin/env python3
"""Build a verified, credential-free Codex bundle from this repository."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".toml", ".yaml", ".yml", ".json", ".py", ".txt", ".ps1"}
EXCLUDED_DIRS = {".git", ".venv", "dist", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}
REQUIRED = {
    "AGENTS.md",
    "INSTALL-CODEX.md",
    ".agents/skills/medpaper-codex-pipeline/SKILL.md",
    ".agents/skills/medpaper-codex-pipeline/agents/openai.yaml",
    "pipeline/pipeline.toml",
    "tools/wf.py",
    "reference/codex-integration.md",
    "reference/methods-structure.md",
}
SECRET_RE = re.compile(
    r"(?i)\b((?:[A-Z0-9]+_)*(?:API_KEY|TOKEN|ACCESS_TOKEN|AUTH_TOKEN|CLIENT_SECRET|"
    r"PRIVATE_KEY|PASSWORD|SECRET))\s*=\s*[\"']([^\"']+)[\"']"
)
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b")


def included_files(output: Path) -> list[Path]:
    files = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.resolve() == output.resolve():
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts) or p.suffix in EXCLUDED_SUFFIXES:
            continue
        if rel.parts and rel.parts[0] == "project" and rel.as_posix() != "project/.gitkeep":
            continue
        files.append(p)
    return files


def placeholder(value: str) -> bool:
    low = value.strip().lower()
    return any(mark in low for mark in ("<", ">", "...", "your ", "example", "change_me"))


def scan(files: list[Path]) -> list[str]:
    problems = []
    for p in files:
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        for m in SECRET_RE.finditer(text):
            if not placeholder(m.group(2)):
                problems.append(f"{rel}: non-placeholder value assigned to {m.group(1)}")
        for m in EMAIL_RE.finditer(text):
            if m.group(1).lower() not in {"example.org", "example.com", "example.net"}:
                problems.append(f"{rel}: personal email address present")
    return sorted(set(problems))


def run_check(cmd: list[str], label: str) -> None:
    print(f">>> {label}")
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode:
        raise SystemExit(f"{label} failed with exit code {proc.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser(description="package a verified medpaper-codex ZIP")
    ap.add_argument("--output", type=Path, default=ROOT.parent / "medpaper-codex-ready.zip")
    ap.add_argument("--skip-selftest", action="store_true")
    args = ap.parse_args()
    output = args.output.expanduser()
    if not output.is_absolute():
        output = (ROOT / output).resolve()

    py = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not py.exists():
        raise SystemExit(".venv is missing; run bootstrap.py before packaging")
    run_check([str(py), "tools/wf.py", "doctor"], "workflow doctor")
    if not args.skip_selftest:
        run_check([str(py), "tools/selftest.py"], "offline regression suite")

    files = included_files(output)
    rels = {p.relative_to(ROOT).as_posix() for p in files}
    missing = sorted(REQUIRED - rels)
    if missing:
        raise SystemExit("required package files missing: " + ", ".join(missing))
    problems = scan(files)
    if problems:
        raise SystemExit("credential/privacy scan failed:\n  " + "\n  ".join(problems))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            rel = p.relative_to(ROOT)
            zf.write(p, Path("medpaper-codex") / rel)

    with zipfile.ZipFile(output) as zf:
        bad = zf.testzip()
        if bad:
            output.unlink(missing_ok=True)
            raise SystemExit(f"ZIP integrity check failed at {bad}")
        count = len(zf.infolist())
    print(f"packaged {count} files -> {output} ({output.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
