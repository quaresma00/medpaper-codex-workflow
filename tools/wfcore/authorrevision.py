"""Read author Word revisions and import proven layout changes without claiming review."""
from __future__ import annotations

from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

from . import buildproof, revision
from .packagefreeze import MANIFEST_REL, _safe_path, _sha256

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
CONTENT_PART = re.compile(r"word/(?:document|header\d+|footer\d+|footnotes|endnotes)\.xml$")
LAYOUT_PART = re.compile(r"(?:docProps/.*|word/(?:styles|settings|fontTable|webSettings)\.xml|word/theme/.*)$")
NUMBERS = re.compile(r"(?<!\w)[+−-]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:%|\b)")
QUALIFIERS = re.compile(r"\b(?:not|no|without|higher|lower|increased|decreased|reduced|causal|causally|prospective|retrospective|randomized|observational)\b", re.I)
CITATIONS = re.compile(r"\[(?:@[^\]]+|\d+(?:[\s,;–-]+\d+)*)\]|\b10\.\d{4,9}/[^\s]+|\bPMC\d+\b|\bPMID\s*:?\s*\d+", re.I)


def _digest(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def _text(node) -> str:
    return unicodedata.normalize("NFC", buildproof.paragraph_text(node).replace("\u00a0", " "))


def inspect_docx(path: Path) -> dict:
    """Keep row/cell/paragraph identities; flattened equal word bags are insufficient."""
    path = path.resolve()
    if path.suffix.casefold() != ".docx":
        raise ValueError("Author revision input must be a DOCX file")
    result = {"parts": {}, "tables": {}, "media": {}, "other_content": {}, "layout": {}, "markup": {}, "sections": {}}
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate Word ZIP members need explicit repair")
            for name in sorted(names):
                if name.endswith("/"):
                    continue
                if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                    raise ValueError("Unsafe Word ZIP member")
                blob = archive.read(name)
                digest = hashlib.sha256(blob).hexdigest().upper()
                if CONTENT_PART.fullmatch(name):
                    root = ET.fromstring(blob)
                    paragraphs = [_text(p) for p in root.iter(W + "p") if _text(p).strip()]
                    result["parts"][name] = paragraphs
                    result["tables"][name] = [
                        [[[_text(p) for p in cell.findall(W + "p")] for cell in row.findall(W + "tc")]
                         for row in table.findall(W + "tr")]
                        for table in root.iter(W + "tbl")]
                    result["markup"][name] = [
                        ET.tostring(node, encoding="unicode") for node in root.iter()
                        if node.tag in {W + "ins", W + "del", W + "moveFrom", W + "moveTo", W + "fldSimple",
                                        W + "instrText", W + "delText", W + "hyperlink", W + "drawing", W + "object",
                                        W + "gridSpan", W + "vMerge", W + "hMerge", W + "numPr", W + "vanish", W + "specVanish"}
                        and not (node.tag==W+"fldSimple" and buildproof.is_page_counter(node.get(W+"instr","")))
                        and not (node.tag==W+"instrText" and buildproof.is_page_counter(node.text))]
                    # Layout/style attributes are observed without normalizing author bytes.
                    result["layout"][name] = [ET.tostring(node, encoding="unicode") for node in root.iter()
                                              if node.tag in {W + "pPr", W + "rPr", W + "sectPr", W + "tblPr", W + "tcPr"}]
                    result["sections"][name] = [
                        {child.tag.rsplit("}", 1)[-1]: {key.rsplit("}", 1)[-1]: value for key, value in child.attrib.items()}
                         for child in section if child.tag in {W + "pgSz", W + "pgMar", W + "type", W + "cols"}}
                        for section in root.iter(W + "sectPr")]
                elif name.startswith(("word/media/", "word/embeddings/")):
                    result["media"][name] = digest
                elif LAYOUT_PART.fullmatch(name):
                    result["layout"][name] = digest
                else:
                    # Relationships, numbering, fields/comments and arbitrary content
                    # must not become an unexamined formatting exception.
                    result["other_content"][name] = digest
    except (OSError, BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError(f"Cannot inspect DOCX {path.name}: {exc}") from exc
    if "word/document.xml" not in result["parts"]:
        raise ValueError("DOCX has no readable main document")
    result["sha256"] = _sha256(path)
    result["semantic_sha256"] = _digest({k: result[k] for k in ("parts", "tables", "media", "other_content", "markup")})
    return result


def compare(managed: Path, author: Path, *, max_changes: int = 8) -> dict:
    if not 1 <= max_changes <= 100:
        raise ValueError("max_changes must be between 1 and 100")
    before, after = inspect_docx(managed), inspect_docx(author)
    changed = [key for key in ("parts", "tables", "media", "other_content", "markup", "layout") if before[key] != after[key]]
    changes = []
    change_count = 0
    for part in sorted(set(before["parts"]) | set(after["parts"])):
        a, b = before["parts"].get(part, []), after["parts"].get(part, [])
        for tag, i, j, k, l in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            change_count += 1
            if len(changes) < max_changes:
                changes.append({"part": part, "operation": tag, "managed_paragraphs": [i + 1, j],
                                "author_paragraphs": [k + 1, l],
                                "before": "\n".join(a[i:j])[:320], "after": "\n".join(b[k:l])[:320]})
    table_changes = []
    for part in sorted(set(before["tables"]) | set(after["tables"])):
        a, b = before["tables"].get(part, []), after["tables"].get(part, [])
        for index in range(max(len(a), len(b))):
            left, right = a[index] if index < len(a) else [], b[index] if index < len(b) else []
            if left == right: continue
            for row in range(max(len(left), len(right))):
                x, y = left[row] if row < len(left) else [], right[row] if row < len(right) else []
                for cell in range(max(len(x), len(y))):
                    old, new = x[cell] if cell < len(x) else None, y[cell] if cell < len(y) else None
                    if old != new:
                        change_count += 1
                        if len(changes) + len(table_changes) < max_changes:
                            table_changes.append({"part": part, "table": index + 1, "row": row + 1, "cell": cell + 1,
                                                  "before": str(old)[:320], "after": str(new)[:320]})
    member_changes = []
    for category in ("media", "other_content"):
        for name in sorted(set(before[category]) | set(after[category])):
            if before[category].get(name) != after[category].get(name):
                change_count += 1
                if len(changes) + len(table_changes) + len(member_changes) < max_changes:
                    member_changes.append({"category": category, "member": name,
                                           "before_sha256": before[category].get(name), "after_sha256": after[category].get(name)})
    text = lambda row: "\n".join(p for values in row["parts"].values() for p in values)
    numbers_changed = Counter(NUMBERS.findall(text(before))) != Counter(NUMBERS.findall(text(after)))
    qualifiers_changed = Counter(m.casefold() for m in QUALIFIERS.findall(text(before))) != Counter(m.casefold() for m in QUALIFIERS.findall(text(after)))
    # Equality includes ordered prose/table structure, protected markup and all
    # non-layout members. A similar sentence or equal numbers never proves meaning.
    same_science = before["semantic_sha256"] == after["semantic_sha256"]
    return {"schema_version": 1, "managed": str(managed.resolve()), "author": str(author.resolve()),
            "managed_sha256": before["sha256"], "author_sha256": after["sha256"],
            "classification": "IDENTICAL" if before["sha256"] == after["sha256"] else
                              "LAYOUT_CANDIDATE" if same_science else "SOURCE_RECONCILIATION_REQUIRED",
            "changed_categories": changed, "numbers_changed": numbers_changed,
            "citations_or_identifiers_changed": Counter(CITATIONS.findall(text(before))) != Counter(CITATIONS.findall(text(after))),
            "clinical_qualifiers_changed": qualifiers_changed,
            "change_count": change_count, "shown_changes": changes, "table_changes": table_changes,
            "member_changes": member_changes, "section_properties": {"before": before["sections"], "after": after["sections"]}
                if before["sections"] != after["sections"] else {},
            "truncated": change_count > len(changes) + len(table_changes) + len(member_changes),
            "next_action": "Inspect actual Word pages and run normal journal/style/blinding checks; no approval is implied."
                           if same_science else
                           "Reconcile the changed content at its actual Markdown/table/figure source in a scoped revision; rebuild affected consumers before importing layout. Moving legends, references or table content also needs reconciliation."}


def managed_source(project: Path, managed: Path) -> tuple[str, dict]:
    project = project.resolve(); managed = managed.resolve()
    try:
        rel = managed.relative_to(project).as_posix()
    except ValueError as exc:
        raise ValueError("Managed Word target must be inside the active project") from exc
    _, managed = _safe_path(project, rel)
    if not rel.startswith("08_submission/bundle/"):
        raise ValueError("Only mutable manifest-listed bundle DOCX files can receive author layout")
    manifest = json.loads((project / MANIFEST_REL).read_text(encoding="utf-8"))
    matches = [item for item in manifest.get("items", []) if item.get("file") == rel and item.get("upload", True)]
    if len(matches) != 1:
        raise ValueError("Managed Word target must have one exact active upload-manifest role")
    receipt = buildproof.load(project).get(rel, {})
    if (receipt.get("tool") not in {"tools/manuscript/build_docx.py", "tools/manuscript/author_revision.py"}
            or not buildproof.inputs_current(receipt)
            or buildproof.content_digest(managed) != receipt.get("content_sha256")):
        raise ValueError("Current managed build provenance is absent or stale; reconcile/rebuild its real sources first")
    return rel, receipt


def adopt_layout(project: Path, managed: Path, author: Path, *, managed_sha256: str, author_sha256: str) -> dict:
    """Import exact author bytes, never manufacture a builder or an accepted review."""
    from .dependencies import guard_build
    project, managed, author = project.resolve(), managed.resolve(), author.resolve()
    if managed == author:
        raise ValueError("Author input and managed output must be separate files")
    guard_build(project)
    batch = revision.active(project) or {}
    from .state import State
    if (batch.get("schema_version") != 2 or batch.get("status") != "active"
            or batch.get("review_stage") != "S24_package_human_review"
            or State(project).load().current != "S24_package_human_review"):
        raise ValueError("Open and seal a scoped S24 package layout revision before adoption")
    rel, prior = managed_source(project, managed)
    revision.guard_outputs(project, [managed])
    report = compare(managed, author)
    if report["managed_sha256"].casefold() != managed_sha256.casefold() or report["author_sha256"].casefold() != author_sha256.casefold():
        raise ValueError("Word files changed since inspection; inspect the current versions again")
    if report["classification"] not in {"IDENTICAL", "LAYOUT_CANDIDATE"}:
        raise ValueError("Author Word contains content/structure changes; reconcile its real sources before layout adoption")
    if buildproof.content_digest(author) != prior["content_sha256"]:
        raise ValueError("Author Word does not match the existing content baseline; reconcile sources first")
    _, snapshot = _safe_path(project, ".wf/author_imports/" + report["author_sha256"] + ".docx")
    _, receipts_path = _safe_path(project, buildproof.RECEIPTS)
    _, round_path = _safe_path(project, ".wf/revisions/" + batch["round_id"] + ".json")
    originals = {path: path.read_bytes() if path.exists() else None for path in
                 (managed, receipts_path, round_path)}
    incoming = author.read_bytes()
    if hashlib.sha256(incoming).hexdigest().upper() != report["author_sha256"]:
        raise ValueError("Author Word changed during import")
    if (_sha256(managed) != report["managed_sha256"] or not buildproof.inputs_current(prior)
            or buildproof.load(project).get(rel) != prior):
        raise ValueError("Managed Word or its sources changed during import; inspect again")
    created_snapshot = not snapshot.exists()
    if not created_snapshot and snapshot.read_bytes() != incoming:
        raise ValueError("Stored author source snapshot is corrupt; preserve it for investigation")
    temporary = None
    replaced = False
    try:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if created_snapshot:
            with snapshot.open("xb") as stream:
                stream.write(incoming)
        with tempfile.NamedTemporaryFile(dir=managed.parent, prefix=".author_layout_", delete=False) as stream:
            temporary = Path(stream.name); stream.write(incoming)
        if any((path.read_bytes() if path.exists() else None) != value for path, value in originals.items()):
            raise ValueError("Managed output or revision changed during import; inspect again")
        if not buildproof.inputs_current(prior) or _sha256(author)!=report["author_sha256"]:
            raise ValueError("Author Word or source inputs changed during import; inspect again")
        os.replace(temporary, managed)
        replaced = True
        if not buildproof.inputs_current(prior) or _sha256(author)!=report["author_sha256"]:
            raise ValueError("Author Word or source inputs changed during import; inspect again")
        sources = [Path(p) for p in prior["sources"]] + [snapshot, Path(__file__).resolve()]
        entrypoints = [project / p for p in prior.get("entrypoints", [])]
        revision.record_build(project, managed, sources, entrypoints=entrypoints,
                              tool="tools/manuscript/author_revision.py",
                              parameters={"operation": "author-layout-import", "previous_managed_sha256": report["managed_sha256"],
                                          "author_sha256": report["author_sha256"], "previous_builder": prior["tool"],
                                          "prior_content_sha256": prior["content_sha256"]})
    except BaseException:
        if replaced:
            for path, value in originals.items():
                if value is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(value)
        if created_snapshot:
            snapshot.unlink(missing_ok=True)
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"path": rel, "author_source": snapshot.relative_to(project).as_posix(),
            "sha256": report["author_sha256"], "status": "IMPORTED_PENDING_ACTUAL_QA",
            "next_action": "Run affected journal/style/blinding checks and inspect actual author Word pages, then continue the existing revision check/close. Baselines, freezes and approvals were not rewritten."}
