"""Detect figure elements from a live matplotlib figure.

This is what turns archetype rules from prose advice into a gate. "A KM curve needs a
number-at-risk table" is only enforceable if code can look at the figure and see whether
one is there.

Detectors are deliberately conservative. An element only belongs in an archetype's
`requires` list if its detector here is reliable; anything fuzzy goes in `advisory`.
Every detector returns (found, evidence) so a failure report can say what it looked for.

The glyph-warning capture and the tick-collision test are adapted from
quaresma00/medical-sci-figure-skill (MIT), which credits scipilot-figure-skill.
"""
from __future__ import annotations

import logging
import re
import warnings

import matplotlib
import numpy as np
from matplotlib.collections import LineCollection, PathCollection, PolyCollection, QuadMesh
from matplotlib.container import BarContainer, ErrorbarContainer
from matplotlib.image import AxesImage
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.text import Annotation, Text

SCALE_BAR_RE = re.compile(r"\d+\s*(?:µm|μm|um|nm|mm|cm|kb|bp)\b", re.I)
NUMBER_RE = re.compile(r"\d")
GLYPH_MARKERS = ("missing from current font", "Glyph", "glyph",
                 "cannot be converted to a character")


# ---------------------------------------------------------------------------
def _axes(fig) -> list:
    return list(fig.get_axes())


def _data_axes(fig) -> list:
    """Axes that plot data, excluding colorbars and decorative panels."""
    return [ax for ax in _axes(fig) if getattr(ax, "_colorbar", None) is None]


def _lines(fig) -> list[Line2D]:
    return [ln for ax in _axes(fig) for ln in ax.get_lines() if ln.get_visible()]


def _texts(fig) -> list[Text]:
    out = []
    for t in fig.findobj(match=Text):
        if t.get_visible() and (t.get_text() or "").strip():
            out.append(t)
    return out


def _containers(fig, kind) -> list:
    return [c for ax in _axes(fig) for c in ax.containers if isinstance(c, kind)]


def _is_vertical(ln: Line2D) -> bool:
    x, y = ln.get_xdata(), ln.get_ydata()
    return len(x) == 2 and np.allclose(float(x[0]), float(x[1])) and not np.allclose(
        float(y[0]), float(y[1]))


def _is_horizontal(ln: Line2D) -> bool:
    x, y = ln.get_xdata(), ln.get_ydata()
    return len(y) == 2 and np.allclose(float(y[0]), float(y[1])) and not np.allclose(
        float(x[0]), float(x[1]))


# ---------------------------------------------------------------------------
# detectors: each returns (bool, evidence string)
# ---------------------------------------------------------------------------
def axis_labels(fig) -> tuple[bool, str]:
    """Both axes labelled, resolved across shared-axis groups.

    A shared-x layout (survival curve above its risk table, a plot above its marginal)
    deliberately puts the x label on the bottom axes only. Checking each axes in isolation
    would call that a defect, so a label on any member of the share group counts.
    """
    plotting = [ax for ax in _data_axes(fig) if ax.has_data() and ax.axison]
    if not plotting:
        return True, "no data axes to label"

    def group_label(ax, which: str) -> str:
        try:
            shared = list(getattr(ax, f"get_shared_{which}_axes")().get_siblings(ax))
        except Exception:  # noqa: BLE001
            shared = [ax]
        getter = "get_xlabel" if which == "x" else "get_ylabel"
        for other in shared or [ax]:
            txt = getattr(other, getter)().strip()
            if txt:
                return txt
        return ""

    ok, missing = [], []
    for ax in plotting:
        xl, yl = group_label(ax, "x"), group_label(ax, "y")
        if xl and yl:
            ok.append(ax)
        else:
            missing.append("x" if not xl else "y")
    if ok:
        return True, f"{len(ok)}/{len(plotting)} data axes labelled on both axes (shared groups resolved)"
    return False, f"no data axes carry both labels; absent: {sorted(set(missing))}"


def bar_artist(fig) -> tuple[bool, str]:
    bars = _containers(fig, BarContainer)
    return bool(bars), f"{len(bars)} bar container(s)"


