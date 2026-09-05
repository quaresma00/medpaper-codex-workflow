"""Path resolution. Stdlib only."""
from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Repo root = parent of tools/. Overridable with MEDPAPER_ROOT."""
    env = os.environ.get("MEDPAPER_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def pipeline_dir() -> Path:
    return repo_root() / "pipeline"


def pipeline_file() -> Path:
    return pipeline_dir() / "pipeline.toml"


def reference_dir() -> Path:
    return repo_root() / "reference"


def tools_dir() -> Path:
    return repo_root() / "tools"


def project_dir(layout: dict | None = None) -> Path:
    env = os.environ.get("MEDPAPER_PROJECT")
    if env:
        return Path(env).resolve()
    name = (layout or {}).get("project_dir", "project")
    return repo_root() / name


def rel(p: Path) -> str:
    """Repo-relative POSIX path for stable printing."""
    try:
        return p.resolve().relative_to(repo_root()).as_posix()
    except ValueError:
        return p.as_posix()
