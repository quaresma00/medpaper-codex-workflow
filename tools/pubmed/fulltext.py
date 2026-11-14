#!/usr/bin/env python3
r"""Retrieve and register actual full text, with truthful route and article identity.

Built-in public routes: Europe PMC -> Unpaywall -> OpenAlex. Unresolved records
continue through the executor's available scholarly tools and authorized browser
routes, then a precise user PDF request; a link or abstract never counts as read.

    .\.venv\Scripts\python.exe tools\pubmed\fulltext.py fetch --citekey smith2023
    .\.venv\Scripts\python.exe tools\pubmed\fulltext.py register --citekey smith2023 \
        --file paper.pdf --access oa --source-url https://example.org/article
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed import eutils as eu  # noqa: E402
from pubmed.identity import inspect, norm  # noqa: E402
from wfcore.readiness import atomic_json  # noqa: E402

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UNPAYWALL = "https://api.unpaywall.org/v2"
OPENALEX = "https://api.openalex.org/works"
MANIFEST = "retrieval_manifest.json"


def out_dir() -> Path:
    d = eu.project_root() / "06_refs" / "fulltext"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(name: str, blob: bytes, entry: dict) -> str:
    identity = inspect(entry, blob, Path(name).suffix)
    if identity["status"] == "mismatch":
        raise ValueError("Wrong article identity; previous full text preserved")
    p = out_dir() / name
    temporary = p.with_suffix(p.suffix + ".tmp")
    temporary.write_bytes(blob)
    temporary.replace(p)
    return f"06_refs/fulltext/{name}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_retrieval(entry: dict, result: dict) -> dict:
    """Upsert a machine-verifiable provenance record for a retrieval result."""
    path = out_dir() / MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    records = {r.get("citekey"): r for r in data.get("retrievals", []) if r.get("citekey")}
    record = {
        "citekey": entry["citekey"],
        "pmid": entry.get("pmid", ""),
        "doi": entry.get("doi", ""),
        "route": result.get("route", ""),
        "access": result.get("access", ""),
        "fulltext": result.get("fulltext", ""),
        "source_url": result.get("source_url", ""),
        "authorization_note": result.get("authorization_note", ""),
        "retrieved_at": _now(),
    }
    prior = records.get(entry["citekey"], {})
    record["attempts"] = [*prior.get("attempts", []), *result.get("attempts", [])]
    for field in ("note", "next_action", "require_pdf"):
        if field in result: record[field] = result[field]
    if entry.get("cache_file"):
        metadata = eu.project_root() / entry["cache_file"]
        record["metadata_cache"] = entry["cache_file"]
        record["metadata_sha256"] = _sha256(metadata)
    source = record["fulltext"]
    if source and not str(source).startswith("http"):
        local = eu.project_root() / source
        if local.is_file():
            record["bytes"] = local.stat().st_size
            record["sha256"] = _sha256(local)
            record["identity"] = inspect(entry, local.read_bytes(), local.suffix)
            prior = records.get(entry["citekey"], {})
            if prior.get("sha256") == record["sha256"] and prior.get("identity_confirmation"):
                record["identity_confirmation"] = prior["identity_confirmation"]
    records[entry["citekey"]] = record
    payload = {"schema": 1, "updated_at": _now(),
               "retrievals": [records[k] for k in sorted(records)]}
    atomic_json(path, payload)
    return record


# ---------------------------------------------------------------------------
def try_europepmc(entry: dict) -> dict | None:
    pmid, pmcid = entry.get("pmid"), entry.get("pmcid")
    if not pmcid and pmid:
        try:
            raw = eu.http_get(f"{EPMC}/search",
                              {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"})
            hits = json.loads(raw).get("resultList", {}).get("result", [])
            if hits:
                pmcid = hits[0].get("pmcid") or ""
                if hits[0].get("isOpenAccess") != "Y" and not pmcid:
                    return None
        except Exception:  # noqa: BLE001
            return None
    if not pmcid:
        return None
    pmcid = pmcid if pmcid.upper().startswith("PMC") else f"PMC{pmcid}"
    formats = (
        ("xml", f"{EPMC}/{pmcid}/fullTextXML", "xml"),
        ("pdf", f"{EPMC}/{pmcid}/pdf", "pdf"),
    )
    for kind, url, ext in formats:
        if entry.get("_require_pdf") and kind != "pdf": continue
        try:
            blob = eu.http_get(url)
        except Exception:  # noqa: BLE001
            continue
        if len(blob) < 2000:
            continue
        rel = _save(f"{entry['citekey']}.{ext}", blob, entry)
        return {"route": f"europepmc-{kind}", "access": "oa", "fulltext": rel,
                "bytes": len(blob), "pmcid": pmcid, "source_url": url}
    return None


def try_unpaywall(entry: dict) -> dict | None:
    doi, email = entry.get("doi"), eu.api_email()
    if not doi or not email:
        return None
    try:
        raw = eu.http_get(f"{UNPAYWALL}/{urllib.parse.quote(doi)}", {"email": email})
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    loc = data.get("best_oa_location") or {}
    url = loc.get("url_for_pdf") or loc.get("url")
    if not url:
        return None
    try:
        blob = eu.http_get(url)
    except Exception:  # noqa: BLE001
        return {"route": "unpaywall-link", "access": "link-only", "fulltext": url,
                "source_url": url,
                "note": "OA landing page found but the file could not be downloaded here"}
    ext = "pdf" if blob[:4] == b"%PDF" else "html"
    return {"route": "unpaywall", "access": "oa",
            "fulltext": _save(f"{entry['citekey']}.{ext}", blob, entry), "bytes": len(blob),
            "license": loc.get("license"), "version": loc.get("version"),
            "source_url": url}


def try_openalex(entry: dict) -> dict | None:
    doi = entry.get("doi")
    if not doi:
        return None
    try:
        raw = eu.http_get(f"{OPENALEX}/doi:{urllib.parse.quote(doi)}",
                          {"mailto": eu.api_email() or ""})
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    loc = data.get("best_oa_location") or {}
    url = loc.get("pdf_url") or loc.get("landing_page_url")
    if not url:
        return None
    try:
        blob = eu.http_get(url)
        ext = "pdf" if blob[:4] == b"%PDF" else "html"
        return {"route": "openalex", "access": "oa",
                "fulltext": _save(f"{entry['citekey']}.{ext}", blob, entry), "bytes": len(blob),
                "source_url": url}
    except Exception:  # noqa: BLE001
        return {"route": "openalex-link", "access": "link-only", "fulltext": url,
                "source_url": url}


ROUTES = (try_europepmc, try_unpaywall, try_openalex)


def fetch_one(entry: dict, *, require_pdf: bool = False) -> dict:
    # Registered reader-approved files are reusable across turns. Do not replace
    # a valid PDF with an XML response or repeat an unchanged successful download.
    try:
        data = json.loads((out_dir()/MANIFEST).read_text(encoding="utf-8"))
        old = next((r for r in data["retrievals"] if r.get("citekey")==entry["citekey"]),None)
        if old and old.get("access") in {"oa","authorized","external"}:
            from wfcore.packagefreeze import _safe_path
            from wfcore.refproof import readable_source_errors
            local = _safe_path(eu.project_root(),old.get("fulltext",""))[1]
            if (local.is_file() and old.get("sha256")==_sha256(local) and
                    (not require_pdf or local.suffix.lower()==".pdf") and not readable_source_errors(eu.project_root(),{**entry,"abstract":""})):
                return {**old,"attempts":[],"note":"Reused the existing identity-confirmed readable file"}
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        pass
    attempts=[]; best_link=None
    for fn in ROUTES:
        try:
            res = fn({**entry,"_require_pdf":require_pdf})
        except Exception as exc:  # noqa: BLE001
            res = None
            attempts.append({"route":fn.__name__,"outcome":"failed","at":_now(),"detail":eu.safe_error(exc)[:400]})
        else:
            source=(res or {}).get("fulltext","")
            local=eu.project_root()/source if source and not str(source).startswith("http") else None
            if local and local.is_file() and (not require_pdf or local.suffix.lower()==".pdf"):
                return {**res,"attempts":[*attempts,{"route":fn.__name__,"outcome":"downloaded","at":_now()}],"require_pdf":require_pdf}
            attempts.append({"route":fn.__name__,"outcome":"link_only" if res else "unavailable","at":_now()})
            if res: best_link=res
    doi = entry.get("doi")
    return {
        "route": "builtin-unresolved", "access": "external-needed",
        "fulltext": (best_link or {}).get("source_url") or (f"https://doi.org/{doi}" if doi else ""),
        "source_url": (best_link or {}).get("source_url") or (f"https://doi.org/{doi}" if doi else ""),
        "attempts":attempts,"require_pdf":require_pdf,
        "next_action":"Try available scansci-pdf multi-source retrieval, including the user's explicitly selected Sci-Hub route; then authorized publisher/institution/browser access. If the required PDF remains unavailable, ask the user for this exact DOI/title/PDF, without silently replacing a necessary source.",
        "note":"Built-in routes exhausted; acquisition remains incomplete. A link/abstract is not a deep read. Never label an external copy OA or institution-authorized without evidence.",
    }


NOTES_TEMPLATE = """# {citekey} - {short_title}