def baseline_zero(fig) -> tuple[bool, str]:
    """Bar charts must include zero on the value axis.

    Orientation is taken from where the bars actually start - vertical bars share a common
    lower y edge, horizontal bars a common left x edge - rather than from guessing at the
    aspect of the rectangles, which inverts for short bars.
    """
    offenders, notes = [], []
    checked = 0
    for ax in _axes(fig):
        patches = [p for c in ax.containers if isinstance(c, BarContainer) for p in c.patches]
        if not patches:
            continue
        checked += 1
        y0s = {round(float(p.get_y()), 6) for p in patches}
        x0s = {round(float(p.get_x()), 6) for p in patches}
        if len(y0s) == 1 and len(x0s) > 1:
            orient, lo, base = "vertical", ax.get_ylim()[0], next(iter(y0s))
        elif len(x0s) == 1 and len(y0s) > 1:
            orient, lo, base = "horizontal", ax.get_xlim()[0], next(iter(x0s))
        else:
            orient, lo, base = "vertical", ax.get_ylim()[0], min(y0s)
        if lo > 0.01 or base > 0.01:
            offenders.append(f"{orient} bars: value axis starts at {lo:.3g}, "
                             f"bars start at {base:.3g}")
        else:
            notes.append(f"{orient} bars from {base:.3g}, axis from {lo:.3g}")
    if not checked:
        return True, "no bar chart present"
    if offenders:
        return False, "truncated baseline: " + "; ".join(offenders)
    return True, f"{checked} bar axes include zero ({'; '.join(notes)})"


def individual_points(fig) -> tuple[bool, str]:
    scatters = [c for ax in _axes(fig) for c in ax.collections
                if isinstance(c, PathCollection) and len(c.get_offsets())]
    marked = [ln for ln in _lines(fig)
              if ln.get_marker() not in (None, "None", "", " ") and ln.get_linestyle() in
              ("None", "none", "")]
    n = sum(len(c.get_offsets()) for c in scatters) + sum(len(ln.get_xdata()) for ln in marked)
    return bool(scatters or marked), f"{len(scatters)} scatter collection(s), {len(marked)} marker-only line(s), ~{n} point(s)"


def error_bars(fig) -> tuple[bool, str]:
    ebs = _containers(fig, ErrorbarContainer)
    lcs = [c for ax in _axes(fig) for c in ax.collections if isinstance(c, LineCollection)]
    return bool(ebs or lcs), f"{len(ebs)} errorbar container(s), {len(lcs)} line collection(s)"


def box_artist(fig) -> tuple[bool, str]:
    """A box plot leaves Rectangle or PathPatch boxes plus a median line inside each."""
    hits = 0
    for ax in _axes(fig):
        rects = [p for p in ax.patches if isinstance(p, Rectangle)
                 and p.get_width() > 0 and p.get_height() > 0]
        medians = [ln for ln in ax.get_lines() if _is_horizontal(ln) and len(ln.get_xdata()) == 2]
        pathpatch = [p for p in ax.patches if type(p).__name__ == "PathPatch"]
        if (rects or pathpatch) and medians:
            hits += 1
    return hits > 0, f"{hits} axes with box+median geometry"


def violin_artist(fig) -> tuple[bool, str]:
    polys = [c for ax in _axes(fig) for c in ax.collections if isinstance(c, PolyCollection)]
    return bool(polys), f"{len(polys)} polygon collection(s) (violin bodies)"


def connected_pairs(fig) -> tuple[bool, str]:
    pairs = [ln for ln in _lines(fig)
             if len(ln.get_xdata()) == 2 and ln.get_linestyle() not in ("None", "none", "")
             and not _is_vertical(ln) and not _is_horizontal(ln)]
    return len(pairs) >= 3, f"{len(pairs)} two-point connecting line(s)"


def step_curve(fig) -> tuple[bool, str]:
    steps = [ln for ln in _lines(fig) if "steps" in str(ln.get_drawstyle())]
    return bool(steps), f"{len(steps)} step curve(s)"


