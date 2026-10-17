"""Author-edited upload copies: an explicit handoff mode, not fabricated independence."""
import json
import re
import shutil
import stat
from pathlib import Path
from .packagefreeze import FREEZE_REL, _sha256, _safe_path, verify_freeze
from .readiness import atomic_json

DIR = "08_submission/final_copy"
RECORD = ".wf/final_copy.json"


def source(project):
    ok, problems, _ = verify_freeze(project)
    if not ok: raise ValueError("source freeze invalid: " + "; ".join(problems))
    freeze = json.loads((project / FREEZE_REL).read_text(encoding="utf-8"))
    files = {str(Path(row["path"]).relative_to("08_submission/bundle")).replace("\\", "/"): project / freeze["release_dir"] / Path(row["path"]).relative_to("08_submission/bundle") for row in freeze["files"]}
    return freeze, files


def prepare(project):
    freeze, files = source(project)
    for rel, path in files.items():
        destination = _safe_path(project, f"{DIR}/{rel}")[1]
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, destination)
            destination.chmod(destination.stat().st_mode | stat.S_IWUSR)
    return len(files)


def record(project, edits, words):
    if not edits or any(len(edit.strip()) < 8 for edit in edits) or len(words.strip()) < 4:
        raise ValueError("record the actual author authorization and concrete manual edits")
    freeze, _ = source(project)
    payload = {"source_freeze_id": freeze["freeze_id"], "author_words": words, "manual_edits": edits,
               "meaning": "Author final-copy handoff; not a new independent review or actual submission", "check": None}
    atomic_json(project / RECORD, payload)
    return payload


def check(project):
    from .presentationdelta import canonical, text
    from .journalspec import docx_problems, load
    from manuscript.build_docx import audit_docx, load_style, planned_figure_ids, figure_legend_cap
    freeze, originals = source(project)
    payload = json.loads((project / RECORD).read_text(encoding="utf-8"))
    if payload["source_freeze_id"] != freeze["freeze_id"]: raise ValueError("source approval changed; record against its actual current release")
    audit = project / "08_submission/independent_submission_audit.md"
    if not audit.is_file() or not re.search(r"(?mi)^\s*PASS(?:\s|$)", audit.read_text(encoding="utf-8")):
        raise ValueError("author final copy does not waive unresolved independent-review findings; original audit must PASS")
    problems = []; actual = {path.relative_to(project / DIR).as_posix(): path for path in (project / DIR).rglob("*") if path.is_file() and not path.name.startswith("~$")}
    if set(actual) != set(originals): problems.append("final-copy inventory must match every exact required upload, not just edited documents")
    style = load_style(project / "08_submission/docx_style.json")
    manifest = json.loads((project / "08_submission/bundle/manifest.json").read_text(encoding="utf-8"))
    roles = {str(Path(item["file"]).relative_to("08_submission/bundle")).replace("\\", "/"): item.get("role", "") for item in manifest["items"] if item.get("upload", True)}
    for rel in set(actual) & set(originals):
        path, old = actual[rel], originals[rel]
        if path.suffix.lower() in {".docx", ".xlsx"}:
            if canonical(text(old), project) != canonical(text(path), project):
                problems.append(f"{rel}: visible scientific content changed; reconcile to source, not a manual-copy waiver")
            if path.suffix.lower() == ".docx":
                role = roles.get(rel, "")
                wanted = planned_figure_ids(project) if role in {"manuscript", "figure_legends"} else None
                problems += audit_docx(path, style, role, wanted, figure_legend_cap())
                problems += docx_problems(path, load(project), project, role)
        elif _sha256(path) != _sha256(old): problems.append(f"{rel}: changed non-Office scientific asset requires its managed producer")
    bindings = {FREEZE_REL: _sha256(project / FREEZE_REL), "08_submission/independent_submission_audit.md": _sha256(audit)}
    for rel in ("08_submission/target_journal.json", "08_submission/guidelines_extract.md", "08_submission/submission_requirements.json", "08_submission/docx_style.json", "00_input/author_info.json"):
        if (project / rel).is_file(): bindings[rel] = _sha256(project / rel)
    payload["check"] = {"ok": not problems, "problems": problems,
                        "files": {f"{DIR}/{rel}": _sha256(path) for rel, path in actual.items()}, "bindings": bindings}
    atomic_json(project / RECORD, payload)
    return problems


def verified(project):
    try:
        payload = json.loads((project / RECORD).read_text(encoding="utf-8")); proof = payload.get("check") or {}
        if not proof.get("ok"): return ["author final-copy check has not passed"]
        actual = {path.relative_to(project).as_posix(): _sha256(path) for path in (project / DIR).rglob("*") if path.is_file() and not path.name.startswith("~$")}
        if actual != proof["files"]: return ["author final-copy inventory/content drifted"]
        for rel, digest in proof["bindings"].items():
            if not (project / rel).is_file() or _sha256(project / rel) != digest: return [f"final-copy context drifted: {rel}"]
        return []
    except (OSError, ValueError, KeyError) as exc: return [str(exc)]
