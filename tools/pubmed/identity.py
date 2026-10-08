"""Check the acquired article's own metadata, never identifiers in its bibliography."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def norm(kind, value):
    text = str(value or "").strip().casefold()
    if kind == "doi":
        return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text).rstrip(" .")
    return text


def inspect(entry, blob: bytes, suffix: str):
    observed = {}
    if suffix.lower() == ".xml":
        try:
            root = ET.fromstring(blob)
            local = lambda node: node.tag.split("}")[-1]
            front = next((x for x in root if local(x) == "front"), None)
            meta = next((x for x in front if local(x) == "article-meta"), None) if front is not None else None
            if meta is not None:
                for child in meta:
                    kind = child.get("pub-id-type", "").casefold()
                    if local(child) == "article-id" and kind in {"doi", "pmid", "pmcid"}:
                        observed[kind] = "".join(child.itertext()).strip()
                title = next((x for x in meta.iter() if local(x) == "article-title"), None)
                if title is not None:
                    observed["title"] = "".join(title.itertext()).strip()
        except ET.ParseError:
            pass
    elif suffix.lower() in {".html", ".htm"}:
        class Metadata(HTMLParser):
            in_head = False

            def handle_starttag(self, tag, attrs):
                if tag.casefold() == "head":
                    self.in_head = True
                values = dict(attrs)
                if tag.casefold() == "meta" and self.in_head:
                    name = (values.get("name") or values.get("property") or "").casefold()
                    field = {"citation_doi": "doi", "citation_pmid": "pmid", "citation_pmcid": "pmcid",
                             "citation_title": "title"}.get(name)
                    if field and values.get("content"):
                        observed[field] = values["content"]

            def handle_endtag(self, tag):
                if tag.casefold() == "head":
                    self.in_head = False
        Metadata(convert_charrefs=True).feed(blob.decode("utf-8", errors="replace"))
    conflicts, matched = [], []
    for kind in ("doi", "pmid", "pmcid"):
        if entry.get(kind) and observed.get(kind):
            (matched if norm(kind, entry[kind]) == norm(kind, observed[kind]) else conflicts).append(kind)
    state = "mismatch" if conflicts else "match" if matched else "pending"
    return {"status": state, "observed": observed, "matched": matched, "conflicts": conflicts,
            "method": "article-front-metadata" if observed else "unresolved",
            "note": "PDF/title-only evidence requires explicit reader confirmation; bibliography identifiers are not identity evidence"}


def errors(entry, path: Path, record):
    from wfcore.packagefreeze import _sha256
    identity = inspect(entry, path.read_bytes(), path.suffix)
    if identity["status"] == "mismatch":
        return ["acquired article metadata contradicts the verified library"]
    if identity["status"] == "match":
        return []
    confirmation = record.get("identity_confirmation", {})
    expected = {k: norm(k, entry.get(k)) for k in ("doi", "pmid", "pmcid", "title")}
    if (confirmation.get("sha256") == _sha256(path) and confirmation.get("expected") == expected
            and str(confirmation.get("confirmed_by", "")).strip()
            and len(str(confirmation.get("note", "")).strip()) >= 30):
        return []
    return ["article identity unresolved; inspect first page and explicitly confirm the exact article (not an AI-invented PASS)"]