def censoring_marks(fig) -> tuple[bool, str]:
    marks = [ln for ln in _lines(fig)
             if ln.get_marker() in ("|", "+", "x", "1", "2", "3", "4", "d", "D")]
    scatters = [c for ax in _axes(fig) for c in ax.collections
                if isinstance(c, PathCollection) and len(c.get_offsets())]
    return bool(marks or scatters), f"{len(marks)} tick-marker line(s), {len(scatters)} scatter overlay(s)"


def risk_table(fig) -> tuple[bool, str]:
    """A number-at-risk panel: axis switched off, carrying a grid of numeric text."""
    for ax in _axes(fig):
        spines_hidden = not ax.axison or all(not s.get_visible() for s in ax.spines.values())
        if not spines_hidden:
            continue
        nums = [t for t in ax.texts if NUMBER_RE.search(t.get_text() or "")]
        if len(nums) >= 3:
            return True, f"panel with {len(nums)} numeric labels and no frame"
    return False, "no frameless panel carrying a numeric grid was found"


def box_nodes(fig) -> tuple[bool, str]:
    """Flow-diagram boxes: rectangles each containing text."""
    rects = [p for ax in _axes(fig) for p in ax.patches
             if isinstance(p, Rectangle) and p.get_width() > 0 and p.get_height() > 0]
    texts = [t for ax in _axes(fig) for t in ax.texts]
    return len(rects) >= 3 and len(texts) >= 3, f"{len(rects)} rectangle(s), {len(texts)} text node(s)"


def null_line(fig) -> tuple[bool, str]:
    verts = [ln for ln in _lines(fig) if _is_vertical(ln)]
    at_null = [ln for ln in verts if abs(float(ln.get_xdata()[0]) - 1.0) < 1e-9
               or abs(float(ln.get_xdata()[0])) < 1e-9]
    return bool(at_null or verts), (f"{len(verts)} vertical reference line(s), "
                                    f"{len(at_null)} at 0 or 1")


def reference_diagonal(fig) -> tuple[bool, str]:
    for ln in _lines(fig):
        x, y = np.asarray(ln.get_xdata(), float), np.asarray(ln.get_ydata(), float)
        if len(x) >= 2 and len(y) == len(x) and np.allclose(x, y, atol=1e-6):
            return True, f"identity line over {len(x)} point(s), style {ln.get_linestyle()!r}"
    return False, "no y=x reference line"


def reference_lines_horizontal(fig) -> tuple[bool, str]:
    hs = [ln for ln in _lines(fig) if _is_horizontal(ln)]
    return len(hs) >= 1, f"{len(hs)} horizontal reference line(s)"


def threshold_lines(fig) -> tuple[bool, str]:
    hs = [ln for ln in _lines(fig) if _is_horizontal(ln)]
    vs = [ln for ln in _lines(fig) if _is_vertical(ln)]
    return bool(hs and vs), f"{len(hs)} horizontal + {len(vs)} vertical cutoff line(s)"


def colorbar(fig) -> tuple[bool, str]:
    cbs = [ax for ax in _axes(fig) if getattr(ax, "_colorbar", None) is not None]
    meshes = [c for ax in _axes(fig) for c in ax.collections if isinstance(c, QuadMesh)]
    imgs = [im for ax in _axes(fig) for im in ax.get_images() if isinstance(im, AxesImage)]
    return bool(cbs), (f"{len(cbs)} colorbar(s) for {len(meshes)} mesh(es) "
                       f"and {len(imgs)} image(s)")


def equal_aspect(fig) -> tuple[bool, str]:
    vals = []
    for ax in _data_axes(fig):
        if not ax.has_data():
            continue
        a = ax.get_aspect()
        vals.append(a)
        if a == "equal" or (isinstance(a, (int, float)) and abs(float(a) - 1.0) < 1e-9):
            return True, f"aspect={a!r}"
    return False, f"aspect ratios seen: {vals}"


def equal_axes_limits(fig) -> tuple[bool, str]:
    for ax in _data_axes(fig):
        if not ax.has_data():
            continue
        xl, yl = ax.get_xlim(), ax.get_ylim()
        if abs((xl[1] - xl[0]) - (yl[1] - yl[0])) < 1e-6:
            return True, f"x span {xl[1] - xl[0]:.3g} == y span {yl[1] - yl[0]:.3g}"
    return False, "no axes with matching x and y spans"


