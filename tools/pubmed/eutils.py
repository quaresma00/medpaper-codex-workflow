"""NCBI E-utilities + Crossref access. Stdlib only (urllib + ElementTree).

Every response is written to project/06_refs/cache/ before it is parsed, and every
search appends to scan_manifest.json. That cache is the evidence the gates inspect:
a claim about the literature that has no cached payload behind it is treated as
fabricated.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF = "https://api.crossref.org/works"
TOOL = "medpaper-codex-pipeline"
UA = f"{TOOL}/1.0 (research pipeline; contact via NCBI_API_EMAIL)"

_last_call = [0.0]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_key() -> str | None:
    return os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY") or None


def api_email() -> str | None:
    return os.environ.get("NCBI_API_EMAIL") or os.environ.get("PUBMED_API_EMAIL") or None


def _min_interval() -> float:
    # NCBI: 3 requests/second without a key, 10/second with one. Stay under.
    return 0.12 if api_key() else 0.36


def _throttle() -> None:
    wait = _min_interval() - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def http_get(url: str, params: dict | None = None, retries: int = 4, timeout: int = 60) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, '')})}"
    last: Exception | None = None
    for attempt in range(retries):
        _throttle()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url} ({last})")


# ---------------------------------------------------------------------------
# project paths / cache
# ---------------------------------------------------------------------------
def repo_root() -> Path:
    env = os.environ.get("MEDPAPER_ROOT")
    return Path(env).resolve() if env else Path(__file__).resolve().parents[2]


def project_root() -> Path:
    env = os.environ.get("MEDPAPER_PROJECT")
    return Path(env).resolve() if env else repo_root() / "project"


def cache_dir() -> Path:
    d = project_root() / "06_refs" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def refs_dir() -> Path:
    d = project_root() / "06_refs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _digest(*parts: str) -> str:
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()[:16]


def cached(name: str, fetch, binary: bool = False):
    """Return cached payload, fetching (and storing) it on first use."""
    p = cache_dir() / name
    if p.exists() and p.stat().st_size > 0:
        return p.read_bytes() if binary else p.read_text(encoding="utf-8")
    blob = fetch()
    if isinstance(blob, str):
        p.write_text(blob, encoding="utf-8")
    else:
        p.write_bytes(blob)
    return blob if binary or isinstance(blob, str) else blob.decode("utf-8", "replace")


def manifest_path() -> Path:
    return cache_dir() / "scan_manifest.json"


def load_manifest() -> dict:
    p = manifest_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"created_at": now(), "queries": []}


def append_manifest(entry: dict) -> None:
    man = load_manifest()
    man.setdefault("queries", []).append(entry)
    man["updated_at"] = now()
    manifest_path().write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# E-utilities
# ---------------------------------------------------------------------------
def esearch(query: str, retmax: int = 100, years: int | None = None, db: str = "pubmed",
            sort: str = "relevance", record: bool = True) -> dict:
    params = {
        "db": db, "term": query, "retmax": retmax, "retmode": "json",
        "sort": sort, "tool": TOOL, "email": api_email(), "api_key": api_key(),
    }
    if years:
        params["reldate"] = int(years) * 365
        params["datetype"] = "pdat"
    name = f"esearch_{db}_{_digest(query, str(retmax), str(years), sort)}.json"
    raw = cached(name, lambda: http_get(f"{EUTILS}/esearch.fcgi", params).decode("utf-8", "replace"))
    data = json.loads(raw)
    res = data.get("esearchresult", {})
    ids = res.get("idlist", [])
    out = {
        "query": query, "db": db, "at": now(), "retmax": retmax, "years": years,
        "count": int(res.get("count", 0) or 0), "ids": ids, "cache_file": f"06_refs/cache/{name}",
        "translation": res.get("querytranslation", ""),
    }
    if record:
        append_manifest(out)
    return out


def efetch(pmids: list[str], db: str = "pubmed") -> list[dict]:
    """Fetch full MEDLINE records in batches of 200."""
    out: list[dict] = []
    pmids = [str(p).strip() for p in pmids if str(p).strip()]
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i + 200]
        name = f"efetch_{db}_{_digest(','.join(batch))}.xml"
        params = {
            "db": db, "id": ",".join(batch), "retmode": "xml",
            "tool": TOOL, "email": api_email(), "api_key": api_key(),
        }
        raw = cached(name, lambda: http_get(f"{EUTILS}/efetch.fcgi", params).decode("utf-8", "replace"))
        out.extend(parse_pubmed_xml(raw, cache_file=f"06_refs/cache/{name}"))
    return out


def parse_pubmed_xml(xml_text: str, cache_file: str = "") -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"unparseable PubMed XML: {exc}")
    records = []
    for art in root.iter("PubmedArticle"):
        records.append(_one_record(art, cache_file))
    for art in root.iter("PubmedBookArticle"):
        rec = _one_record(art, cache_file)
        rec["type"] = "book"
        records.append(rec)
    return records


def _text(node, path: str, default: str = "") -> str:
    el = node.find(path)
    if el is None:
        return default
    return "".join(el.itertext()).strip()


def _one_record(art, cache_file: str) -> dict:
    pmid = _text(art, ".//MedlineCitation/PMID")
    title = _text(art, ".//Article/ArticleTitle") or _text(art, ".//BookTitle")

    parts = []
    for ab in art.findall(".//Article/Abstract/AbstractText"):
        label = ab.get("Label")
        body = "".join(ab.itertext()).strip()
        if body:
            parts.append(f"{label}: {body}" if label else body)
    abstract = "\n".join(parts).strip()

    authors = []
    for a in art.findall(".//AuthorList/Author"):
        coll = _text(a, "CollectiveName")
        if coll:
            authors.append({"last": coll, "first": "", "collective": True})
            continue
        last, fore = _text(a, "LastName"), _text(a, "ForeName")
        if last:
            authors.append({"last": last, "first": fore, "initials": _text(a, "Initials")})

    year = _text(art, ".//Journal/JournalIssue/PubDate/Year")
    if not year:
        m = re.search(r"(19|20)\d{2}", _text(art, ".//Journal/JournalIssue/PubDate/MedlineDate"))
        year = m.group(0) if m else ""

    doi = ""
    for el in art.findall(".//ELocationID"):
        if el.get("EIdType") == "doi":
            doi = (el.text or "").strip()
    pmcid = ""
    for el in art.findall(".//ArticleIdList/ArticleId"):
        t = el.get("IdType")
        if t == "doi" and not doi:
            doi = (el.text or "").strip()
        elif t == "pmc":
            pmcid = (el.text or "").strip()

    ptypes = [(_p.text or "").strip() for _p in art.findall(".//PublicationTypeList/PublicationType")]
    corrections = [c.get("RefType", "") for c in art.findall(".//CommentsCorrectionsList/CommentsCorrections")]
    flags = []
    if any("Retract" in t for t in ptypes) or "RetractionIn" in corrections:
        flags.append("RETRACTED_OR_RETRACTION")
    if "ExpressionOfConcernIn" in corrections:
        flags.append("EXPRESSION_OF_CONCERN")
    if "Preprint" in ptypes:
        flags.append("PREPRINT")

    return {
        "pmid": pmid,
        "doi": doi.lower(),
        "pmcid": pmcid,
        "title": re.sub(r"\s+", " ", title).strip().rstrip("."),
        "abstract": abstract,
        "authors": authors,
        "journal": _text(art, ".//Journal/Title"),
        "journal_abbrev": _text(art, ".//Journal/ISOAbbreviation"),
        "year": year,
        "volume": _text(art, ".//JournalIssue/Volume"),
        "issue": _text(art, ".//JournalIssue/Issue"),
        "pages": _text(art, ".//Pagination/MedlinePgn") or _text(art, ".//Pagination/StartPage"),
        "publication_types": ptypes,
        "mesh": [(_m.text or "").strip() for _m in art.findall(".//MeshHeading/DescriptorName")],
        "flags": flags,
        "source": "pubmed",
        "cache_file": cache_file,
        "retrieved_at": now(),
    }


def crossref_by_doi(doi: str) -> dict | None:
    if not doi:
        return None
    name = f"crossref_{_digest(doi)}.json"
    try:
        raw = cached(name, lambda: http_get(f"{CROSSREF}/{urllib.parse.quote(doi)}",
                                           {"mailto": api_email() or ""}).decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None
    try:
        msg = json.loads(raw).get("message", {})
    except json.JSONDecodeError:
        return None
    issued = msg.get("issued", {}).get("date-parts", [[None]])[0]
    return {
        "doi": (msg.get("DOI") or "").lower(),
        "title": (msg.get("title") or [""])[0],
        "journal": (msg.get("container-title") or [""])[0],
        "year": str(issued[0]) if issued and issued[0] else "",
        "authors": [{"last": a.get("family", ""), "first": a.get("given", "")}
                    for a in msg.get("author", [])],
        "type": msg.get("type", ""),
        "source": "crossref",
    }


# ---------------------------------------------------------------------------
# citekeys
# ---------------------------------------------------------------------------
STOPWORDS = {
    "the", "a", "an", "of", "and", "in", "on", "for", "with", "to", "from", "by",
    "at", "as", "is", "are", "was", "were", "be", "been", "its", "their", "this",
    "that", "these", "those", "study", "analysis", "using", "based", "among",
    "between", "after", "before", "during", "effect", "effects", "role", "new",
}


def _ascii(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))


def make_citekey(rec: dict, taken: set[str] | None = None) -> str:
    taken = taken or set()
    authors = rec.get("authors") or []
    last = _ascii(authors[0]["last"]) if authors else "anon"
    last = re.sub(r"[^A-Za-z]", "", last).lower() or "anon"
    year = re.sub(r"[^0-9]", "", str(rec.get("year") or ""))[:4] or "0000"
    words = [w for w in re.findall(r"[A-Za-z]{3,}", _ascii(rec.get("title", "")).lower())
             if w not in STOPWORDS]
    word = words[0] if words else "untitled"
    base = f"{last}{year}{word}"
    if base not in taken:
        return base
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        cand = f"{base}{suffix}"
        if cand not in taken:
            return cand
    return f"{base}{rec.get('pmid', '')}"


# ---------------------------------------------------------------------------
def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)
