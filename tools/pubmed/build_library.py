#!/usr/bin/env python3
"""Build 06_refs/library.json and export refs.bib / refs.ris.

Records without an abstract remain candidates pending registered full-text evidence; never
write a substitute abstract. Citekeys already
used anywhere in the project are pulled in automatically so no citation is orphaned.

    .venv/Scripts/python.exe tools/pubmed/build_library.py --add-ids <selected PMIDs>
    .venv/Scripts/python.exe tools/pubmed/build_library.py --add-query "<uncovered argument>"
    .venv/Scripts/python.exe tools/pubmed/build_library.py --add-ids 12345678,23456789
    .venv/Scripts/python.exe tools/pubmed/build_library.py --refresh-identifiers 12345678,23456789
    .venv/Scripts/python.exe tools/pubmed/build_library.py --export
    .venv/Scripts/python.exe tools/pubmed/build_library.py --report
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed import eutils as eu  # noqa: E402

LIB = "library.json"
MANUSCRIPT_GLOBS = [
    "01_protocol/*.md", "03_analysis/*.md", "07_manuscript/*.md",
]
CITE_RE = re.compile(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)")


def lib_path() -> Path:
    return eu.refs_dir() / LIB


def load_library() -> dict:
    p = lib_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"built_at": eu.now(), "queries": [], "entries": []}


def save_library(lib: dict) -> None:
    lib["updated_at"] = eu.now()
    lib_path().write_text(json.dumps(lib, indent=2, ensure_ascii=False), encoding="utf-8")


def used_citekeys() -> set[str]:
    """Citekeys already referenced in project prose - these must stay in the library."""
    out: set[str] = set()
    for pattern in MANUSCRIPT_GLOBS:
        for p in eu.project_root().glob(pattern):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in re.finditer(r"\[([^\]]*@[^\]]*)\]", text):
                out.update(CITE_RE.findall(m.group(1)))
    return out


def _entry_from_record(rec: dict, taken: set[str]) -> dict:
    key = eu.make_citekey(rec, taken)
    taken.add(key)
    return {
        "citekey": key,
        "pmid": rec.get("pmid", ""),
        "doi": rec.get("doi", ""),
        "pmcid": rec.get("pmcid", ""),
        "title": rec.get("title", ""),
        "abstract": rec.get("abstract", ""),
        "authors": rec.get("authors", []),
        "journal": rec.get("journal", ""),
        "journal_abbrev": rec.get("journal_abbrev", ""),
        "year": rec.get("year", ""),
        "volume": rec.get("volume", ""),
        "issue": rec.get("issue", ""),
        "pages": rec.get("pages", ""),
        "publication_types": rec.get("publication_types", []),
        "mesh": rec.get("mesh", [])[:15],
        "flags": rec.get("flags", []),
        "source": rec.get("source", "pubmed"),
        "cache_file": rec.get("cache_file", ""),
        "retrieved_at": rec.get("retrieved_at", eu.now()),
    }


def add_records(lib: dict, records: list[dict]) -> tuple[int, int, int]:
    by_pmid = {e.get("pmid"): e for e in lib["entries"] if e.get("pmid")}
    by_doi = {e.get("doi"): e for e in lib["entries"] if e.get("doi")}
    taken = {e["citekey"] for e in lib["entries"]}
    added = dropped = dup = 0
    for rec in records:
        if rec.get("pmid") and rec["pmid"] in by_pmid:
            dup += 1
            continue
        if rec.get("doi") and rec["doi"] in by_doi:
            dup += 1
            continue
        entry = _entry_from_record(rec, taken)
        lib["entries"].append(entry)
        if entry["pmid"]:
            by_pmid[entry["pmid"]] = entry
        if entry["doi"]:
            by_doi[entry["doi"]] = entry
        added += 1
    return added, dropped, dup


def refresh_identifiers(lib: dict, pmids: list[str]) -> int:
    """Repair existing identifiers from fresh PubMed XML, without changing science.

    This is intentionally separate from duplicate-skipping acquisition. It neither
    edits a verification receipt nor grants verified status; verify.py must run again.
    """
    from wfcore import refproof, revision
    from wfcore.packagefreeze import _safe_path
    from wfcore.scientificfreeze import FREEZE_REL

    project = eu.project_root()
    ids = list(dict.fromkeys(str(p).strip() for p in pmids if str(p).strip()))
    if not ids or any(not re.fullmatch(r"\d+", p) for p in ids):
        raise ValueError("Identifier refresh requires existing numeric PMIDs")
    by_pmid: dict[str, list[dict]] = {}
    for entry in lib["entries"]:
        by_pmid.setdefault(str(entry.get("pmid", "")), []).append(entry)
    if any(len(by_pmid.get(p, [])) != 1 for p in ids):
        raise ValueError("Each refresh PMID must identify exactly one existing library entry")

    refs = eu.refs_dir()
    proof = refs / "verified.json"
    outputs = [lib_path(), refs / "refs.bib", refs / "refs.ris"]
    if proof.exists():
        outputs.append(proof)
    revision.guard_outputs(project, outputs)
    if (project / FREEZE_REL).exists():
        batch = revision.active(project) or {}
        if not (revision.permits(project, "S13_reflib") and any(
                item.get("kind") == "references" and item.get("owning_stage") == "S13_reflib"
                for item in batch.get("items", []))):
            raise ValueError("Scientific master is frozen; open and seal a scoped references revision permitting S13_reflib")

    # Preserve previous outputs during network/identity failures; detect edits made
    # while the fresh request is in flight rather than overwriting an author's work.
    previous = {p: p.read_bytes() if p.exists() else None for p in outputs}
    records = eu.efetch(ids, fresh=True, purpose="identifier_refresh")
    fetched: dict[str, dict] = {}
    for rec in records:
        pmid = str(rec.get("pmid", ""))
        if pmid not in ids or pmid in fetched:
            raise ValueError("Fresh PubMed response has an unexpected or duplicate PMID")
        fetched[pmid] = rec
    if set(fetched) != set(ids):
        raise ValueError("Fresh PubMed response did not return every requested PMID")

    candidate = copy.deepcopy(lib)
    candidates = {str(e.get("pmid", "")): e for e in candidate["entries"]}
    allowed_differences = {"DOI differs from PubMed payload", "PMCID differs from PubMed payload"}
    payloads: dict[Path, dict] = {}
    for pmid in ids:
        rec, entry = fetched[pmid], by_pmid[pmid][0]
        rel, cached = _safe_path(project, rec.get("cache_file", ""))
        if (rec.get("fresh_fetch") is not True or not rel.startswith("06_refs/cache/")
                or cached.suffix.lower() != ".xml" or not cached.is_file()
                or not rec.get("retrieved_at") or not rec.get("cache_sha256")
                or rec["cache_sha256"] != refproof.file_sha256(cached)):
            raise ValueError(f"PMID {pmid}: fresh preserved PubMed XML is required")
        if cached not in payloads:
            payloads[cached] = refproof.parse_pubmed_payload(cached.read_bytes())
        source = payloads[cached].get(pmid)
        if source is None or refproof.canonical_source(rec) != refproof.canonical_source(source):
            raise ValueError(f"PMID {pmid}: fetched metadata does not match its preserved PubMed XML")
        problems = [p for p in refproof.compare_entry_to_source(entry, source)
                    if p not in allowed_differences]
        before, after = refproof.canonical_source(entry), refproof.canonical_source(source)
        for field in ("title", "authors", "year", "journal", "abstract", "flags"):
            left, right = before[field], after[field]
            if field == "abstract":
                left, right = refproof.normalized_abstract(left), refproof.normalized_abstract(right)
            if left != right:
                problems.append(f"{field} changed; this is not an identifier-only repair")
        # These fields are preserved too; do not silently ignore a new edition or
        # changed publication status while repairing a DOI/PMCID.
        for field in ("journal_abbrev", "volume", "issue", "pages", "publication_types", "mesh"):
            value = rec.get(field, [] if field in {"publication_types", "mesh"} else "")
            if field == "mesh":
                value = value[:15]  # Existing acquisition stores these first 15 terms.
            if field in entry and entry[field] != value:
                problems.append(f"{field} changed; use a reviewed bibliographic revision")
        if problems:
            raise ValueError(f"PMID {pmid}: " + "; ".join(dict.fromkeys(problems)))
        repaired = candidates[pmid]
        for field in ("doi", "pmcid"):
            repaired[field] = source[field]
        for field in ("cache_file", "retrieved_at"):
            repaired[field] = rec[field]

    candidate["updated_at"] = eu.now()
    entries = sorted(candidate["entries"], key=lambda e: e["citekey"])
    contents = {
        lib_path(): json.dumps(candidate, indent=2, ensure_ascii=False).encode("utf-8"),
        refs / "refs.bib": to_bibtex(entries).encode("utf-8"),
        refs / "refs.ris": to_ris(entries).encode("utf-8"),
    }
    _commit_identifier_refresh(contents, proof, previous)
    return len(ids)


def _commit_identifier_refresh(contents: dict[Path, bytes], proof: Path,
                               previous: dict[Path, bytes | None]) -> None:
    """Stage all exports before replacing files; roll back a failed commit."""
    staged: dict[Path, Path] = {}
    changed: list[Path] = []
    try:
        for path, content in contents.items():
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".identifier_refresh_", delete=False) as stream:
                staged[path] = Path(stream.name)
                stream.write(content)
        if any((p.read_bytes() if p.exists() else None) != old for p, old in previous.items()):
            raise ValueError("Reference outputs changed during refresh; retry against the current library")
        if proof not in previous and proof.exists():
            raise ValueError("Verification receipt appeared during refresh; retry against the current library")
        for path, temporary in staged.items():
            os.replace(temporary, path)
            changed.append(path)
        if proof in previous:
            proof.unlink()
            changed.append(proof)
    except BaseException:
        for path in reversed(changed):
            original = previous[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# exporters
# ---------------------------------------------------------------------------
BIB_ESCAPE = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}


def _bib_escape(s: str) -> str:
    out = []
    for ch in s or "":
        out.append(BIB_ESCAPE.get(ch, ch))
    return "".join(out)


def to_bibtex(entries: list[dict]) -> str:
    chunks = ["% Generated from library.json. Do not edit by hand - regenerate with --export.\n"]
    for e in entries:
        authors = " and ".join(
            ("{" + _bib_escape(a["last"]) + "}" if a.get("collective") else
             "{" + _bib_escape(a["last"]) + "}, " +
             (_bib_escape(a["suffix"]) + ", " if a.get("suffix") else "") +
             _bib_escape(a.get("first") or a.get("initials", "")))
            for a in e.get("authors", []) if a.get("last")
        )
        fields = [
            ("author", authors),
            ("title", _bib_escape(e.get("title", ""))),
            ("journal", _bib_escape(e.get("journal", ""))),
            ("year", e.get("year", "")),
            ("volume", e.get("volume", "")),
            ("number", e.get("issue", "")),
            ("pages", (e.get("pages", "") or "").replace("-", "--")),
            ("doi", e.get("doi", "")),
            ("pmid", e.get("pmid", "")),
        ]
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
        note = ""
        if e.get("flags"):
            note = f",\n  note = {{FLAGS: {', '.join(e['flags'])}}}"
        chunks.append(f"@article{{{e['citekey']},\n{body}{note}\n}}\n")
    return "\n".join(chunks)


def to_ris(entries: list[dict]) -> str:
    out = []
    for e in entries:
        lines = ["TY  - JOUR"]
        for a in e.get("authors", []):
            if a.get("last"):
                name = a["last"] if a.get("collective") else (
                    f"{a['last']}, {a.get('first') or a.get('initials', '')}".strip(", ") +
                    (f", {a['suffix']}" if a.get("suffix") else ""))
                lines.append(f"AU  - {name}")
        lines += [
            f"TI  - {e.get('title', '')}",
            f"JO  - {e.get('journal', '')}",
            f"PY  - {e.get('year', '')}",
        ]
        for tag, key in (("VL", "volume"), ("IS", "issue"), ("SP", "pages"), ("DO", "doi")):
            if e.get(key):
                lines.append(f"{tag}  - {e[key]}")
        if e.get("abstract"):
            lines.append(f"AB  - {e['abstract']}")
        if e.get("pmid"):
            lines.append(f"AN  - {e['pmid']}")
        lines.append(f"ID  - {e['citekey']}")
        lines.append("ER  - ")
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def export(lib: dict) -> None:
    entries = sorted(lib["entries"], key=lambda e: e["citekey"])
    (eu.refs_dir() / "refs.bib").write_text(to_bibtex(entries), encoding="utf-8")
    (eu.refs_dir() / "refs.ris").write_text(to_ris(entries), encoding="utf-8")
    print(f"exported {len(entries)} entries -> 06_refs/refs.bib, 06_refs/refs.ris")


def report(lib: dict) -> None:
    entries = lib["entries"]
    print(f"library: {len(entries)} entries")
    no_abs = [e["citekey"] for e in entries if not (e.get("abstract") or "").strip()]
    flagged = [(e["citekey"], e["flags"]) for e in entries if e.get("flags")]
    years = sorted(int(e["year"]) for e in entries if str(e.get("year", "")).isdigit())
    if years:
        recent = sum(1 for y in years if y >= years[-1] - 4)
        print(f"years  : {years[0]}-{years[-1]}  ({recent} from the last 5 years)")
    print(f"with abstract : {len(entries) - len(no_abs)}/{len(entries)}")
    if no_abs:
        print(f"  requires registered, identity-checked full text before citation: {', '.join(no_abs)}")
    if flagged:
        print("flagged records (do not cite as evidence):")
        for k, f in flagged:
            print(f"  {k}: {', '.join(f)}")
    orphans = used_citekeys() - {e["citekey"] for e in entries}
    if orphans:
        print(f"!! cited in the project but absent from the library: {', '.join(sorted(orphans))}")
    print("\njournals:")
    from collections import Counter
    for name, n in Counter(e.get("journal", "?") for e in entries).most_common(15):
        print(f"  {n:>3}  {name}")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="build and export the verified reference library")
    ap.add_argument("--topic", help="primary topic; runs a small family of queries")
    ap.add_argument("--add-query", action="append", default=[], help="one extra query (repeatable)")
    ap.add_argument("--add-ids", help="comma-separated PMIDs to add directly")
    ap.add_argument("--refresh-identifiers", metavar="PMID[,PMID...]",
                    help="fresh-fetch existing PMIDs; repair DOI/PMCID only, reexport and invalidate old verification")
    ap.add_argument("--target", type=int, help="legacy advisory planning hint; never skips remaining coverage queries")
    ap.add_argument("--retmax", type=int, default=60, help="records to pull per query")
    ap.add_argument("--years", type=int, help="restrict searches to the last N years")
    ap.add_argument("--export", action="store_true", help="regenerate refs.bib and refs.ris")
    ap.add_argument("--report", action="store_true", help="audit the current library")
    ap.add_argument("--uncited-reason", nargs=2, action="append", default=[], metavar=("CITEKEY","REASON"), help="record why a genuine library entry is not cited; does not modify metadata")
    ap.add_argument("--drop", action="append", default=[], help="remove a citekey")
    args = ap.parse_args()

    lib = load_library()
    if args.refresh_identifiers is not None:
        if args.topic or args.add_query or args.add_ids or args.drop or args.export or args.uncited_reason:
            ap.error("--refresh-identifiers is a standalone repair; it already reexports BibTeX/RIS")
        ids = [p.strip() for p in args.refresh_identifiers.split(",") if p.strip()]
        count = refresh_identifiers(lib, ids)
        print(f"Refreshed identifiers for {count} existing PMID(s); citekeys and scientific metadata preserved.")
        print("BibTeX/RIS regenerated; previous verification invalidated. Run tools/pubmed/verify.py before citation.")
        if args.report:
            report(load_library())
        return 0
    if args.uncited_reason:
        if args.topic or args.add_query or args.add_ids or args.drop or args.export:
            raise ValueError("Record usage separately from metadata acquisition/export")
        from wfcore.readiness import atomic_json
        usage=eu.project_root()/"06_refs/usage.json"
        record=json.loads(usage.read_text(encoding="utf-8")) if usage.is_file() else {"uncited_reasons":{}}
        for key,reason in args.uncited_reason:
            if key not in {e["citekey"] for e in lib["entries"]} or len(reason.strip())<20:
                raise ValueError("Uncited reason needs an existing citekey and concrete explanation")
            record["uncited_reasons"][key]=reason
        atomic_json(usage,record)
        print("Uncited usage explanations recorded; verified bibliographic metadata unchanged")
        return 0

    for key in args.drop:
        before = len(lib["entries"])
        lib["entries"] = [e for e in lib["entries"] if e["citekey"] != key]
        print(f"dropped {key}" if len(lib["entries"]) < before else f"{key} not in library")

    queries: list[str] = []
    if args.topic:
        queries += [
            args.topic,
            f"{args.topic} AND (epidemiology OR prevalence OR incidence)",
            f"{args.topic} AND (cohort OR cross-sectional OR case-control)",
            f"{args.topic} AND (systematic review OR meta-analysis)",
            f"{args.topic} AND (guideline OR consensus OR definition)",
        ]
    queries += args.add_query

    for q in queries:
        res = eu.esearch(q, retmax=args.retmax, years=args.years)
        recs = eu.efetch(res["ids"])
        added, dropped, dup = add_records(lib, recs)
        lib.setdefault("queries", []).append(
            {"query": q, "at": eu.now(), "hits": res["count"], "added": added,
             "dropped_no_abstract": dropped, "duplicates": dup,
             "cache_file": res["cache_file"]}
        )
        print(f"[{q[:60]}] hits={res['count']} +{added} added, "
              f"{dup} duplicate(s); records without abstracts await full-text verification")

    if args.add_ids:
        ids = [x for x in args.add_ids.replace(" ", "").split(",") if x]
        recs = eu.efetch(ids)
        added, dropped, dup = add_records(lib, recs)
        print(f"[--add-ids] +{added} added, {dup} already present; no-abstract records require registered full text")

    missing = used_citekeys() - {e["citekey"] for e in lib["entries"]}
    if missing:
        print(f"\n!! {len(missing)} citekey(s) are cited in the project but not in the library:")
        print("   " + ", ".join(sorted(missing)))
        print("   Add them with --add-ids <pmid>, or fix the citation. Never leave a dangling key.")

    save_library(lib)
    if args.export or queries or args.add_ids or args.drop:
        export(lib)
    if args.report:
        report(lib)

    n = len(lib["entries"])
    print(f"\nlibrary now holds {n} entr{'y' if n == 1 else 'ies'} "
          f"-> next: .venv/Scripts/python.exe tools/pubmed/verify.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
