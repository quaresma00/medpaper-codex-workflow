"""Measure actual svglite output and observed R layers, without fabricating artist QA.

Text boxes use measured SVG textLength and conservative font-height estimates. Complex
glyph/rotation/layout cases remain explicit visual-review items, not invented PASS results.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

NS = {"s": "http://www.w3.org/2000/svg"}


def sequence(value):
    return value if isinstance(value, list) else [] if value is None else [value]


def audit_svg(path, metadata):
    root = ET.parse(path).getroot()
    canvas = [float(x) for x in root.get("viewBox", "").split()]
    if len(canvas) != 4:
        raise ValueError("SVG has no measurable viewBox")
    fonts, strokes, texts, boxes, unsupported = [], [], [], [], []
    for node in root.iter():
        style = dict(re.findall(r"([\w-]+)\s*:\s*([^;]+)", node.get("style", "")))
        width = style.get("stroke-width", node.get("stroke-width"))
        if width and style.get("stroke", "") != "none":
            match = re.fullmatch(r"([\d.]+)(?:px|pt)?", width.strip())
            if match and float(match[1]) > 0:
                strokes.append(float(match[1]))
        if node.tag.rsplit("}", 1)[-1] != "text":
            continue
        text = "".join(node.itertext()).strip()
        if not text:
            continue
        texts.append(text)
        size = style.get("font-size", "")
        match = re.match(r"([\d.]+)", size)
        if not match:
            unsupported.append(f"font measurement unavailable: {text[:40]}")
            continue
        font = float(match[1]); fonts.append(font)
        length = node.get("textLength")
        transform = node.get("transform", "")
        try:
            x, y = float(node.get("x", "0")), float(node.get("y", "0"))
            w = float(length)
        except (ValueError, TypeError):
            unsupported.append(f"text box measurement unavailable: {text[:40]}")
            continue
        anchor = node.get("text-anchor", "start")
        left = x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
        corners = [(left, y - font), (left + w, y - font), (left, y + font * .25), (left + w, y + font * .25)]
        if transform:
            rotate = re.fullmatch(r"rotate\(([-\d.]+)(?:[, ]+([-\d.]+)[, ]+([-\d.]+))?\)", transform)
            if not rotate:
                unsupported.append(f"unmeasured SVG transform: {text[:40]}")
                continue
            angle = math.radians(float(rotate[1])); ox, oy = float(rotate[2] or 0), float(rotate[3] or 0)
            corners = [(ox + (a - ox) * math.cos(angle) - (b - oy) * math.sin(angle),
                        oy + (a - ox) * math.sin(angle) + (b - oy) * math.cos(angle)) for a, b in corners]
        box = [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]
        boxes.append({"text": text, "bbox": box})
    clipped = [b for b in boxes if b["bbox"][0] < -.5 or b["bbox"][1] < -.5 or
               b["bbox"][2] > canvas[2] + .5 or b["bbox"][3] > canvas[3] + .5]
    collisions = []
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            dx = min(a["bbox"][2], b["bbox"][2]) - max(a["bbox"][0], b["bbox"][0])
            dy = min(a["bbox"][3], b["bbox"][3]) - max(a["bbox"][1], b["bbox"][1])
            if dx > 1 and dy > 1:
                collisions.append({"labels": [a["text"][:50], b["text"][:50]], "overlap_pt2": round(dx * dy, 2)})
    panels = sequence(metadata.get("panels"))
    layers = [l for p in panels for l in sequence(p.get("layers")) if l.get("rows", 0) > 0]
    geoms = {l.get("geom") for l in layers}
    def element(found, evidence):
        return {"found": bool(found), "evidence": evidence}
    bars = [l for l in layers if l.get("geom") in {"GeomBar", "GeomCol"}]
    bar_zero = all(l.get("ymin") == 0 or l.get("xmin") == 0 for l in bars)
    labels_present = bool(panels) and all(p.get("x_label") and p.get("y_label") for p in panels)
    null = any(v in (0, 1) for l in layers if l.get("geom") == "GeomVline" for v in sequence(l.get("xintercept")))
    diagonal = any(1 in sequence(l.get("slope")) and 0 in sequence(l.get("intercept")) for l in layers if l.get("geom") == "GeomAbline")
    ranges = [r for p in panels for r in sequence(p.get("ranges"))]
    equal = bool(ranges) and all(len(sequence(r.get("x"))) == 2 and len(sequence(r.get("y"))) == 2 and
                all(abs(x-y) < 1e-8 for x, y in zip(sequence(r["x"]), sequence(r["y"]))) for r in ranges)
    stats = any(re.search(r"\b(?:HR|OR|RR|AUC|n|P|r)\s*(?:[=<>]|\d|\()", t, re.I) for t in texts)
    elements = {
        "axis_labels": element(labels_present, "Observed built ggplot axis labels on all declared panels"),
        "bar_artist": element(bool(bars), "Observed nonempty GeomBar/GeomCol"),
        "baseline_zero": element(not bars or bar_zero, "Observed built bar xmin/ymin; no bar" if not bars else "Bar data start at zero"),
        "individual_points": element("GeomPoint" in geoms or "GeomJitter" in geoms, "Observed nonempty point/jitter layer"),
        "box_artist": element("GeomBoxplot" in geoms, "Observed nonempty GeomBoxplot"),
        "violin_artist": element("GeomViolin" in geoms, "Observed nonempty GeomViolin"),
        "error_bars": element(bool(geoms & {"GeomErrorbar", "GeomErrorbarh", "GeomPointrange", "GeomLinerange"}), "Observed built interval layer"),
        "step_curve": element("GeomStep" in geoms, "Observed nonempty GeomStep"),
        "confidence_band": element("GeomRibbon" in geoms, "Observed nonempty GeomRibbon"),
        "censoring_marks": element(any(l.get("geom") == "GeomPoint" and any(s in (3, 43, 124, "+", "|") for s in sequence(l.get("shape"))) for l in layers), "Observed censor-like point shapes; survival meaning still reviewed"),
        "risk_table": element(any(re.search(r"number[s]? at risk|no\. at risk", t, re.I) for t in texts), "Rendered number-at-risk heading; row/time alignment needs visual review"),
        "legend_present": element(any(p.get("legend") for p in panels), "Observed nonempty ggplot guide-box"),
        "figure_statistics": element(stats, "Actual rendered statistical labels, not a metadata assertion"),
        "null_line": element(null, "Observed vertical intercept at 0 or 1; effect scale still reviewed"),
        "reference_diagonal": element(diagonal, "Observed slope=1, intercept=0 reference line"),
        "equal_axes_limits": element(equal, "Built panel x/y ranges compared"),
        "connected_pairs": element(any(l.get("geom") in {"GeomLine", "GeomPath"} and any(n >= 2 for n in sequence(l.get("group_sizes"))) for l in layers), "Observed within-group connected observations; pairing semantics still reviewed"),
    }
    return {"engine": "R", "schema_version": 1, "min_font_pt": min(fonts) if fonts else None,
            "min_line_pt": min(strokes) if strokes else None, "figure_text": sorted(set(texts)),
            "text_clipped_at_edge": clipped, "r_text_box_collisions": collisions,
            "measurement_limits": unsupported + ["Text height/overlap are conservative estimates; PDF font fallback, clipping paths, glyph coverage and complex grid layout require visual inspection."],
            "n_axes": len(ranges), "elements": elements, "runtime": metadata}
