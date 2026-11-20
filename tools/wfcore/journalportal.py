"""Observed portal exceptions and journal/date-named upload handoffs.

Portal observations are current-source evidence, never inferred from a login screen.
Delivery copies are separate from managed bundle sources and frozen releases.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from . import journalcontext as jc
from .packagefreeze import MANIFEST_REL, _safe_path, _sha256, expected_files
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


DELIVERY_ROOT = "08_submission/submission_packages"
DELIVERY_MODES = {"editable", "read-only"}
BUNDLE = "08_submission/bundle"
ALTERNATE_FORMATS = {".docx", ".xlsx", ".pdf", ".csv", ".tsv", ".odt", ".ods",
                     ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".svg", ".eps"}


def _delivery_record_path(project, context):
    context_id = str(context["context_id"])
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", context_id):
        raise ValueError("Invalid journal context identity for author delivery")
    return _safe_path(project, f".wf/deliveries/{context_id}.json")[1]


def _delivery_record(project, context):
    path = _delivery_record_path(project, context)
    row = load(project, path.relative_to(project).as_posix()) if path.is_file() else context.get("delivery")
    if row and row.get("context_id") != context["context_id"]:
        raise ValueError("Author delivery belongs to another journal context")
    return row


def _exact_path(project, relative):
    relative, path = _safe_path(project, relative)
    if path != project.joinpath(*PurePosixPath(relative).parts):
        raise ValueError(f"Author delivery path is redirected: {relative}")
    return path


def _directory(project, row):
    relative = PurePosixPath(row["directory"])
    if relative.parent.as_posix() != DELIVERY_ROOT:
        raise ValueError("Author copy must be a named directory under the delivery root")
    return _exact_path(project, relative.as_posix())


def _observed(project, row):
    directory = _directory(project, row)
    if not directory.is_dir():
        return None, {}, []
    files, modes, locks = {}, {}, []
    expected = _expected_copy(row)
    def raise_error(error):
        raise error
    for root, dirs, names in os.walk(directory, followlinks=False, onerror=raise_error):
        for name in dirs + names:
            path = Path(root) / name
            key = path.relative_to(directory).as_posix()
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError(f"Author copy contains a redirected path: {key}")
            if path.is_dir():
                continue
            if path.name.startswith("~$"):
                locks.append(key)
                continue
            if not path.is_file():
                raise ValueError(f"Author copy contains a non-file entry: {key}")
            files[key] = _sha256(path) if key in expected else None
            modes[key] = "writable" if path.stat().st_mode & stat.S_IWUSR else "read-only"
    return files, modes, sorted(locks)


def _expected_copy(row):
    return {**row["files"], **{key: item["sha256"] for key, item in row.get("auxiliary", {}).items()}}


def _set_mode(path, mode):
    bits = path.stat().st_mode
    write_bits = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    path.chmod(bits | stat.S_IWUSR if mode == "editable" else bits & ~write_bits)


def _file_snapshots(files):
    return {PurePosixPath(rel).relative_to(BUNDLE).as_posix(): _sha256(path) for rel, path in files.items()}


def _upload_key(rel):
    return PurePosixPath(rel).relative_to(BUNDLE).as_posix()


def delivery_status(project, *, verify_files=True):
    """Describe file identity and actual write flags independently of workflow review."""
    project = project.resolve()
    context = jc.current(project)
    row = _delivery_record(project, context)
    if not row:
        return {"directory": None, "status": "not_prepared", "scope": "author_delivery_files"}
    if not verify_files:
        return {"directory": row["directory"], "scope": "author_delivery_files",
                "status": "identity_not_checked" if _directory(project, row).is_dir() else "missing",
                "requested_file_mode": row.get("mode", "read-only")}
    actual, modes, locks = _observed(project, row)
    expected = _expected_copy(row)
    manifest = project / MANIFEST_REL
    manifest_current = manifest.is_file() and _sha256(manifest) == row.get("manifest_sha256")
    # Manifest identity and copy identity answer different questions. Neither is an audit.
    if manifest_current:
        try:
            manifest_current = _file_snapshots(expected_files(project)) == row["files"]
        except (OSError, ValueError):
            manifest_current = False
    observed_modes = set(modes.get(key) for key in expected if key in modes)
    copy_problems = []
    if actual is None:
        copy_problems.append("delivery directory is missing")
    else:
        for key in sorted(set(actual) | set(expected)):
            if key not in expected or key not in actual or actual[key] != expected[key]:
                issue = "unexpected" if key not in expected else "missing" if key not in actual else "changed"
                copy_problems.append(f"{issue}: {key}")
    return {**row, "status": "changed_or_missing" if copy_problems else "current" if manifest_current else "managed_uploads_changed",
            "scope": "author_delivery_files", "manifest_current": manifest_current,
            "requested_file_mode": row.get("mode", "read-only"),
            "observed_file_mode": next(iter(observed_modes)) if len(observed_modes) == 1 else "mixed" if observed_modes else "unknown",
            "office_lock_count": len(locks), "office_lock_files": locks[:12],
            "copy_problems": copy_problems[:12], "copy_problem_count": len(copy_problems),
            "meaning": "Author working copy; upload inventory and auxiliary files are tracked separately. Approval, final audit and submission have separate states."}


def deliver(project, mode="editable"):
    """Publish manifest uploads as a versioned author copy with explicit write flags."""
    if mode not in DELIVERY_MODES:
        raise ValueError("Author delivery mode must be editable or read-only")
    project = project.resolve()
    context = jc.current(project)
    old = _delivery_record(project, context)
    manifest = _exact_path(project, MANIFEST_REL)
    manifest_sha = _sha256(manifest)
    manifest_data = load(project, MANIFEST_REL)
    manifest_context = manifest_data.get("journal_context_id")
    if manifest_context is not None and manifest_context != context["context_id"]:
        raise ValueError("Managed uploads belong to a different journal context")
    files = expected_files(project)
    if any(path.name.startswith("~$") for path in files.values()):
        raise ValueError("Office lock files are not upload documents; correct the exact manifest")
    snapshots = _file_snapshots(files)
    record_path = _delivery_record_path(project, context)
    auxiliary = {}
    if old:
        actual, modes, _ = _observed(project, old)
        old_auxiliary = old.get("auxiliary", {})
        current_auxiliary = {key: item for key, item in old_auxiliary.items()
                             if snapshots.get(_upload_key(item["upload"])) == item["upload_sha256"]}
        if actual != _expected_copy(old):
            if (len(current_auxiliary) != len(old_auxiliary)
                    or actual != _expected_copy({"files": snapshots, "auxiliary": current_auxiliary})):
                raise ValueError("The named delivery copy was edited or removed; inspect/reconcile its changes before preparing another copy")
        requested = "writable" if mode == "editable" else "read-only"
        if (actual == _expected_copy({"files": snapshots, "auxiliary": old_auxiliary})
                and old.get("mode", "read-only") == mode and all(v == requested for v in modes.values())):
            if old.get("manifest_sha256") != manifest_sha or old["files"] != snapshots:
                atomic_json(record_path, {**old, "manifest_sha256": manifest_sha, "files": snapshots})
            return delivery_status(project)
        # An auxiliary belongs to these exact source upload bytes. Obsolete versions
        # stay in the prior author copy and can be reconverted against current sources.
        upload_names = {name.casefold() for name in snapshots}
        auxiliary = {key: item for key, item in current_auxiliary.items() if key.casefold() not in upload_names}
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    base = f"{_safe_name(context['identity']['journal'])}_{stamp}"
    root = _exact_path(project, DELIVERY_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    sequence, name = 1, base
    while (root / name).exists():
        sequence += 1
        name = f"{base}_{sequence:02d}"
    destination = _exact_path(project, f"{DELIVERY_ROOT}/{name}")
    with tempfile.TemporaryDirectory(prefix=".delivery-", dir=root) as folder:
        staged = Path(folder) / name
        staged.mkdir()
        sources = {**{_upload_key(rel): path for rel, path in files.items()},
                   **{key: _directory(project, old) / key for key in auxiliary}}
        for key, path in sources.items():
            output = staged / key
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)
            digest = snapshots[key] if key in snapshots else auxiliary[key]["sha256"]
            if _sha256(output) != digest:
                raise ValueError(f"Source changed during author delivery: {key}")
            _set_mode(output, mode)
        if (_sha256(manifest) != manifest_sha or _file_snapshots(files) != snapshots
                or jc.current(project)["context_id"] != context["context_id"]):
            raise ValueError("Managed uploads or journal context changed during author delivery")
        staged.rename(destination)
    row = {"schema_version": 2, "context_id": context["context_id"],
           "directory": destination.relative_to(project).as_posix(), "mode": mode,
           "prepared_at": jc.now(), "preparation_timezone": "Asia/Shanghai", "files": snapshots,
           "manifest_sha256": manifest_sha, "auxiliary": auxiliary}
    atomic_json(record_path, row)
    return delivery_status(project)


def _upload_items(project):
    return {item["file"].replace("\\", "/"): item for item in load(project, MANIFEST_REL)["items"]
            if item.get("upload", True) is not False}


def _check_alternate_format(path):
    suffix = path.suffix.lower()
    if suffix not in ALTERNATE_FORMATS or path.name.startswith("~$"):
        raise ValueError("Choose one supported alternate-format document or figure; SDK reports and lock files stay in staging")
    parts = {".xlsx": "xl/workbook.xml", ".docx": "word/document.xml",
             ".ods": "content.xml", ".odt": "content.xml"}
    if suffix in parts:
        try:
            with ZipFile(path) as archive:
                archive.getinfo(parts[suffix])
        except (BadZipFile, KeyError) as exc:
            raise ValueError(f"Alternate format does not contain its expected {suffix} document structure") from exc
    elif suffix == ".pdf":
        with path.open("rb") as stream:
            if b"%PDF-" not in stream.read(1024):
                raise ValueError("Alternate PDF file lacks a PDF header")


def attach_format(project, upload, alternate):
    """Register one exact auxiliary file against a current delivered upload version."""
    project = project.resolve()
    context = jc.current(project)
    old = _delivery_record(project, context)
    if not old:
        raise ValueError("Prepare an author delivery before adding an auxiliary format")
    rel, upload_path = _safe_path(project, upload)
    uploads = expected_files(project)
    if rel not in uploads:
        raise ValueError(f"Choose an actual upload path from the current manifest: {rel}")
    upload_key = _upload_key(rel)
    item = _upload_items(project)[rel]
    alternate = Path(alternate).resolve()
    if not alternate.is_file() or alternate.stat().st_size == 0:
        raise ValueError("Alternate-format input must be an existing nonempty file")
    _check_alternate_format(alternate)
    if alternate.suffix.casefold() == upload_path.suffix.casefold():
        raise ValueError("Auxiliary format must differ from the linked upload format")
    key = (PurePosixPath(upload_key).parent / alternate.name).as_posix()
    if any(key.casefold() == name.casefold() for name in old["files"]):
        raise ValueError("Auxiliary name conflicts with a delivered upload")
    previous = old.get("auxiliary", {})
    if any(key.casefold() == name.casefold() and key != name for name in previous):
        raise ValueError("Auxiliary name conflicts with an existing auxiliary file")
    directory = _directory(project, old)
    output = _exact_path(project, (directory / key).relative_to(project).as_posix())
    manifest = project / MANIFEST_REL
    manifest_sha = _sha256(manifest)
    expected_upload_hash = old["files"].get(upload_key)
    if (old.get("manifest_sha256") != manifest_sha or not expected_upload_hash or not upload_path.is_file()
            or _sha256(upload_path) != expected_upload_hash or not (directory / upload_key).is_file()
            or _sha256(_exact_path(project, f"{old['directory']}/{upload_key}")) != expected_upload_hash):
        raise ValueError("Linked upload or manifest changed; reconcile that upload before adding its alternate format")
    content_hash = _sha256(alternate)
    existing = previous.get(key)
    row = {"role": "auxiliary_format", "format": alternate.suffix.lower().lstrip("."), "sha256": content_hash,
           "upload": rel, "upload_role": item.get("role"), "upload_sha256": expected_upload_hash}
    if existing and existing != row:
        raise ValueError("An auxiliary file with this name already represents another version or upload; use a new filename")
    # Reconcile an independently placed file only when the explicitly supplied bytes match.
    # Different author bytes are always preserved, even if they occupy an untracked filename.
    created = False
    try:
        if output.exists():
            if not output.is_file() or _sha256(output) != content_hash:
                raise ValueError("Existing author file differs from this alternate format; use a new filename")
        else:
            with alternate.open("rb") as source, output.open("xb") as destination:
                created = True
                shutil.copyfileobj(source, destination)
            if _sha256(output) != content_hash:
                raise ValueError("Alternate-format input changed during delivery")
            _set_mode(output, old.get("mode", "read-only"))
        if (_sha256(manifest) != manifest_sha or _sha256(upload_path) != expected_upload_hash
                or _sha256(directory / upload_key) != expected_upload_hash
                or jc.current(project)["context_id"] != context["context_id"]
                or _delivery_record(project, context) != old):
            raise ValueError("Delivery or linked source changed during attachment; inspect current files")
        if row != existing or created:
            atomic_json(_delivery_record_path(project, context),
                        {**old, "schema_version": 2, "auxiliary": {**previous, key: row}})
    except BaseException:
        if created and output.is_file():
            _set_mode(output, "editable")
            output.unlink()
        raise
    return {"file": output.relative_to(project).as_posix(), **row,
            "scope": "auxiliary_format", "upload_manifest_changed": False,
            "status": delivery_status(project)["status"],
            "meaning": "Auxiliary format recorded for author use. Conversion equivalence and actual rendering require their own checks."}


def _office_edit_settings(path):
    if path.suffix.lower() not in {".docx", ".xlsx"}:
        return {}
    try:
        with ZipFile(path) as archive:
            if path.suffix.lower() == ".docx":
                if "word/settings.xml" not in archive.namelist():
                    return {"office_document_protected": False, "office_write_protection_setting_present": False}
                root = ET.fromstring(archive.read("word/settings.xml"))
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                protection = root.find(ns + "documentProtection")
                return {"office_document_protected": protection is not None and protection.get(ns + "enforcement") in {"1", "true", "on"},
                        "office_write_protection_setting_present": root.find(ns + "writeProtection") is not None}
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            root = ET.fromstring(archive.read("xl/workbook.xml"))
            protection = root.find(ns + "workbookProtection")
            locked = [flag for flag in ("lockStructure", "lockWindows", "lockRevision")
                      if protection is not None and protection.get(flag) in {"1", "true", "on"}]
            protected_sheets = 0
            for name in archive.namelist():
                if not re.fullmatch(r"xl/worksheets/[^/]+\.xml", name):
                    continue
                with archive.open(name) as stream:
                    for _, node in ET.iterparse(stream, ("end",)):
                        if node.tag == ns + "sheetProtection" and node.get("sheet") in {"1", "true", "on"}:
                            protected_sheets += 1
                            break
                        node.clear()
            return {"office_workbook_protection_flags": locked, "office_protected_worksheets": protected_sheets}
    except (BadZipFile, ET.ParseError, KeyError):
        return {"office_edit_settings": "unreadable"}


def delivery_files(project, upload=None):
    """Find exact upload roles and known producer inputs without a project-tree scan."""
    project = project.resolve()
    context = jc.current(project)
    row = _delivery_record(project, context)
    selected = _safe_path(project, upload)[0] if upload else None
    uploads = expected_files(project, require_exists=False)
    records = _upload_items(project)
    if selected is not None and selected not in uploads:
        raise ValueError(f"Choose an actual upload path from the current manifest: {selected}")
    from .buildproof import load as build_receipts, project_inputs
    receipts = build_receipts(project)
    directory = _directory(project, row) if row else None
    items = []
    for rel, path in uploads.items():
        if selected is not None and rel != selected:
            continue
        item = records[rel]
        key = _upload_key(rel)
        delivered = directory / key if directory and key in row["files"] else None
        auxiliary = []
        for name, value in (row or {}).get("auxiliary", {}).items():
            if value["upload"] != rel:
                continue
            part = {"delivered_file": f"{row['directory']}/{name}", "role": value["role"], "format": value["format"]}
            if selected:
                actual = _exact_path(project, part["delivered_file"])
                part["file_present"] = actual.is_file()
                if actual.is_file():
                    part["file_mode"] = "writable" if actual.stat().st_mode & stat.S_IWUSR else "read-only"
                    part.update(_office_edit_settings(actual))
            auxiliary.append(part)
        info = {"file": rel, "role": item.get("role"), "file_present": path.is_file(),
                "sources": project_inputs(project, receipts.get(rel, {})), "auxiliary": auxiliary}
        if delivered and delivered.is_file():
            info["delivered_file"] = delivered.relative_to(project).as_posix()
            info["file_mode"] = "writable" if delivered.stat().st_mode & stat.S_IWUSR else "read-only"
            if selected:
                _exact_path(project, info["delivered_file"])
                info.update(_office_edit_settings(delivered))
                info["office_lock_file_present"] = any(delivered.with_name(name).is_file()
                    for name in ("~$" + delivered.name, "~$" + delivered.name[2:]))
        items.append(info)
    return {"scope": "upload_inventory", "upload_count": len(items), "uploads": items,
            "author_copy": (row or {}).get("directory")}
