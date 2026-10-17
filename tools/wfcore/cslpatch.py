"""Scoped, inspectable formatting-only CSL overrides. Never mutate shared styles or refs."""
import json
from pathlib import Path
from xml.etree import ElementTree as ET


def apply(base: Path, patch: Path, output: Path):
    data = json.loads(patch.read_text(encoding="utf-8"))
    if not data.get("source") or not isinstance(data.get("changes"), list): raise ValueError("CSL patch needs the actual official rule source and changes")
    root = ET.parse(base)
    for item in data["changes"]:
        selector = item.get("selector", "")
        if not selector.startswith(".//csl:") or ".." in selector[3:]: raise ValueError("use a scoped CSL element selector")
        found = root.findall(selector, {"csl": "http://purl.org/net/xbiblio/csl"})
        if not found or (len(found) != 1 and not item.get("all")): raise ValueError("CSL patch selector is missing or ambiguous")
        for node in found:
            for name, value in item.get("attributes", {}).items():
                if name not in {"delimiter", "prefix", "suffix", "font-style", "font-weight", "text-case", "strip-periods", "sort-separator", "and", "delimiter-precedes-last", "et-al-min", "et-al-use-first", "collapse", "second-field-align", "hanging-indent"}:
                    raise ValueError(f"not an allowed citation-format attribute: {name}")
                node.set(name, str(value))
    root.write(output, encoding="utf-8", xml_declaration=True)
