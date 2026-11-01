"""Small source snapshots and exact report ingestion; not a host security sandbox."""
from __future__ import annotations

import re
from pathlib import Path

from .packagefreeze import _sha256, _safe_path

ROOTS = ("00_input", "01_protocol", "03_analysis/code", "03_analysis/results",
         "04_tables", "05_figures", "06_refs", "07_manuscript", "08_submission")
SKIP = {"__pycache__", "releases", "review_packages", "journal_archives", "cache", "fulltext"}


def snapshot(project: Path) -> dict[str, str]:
    # No patient data, external data sources or full-text library rereads. The review's
    # selected inputs separately bind any full texts actually supplied to the reviewer.
    files = {}
    for root in ROOTS:
        for path in (project / root).rglob("*"):
            if (path.is_file() and not any(part in SKIP for part in path.relative_to(project).parts)
                    and not path.name.startswith("~$") and path.suffix.lower() not in {".pyc", ".log", ".tmp"}):
                rel = path.relative_to(project).as_posix()
                files[rel] = _sha256(_safe_path(project, rel)[1])
    return files


def verify(project: Path, before: dict[str, str]) -> None:
    current = snapshot(project)
    drift = sorted(p for p in set(before) | set(current) if before.get(p) != current.get(p))
    if drift:
        raise ValueError("Files changed during independent reading; restart or prepare current revalidation: " + ", ".join(drift[:8]))


def extract(raw: str) -> str:
    """Accept the actual supplied Markdown reply, never search host/thread state JSON."""
    start, end = "<<<REPORT>>>", "<<<END>>>"
    if start in raw or end in raw:
        if raw.count(start) != 1 or raw.count(end) != 1 or raw.index(end) < raw.index(start):
            raise ValueError("Expected exactly one complete <<<REPORT>>> ... <<<END>>> block")
        return raw.split(start, 1)[1].split(end, 1)[0]
    if raw.lstrip().startswith(("{", "[")) or not re.search(r"(?m)^#{1,3}\s", raw):
        raise ValueError("Supply the actual Markdown report, not a host state or report summary")
    return raw
