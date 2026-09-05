#!/usr/bin/env python3
"""Literature search CLI. Every call caches its payload and logs to scan_manifest.json.

    .venv/Scripts/python.exe tools/pubmed/client.py search --query "..." --retmax 100
    .venv/Scripts/python.exe tools/pubmed/client.py search --query "..." --years 5 --journals
    .venv/Scripts/python.exe tools/pubmed/client.py fetch  --ids 12345678,23456789 --with-abstract
    .venv/Scripts/python.exe tools/pubmed/client.py show   --pmid 12345678
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed import eutils as eu  # noqa: E402


def _fmt_authors(rec: dict, limit: int = 3) -> str:
    a = rec.get("authors") or []
    names = [f"{x['last']} {x.get('initials') or ''}".strip() for x in a[:limit]]
    return ", ".join(names) + (" et al." if len(a) > limit else "")


def cmd_search(args) -> int:
    res = eu.esearch(args.query, retmax=args.retmax, years=args.years, sort=args.sort)
    print(f"query      : {res['query']}")
    if res.get("translation"):
        print(f"translated : {res['translation']}")
    print(f"total hits : {res['count']}   retrieved: {len(res['ids'])}")
    print(f"cached at  : {res['cache_file']}")
    if not res["ids"]:
        print("\nno hits. Broaden the query before concluding a gap exists.")
        return 0

    recs = eu.efetch(res["ids"][: args.retmax])
    print()
    for i, r in enumerate(recs, 1):
        flags = f"  [{', '.join(r['flags'])}]" if r["flags"] else ""
        print(f"{i:>3}. {r['year']}  {r['journal_abbrev'] or r['journal']}")
        print(f"     {r['title']}{flags}")
        print(f"     {_fmt_authors(r)}  PMID {r['pmid']}"
              + (f"  doi:{r['doi']}" if r["doi"] else "")
              + ("  [no abstract]" if not r["abstract"] else ""))

    if args.journals:
        print("\njournal distribution (acceptance-probability signal for S20):")
        counter = Counter((r["journal"] or "?") for r in recs)
        for name, n in counter.most_common(25):
            print(f"  {n:>3}  {name}")

    no_abs = sum(1 for r in recs if not r["abstract"])
    print(f"\n{len(recs)} record(s) parsed; {no_abs} without an abstract "
          f"(those are ineligible for the reference library).")
    return 0


def cmd_fetch(args) -> int:
    ids = [x for x in (args.ids or "").replace(" ", "").split(",") if x]
    if not ids:
        eu.die("--ids is required")
    recs = eu.efetch(ids)
    if args.json:
        print(json.dumps(recs, indent=2, ensure_ascii=False))
        return 0
    for r in recs:
        print("=" * 78)
        print(f"{r['title']}")
        print(f"{_fmt_authors(r, 8)}")
        print(f"{r['journal']} {r['year']};{r['volume']}({r['issue']}):{r['pages']}")
        print(f"PMID {r['pmid']}" + (f"  DOI {r['doi']}" if r["doi"] else "")
              + (f"  PMC {r['pmcid']}" if r["pmcid"] else ""))
        if r["flags"]:
            print(f"!! {', '.join(r['flags'])}")
        if r["mesh"]:
            print(f"MeSH: {'; '.join(r['mesh'][:12])}")
        if args.with_abstract:
            print()
            print(r["abstract"] or "(no abstract on record)")
    print("=" * 78)
    print(f"{len(recs)} record(s). Payload cached under 06_refs/cache/.")
    return 0


def cmd_show(args) -> int:
    recs = eu.efetch([args.pmid])
    if not recs:
        eu.die(f"PMID {args.pmid} returned no record")
    print(json.dumps(recs[0], indent=2, ensure_ascii=False))
    return 0


def cmd_manifest(args) -> int:
    man = eu.load_manifest()
    qs = man.get("queries", [])
    ids = set()
    print(f"{len(qs)} recorded search(es)")
    for q in qs:
        ids.update(q.get("ids", []))
        print(f"  {q['at']}  hits={q['count']:<7} kept={len(q.get('ids', [])):<4} {q['query'][:70]}")
    print(f"\n{len(ids)} unique record(s) retrieved overall")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="PubMed access with mandatory caching")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="esearch + efetch, logged to the manifest")
    p.add_argument("--query", required=True)
    p.add_argument("--retmax", type=int, default=50)
    p.add_argument("--years", type=int, help="restrict to the last N years")
    p.add_argument("--sort", default="relevance", choices=["relevance", "pub_date", "Author", "JournalName"])
    p.add_argument("--journals", action="store_true", help="also print the journal distribution")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("fetch", help="full records for specific PMIDs")
    p.add_argument("--ids", required=True)
    p.add_argument("--with-abstract", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_fetch)

    p = sub.add_parser("show", help="one record as JSON")
    p.add_argument("--pmid", required=True)
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("manifest", help="what has been searched so far")
    p.set_defaults(fn=cmd_manifest)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