def scale_bar(fig) -> tuple[bool, str]:
    labels = [t.get_text() for t in _texts(fig) if SCALE_BAR_RE.search(t.get_text() or "")]
    thick = [ln for ln in _lines(fig) if _is_horizontal(ln) and ln.get_linewidth() >= 1.5]
    rects = [p for ax in _axes(fig) for p in ax.patches
             if isinstance(p, Rectangle) and p.get_height() > 0
             and p.get_width() > p.get_height() * 4]
    ok = bool(labels) and bool(thick or rects)
    return ok, (f"unit label(s) {labels[:3]}, {len(thick)} thick rule(s), {len(rects)} bar patch(es)"
                if labels else "no physical unit label (e.g. '50 um') found in the panel")


def bitmap_panel(fig) -> tuple[bool, str]:
    imgs = [im for ax in _axes(fig) for im in ax.get_images()]
    off = [ax for ax in _axes(fig) if not ax.axison]
    return bool(imgs), f"{len(imgs)} raster image(s), {len(off)} axis-off panel(s)"


def legend_present(fig) -> tuple[bool, str]:
    legs = [ax.get_legend() for ax in _axes(fig) if ax.get_legend() is not None]
    return bool(legs or fig.legends), f"{len(legs)} axes legend(s), {len(fig.legends)} figure legend(s)"


def figure_statistics(fig) -> tuple[bool, str]:
    """Numeric text inside the panel. Those numbers are then provenance-checked."""
    vals = [t.get_text().strip() for t in _texts(fig) if NUMBER_RE.search(t.get_text() or "")]
    tickish = set()
    for ax in _axes(fig):
        tickish |= {t.get_text().strip() for t in ax.get_xticklabels() + ax.get_yticklabels()}
    meaningful = [v for v in vals if v not in tickish and len(v) > 2]
    return bool(meaningful), f"{len(meaningful)} non-tick numeric label(s): {meaningful[:4]}"


def repelled_labels(fig) -> tuple[bool, str]:
    anns = [a for a in fig.findobj(match=Annotation) if (a.get_text() or "").strip()]
    return bool(anns), f"{len(anns)} annotation(s)"


def log_axis(fig) -> tuple[bool, str]:
    scales = [(ax.get_xscale(), ax.get_yscale()) for ax in _data_axes(fig)]
    return any("log" in s for pair in scales for s in pair), f"scales {scales}"


DETECTORS = {
    "axis_labels": axis_labels,
    "bar_artist": bar_artist,
    "baseline_zero": baseline_zero,
    "individual_points": individual_points,
    "error_bars": error_bars,
    "box_artist": box_artist,
    "violin_artist": violin_artist,
    "connected_pairs": connected_pairs,
    "step_curve": step_curve,
    "censoring_marks": censoring_marks,
    "risk_table": risk_table,
    "box_nodes": box_nodes,
    "null_line": null_line,
    "reference_diagonal": reference_diagonal,
    "reference_lines_horizontal": reference_lines_horizontal,
    "threshold_lines": threshold_lines,
    "colorbar": colorbar,
    "equal_aspect": equal_aspect,
    "equal_axes_limits": equal_axes_limits,
    "scale_bar": scale_bar,
    "bitmap_panel": bitmap_panel,
    "legend_present": legend_present,
    "figure_statistics": figure_statistics,
    "repelled_labels": repelled_labels,
    "log_axis": log_axis,
}


def detect_all(fig) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, fn in DETECTORS.items():
        try:
            found, evidence = fn(fig)
        except Exception as exc:  # noqa: BLE001 - a broken detector must not kill the render
            found, evidence = False, f"detector raised {type(exc).__name__}: {exc}"
        out[name] = {"found": bool(found), "evidence": evidence}
    return out


# ---------------------------------------------------------------------------
# checks that need the draw pass rather than the artist tree
# ---------------------------------------------------------------------------
class _GlyphHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        msg = record.getMessage()
        if any(m in msg for m in GLYPH_MARKERS):
            self.messages.append(msg)


