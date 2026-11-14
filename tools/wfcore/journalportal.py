"""Observed portal exceptions and journal/date-named upload handoffs.

Portal observations are current-source evidence, never inferred from a login screen.
Delivery copies contain only manifest uploads and do not replace managed sources.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unicodedata

from . import journalcontext as jc
from .packagefreeze import _safe_path, _sha256, expected_files
from .readiness import atomic_json, load


def _slot(row):
    check=row.get("check",{})
    return check.get("type"),check.get("field"),tuple(sorted(check.get("roles",[])))


def supersession_problems(project, context, rows):
    """A required observed portal clause may replace only its explicit counterpart."""
    errors=[]; by_id={r.get("id"):r for r in rows if isinstance(r,dict)}
    for row in rows:
        if not isinstance(row,dict): continue
        other=row.get("superseded_by")
        if not other: continue
        replacement=by_id.get(other,{})
        guide=context.get("sources",{}).get(row.get("source_id"),{})
        portal=context.get("sources",{}).get(replacement.get("source_id"),{})
        if (guide.get("source_kind","guide")!="guide" or portal.get("source_kind")!="portal" or
                replacement.get("status")!="required" or row.get("status")!="required" or
                replacement.get("resolves")!=row.get("id") or replacement.get("superseded_by") or
                row.get("topic")!=replacement.get("topic") or _slot(row)!=_slot(replacement) or
                _slot(row)[0] not in {"style","profile","limit","uploads","figure","manual"} or
                len(str(row.get("conflict_reason","")).strip())<40):
            errors.append(f"{row.get('id')}: portal conflict needs two current required clauses, the same field/roles, reciprocal links and a substantive resolution")
        elif (_slot(row)[0]=="limit" and type(row.get("check",{}).get("value")) is int and
              type(replacement.get("check",{}).get("value")) is int and replacement["check"]["value"]>=row["check"]["value"]):
            errors.append(f"{row.get('id')}: compatible ceilings are not a conflict; keep the stricter explicit limit rather than relax the guide")
    for row in rows:
        if isinstance(row,dict) and row.get("resolves"):
            old=by_id.get(row["resolves"],{})
            if old.get("superseded_by")!=row.get("id"):
                errors.append(f"{row.get('id')}: portal resolution has no reciprocal guide clause")
    return errors


def resolve(project, guide_rule, portal_rule, reason):
    context=jc.current(project); req=load(project,jc.REQUIREMENTS)
    rows=req.get("guide_rules",[]); by_id={r["id"]:r for r in rows}
    if guide_rule not in by_id or portal_rule not in by_id: raise ValueError("Use two actual current guide_rules IDs")
    old,new=by_id[guide_rule],by_id[portal_rule]
    candidate=[dict(r) for r in rows]
    next(r for r in candidate if r["id"]==guide_rule).update(superseded_by=portal_rule,conflict_reason=reason)
    next(r for r in candidate if r["id"]==portal_rule).update(resolves=guide_rule)
    problems=supersession_problems(project,context,candidate)
    if problems: raise ValueError("; ".join(problems))
    # Source passage/configuration validation is still performed by ordinary seal.
    req["guide_rules"]=candidate; atomic_json(project/jc.REQUIREMENTS,req)
    context.pop("seal",None);atomic_json(project/jc.CONTEXT,context)
    return {"guide_rule":old["id"],"portal_rule":new["id"],"meaning":"Current required portal implementation; reconcile configuration, then reseal"}


def _safe_name(journal):
    value=unicodedata.normalize("NFKC",journal)
    value=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",value)
    value=re.sub(r"\s+","_",value).strip(" ._")[:90]
    if not value: raise ValueError("Actual journal name cannot form a safe delivery-directory name")
    return value


def _observed(project, row):
    directory=_safe_path(project,row["directory"])[1]
    if not directory.is_dir(): return None
    return {p.relative_to(directory).as_posix():_sha256(p) for p in directory.rglob("*") if p.is_file() and not p.name.startswith("~$")}


def delivery_status(project):
    context=jc.current(project); row=context.get("delivery")
    if not row: return {"directory":None,"status":"not_prepared","meaning":"No actual submission has been made"}
    actual=_observed(project,row)
    return {**row,"status":"current" if actual==row.get("files") else "changed_or_missing",
            "meaning":"Read-only preparation/upload copy; not an actual submission or a second authoring source"}


def deliver(project):
    """Publish exact current uploads without overwriting an author's changed copy."""
    jc.guard(project);context=jc.current(project);old=context.get("delivery")
    files=expected_files(project)
    if any(path.name.startswith("~$") for path in files.values()):
        raise ValueError("Office lock files are not upload documents; correct the exact manifest")
    snapshots={str(PurePosixPath(rel).relative_to("08_submission/bundle")):_sha256(path) for rel,path in files.items()}
    if old:
        if _observed(project,old)!=old.get("files"):
            raise ValueError("The named delivery copy was edited or removed; inspect/reconcile those changes with managed sources before creating another copy. It was not overwritten")
        if old.get("files")==snapshots:
            old["manifest_sha256"]=_sha256(project/"08_submission/bundle/manifest.json")
            context["delivery"]=old;atomic_json(project/jc.CONTEXT,context)
            return delivery_status(project)
    # This is preparation time, not the time of an unperformed Submit action.
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    base=f"{_safe_name(context['identity']['journal'])}_{stamp}"
    root=project/"08_submission/submission_packages";root.mkdir(parents=True,exist_ok=True)
    sequence=1;name=base
    while (root/name).exists():
        sequence+=1;name=f"{base}_{sequence:02d}"
    destination=root/name;_safe_path(project,destination.relative_to(project).as_posix())
    with tempfile.TemporaryDirectory(prefix=".delivery-",dir=root) as folder:
        staged=Path(folder)/name;staged.mkdir()
        for rel,path in files.items():
            relative=PurePosixPath(rel).relative_to("08_submission/bundle")
            output=staged/Path(relative);output.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,output)
        if any(_sha256(path)!=snapshots[str(PurePosixPath(rel).relative_to("08_submission/bundle"))] for rel,path in files.items()):
            raise ValueError("Managed uploads changed during delivery; no named package published")
        staged.rename(destination)
    for path in destination.rglob("*"):
        if path.is_file(): path.chmod(path.stat().st_mode & ~(stat.S_IWUSR|stat.S_IWGRP|stat.S_IWOTH))
    row={"context_id":context["context_id"],"directory":destination.relative_to(project).as_posix(),
         "prepared_at":jc.now(),"preparation_timezone":"Asia/Shanghai","files":snapshots,
         "manifest_sha256":_sha256(project/"08_submission/bundle/manifest.json")}
    context["delivery"]=row;atomic_json(project/jc.CONTEXT,context)
    return delivery_status(project)
