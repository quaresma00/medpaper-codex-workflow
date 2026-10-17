"""Observed managed-builder inputs/outputs shared by dependency planning and delivery QA."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json

RECEIPTS = ".wf/build_receipts.json"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def content_parts(path: Path) -> list[str]:
    """Content, not ZIP bytes: includes text and embedded media; ignores layout whitespace."""
    import hashlib
    if path.suffix.lower() != ".docx":
        return [_sha256(path)]
    parts = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith("word/media/") and not name.endswith("/"):
                parts.append(name+"\n"+hashlib.sha256(archive.read(name)).hexdigest())
                continue
            if not re.fullmatch(r"word/(document|footnotes|endnotes|header\d+|footer\d+)\.xml", name):
                continue
            root = ET.fromstring(archive.read(name))
            for parent in root.iter():
                for node in list(parent):
                    if node.tag == W+"fldSimple" and re.match(r"\s*(PAGE|NUMPAGES|SECTIONPAGES)\b",node.get(W+"instr",""),re.I):
                        parent.remove(node)
            paragraphs=[]
            for p in root.iter(W+"p"):
                text=[];fields=[]
                for node in p.iter():
                    if node.tag==W+"fldChar":
                        flag=node.get(W+"fldCharType")
                        if flag=="begin": fields.append({"instruction":"","page":False})
                        elif flag=="separate" and fields:
                            fields[-1]["page"]=bool(re.match(r"\s*(PAGE|NUMPAGES|SECTIONPAGES)\b",fields[-1]["instruction"],re.I))
                        elif flag=="end" and fields: fields.pop()
                    elif node.tag==W+"instrText" and fields:
                        fields[-1]["instruction"]+=node.text or ""
                    elif node.tag==W+"t" and not any(f["page"] for f in fields):
                        text.append(node.text or "")
                paragraphs.append("".join(text))
            text=" ".join(paragraphs)
            text = re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()
            if text:
                parts.append(name+"\n"+text)
    return parts


def content_digest(path: Path) -> str:
    import hashlib
    if path.suffix.lower() != ".docx": return _sha256(path)
    return hashlib.sha256("\n".join(content_parts(path)).encode("utf-8")).hexdigest().upper()


def load(project: Path) -> dict:
    path = project / RECEIPTS
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def record(project: Path, output: Path, sources: list[Path], *, entrypoints=None, tool=None, parameters=None) -> dict:
    project = project.resolve()
    rel, output = _safe_path(project, output.resolve().relative_to(project).as_posix())
    inputs = {str(p.resolve()): _sha256(p) for p in sources if p is not None}
    direct = [p.resolve().relative_to(project).as_posix() for p in entrypoints or []]
    row = {"sha256": _sha256(output), "content_sha256": content_digest(output), "sources": inputs,
           "entrypoints": direct, "tool": tool, "parameters": parameters or {}}
    from .paths import repo_root
    row["engine_inputs"]=[name for name in inputs if any(Path(name).is_relative_to(repo_root()/folder)
                                                       for folder in ("tools","pipeline","reference"))]
    receipts = load(project); receipts[rel] = row
    atomic_json(project / RECEIPTS, receipts)
    return row


def inputs_current(receipt: dict) -> bool:
    # A historic builder version is provenance, not a reason to redo an unchanged manuscript.
    return bool(receipt.get("sources")) and all(Path(p).is_file() and _sha256(Path(p)) == h for p,h in receipt["sources"].items()
                                                if p not in receipt.get("engine_inputs",[]))


def project_inputs(project: Path, receipt: dict) -> list[str]:
    out = []
    for name in receipt.get("sources", {}):
        try:
            rel = Path(name).resolve().relative_to(project.resolve()).as_posix()
            _safe_path(project, rel); out.append(rel)
        except ValueError:
            continue  # Engine inputs are hash-bound, never project edit targets.
    return sorted(out)
