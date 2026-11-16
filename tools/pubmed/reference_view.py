#!/usr/bin/env python3
"""Project selected, genuinely verified source fields into a stable producer input.

This is a derived input view, not another bibliography or citation permission. Its
bytes deliberately exclude library growth, usage notes and retrieval-event identity.
Producers consuming raw XML/full text must still declare those actual files as inputs.

    reference_view.py export --citekeys key1,key2 --fields title,abstract --output 06_refs/views/method_sources.json
    reference_view.py check --input 06_refs/views/method_sources.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed import eutils as eu
from wfcore import refproof
from wfcore.packagefreeze import _safe_path

KIND = "medpaper-reference-input-view"
IDENTITY = frozenset({"citekey", "pmid", "doi", "pmcid"})
FIELDS = IDENTITY | {"title", "abstract", "authors", "journal", "year"}
OUTPUT_RE = re.compile(r"06_refs/views/[A-Za-z0-9][A-Za-z0-9_.-]*\.json")


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def _bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _path(project: Path, raw: str) -> tuple[str, Path]:
    rel, path = _safe_path(project, raw)
    if not OUTPUT_RE.fullmatch(rel):
        raise ValueError("Reference views belong only in 06_refs/views/<name>.json")
    if path.relative_to(project.resolve()).as_posix() != rel:
        raise ValueError("Reference view paths cannot redirect through symlinks")
    return rel, path


def _selection(project: Path, citekeys, pmids) -> list[str]:
    entries = _read(project / "06_refs/library.json").get("entries")
    if not isinstance(entries, list) or any(not isinstance(row, dict) for row in entries):
        raise ValueError("The managed reference library has no valid entry list")
    by_key, by_pmid = {}, {}
    for row in entries:
        key, pmid = str(row.get("citekey", "")), str(row.get("pmid", ""))
        if not key or not re.fullmatch(r"\d+", pmid):
            raise ValueError("Every reference needs its existing citekey and real numeric PMID")
        if key in by_key or pmid in by_pmid:
            raise ValueError("Duplicate citekey or PMID makes a reference selection ambiguous")
        by_key[key], by_pmid[pmid] = row, key
    selected = set(citekeys)
    for pmid in pmids:
        if pmid not in by_pmid:
            raise ValueError(f"Selected PMID is absent from the managed library: {pmid}")
        selected.add(by_pmid[pmid])
    if not selected:
        raise ValueError("Select at least one existing citekey or PMID explicitly")
    missing = selected - set(by_key)
    if missing:
        raise ValueError("Selected citekeys are absent from the managed library: " + ", ".join(sorted(missing)))
    return sorted(selected)


def project_view(project: Path, *, citekeys=(), pmids=(), fields) -> dict:
    """Revalidate current receipts and read only selected source-verified fields."""
    fields = set(fields)
    if not fields or any(not isinstance(field, str) for field in fields) or fields - FIELDS:
        raise ValueError("Explicit fields must be selected from: " + ", ".join(sorted(FIELDS)))
    watched = [project / "06_refs/library.json", project / "06_refs/verified.json"]
    before = {path: refproof.file_sha256(path) for path in watched if path.is_file()}
    selected = _selection(project, citekeys, pmids)
    valid, problems, _ = refproof.validate_local_proof(project, required_keys=set(selected))
    if not valid:
        raise ValueError("Current genuine reference proof is required: " + "; ".join(problems[:8]))
    library = _read(watched[0])
    entries = {row["citekey"]: row for row in library["entries"]}
    receipts = _read(watched[1])["records"]
    payloads, payload_hashes, records = {}, {}, []
    wanted = sorted(IDENTITY | fields)
    for key in selected:
        evidence = receipts[key]["evidence"]
        _, path = _safe_path(project, evidence["cache_file"])
        if path not in payloads:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != evidence["payload_sha256"].casefold():
                raise ValueError(f"{key}: source XML changed while creating the reference view")
            payloads[path] = refproof.parse_pubmed_payload(raw)
            payload_hashes[path] = digest
        source = payloads[path].get(str(entries[key]["pmid"]))
        if source is None or refproof.record_sha256(source) != evidence["record_sha256"]:
            raise ValueError(f"{key}: selected article identity changed while creating the reference view")
        values = {**refproof.canonical_source(source), "citekey": key}
        records.append({field: values[field] for field in wanted})
    if (any(not path.is_file() or refproof.file_sha256(path) != digest for path, digest in before.items())
            or any(refproof.file_sha256(path) != digest for path, digest in payload_hashes.items())):
        raise ValueError("Reference inputs changed during view validation; retry with the current source proof")
    return {"schema_version": 1, "kind": KIND, "fields": wanted, "records": records}


def _owned(value: dict) -> bool:
    return value.get("kind") == KIND and value.get("schema_version") == 1


def export_view(project: Path, output: str, *, citekeys=(), pmids=(), fields, replace=False) -> dict:
    rel, path = _path(project, output)
    existing = path.read_bytes() if path.is_file() else None
    prior = _read(path) if existing is not None else None
    if prior is not None and not _owned(prior):
        raise ValueError("Refusing to overwrite an unrelated JSON file")
    view = project_view(project, citekeys=citekeys, pmids=pmids, fields=fields)
    content = _bytes(view)
    if existing == content:
        return {"status": "unchanged", "file": rel, "records": len(view["records"]), "fields": view["fields"]}
    if prior is not None and not replace:
        old_keys = sorted(row.get("citekey", "") for row in prior.get("records", []) if isinstance(row, dict))
        if old_keys != [row["citekey"] for row in view["records"]] or prior.get("fields") != view["fields"]:
            raise ValueError("Changing a managed view's selection/fields requires --replace and the actual revision scope")
    from wfcore.dependencies import guard_build
    from wfcore.revision import guard_outputs
    guard_build(project)
    guard_outputs(project, [path])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".reference-view-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        if (path.read_bytes() if path.is_file() else None) != existing:
            raise ValueError("Reference view changed during export; preserve the current file and retry")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"status": "written", "file": rel, "records": len(view["records"]), "fields": view["fields"]}


def check_view(project: Path, input_path: str) -> dict:
    rel, path = _path(project, input_path)
    view = _read(path)
    if not _owned(view) or not isinstance(view.get("fields"), list) or not isinstance(view.get("records"), list):
        raise ValueError("Not a managed reference input view")
    records = view["records"]
    if (not records or any(not isinstance(row, dict) or not IDENTITY.issubset(row) for row in records)
            or not IDENTITY.issubset(view["fields"])):
        raise ValueError("Reference view lacks mandatory article identities")
    keys = [row["citekey"] for row in records]
    if any(not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Reference view contains ambiguous citekeys")
    actual = project_view(project, citekeys=keys, fields=view["fields"])
    if path.read_bytes() != _bytes(actual):
        raise ValueError("Selected reference identity/content or view definition changed; refresh only this view and its actual consumers")
    return {"status": "valid", "file": rel, "records": len(records), "fields": view["fields"]}


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, help="actual workflow project root; defaults to MEDPAPER_PROJECT")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write selected verified fields only when their projection changes")
    export.add_argument("--citekeys", default="", help="comma-separated existing citekeys")
    export.add_argument("--pmids", default="", help="comma-separated existing PMIDs")
    export.add_argument("--fields", required=True, help="explicit comma-separated fields; article identities are always retained")
    export.add_argument("--output", required=True, help="06_refs/views/<name>.json")
    export.add_argument("--replace", action="store_true", help="explicitly change this managed view's selection/fields")
    check = commands.add_parser("check", help="read-only comparison with current genuine source proof")
    check.add_argument("--input", required=True, help="managed reference view to check")
    args = parser.parse_args()
    project = (args.project or eu.project_root()).resolve()
    try:
        if args.command == "export":
            result = export_view(project, args.output, citekeys=_csv(args.citekeys), pmids=_csv(args.pmids),
                                 fields=_csv(args.fields), replace=args.replace)
        else:
            result = check_view(project, args.input)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
