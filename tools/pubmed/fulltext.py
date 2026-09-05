#!/usr/bin/env python3
r"""Fetch open-access full text for the deep-read papers.

Legal open-access routes only, tried in order: Europe PMC / PMC OA -> Unpaywall ->
OpenAlex. Paywalled papers are recorded as paywalled; they are never
silently treated as read.

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

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UNPAYWALL = "https://api.unpaywall.org/v2"
OPENALEX = "https://api.openalex.org/works"
MANIFEST = "retrieval_manifest.json"


def out_dir() -> Path:
    d = eu.project_root() / "06_refs" / "fulltext"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(name: str, blob: bytes) -> str:
    p = out_dir() / name
    p.write_bytes(blob)
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
    source = record["fulltext"]
    if source and not str(source).startswith("http"):
        local = eu.project_root() / source
        if local.is_file():
            record["bytes"] = local.stat().st_size
            record["sha256"] = _sha256(local)
    records[entry["citekey"]] = record
    payload = {"schema": 1, "updated_at": _now(),
               "retrievals": [records[k] for k in sorted(records)]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
    for kind, url, ext in (
        ("xml", f"{EPMC}/{pmcid}/fullTextXML", "xml"),
        ("pdf", f"{EPMC}/{pmcid}/pdf", "pdf"),
    ):
        try:
            blob = eu.http_get(url)
        except Exception:  # noqa: BLE001
            continue
        if len(blob) < 2000:
            continue
        rel = _save(f"{entry['citekey']}.{ext}", blob)
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
            "fulltext": _save(f"{entry['citekey']}.{ext}", blob), "bytes": len(blob),
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
                "fulltext": _save(f"{entry['citekey']}.{ext}", blob), "bytes": len(blob),
                "source_url": url}
    except Exception:  # noqa: BLE001
        return {"route": "openalex-link", "access": "link-only", "fulltext": url,
                "source_url": url}


ROUTES = (try_europepmc, try_unpaywall, try_openalex)


def fetch_one(entry: dict) -> dict:
    for fn in ROUTES:
        try:
            res = fn(entry)
        except Exception as exc:  # noqa: BLE001
            res = None
            print(f"    {fn.__name__} raised {type(exc).__name__}: {exc}")
        if res:
            return res
    doi = entry.get("doi")
    return {
        "route": "none", "access": "paywalled",
        "fulltext": f"https://doi.org/{doi}" if doi else "",
        "source_url": f"https://doi.org/{doi}" if doi else "",
        "note": "no open-access copy found. Use your institutional access, or rely on the "
                "abstract and say so explicitly in the deep-read notes.",
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
    ap = argparse.ArgumentParser(description="fetch open-access full text for deep reading")
    ap.add_argument("command", nargs="?", choices=("fetch", "register"), default="fetch")
    ap.add_argument("--citekey", action="append", default=[])
    ap.add_argument("--all-deepread", action="store_true",
                    help="fetch everything listed in deepread_index.json")
    ap.add_argument("--no-stub", action="store_true", help="do not create the notes stub")
    ap.add_argument("--file", type=Path, help="local PDF/XML/HTML to register")
    ap.add_argument("--access", choices=("oa", "authorized"),
                    help="legal access basis for a registered file")
    ap.add_argument("--source-url", help="landing page or authoritative source URL")
    ap.add_argument("--route", default="external", help="acquisition route, e.g. scansci-pdf")
    ap.add_argument("--authorization-note",
                    help="required for institutionally authorized full text")
    ap.add_argument("--replace-existing", action="store_true",
                    help="replace a different previously registered file for this citekey")
    args = ap.parse_args()

    lib_path = eu.refs_dir() / "library.json"
    if not lib_path.exists():
        eu.die("06_refs/library.json missing. Build the library first (S13).")
    entries = {e["citekey"]: e for e in json.loads(lib_path.read_text(encoding="utf-8")).get("entries", [])}

    keys = list(args.citekey)
    dr_path = eu.project_root() / "06_refs" / "deepread" / "deepread_index.json"
    if args.all_deepread:
        if not dr_path.exists():
            eu.die("deepread_index.json missing; pass --citekey instead")
        keys += [i["citekey"] for i in json.loads(dr_path.read_text(encoding="utf-8")).get("selected", [])]
    if not keys:
        eu.die("give at least one --citekey (or --all-deepread)")

    if args.command == "register":
        if len(keys) != 1 or not args.file or not args.access or not args.source_url:
            eu.die("register requires one --citekey plus --file, --access and --source-url")
        if args.access == "authorized" and not (args.authorization_note or "").strip():
            eu.die("--authorization-note is required when --access authorized")
        if not re.match(r"^https?://", args.source_url, re.I):
            eu.die("--source-url must be an http(s) URL")
        key = keys[0]
        entry = entries.get(key)
        if not entry:
            eu.die(f"{key}: not in library.json - add and verify it before registration")
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
        if dest.exists() and source != dest.resolve() and _sha256(dest) != _sha256(source):
            if not args.replace_existing:
                eu.die(f"{dest.name} already exists with different content; inspect it or pass "
                       "--replace-existing explicitly")
        if source != dest.resolve():
            shutil.copy2(source, dest)
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
    for key in dict.fromkeys(keys):
        entry = entries.get(key)
        if not entry:
            print(f"{key}: not in library.json - add it before deep-reading")
            continue
        print(f"{key}: {entry.get('title', '')[:70]}")
        res = fetch_one(entry)
        record_retrieval(entry, res)
        results[key] = res
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