def glyph_warnings(fig) -> list[str]:
    """Missing-glyph warnings raised while rasterizing.

    Catches tofu boxes from an unavailable CJK font and broken Unicode minus signs -
    both of which look fine in the code and wrong on the page.
    """
    collected: list[str] = []
    mpl_logger = logging.getLogger("matplotlib")
    prev = mpl_logger.level
    mpl_logger.setLevel(logging.WARNING)
    handler = _GlyphHandler()
    mpl_logger.addHandler(handler)
    try:
        with warnings.catch_warnings(record=True) as ws:
            warnings.filterwarnings("always", category=UserWarning)
            fig.canvas.draw()
            for w in ws:
                s = str(w.message)
                if any(m in s for m in GLYPH_MARKERS):
                    collected.append(s)
    finally:
        mpl_logger.removeHandler(handler)
        mpl_logger.setLevel(prev)
    collected.extend(handler.messages)
    return list(dict.fromkeys(collected))


def interior_voids(fig, renderer, max_frac: float = 0.10) -> list[dict]:
    """Dead bands between adjacent panels.

    The outer-margin check cannot see these: a figure can have tight margins on all four
    sides and still waste a fifth of its height in a gap between two panels. Reports gaps
    wider than `max_frac` of the corresponding figure dimension.
    """
    out = []
    boxes = []
    for i, ax in enumerate(_axes(fig)):
        if ax.get_subplotspec() is None:
            continue
        try:
            bb = ax.get_tightbbox(renderer)
        except Exception:  # noqa: BLE001
            continue
        if bb is not None:
            boxes.append((i, bb))

    W, H = float(fig.bbox.width), float(fig.bbox.height)
    for a in range(len(boxes)):
        for b in range(a + 1, len(boxes)):
            ia, ba = boxes[a]
            ib, bb2 = boxes[b]
            # vertical gap only counts when the two panels overlap horizontally
            if min(ba.x1, bb2.x1) - max(ba.x0, bb2.x0) > 1:
                gap = max(ba.y0 - bb2.y1, bb2.y0 - ba.y1)
                if gap > max_frac * H:
                    out.append({"axes": [ia, ib], "direction": "vertical",
                                "gap_px": round(gap, 1),
                                "gap_pct": round(100 * gap / H, 1)})
            if min(ba.y1, bb2.y1) - max(ba.y0, bb2.y0) > 1:
                gap = max(ba.x0 - bb2.x1, bb2.x0 - ba.x1)
                if gap > max_frac * W:
                    out.append({"axes": [ia, ib], "direction": "horizontal",
                                "gap_px": round(gap, 1),
                                "gap_pct": round(100 * gap / W, 1)})
    return out


def tick_label_collisions(fig, renderer, tol: float = 1.0) -> list[dict]:
    """Adjacent tick labels whose bounding boxes touch.

    Panel-level bbox checks miss this: a panel can sit clear of its neighbours while its
    own x tick labels run into each other.
    """
    out = []
    for idx, ax in enumerate(_axes(fig)):
        if ax.get_subplotspec() is None or not ax.axison:
            continue
        for axis_name, labels in (("x", ax.get_xticklabels()), ("y", ax.get_yticklabels())):
            boxes = []
            for lab in labels:
                try:
                    if lab.get_visible() and (lab.get_text() or "").strip():
                        boxes.append((lab.get_text(), lab.get_window_extent(renderer)))
                except Exception:  # noqa: BLE001
                    continue
            if len(boxes) < 2:
                continue
            boxes.sort(key=lambda p: p[1].x0 if axis_name == "x" else p[1].y0)
            for (t1, b1), (t2, b2) in zip(boxes, boxes[1:]):
                gap = (b2.x0 - b1.x1) if axis_name == "x" else (b2.y0 - b1.y1)
                if gap < -tol:
                    out.append({"axes": idx, "axis": axis_name,
                                "labels": [t1[:12], t2[:12]],
                                "overlap_px": round(-gap, 1)})
    return out
