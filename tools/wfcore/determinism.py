"""Stable generated containers; never discard clinical dates or arbitrary JSON fields."""
from __future__ import annotations
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

FIXED = "2000-01-01T00:00:00Z"
VOLATILE_XML = {"{http://purl.org/dc/terms/}created", "{http://purl.org/dc/terms/}modified",
                "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy",
                "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}revision"}
for prefix, uri in {"cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
                    "dc": "http://purl.org/dc/elements/1.1/", "dcterms": "http://purl.org/dc/terms/",
                    "xsi": "http://www.w3.org/2001/XMLSchema-instance"}.items():
    ET.register_namespace(prefix, uri)


def _core(blob: bytes, *, fixed=False) -> bytes:
    root = ET.fromstring(blob)
    for node in list(root):
        if node.tag in VOLATILE_XML:
            if fixed and node.tag.endswith(("}created", "}modified")):
                node.text = FIXED
            else:
                root.remove(node)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def content_sha256(path: Path) -> str:
    """Ignore container times, not wording, styling, images, authors or numerical facts."""
    digest = hashlib.sha256()
    if path.suffix.lower() in {".docx", ".xlsx"}:
        if not zipfile.is_zipfile(path):
            from .packagefreeze import _sha256
            return _sha256(path)  # invalid Office bytes never gain a content-equivalence exemption
        with zipfile.ZipFile(path) as archive:
            if archive.testzip():
                raise ValueError("corrupt Office container")
            for name in sorted(archive.namelist()):
                blob = archive.read(name)
                if name == "docProps/core.xml": blob = _core(blob)
                digest.update(name.encode() + b"\0" + blob + b"\0")
            digest.update(b"zip-comment\0" + archive.comment)
        raw = path.read_bytes(); end = raw.rfind(b"PK\x05\x06")
        if end < 0 or end + 22 > len(raw): raise ValueError("Office ZIP end record missing")
        boundary = end + 22 + int.from_bytes(raw[end+20:end+22], "little")
        digest.update(b"trailing-bytes\0" + raw[boundary:])
        return digest.hexdigest().upper()
    if path.suffix.lower() == ".json" and path.as_posix().endswith(("04_tables/manifest.json", "05_figures/qc/qc_report.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        # Only explicitly known top-level build metadata; a clinical date inside a row stays.
        for key in ("created_at", "generated_at", "checked_at"):
            doc.pop(key, None)
        return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest().upper()
    from .packagefreeze import _sha256
    return _sha256(path)


def normalize(path: Path) -> None:
    """Called only on task-generated staging files, never approved originals."""
    suffix = path.suffix.lower()
    if suffix in {".docx", ".xlsx"}:
        with zipfile.ZipFile(path) as archive:
            parts = [(info.filename, archive.read(info.filename), info.external_attr) for info in archive.infolist()]
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, blob, attributes in sorted(parts):
                if name == "docProps/core.xml": blob = _core(blob, fixed=True)
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = attributes
                archive.writestr(info, blob)
        path.write_bytes(output.getvalue())
    elif suffix == ".pdf":
        # A real PDF parser maintains xref offsets/streams; do not edit PDF bytes with regex.
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(path); writer = PdfWriter(clone_from=reader)
        writer.add_metadata({"/CreationDate": "D:20000101000000Z", "/ModDate": "D:20000101000000Z"})
        from pypdf.generic import ArrayObject, ByteStringObject
        writer._ID = ArrayObject([ByteStringObject(b"0"*16), ByteStringObject(b"0"*16)])
        stable = io.BytesIO(); writer.write(stable)
        identity = hashlib.md5(stable.getvalue(), usedforsecurity=False).digest()
        writer._ID = ArrayObject([ByteStringObject(identity), ByteStringObject(identity)])
        output = io.BytesIO(); writer.write(output); path.write_bytes(output.getvalue())
    elif suffix in {".tif", ".tiff"}:
        from PIL import Image, ImageSequence
        with Image.open(path) as image:
            options = {key: image.info[key] for key in ("dpi", "icc_profile") if key in image.info}
            frames = [frame.copy() for frame in ImageSequence.Iterator(image)]
        output = io.BytesIO()
        frames[0].save(output, format="TIFF", compression="tiff_deflate", save_all=True, append_images=frames[1:], **options)
        path.write_bytes(output.getvalue())


def receipt(path: Path, rel: str) -> dict:
    from .packagefreeze import _sha256
    return {"path": rel, "sha256": _sha256(path), "content_sha256": content_sha256(path)}


def holds(project: Path, row: dict) -> bool:
    path = project / row["path"]
    if row.get("deleted"): return not path.exists()
    if not path.is_file(): return False
    from .packagefreeze import _sha256
    return _sha256(path).casefold() == str(row.get("sha256", "")).casefold() or bool(
        row.get("content_sha256") and content_sha256(path).casefold() == row["content_sha256"].casefold())
