#!/usr/bin/env python3
"""Independently verify every library entry against the source of record.

Freshly re-fetches each PMID (and optionally cross-checks the DOI against Crossref),
then compares PMID / DOI / title / journal / year / first author.  The output binds
the exact library to hashed raw PubMed XML.  Gates reparse that XML and never trust
the authored ``verified`` boolean by itself.  Failures are quarantined, never patched.

    .venv/Scripts/python.exe tools/pubmed/verify.py
    .venv/Scripts/python.exe tools/pubmed/verify.py --strict     # also require a DOI/Crossref match
    .venv/Scripts/python.exe tools/pubmed/verify.py --quarantine # move failures out of library.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed import eutils as eu  # noqa: E402
from wfcore import refproof  # noqa: E402

TITLE_THRESHOLD = 0.92
JOURNAL_THRESHOLD = 0.85


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def ratio(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def verify_entry(entry: dict, live: dict | None, strict: bool) -> dict:
    checks: list[dict] = []
    if live is None:
        return {
            "verified": False, "via": "pubmed", "at": eu.now(),
            "reason": f"PMID {entry.get('pmid') or '(none)'} returned no record on re-fetch",
            "checks": [],
        }

    pmid_ok = str(entry.get("pmid", "")) == str(live.get("pmid", ""))
    checks.append({"field": "pmid", "ok": pmid_ok, "expected": live.get("pmid", "")})
    entry_doi = str(entry.get("doi", "")).strip().casefold()
    live_doi = str(live.get("doi", "")).strip().casefold()
    doi_ok = entry_doi == live_doi
    checks.append({"field": "doi", "ok": doi_ok, "expected": live_doi})
    checks.append({"field": "pmcid", "ok": str(entry.get("pmcid", "")).upper() == str(live.get("pmcid", "")).upper(),
                   "expected": live.get("pmcid", "")})
    checks.append({"field": "authors", "ok": refproof.canonical_authors(entry) == refproof.canonical_authors(live),
                   "expected": refproof.canonical_authors(live)})

    t = ratio(entry.get("title", ""), live.get("title", ""))
    checks.append({"field": "title", "score": round(t, 3), "ok": t >= TITLE_THRESHOLD,
                   "expected": live.get("title", "")})
    j = ratio(entry.get("journal", ""), live.get("journal", ""))
    checks.append({"field": "journal", "score": round(j, 3), "ok": j >= JOURNAL_THRESHOLD,
                   "expected": live.get("journal", "")})
    y_ok = str(entry.get("year", "")) == str(live.get("year", ""))
    checks.append({"field": "year", "ok": y_ok, "expected": live.get("year", "")})

    ea = (entry.get("authors") or [{}])[0].get("last", "")
    la = (live.get("authors") or [{}])[0].get("last", "")
    a_ok = norm(ea) == norm(la)
    checks.append({"field": "first_author", "ok": a_ok, "expected": la})

    abs_ok = bool((live.get("abstract") or "").strip())
    checks.append({"field": "abstract_present", "ok": abs_ok})
    flags_ok = not live.get("flags")
    checks.append({"field": "citable_status", "ok": flags_ok,
                   "expected": "no retraction, expression-of-concern or preprint flag"})

    result = {
        "verified": all(c["ok"] for c in checks),
        "via": "pubmed",
        "at": eu.now(),
        "pmid": live.get("pmid", ""),
        "doi": live.get("doi", ""),
        "cache_file": live.get("cache_file", ""),
        "checks": checks,
        "flags": live.get("flags", []),
        "evidence": refproof.evidence_for_live_record(live),
    }

    if strict and entry.get("doi"):
        cr = eu.crossref_by_doi(entry["doi"])
        if cr is None:
            result["verified"] = False
            result["reason"] = f"DOI {entry['doi']} not resolvable at Crossref"
        else:
            ct = ratio(entry.get("title", ""), cr.get("title", ""))
            result["checks"].append({"field": "crossref_title", "score": round(ct, 3),
                                     "ok": ct >= TITLE_THRESHOLD, "expected": cr.get("title", "")})
            result["via"] = "pubmed+crossref"
            if ct < TITLE_THRESHOLD:
                result["verified"] = False
    if not result["verified"] and "reason" not in result:
        bad = [c["field"] for c in result["checks"] if not c["ok"]]
        result["reason"] = "mismatch on: " + ", ".join(bad)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="verify every reference against the source API")
    ap.add_argument("--strict", action="store_true", help="also require a Crossref DOI match")
    ap.add_argument("--quarantine", action="store_true",
                    help="move failures from library.json into quarantine.json")
    ap.add_argument("--check", action="store_true",
                    help="validate the existing proof without trusting verified=true")
    args = ap.parse_args()

    lib_path = eu.refs_dir() / "library.json"
    if not lib_path.exists():
        eu.die("06_refs/library.json does not exist. Run build_library.py first.")
    lib = json.loads(lib_path.read_text(encoding="utf-8"))
    entries = lib.get("entries", [])
    if not entries:
        eu.die("library.json has no entries")

    if args.check:
        ok, problems, count = refproof.validate_local_proof(eu.project_root())
        if not ok:
            print("reference proof failed:\n  " + "\n  ".join(problems[:20]), file=sys.stderr)
            return 2
        print(f"reference proof valid for {count} PubMed record(s)")
        return 0

    pmids = [e["pmid"] for e in entries if e.get("pmid")]
    if len(pmids) != len(entries):
        eu.die("every library entry must have a PMID before verification")
    print(f"freshly re-fetching {len(pmids)} record(s) from PubMed...")
    live_recs = eu.efetch(pmids, fresh=True, purpose="verify")
    live_by_pmid = {r["pmid"]: r for r in live_recs}

    records: dict[str, dict] = {}
    failures: list[tuple[str, str]] = []
    for e in entries:
        live = live_by_pmid.get(e.get("pmid", ""))
        res = verify_entry(e, live, args.strict)
        records[e["citekey"]] = res
        if not res["verified"]:
            failures.append((e["citekey"], res.get("reason", "unknown")))

    out = {
        "schema": refproof.SCHEMA,
        "generator": {
            "tool": refproof.GENERATOR,
            "mode": "fresh_ncbi_pubmed_efetch",
            "source": "NCBI PubMed EFetch",
        },
        "verified_at": eu.now(),
        "strict": args.strict,
        "library_sha256": refproof.file_sha256(lib_path),
        "n_entries": len(entries),
        "n_verified": sum(1 for r in records.values() if r["verified"]),
        "records": records,
    }
    verified_path = eu.refs_dir() / "verified.json"
    verified_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nverified {out['n_verified']}/{len(entries)}")
    flagged = [(k, r["flags"]) for k, r in records.items() if r.get("flags")]
    if flagged:
        print("\nflagged records - do not cite these as evidence:")
        for k, f in flagged:
            print(f"  {k}: {', '.join(f)}")
    if failures:
        print(f"\n{len(failures)} failure(s):")
        for k, why in failures:
            print(f"  {k}: {why}")
        print("\nA failure means the entry does not match the source of record.")
        print("Fix it by re-fetching the real record, never by editing the metadata to match.")
        if args.quarantine:
            bad = {k for k, _ in failures}
            keep = [e for e in entries if e["citekey"] not in bad]
            removed = [e for e in entries if e["citekey"] in bad]
            (eu.refs_dir() / "quarantine.json").write_text(
                json.dumps({"at": eu.now(), "entries": removed}, indent=2, ensure_ascii=False),
                encoding="utf-8")
            lib["entries"] = keep
            lib_path.write_text(json.dumps(lib, indent=2, ensure_ascii=False), encoding="utf-8")
            # Quarantine changes the library and therefore invalidates every derived
            # proof/export.  Remove them instead of leaving stale files that can look
            # authoritative to a human or an agent.  The next verifier run recreates
            # the proof from a new source request.
            for stale in (verified_path, eu.refs_dir() / "refs.bib", eu.refs_dir() / "refs.ris"):
                stale.unlink(missing_ok=True)
            print(f"\nquarantined {len(removed)} entr{'y' if len(removed) == 1 else 'ies'};"
                  f" library now holds {len(keep)}")
            print("removed stale verified.json/refs.bib/refs.ris")
            print("re-export and freshly verify the remaining library before continuing")
    else:
        print("\nall entries match the source of record.")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