Source: {source}
Access: {access} (route: {route})
PMID {pmid} | DOI {doi}

## Design and population

## What they did differently from us

## Their key numbers

## How this supports or contradicts our finding

## What a reviewer would take from this
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="retrieve/register actual full text and unresolved route attempts")
    ap.add_argument("command", nargs="?", choices=("fetch", "register", "confirm", "attempt"), default="fetch")
    ap.add_argument("--require-pdf",action="store_true",help="PDF is necessary for actual figure/layout reading; XML/links do not complete this request")
    ap.add_argument("--outcome",choices=("not_found","failed","login_required","unavailable"),help="actual external tool/browser outcome for attempt")
    ap.add_argument("--note",help="concrete actual failed retrieval reason; never invent an attempted route")
    ap.add_argument("--confirmed-by", help="actual reader who explicitly confirmed article identity")
    ap.add_argument("--identity-note", help="concrete first-page/title/authors/identifier evidence, >=30 chars")
    ap.add_argument("--citekey", action="append", default=[])
    ap.add_argument("--pmid", action="append", default=[], help="comparator-only fresh PubMed route; does not edit the scientific library")
    ap.add_argument("--all-deepread", action="store_true",
                    help="fetch everything listed in deepread_index.json")
    ap.add_argument("--no-stub", action="store_true", help="do not create the notes stub")
    ap.add_argument("--file", type=Path, help="local PDF/XML/HTML to register")
    ap.add_argument("--access", choices=("oa", "authorized", "external"),
                    help="actual acquisition category; external does not assert OA/license/institutional rights")
    ap.add_argument("--source-url", help="landing page or authoritative source URL")
    ap.add_argument("--route", default="external", help="acquisition route, e.g. scansci-pdf")
    ap.add_argument("--authorization-note",
                    help="required for institutionally authorized full text")
    ap.add_argument("--replace-existing", action="store_true",
                    help="replace a different previously registered file for this citekey")
    args = ap.parse_args()

    lib_path = eu.refs_dir() / "library.json"
    entries = {e["citekey"]: e for e in json.loads(lib_path.read_text(encoding="utf-8")).get("entries", [])} if lib_path.is_file() else {}

    keys = list(args.citekey)
    # Comparator-only acquisition must not mutate a frozen scientific bibliography.
    if args.pmid:
        fetched = eu.efetch(args.pmid, fresh=True, purpose="benchmark")
        if {str(e["pmid"]) for e in fetched} != set(args.pmid):
            eu.die("Comparator metadata retrieval incomplete; never replace missing IDs with invented entries")
        for entry in fetched:
            key = "benchmark" + str(entry["pmid"])
            entry["citekey"] = key; entries[key] = entry; keys.append(key)
    dr_path = eu.project_root() / "06_refs" / "deepread" / "deepread_index.json"
    if args.all_deepread:
        if not dr_path.exists():
            eu.die("deepread_index.json missing; pass --citekey instead")
        keys += [i["citekey"] for i in json.loads(dr_path.read_text(encoding="utf-8")).get("selected", [])]
    if not keys:
        eu.die("give at least one --citekey (or --all-deepread)")

    if args.command == "attempt":
        if len(keys)!=1 or not args.outcome or len((args.note or "").strip())<20 or args.route=="external":
            eu.die("attempt needs one actual citekey, specific --route, --outcome and concrete --note (>=20 characters)")
        path=out_dir()/MANIFEST
        data=json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"retrievals":[]}
        record=next((r for r in data["retrievals"] if r.get("citekey")==keys[0]),None)
        if not record or keys[0] not in entries: eu.die("Run actual built-in retrieval for the registered entry first")
        record.setdefault("attempts",[]).append({"route":args.route,"outcome":args.outcome,"at":_now(),"detail":eu.safe_error(args.note)})
        atomic_json(path,data)
        print(keys[0]+": actual failed route recorded; no full-text/read/verification status was granted")
        return 0

    if args.command == "confirm":
        if len(keys) != 1 or not (args.confirmed_by or "").strip() or len((args.identity_note or "").strip()) < 30:
            eu.die("confirm requires one citekey and actual --confirmed-by / --identity-note; do not invent user confirmation")
        key = keys[0]
        entry = entries.get(key)
        data = json.loads((out_dir() / MANIFEST).read_text(encoding="utf-8"))
        record = next((r for r in data["retrievals"] if r["citekey"] == key), None)
        if not entry or not record:
            eu.die("Library entry / registration missing")
        from wfcore.packagefreeze import _safe_path
        local = _safe_path(eu.project_root(), record["fulltext"])[1]
        if record.get("sha256") != _sha256(local) or inspect(entry, local.read_bytes(), local.suffix)["status"] == "mismatch":
            eu.die("Changed file or contradictory article identity; confirmation rejected")
        record["identity_confirmation"] = {"confirmed_by": args.confirmed_by.strip(), "note": args.identity_note.strip(),
            "sha256": record["sha256"], "expected": {k: norm(k, entry.get(k)) for k in ("doi", "pmid", "pmcid", "title")},
            "confirmed_at": _now()}
        atomic_json(out_dir() / MANIFEST, data)
        print(f"{key}: explicit reader confirmation recorded for the exact registered file")
        return 0

    if args.command == "register":
        if len(keys) != 1 or not args.file or not args.access or not args.source_url:
            eu.die("register requires one --citekey plus --file, --access and --source-url")
        if args.access in {"authorized","external"} and not (args.authorization_note or "").strip():
            eu.die("--authorization-note is required for the actual authorized/external acquisition basis; do not claim a license")
        if not re.match(r"^https?://", args.source_url, re.I):
            eu.die("--source-url must be an http(s) URL")
        key = keys[0]
        entry = entries.get(key)
        if not entry:
            eu.die(f"{key}: not in library.json - fetch it with build_library.py --add-ids before registration; verify after full-text registration")
        source = args.file.expanduser().resolve()
        if not source.is_file():
            eu.die(f"file not found: {source}")
        suffix = source.suffix.lower()
        if suffix not in {".pdf", ".xml", ".html", ".htm"}:
            eu.die("registered full text must be PDF, XML or HTML")
        if source.stat().st_size < 1000:
            eu.die("registered full text is implausibly small (<1000 bytes)")
        if suffix == ".pdf":
            with source.open("rb") as stream:
                if stream.read(4) != b"%PDF":
                    eu.die("file has a .pdf suffix but no PDF signature")
        dest = out_dir() / f"{key}{suffix}"
        if inspect(entry, source.read_bytes(), suffix)["status"] == "mismatch":
            eu.die("Wrong article identity; registration rejected and previous full text preserved")
        if dest.exists() and source != dest.resolve() and _sha256(dest) != _sha256(source):
            if not args.replace_existing:
                eu.die(f"{dest.name} already exists with different content; inspect it or pass "
                       "--replace-existing explicitly")
        if source != dest.resolve():
            temporary = dest.with_suffix(dest.suffix + ".tmp")
            shutil.copy2(source, temporary)
            temporary.replace(dest)
        result = {
            "route": args.route.strip() or "external",
            "access": args.access,
            "fulltext": f"06_refs/fulltext/{dest.name}",
            "source_url": args.source_url,
            "authorization_note": (args.authorization_note or "").strip(),
        }
        record = record_retrieval(entry, result)
        print(f"{key}: registered {record['fulltext']}")
        print(f"    route={record['route']} access={record['access']} sha256={record['sha256']}")
        if not args.no_stub:
            notes = eu.project_root() / "06_refs" / "deepread" / f"{key}.md"
            notes.parent.mkdir(parents=True, exist_ok=True)
            if not notes.exists():
                notes.write_text(NOTES_TEMPLATE.format(
                    citekey=key,
                    short_title=re.sub(r"\s+", " ", entry.get("title", ""))[:80],
                    source=f"{entry.get('journal', '')} {entry.get('year', '')}",
                    access=result["access"], route=result["route"],
                    pmid=entry.get("pmid", ""), doi=entry.get("doi", ""),
                ), encoding="utf-8")
                print(f"    notes stub: 06_refs/deepread/{key}.md")
        return 0

    results = {}
    failed = []
    for key in dict.fromkeys(keys):
        entry = entries.get(key)
        if not entry:
            print(f"{key}: not in library.json - add it before deep-reading")
            failed.append(key)
            continue
        print(f"{key}: {entry.get('title', '')[:70]}")
        res = fetch_one(entry,require_pdf=args.require_pdf)
        record_retrieval(entry, res)
        results[key] = res
        source = res.get("fulltext", "")
        if res.get("access") not in {"oa", "authorized", "external"} or not source or source.startswith("http") or not (eu.project_root() / source).is_file():
            failed.append(key)
        print(f"    -> {res['route']} / {res['access']} / {res.get('fulltext', '')}")
        if res.get("note"):
            print(f"       {res['note']}")

        if not args.no_stub:
            notes = eu.project_root() / "06_refs" / "deepread" / f"{key}.md"
            notes.parent.mkdir(parents=True, exist_ok=True)
            if not notes.exists():
                notes.write_text(NOTES_TEMPLATE.format(
                    citekey=key,
                    short_title=re.sub(r"\s+", " ", entry.get("title", ""))[:80],
                    source=f"{entry.get('journal', '')} {entry.get('year', '')}",
                    access=res["access"], route=res["route"],
                    pmid=entry.get("pmid", ""), doi=entry.get("doi", ""),
                ), encoding="utf-8")
                print(f"       notes stub: 06_refs/deepread/{key}.md")

    oa = sum(1 for r in results.values() if r["access"] == "oa")
    print(f"\n{oa}/{len(results)} available open access.")
    print("Fill in every notes file, then record them in 06_refs/deepread/deepread_index.json.")
    print("Notes under 400 characters are rejected by the S15 gate.")
    if failed:
        print("Incomplete full-text acquisition: " + ", ".join(failed) + "; downstream reading/sealing must stop; genuine partial receipts preserved")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
