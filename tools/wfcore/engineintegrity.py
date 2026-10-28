"""Detect changed installed engine files without git or claims of an OS security sandbox."""
import hashlib,json
from pathlib import Path,PurePosixPath

BASELINE=".medpaper-engine.json"
PREFIXES=("tools/","pipeline/","reference/",".agents/")


def engine_member(name):
    return name.startswith(PREFIXES) or name in {"AGENTS.md","bootstrap.py","requirements.txt"}


def verify_engine(root,required=False):
    root=Path(root).resolve(); baseline=root/BASELINE
    if not baseline.is_file():
        if required: raise ValueError("Required installed-engine baseline is missing; repair through maintenance, never silently downgrade to legacy mode")
        return "maintenance/legacy checkout: no packaged baseline; not certified immutable"
    row=json.loads(baseline.read_text(encoding="utf-8"))
    if not isinstance(row,dict) or row.get("schema_version")!=1 or not isinstance(row.get("files"),dict) or not row["files"]: raise ValueError("Installed engine baseline is invalid; repair through workflow maintenance, never a study-side reset")
    defects=[]
    for relative,expected in row["files"].items():
        part=PurePosixPath(relative)
        if part.is_absolute() or ".." in part.parts or not engine_member(relative): raise ValueError("Invalid engine baseline path")
        path=(root/part).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected: defects.append(relative)
    if defects: raise ValueError("Installed engine changed: "+", ".join(defects[:8])+". Stop study work; report a focused maintenance defect. Do not edit engine/state or weaken integrity gates to proceed.")
    return "packaged engine identity matches"
