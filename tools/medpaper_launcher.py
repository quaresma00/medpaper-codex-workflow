#!/usr/bin/env python3
"""Source for the global skill's scripts/start_medpaper.py; invoke that installed copy."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath


SKILL_DIR = Path(__file__).resolve().parents[1]
ARCHIVE = SKILL_DIR / "assets" / "medpaper-codex-ready.zip"
ARCHIVE_ROOT = "medpaper-codex"


def is_pipeline(path: Path) -> bool:
    return (path / "pipeline" / "pipeline.toml").is_file() and (path / "tools" / "wf.py").is_file()


def pipeline_version(path: Path) -> str:
    definition = path / "pipeline" / "pipeline.toml"
    data = tomllib.loads(definition.read_text(encoding="utf-8"))
    return str(data.get("meta", {}).get("version", "unknown"))


def bundled_version() -> str:
    with zipfile.ZipFile(ARCHIVE) as zf:
        raw = zf.read(f"{ARCHIVE_ROOT}/pipeline/pipeline.toml").decode("utf-8")
    return str(tomllib.loads(raw).get("meta", {}).get("version", "unknown"))


def default_workspace() -> Path:
    current = Path.cwd().resolve()
    return current if is_pipeline(current) else current / "medpaper-study"


def safe_members(zf: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    for info in zf.infolist():
        name = PurePosixPath(info.filename)
        if name.is_absolute() or ".." in name.parts:
            raise RuntimeError(f"unsafe archive member: {info.filename}")
        if not name.parts or name.parts[0] != ARCHIVE_ROOT:
            raise RuntimeError(f"unexpected archive root: {info.filename}")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise RuntimeError(f"symbolic links are not allowed: {info.filename}")
        relative = PurePosixPath(*name.parts[1:])
        if relative.parts:
            members.append((info, relative))
    return members


def extract_new(workspace: Path) -> None:
    if not ARCHIVE.is_file():
        raise RuntimeError(f"bundled pipeline archive is missing: {ARCHIVE}")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if workspace.exists() and any(workspace.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty unrelated directory: {workspace}")

    temp_root = Path(tempfile.mkdtemp(prefix=".medpaper-install-", dir=workspace.parent))
    try:
        with zipfile.ZipFile(ARCHIVE) as zf:
            members = safe_members(zf)
            corrupt = zf.testzip()
            if corrupt:
                raise RuntimeError(f"bundled archive failed integrity check at {corrupt}")
            for info, relative in members:
                destination = temp_root.joinpath(*relative.parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as source, destination.open("wb") as sink:
                    shutil.copyfileobj(source, sink)
        if not is_pipeline(temp_root):
            raise RuntimeError("bundled archive does not contain a valid medpaper pipeline")
        if workspace.exists():
            workspace.rmdir()
        temp_root.replace(workspace)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def refresh_existing(workspace: Path) -> bool:
    """Replace only bundled engine files; preserve project data, venv, git and extras."""
    installed = pipeline_version(workspace)
    baseline=workspace/".medpaper-engine.json"
    if baseline.is_file():
        try: manifest=json.loads(baseline.read_text(encoding="utf-8"))
        except (ValueError,UnicodeError) as exc: raise RuntimeError("Installed engine baseline is unreadable; preserve the workspace for explicit maintenance") from exc
        if not isinstance(manifest,dict) or manifest.get("schema_version")!=1 or not isinstance(manifest.get("files"),dict) or not manifest["files"]:
            raise RuntimeError("Installed engine baseline is invalid; maintain explicitly rather than silently refreshing study code")
        for relative,expected in manifest["files"].items():
            part=PurePosixPath(relative); file=(workspace/part).resolve()
            if part.is_absolute() or ".." in part.parts or not file.is_relative_to(workspace.resolve()) or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
                raise RuntimeError("Installed engine was modified; preserve it and report the maintenance defect before upgrade: "+relative)
    bundled = bundled_version()
    if installed == bundled:
        return False
    temp_root = Path(tempfile.mkdtemp(prefix=".medpaper-refresh-", dir=workspace.parent))
    try:
        with zipfile.ZipFile(ARCHIVE) as zf:
            members = safe_members(zf)
            corrupt = zf.testzip()
            if corrupt:
                raise RuntimeError(f"bundled archive failed integrity check at {corrupt}")
            for info, relative in members:
                if relative.parts[0] == "project":
                    continue
                destination = temp_root.joinpath(*relative.parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as source, destination.open("wb") as sink:
                    shutil.copyfileobj(source, sink)
        workspace_resolved = workspace.resolve()
        # Update exactly the files carried by the engine bundle. Never replace whole
        # tools/reference/.agents directories: they may also contain user helpers.
        updates = []
        for source in temp_root.rglob("*"):
            if not source.is_file():
                continue
            destination = workspace / source.relative_to(temp_root)
            try:
                destination.resolve().relative_to(workspace_resolved)
            except ValueError as exc:
                raise RuntimeError(f"unsafe engine refresh target: {destination}") from exc
            if destination.is_dir():
                raise RuntimeError(f"engine file conflicts with an existing directory: {destination}")
            updates.append((source, destination))
        for source, destination in updates:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
        print(f"updated bundled medpaper engine {installed} -> {bundled}; project data preserved")
        return True
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def run_pipeline(workspace: Path, no_bootstrap: bool, refreshed: bool = False) -> int:
    if no_bootstrap:
        print(f"medpaper workspace ready: {workspace}")
        return 0
    uv = shutil.which("uv")
    venv_python = workspace / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not venv_python.is_file():
        if not uv:
            raise RuntimeError("uv was not found on PATH; install uv before bootstrapping medpaper")
        command = [uv, "run", "--python", "3.13", "python", "bootstrap.py"]
    elif refreshed:
        if not uv:
            raise RuntimeError("uv was not found on PATH; it is required to refresh pinned dependencies")
        command = [uv, "run", "--python", "3.13", "python", "bootstrap.py", "--skip-selftest"]
    else:
        command = [str(venv_python), "tools/wf.py", "status"]
    print(f"medpaper workspace: {workspace}")
    result = subprocess.run(command, cwd=workspace).returncode
    if result == 0 and command[-1] != "status":
        return subprocess.run([str(venv_python), "tools/wf.py", "status"], cwd=workspace).returncode
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="initialize or resume bundled medpaper pipeline")
    parser.add_argument("--workspace", type=Path, help="target workspace; defaults to cwd or cwd/medpaper-study")
    parser.add_argument("--no-bootstrap", action="store_true", help="extract only (for inspection/testing)")
    args = parser.parse_args()

    workspace = (args.workspace.expanduser() if args.workspace else default_workspace()).resolve()
    try:
        refreshed = False
        if not is_pipeline(workspace):
            extract_new(workspace)
            print(f"installed bundled medpaper pipeline {pipeline_version(workspace)} at {workspace}")
        else:
            refreshed = refresh_existing(workspace)
            print(f"resuming existing medpaper workspace at {workspace}")
        return run_pipeline(workspace, args.no_bootstrap, refreshed)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"medpaper launcher error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
