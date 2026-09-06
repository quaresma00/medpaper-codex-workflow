"""Reference-integrity checks.

Every formal citation must resolve to metadata independently reconstructed from
fresh PubMed EFetch evidence.  The authored ``verified`` boolean is only a status
field; the gates reparse the raw XML, recompute its hashes and metadata, bind the
receipt to the current library, and perform a separate live source check at S13.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree as ET

from . import Ctx, Result, check
from .. import refproof

BIB = "06_refs/refs.bib"
RIS = "06_refs/refs.ris"
LIB = "06_refs/library.json"
VER = "06_refs/verified.json"
RETRIEVALS = "06_refs/fulltext/retrieval_manifest.json"

FENCE_RE = re.compile(r"```.*?```", re.S)
BRACKET_CITE_RE = re.compile(r"\[([^\]]*@[^\]]*)\]")
KEY_RE = re.compile(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)")
BIB_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s}]+)\s*,", re.M)
TITLE_REFERENCE_COUNT_RE = re.compile(
    r"(?im)^\s*(?:[-+*]\s+)?(?:\*\*)?"
    r"(?:number\s+of\s+references|reference\s+count|references)"
    r"\s*:\s*(?:\*\*)?\s*(\d+)\b"
)
TITLE_REFERENCE_COUNT_SUB_RE = re.compile(
    r"(?im)^(\s*(?:[-+*]\s+)?(?:\*\*)?"
    r"(?:number\s+of\s+references|reference\s+count|references)"
    r"\s*:\s*(?:\*\*)?\s*)\d+\b"
)


def _file_sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_like_date(value: object) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}(?:T.*)?$", str(value or "").strip()))


def _verification_age_days(value: object) -> int | None:
    try:
        stamp = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None
    return (date.today() - stamp).days


def citekeys(text: str) -> list[str]:
    text = FENCE_RE.sub(" ", text)
    keys: list[str] = []
    for group in BRACKET_CITE_RE.findall(text):
        keys.extend(KEY_RE.findall(group))
    # bare in-text citations: "as @smith2020 showed"
    stripped = BRACKET_CITE_RE.sub(" ", text)
    keys.extend(KEY_RE.findall(stripped))
    return keys


def actual_reference_count(text: str) -> int:
    """Count distinct Pandoc citekeys actually used by the canonical manuscript."""
    return len(set(citekeys(text)))


def declared_reference_counts(text: str) -> list[int]:
    """Return explicit reference-count fields, without treating a References heading as one."""
    return [int(value) for value in TITLE_REFERENCE_COUNT_RE.findall(text)]


def synchronize_reference_count(text: str, actual: int, *, add: bool = False) -> tuple[str, bool]:
    """Update an existing title-page count; add one only when explicitly requested."""
    fields = declared_reference_counts(text)
    if len(fields) > 1:
        raise ValueError("title page contains more than one reference-count field")
    if fields:
        updated = TITLE_REFERENCE_COUNT_SUB_RE.sub(rf"\g<1>{actual}", text, count=1)
        return updated, updated != text
    if not add:
        return text, False
    separator = "\n" if text.endswith("\n") else "\n\n"
    return text + separator + f"Number of references: {actual}\n", True


def _docx_text(path) -> str:
    """Read visible title-page text from the main Word document part."""
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ns = {"w": w_ns}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    return "\n".join(
        "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
        for paragraph in root.findall(".//w:p", ns)
    )


@check("title_page_reference_count")
def title_page_reference_count(ctx: Ctx) -> Result:
    """If a title page declares a count, bind it to citations actually used in the paper."""
    manuscript_rel = ctx.spec.get("manuscript", "07_manuscript/full_manuscript.md")
    title_rel = ctx.spec.get("title_page", "07_manuscript/title_page.md")
    if not ctx.p(manuscript_rel).is_file():
        return Result(False, "title_page_reference_count", f"{manuscript_rel} missing")
    if not ctx.p(title_rel).is_file():
        return Result(False, "title_page_reference_count", f"{title_rel} missing")

    actual = actual_reference_count(ctx.read(manuscript_rel))
    problems: list[str] = []
    declared_any = False
    source_values = declared_reference_counts(ctx.read(title_rel))
    if len(source_values) > 1:
        problems.append(f"{title_rel}: more than one reference-count field")
    elif source_values:
        declared_any = True
        if source_values[0] != actual:
            problems.append(
                f"{title_rel}: declares {source_values[0]} references but the manuscript uses {actual} distinct citekeys"
            )

    manifest_path = ctx.p("08_submission/bundle/manifest.json")
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            problems.append(f"08_submission/bundle/manifest.json cannot be read: {exc}")
            manifest = {}
        for item in manifest.get("items", []):
            if str(item.get("role", "")).casefold() != "title_page":
                continue
            rel = str(item.get("file", "")).strip()
            path = ctx.p(rel) if rel else None
            if path is None or path.suffix.casefold() != ".docx" or not path.is_file():
                continue
            try:
                values = declared_reference_counts(_docx_text(path))
            except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
                problems.append(f"{rel}: cannot inspect reference count ({exc})")
                continue
            if len(values) > 1:
                problems.append(f"{rel}: more than one reference-count field")
            elif values:
                declared_any = True
                if values[0] != actual:
                    problems.append(
                        f"{rel}: declares {values[0]} references but the manuscript uses {actual} distinct citekeys"
                    )
            elif source_values:
                problems.append(f"{rel}: lost the reference-count field present in {title_rel}")

    if problems:
        return Result(
            False,
            "title_page_reference_count",
            "; ".join(problems[:6]),
            ["Run tools/manuscript/reference_count.py sync; use --add only when the journal requires the field."],
        )
    if declared_any:
        return Result(True, "title_page_reference_count",
                      f"title-page count matches {actual} distinct citekey(s) actually used")
    return Result(True, "title_page_reference_count",
                  f"manuscript uses {actual} distinct citekey(s); title page does not declare a count")


def bib_keys(text: str) -> set[str]:
    return {k for _, k in BIB_ENTRY_RE.findall(text)}


def _verified_map(ctx: Ctx) -> dict:
    if not ctx.p(VER).exists():
        return {}
    try:
        data = ctx.read_json(VER)
    except Exception:  # noqa: BLE001
        return {}
    return data.get("records", data if isinstance(data, dict) else {})


@check("citekeys_resolve")
def citekeys_resolve(ctx: Ctx) -> Result:
    paths = ctx.spec.get("paths", [])
    allow_unverified = bool(ctx.spec.get("allow_unverified", False))
    present = [p for p in paths if ctx.p(p).exists()]
    if not present:
        return Result(False, "citekeys_resolve", "none of the target files exist: " + ", ".join(paths))

    used: dict[str, list[str]] = {}
    for rel in present:
        for k in citekeys(ctx.read(rel)):
            used.setdefault(k, []).append(rel)
    if not used:
        return Result(
            False,
            "citekeys_resolve",
            "no pandoc citations found in " + ", ".join(present),
            ["Cite with pandoc markers: [@author2023] or [@a2023; @b2021]."],
        )

    have_bib = ctx.p(BIB).exists()
    known = bib_keys(ctx.read(BIB)) if have_bib else set()
    ver = _verified_map(ctx)

    if not have_bib and allow_unverified:
        return Result(
            True,
            "citekeys_resolve",
            f"{len(used)} citekey(s); refs.bib not built yet (permitted at this stage)",
            severity="warn",
        )

    unknown = sorted(k for k in used if k not in known)
    unverified = sorted(
        k for k in used
        if k in known and not (ver.get(k, {}) or {}).get("verified") is True
    )
    problems = []
    if unknown:
        problems.append(f"{len(unknown)} citekey(s) absent from refs.bib: " + ", ".join(unknown[:8]))
    if unverified and not allow_unverified:
        problems.append(f"{len(unverified)} citekey(s) not verified: " + ", ".join(unverified[:8]))
    if not allow_unverified:
        proof_ok, proof_problems, _ = refproof.validate_local_proof(
            ctx.project,
            required_keys=set(used),
            max_age_days=int(ctx.target("reference_verification_age_days_max", 90)),
        )
        if not proof_ok:
            problems.append("reference proof invalid: " + "; ".join(proof_problems[:4]))
    if problems:
        return Result(
            False,
            "citekeys_resolve",
            "; ".join(problems),
            [
                "Never invent a citekey. Add references with: .venv/Scripts/python.exe tools/pubmed/build_library.py",
                "Then verify with: .venv/Scripts/python.exe tools/pubmed/verify.py",
            ],
        )
    return Result(
        True,
        "citekeys_resolve",
        f"{len(used)} distinct citekey(s), all bound to hashed fresh-PubMed evidence",
    )


@check("citation_count")
def citation_count(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    if not ctx.p(rel).exists():
        return Result(False, "citation_count", f"{rel} missing")
    n = len(set(citekeys(ctx.read(rel))))
    lo, hi = ctx.spec_bound("min"), ctx.spec_bound("max")
    if lo is not None and n < lo:
        return Result(False, "citation_count", f"{rel}: {n} distinct references, target >= {lo}")
    if hi is not None and n > hi:
        return Result(False, "citation_count", f"{rel}: {n} distinct references, target <= {hi}")
    return Result(True, "citation_count", f"{rel}: {n} distinct references (target {lo}-{hi})")


@check("refs_library")
def refs_library(ctx: Ctx) -> Result:
    if not ctx.p(LIB).exists():
        return Result(False, "refs_library", f"{LIB} missing")
    try:
        lib = ctx.read_json(LIB)
    except json.JSONDecodeError as exc:
        return Result(False, "refs_library", f"{LIB} invalid JSON: {exc}")
    entries = lib.get("entries", [])
    lo = ctx.spec.get("min_entries", ctx.target("reflib_min", 45))
    hi = ctx.spec.get("max_entries", ctx.target("reflib_max", 60))

    problems = []
    if len(entries) < lo:
        problems.append(f"{len(entries)} entries, need >= {lo}")
    if hi and len(entries) > hi:
        problems.append(f"{len(entries)} entries, allowed <= {hi}")

    if ctx.spec.get("require_abstract", True):
        no_abs = [e.get("citekey", "?") for e in entries if not (e.get("abstract") or "").strip()]
        if no_abs:
            problems.append(
                f"{len(no_abs)} entry/entries without an abstract (must be removed): " + ", ".join(no_abs[:6])
            )
    missing_id = [e.get("citekey", "?") for e in entries if not (e.get("pmid") or e.get("doi"))]
    if missing_id:
        problems.append(f"{len(missing_id)} entry/entries with neither PMID nor DOI: " + ", ".join(missing_id[:6]))

    if ctx.spec.get("require_verified", True):
        proof_ok, proof_problems, _ = refproof.validate_local_proof(
            ctx.project,
            max_age_days=int(ctx.target("reference_verification_age_days_max", 90)),
        )
        if not proof_ok:
            problems.append("reference proof invalid: " + "; ".join(proof_problems[:5]))

    dupes = _dupes([e.get("citekey") for e in entries])
    if dupes:
        problems.append("duplicate citekeys: " + ", ".join(dupes[:6]))

    if problems:
        return Result(
            False,
            "refs_library",
            "; ".join(problems),
            [
                "Rebuild with: .venv/Scripts/python.exe tools/pubmed/build_library.py --topic \"...\" --target 50",
                "Entries without abstracts must be dropped, not padded with a summary you wrote.",
            ],
        )
    return Result(
        True,
        "refs_library",
        f"{len(entries)} PubMed-proven entries, all with abstracts and an ID",
    )


@check("reference_provenance")
def reference_provenance(ctx: Ctx) -> Result:
    """Independently re-fetch the library at S13; fail closed if NCBI is unavailable."""
    max_age = int(ctx.target("reference_verification_age_days_max", 90))
    ok, problems, count = refproof.validate_local_proof(
        ctx.project, max_age_days=max_age)
    if not ok:
        return Result(
            False,
            "reference_provenance",
            "; ".join(problems[:8]),
            ["Delete the forged/stale verification output and run tools/pubmed/verify.py; never patch verified.json."],
        )
    if not ctx.spec.get("live", False):
        return Result(True, "reference_provenance",
                      f"{count} record(s) bound to reparsed hashed PubMed XML")
    try:
        library = ctx.read_json(LIB)
        entries = library.get("entries", [])
        pmids = [str(item.get("pmid", "")) for item in entries]
        if not pmids or any(not re.fullmatch(r"\d+", pmid) for pmid in pmids):
            raise ValueError("every entry must have a numeric PMID")
        from pubmed import eutils as eu

        live_records = eu.efetch(pmids, fresh=True, purpose="gate")
        live = {str(item.get("pmid", "")): item for item in live_records}
    except Exception as exc:  # noqa: BLE001 - network failure must close the gate
        return Result(
            False,
            "reference_provenance",
            f"independent live PubMed re-fetch failed closed: {exc}",
            ["Restore NCBI access and rerun the gate; do not replace it with a local boolean."],
        )
    live_problems = []
    for entry in entries:
        key, pmid = str(entry.get("citekey", "?")), str(entry.get("pmid", ""))
        source = live.get(pmid)
        if source is None:
            live_problems.append(f"{key}: PMID {pmid} was not returned by PubMed")
            continue
        live_problems.extend(
            f"{key}: {problem}" for problem in
            refproof.compare_entry_to_source(entry, source)
        )
    if set(live) != set(pmids):
        live_problems.append("the independent PubMed response PMID set differs from the library")
    if live_problems:
        return Result(False, "reference_provenance", "; ".join(live_problems[:8]),
                      ["Rebuild the affected entry from the returned PubMed record; never edit the proof to match."])
    return Result(True, "reference_provenance",
                  f"{len(entries)} record(s) independently re-fetched and matched against live PubMed")


@check("bib_ris_match_library")
def bib_ris_match_library(ctx: Ctx) -> Result:
    for rel in (LIB, BIB, RIS):
        if not ctx.p(rel).exists():
            return Result(False, "bib_ris_match_library", f"{rel} missing")
    lib = ctx.read_json(LIB)
    lib_keys = {e.get("citekey") for e in lib.get("entries", []) if e.get("citekey")}
    bkeys = bib_keys(ctx.read(BIB))
    n_ris = len(re.findall(r"^TY\s+-\s+", ctx.read(RIS), re.M))
    problems = []
    if lib_keys != bkeys:
        only_lib = sorted(lib_keys - bkeys)[:5]
        only_bib = sorted(bkeys - lib_keys)[:5]
        problems.append(f"library/bib mismatch (library-only: {only_lib}, bib-only: {only_bib})")
    if n_ris != len(lib_keys):
        problems.append(f"RIS has {n_ris} records vs {len(lib_keys)} library entries")
    if problems:
        return Result(
            False,
            "bib_ris_match_library",
            "; ".join(problems),
            ["Regenerate both formats from library.json rather than editing them by hand."],
        )
    return Result(True, "bib_ris_match_library", f"library / bib / ris agree on {len(lib_keys)} records")


@check("pubmed_cache_fresh")
def pubmed_cache_fresh(ctx: Ctx) -> Result:
    """Proof-of-retrieval: a real search happened and its payload is on disk."""
    rel = ctx.spec.get("manifest", "06_refs/cache/scan_manifest.json")
    if not ctx.p(rel).exists():
        return Result(
            False,
            "pubmed_cache_fresh",
            f"{rel} missing - no evidence any literature search was actually run",
            ["Search via: .venv/Scripts/python.exe tools/pubmed/client.py search --query \"...\" (writes the manifest and caches raw payloads)"],
        )
    try:
        man = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "pubmed_cache_fresh", f"{rel} invalid JSON: {exc}")
    queries = man.get("queries", [])
    min_q = ctx.spec.get("min_queries", 3)
    min_hits = ctx.spec.get("min_hits", 20)

    uniq_q = {q.get("query", "").strip().lower() for q in queries if q.get("query")}
    pmids: set[str] = set()
    missing_cache = []
    for q in queries:
        pmids.update(str(x) for x in q.get("ids", []))
        cf = q.get("cache_file")
        if cf and not ctx.p(cf).exists():
            missing_cache.append(cf)

    problems = []
    if len(uniq_q) < min_q:
        problems.append(f"{len(uniq_q)} distinct queries, need >= {min_q}")
    if len(pmids) < min_hits:
        problems.append(f"{len(pmids)} unique records retrieved, need >= {min_hits}")
    if missing_cache:
        problems.append(f"{len(missing_cache)} cached payload(s) missing: " + ", ".join(missing_cache[:4]))
    if problems:
        return Result(False, "pubmed_cache_fresh", "; ".join(problems))
    return Result(
        True,
        "pubmed_cache_fresh",
        f"{len(uniq_q)} queries, {len(pmids)} unique records, payloads cached",
    )


@check("deepread_complete")
def deepread_complete(ctx: Ctx) -> Result:
    rel = "06_refs/deepread/deepread_index.json"
    if not ctx.p(rel).exists():
        return Result(False, "deepread_complete", f"{rel} missing")
    try:
        idx = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "deepread_complete", f"{rel} invalid JSON: {exc}")
    sel = idx.get("selected", [])
    want = ctx.target("deepread_count", 5)
    problems = []
    if len(sel) < max(3, want - 1):
        problems.append(f"{len(sel)} paper(s) selected, target ~{want}")

    lib_keys = set()
    if ctx.p(LIB).exists():
        try:
            lib_keys = {e.get("citekey") for e in ctx.read_json(LIB).get("entries", [])}
        except Exception:  # noqa: BLE001
            pass

    retrievals = {}
    if ctx.p(RETRIEVALS).exists():
        try:
            retrievals = {r.get("citekey"): r for r in
                          ctx.read_json(RETRIEVALS).get("retrievals", []) if r.get("citekey")}
        except Exception:  # noqa: BLE001
            retrievals = {}
    else:
        problems.append(f"{RETRIEVALS} missing")

    for item in sel:
        ck = item.get("citekey", "?")
        if lib_keys and ck not in lib_keys:
            problems.append(f"{ck} is not in library.json")
        if not item.get("reason"):
            problems.append(f"{ck}: no selection reason recorded")
        src = item.get("fulltext")
        if not src:
            problems.append(f"{ck}: no full-text source recorded")
        elif str(src).startswith("http"):
            problems.append(f"{ck}: link or abstract only; a registered local full text is required")
        elif not ctx.p(str(src)).exists():
            problems.append(f"{ck}: full text {src} not on disk")
        record = retrievals.get(ck)
        if not record:
            problems.append(f"{ck}: no retrieval-manifest record")
        else:
            if record.get("access") not in {"oa", "authorized"}:
                problems.append(f"{ck}: access is {record.get('access')!r}, not full-text access")
            if record.get("fulltext") != src:
                problems.append(f"{ck}: deepread index and retrieval manifest disagree on file")
            local = ctx.p(str(src)) if src and not str(src).startswith("http") else None
            if local and local.is_file() and record.get("sha256"):
                digest = _file_sha256(local)
                if digest != record.get("sha256"):
                    problems.append(f"{ck}: registered full text changed after acquisition")
        notes = item.get("notes")
        if not notes:
            problems.append(f"{ck}: no notes file")
        else:
            np = ctx.p(str(notes))
            if not np.exists():
                problems.append(f"{ck}: notes file {notes} missing")
            elif len(np.read_text(encoding="utf-8", errors="replace").strip()) < 400:
                problems.append(f"{ck}: notes too thin to have been a real read")
    if problems:
        return Result(
            False,
            "deepread_complete",
            "; ".join(problems[:8]),
            ["Fetch or register legal full text with: .\\.venv\\Scripts\\python.exe "
             "tools\\pubmed\\fulltext.py fetch --citekey KEY"],
        )
    return Result(True, "deepread_complete", f"{len(sel)} paper(s) fetched and read with notes on disk")


@check("deepread_cited")
def deepread_cited(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    idx_rel = "06_refs/deepread/deepread_index.json"
    if not ctx.p(rel).exists() or not ctx.p(idx_rel).exists():
        return Result(False, "deepread_cited", "discussion or deepread index missing")
    sel = [i.get("citekey") for i in ctx.read_json(idx_rel).get("selected", []) if i.get("citekey")]
    used = set(citekeys(ctx.read(rel)))
    absent = [k for k in sel if k not in used]
    if absent:
        return Result(
            False,
            "deepread_cited",
            "deep-read paper(s) never cited in the Discussion: " + ", ".join(absent),
            ["If a paper turned out irrelevant, drop it from deepread_index.json and record why."],
        )
    return Result(True, "deepread_cited", f"all {len(sel)} deep-read paper(s) engaged in the Discussion")


@check("guidelines_sourced")
def guidelines_sourced(ctx: Ctx) -> Result:
    tj, gx = "08_submission/target_journal.json", "08_submission/guidelines_extract.md"
    for rel in (tj, gx):
        if not ctx.p(rel).exists():
            return Result(False, "guidelines_sourced", f"{rel} missing")
    meta = ctx.read_json(tj)
    url = (meta.get("guidelines_url") or "").strip()
    text = ctx.read(gx)
    problems = []
    if not url.startswith("http"):
        problems.append("target_journal.json has no usable guidelines_url")
    elif url not in text:
        problems.append("guidelines_extract.md does not cite the exact guidelines_url it came from")
    freshness = int(ctx.target("journal_source_age_days_max", 90))
    for key in ("guidelines_fetched_at", "scie_verified_at", "jcr_verified_at",
                "integrity_checked_at"):
        value = meta.get(key)
        if not _looks_like_date(value):
            problems.append(f"{key} must be an ISO date")
            continue
        age = _verification_age_days(value)
        if age is None or age < 0 or age > freshness:
            problems.append(f"{key} must be verified within {freshness} days")
    if meta.get("scie_indexed") is not True:
        problems.append("target journal is not verified as currently SCIE-indexed")
    scie_url = str(meta.get("scie_source_url") or "").strip()
    if not scie_url.startswith("http"):
        problems.append("no authoritative scie_source_url recorded")
    quartile = str(meta.get("jcr_quartile") or "").strip().upper()
    if quartile not in {"Q1", "Q2", "Q3", "Q4"}:
        problems.append("jcr_quartile must be a current Q1-Q4 value")
    if not str(meta.get("jcr_source") or "").strip():
        problems.append("jcr_source not recorded")
    if str(meta.get("integrity_status") or "").strip().lower() != "clear":
        problems.append("integrity_status is not clear")
    integrity_sources = meta.get("integrity_sources")
    if not isinstance(integrity_sources, list) or len({str(x).strip() for x in integrity_sources
                                                       if str(x).startswith("http")}) < 2:
        problems.append("integrity_sources must contain at least two source URLs")
    abbreviation_placement = str(meta.get("abbreviation_placement", "")).strip().lower()
    abbreviation_source = str(meta.get("abbreviation_rule_source", "")).strip()
    if abbreviation_placement not in {"central", "local_required"}:
        problems.append("abbreviation_placement must be central or local_required")
    if not abbreviation_source or (url and url not in abbreviation_source):
        problems.append("abbreviation_rule_source must cite the exact guidelines_url")
    snapshots = ctx.glob("08_submission/cache/*")
    if not snapshots:
        problems.append("no raw snapshot under 08_submission/cache/ - guidelines were not actually fetched")
    for need in ("Word limits", "Reference style", "Figure", "Table", "Required statements", "Submission items"):
        if need.lower() not in text.lower():
            problems.append(f"guidelines_extract.md does not cover: {need}")
    if problems:
        return Result(
            False,
            "guidelines_sourced",
            "; ".join(problems[:12]),
            ["Verify current SCIE/JCR status and integrity, then fetch and snapshot the live "
             "author instructions; do not recall them from memory."],
        )
    return Result(True, "guidelines_sourced",
                  f"{quartile} SCIE journal cleared; guidelines fetched, snapshotted and extracted")


def _dupes(items) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x in seen and x not in out:
            out.append(x)
        seen.add(x)
    return out

