"""Journal-grade matplotlib defaults and a panel-first figure builder.

Two things matter here.

1. Physical sizing. Figures are built at the width they will be printed at, so the
   font sizes in the file are the font sizes on the page. Never scale a figure
   afterwards.
2. Panel-first composition. Each panel is a SubFigure that owns its own axes,
   ticks, labels, legend and colorbar. A SubFigure's constrained-layout solver only
   redistributes space inside its own rectangle, so a long tick label can never push
   into a sibling panel. Hand-placed axes cannot give that guarantee.

See reference/figure-standards.md for the numbers and their sources.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.transforms import ScaledTranslation

MM = 1.0 / 25.4
# Outer layout pad, inches. savefig writes the exact figsize (pad_inches=0), so this
# pad is literally the printed white margin. ~1.3 mm keeps the outermost tick label
# off the canvas edge without wasting column width.
PANEL_PAD_IN = 0.05

# Publisher column widths (mm). Wiley: 80-180mm. Most publishers: ~90 / ~180.
WIDTHS_MM = {"single": 90.0, "1.5": 140.0, "double": 180.0}

# Okabe-Ito: distinguishable under all common colour-vision deficiencies and in greyscale.
# This stays the default because it is the only palette here with that guarantee.
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7",
           "#E69F00", "#56B4E9", "#F0E442", "#000000"]

# Journal house palettes, values as published in ggsci (Nan Xiao, GPL-3 package;
# the colour values themselves are the journals' own brand colours).
# Use one when a reviewer or an editor expects the journal's look. None of them is
# fully colour-blind safe, so keep a second visual channel: marker or line style.
PALETTE_NEJM = ["#BC3C29", "#0072B5", "#E18727", "#20854E",
                "#7876B1", "#6F99AD", "#FFDC91", "#EE4C97"]
PALETTE_LANCET = ["#00468B", "#ED0000", "#42B540", "#0099B4",
                  "#925E9F", "#FDAF91", "#AD002A", "#ADB6B6"]
PALETTE_JAMA = ["#374E55", "#DF8F44", "#00A1D5", "#B24745",
                "#79AF97", "#6A6599", "#80796B"]
PALETTE_JCO = ["#0073C2", "#EFC000", "#868686", "#CD534C", "#7AA6DC", "#003C67"]
PALETTE_NATURE = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488",
                  "#F39B7F", "#8491B4", "#91D1C2", "#DC0000"]

PALETTES = {
    "okabe_ito": PALETTE,
    "nejm": PALETTE_NEJM,
    "lancet": PALETTE_LANCET,
    "jama": PALETTE_JAMA,
    "jco": PALETTE_JCO,
    "nature": PALETTE_NATURE,
}
# Red/green pairs are unreadable for the ~8% of men with deuteranopia.
RISKY_PAIRS = {"nejm", "lancet", "nature"}

GREY = "#4D4D4D"          # non-data elements only: reference lines, error bands
LIGHT_GREY = "#BFBFBF"

FONT_STACK = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]


def apply_style(base_pt: float = 7.0, palette: str = "okabe_ito") -> list[str]:
    """Call once at the top of every plotting script.

    `palette`: okabe_ito (default, colour-blind safe) | nejm | lancet | jama | jco | nature.
    Returns the colour list so a script can index it directly.
    """
    if palette not in PALETTES:
        raise ValueError(f"palette must be one of {sorted(PALETTES)}, got {palette!r}")
    colors = PALETTES[palette]
    if palette in RISKY_PAIRS:
        print(f"  note: the {palette} palette contains a red/green pair. Dual-encode with "
              f"marker or line style so the figure survives colour-blind readers and "
              f"greyscale printing.")
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FONT_STACK,
        "font.size": base_pt,
        "axes.labelsize": base_pt + 1,
        "axes.titlesize": base_pt + 1,
        "xtick.labelsize": base_pt,
        "ytick.labelsize": base_pt,
        "legend.fontsize": base_pt,
        "figure.titlesize": base_pt + 2,

        "axes.linewidth": 0.6,
        "lines.linewidth": 1.0,
        "lines.markersize": 3.0,
        "patch.linewidth": 0.6,
        "grid.linewidth": 0.4,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.minor.width": 0.4,
        "ytick.minor.width": 0.4,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.direction": "out",
        "ytick.direction": "out",

        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.axisbelow": True,
        "axes.prop_cycle": matplotlib.cycler(color=colors),
        # Use the ASCII hyphen-minus for negative numbers. The typographic Unicode
        # minus is absent from some font builds and renders as a tofu box.
        "axes.unicode_minus": False,

        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.columnspacing": 1.0,
        "legend.borderaxespad": 0.3,

        "figure.dpi": 150,
        "savefig.dpi": 600,
        "savefig.bbox": None,        # constrained layout already handles it; bbox_inches
        "savefig.pad_inches": 0.0,   # would silently change the physical width
        "savefig.transparent": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",

        # Keep text as text so an editor can fix a typo in Illustrator.
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "mathtext.fontset": "stixsans",   # match the sans body text
    })
    return colors


def size_mm(width: str = "single", height_mm: float | None = None) -> tuple[float, float]:
    if width not in WIDTHS_MM:
        raise ValueError(f"width must be one of {list(WIDTHS_MM)}, got {width!r}")
    w = WIDTHS_MM[width]
    return w, height_mm if height_mm else w * 0.72


def figure(width: str = "single", height_mm: float | None = None,
           panels: tuple[int, int] = (1, 1), width_ratios=None, height_ratios=None,
           letters: bool = True, letter_pt: float = 9.0):
    """Panel-first figure.

    Returns (fig, panels) where `panels` is a list of (subfigure, axes) in row-major
    order. Each subfigure is an independent layout domain - put that panel's axes,
    labels, legend and colorbar inside it and nothing can leak into a neighbour.

        fig, panels = figure(width="double", height_mm=80, panels=(1, 2))
        (sfA, axA), (sfB, axB) = panels
        axA.plot(...)
        sfA.suptitle("Discrimination")      # centred over panel A only
    """
    w_mm, h_mm = size_mm(width, height_mm)
    fig = plt.figure(figsize=(w_mm * MM, h_mm * MM), layout="constrained")
    fig.get_layout_engine().set(w_pad=PANEL_PAD_IN, h_pad=PANEL_PAD_IN, wspace=0.04, hspace=0.04)

    nrows, ncols = panels
    gs = fig.add_gridspec(nrows, ncols, width_ratios=width_ratios, height_ratios=height_ratios)

    out = []
    idx = 0
    for r in range(nrows):
        for c in range(ncols):
            sf = fig.add_subfigure(gs[r, c])
            ax = sf.subplots()
            if letters and nrows * ncols > 1:
                label_panel(sf, chr(ord("A") + idx), letter_pt)
            out.append((sf, ax))
            idx += 1
    return fig, out


def subpanels(sf, panels: tuple[int, int] = (1, 1), **kw):
    """Split one panel into sub-axes that still share only that panel's rectangle."""
    return sf.subplots(*panels, **kw)


def label_panel(sf, letter: str, pt: float = 9.0, pad_in: float = PANEL_PAD_IN) -> None:
    """Panel letter at the top-left of the panel's own rectangle.

    Drawn on the SubFigure rather than inside the axes, so it cannot collide with the
    axis title or the y-axis label. Offset inward by exactly the layout pad, in inches:
    SubFigure.text is not part of the constrained-layout solve, so without the offset the
    letter lands on the canvas edge and makes the printed margins uneven.
    """
    trans = sf.transSubfigure + ScaledTranslation(pad_in, -pad_in, sf.dpi_scale_trans)
    sf.text(0.0, 1.0, letter, transform=trans, fontsize=pt, fontweight="bold",
            va="top", ha="left", color="black")


def significance(ax, x1: float, x2: float, y: float, text: str = "*",
                 tick: float | None = None, pt: float | None = None) -> None:
    """Significance bracket above the data, with headroom reserved for the marker.

    Extends the y-limit so the bracket and its asterisks cannot crowd the panel title.
    `tick` defaults to 2% of the current y-range.
    """
    lo, hi = ax.get_ylim()
    span = (hi - lo) or 1.0
    t = tick if tick is not None else 0.02 * span
    ax.plot([x1, x1, x2, x2], [y, y + t, y + t, y], lw=0.6, c="black",
            clip_on=False, solid_capstyle="butt")
    ax.text((x1 + x2) / 2, y + t, text, ha="center", va="bottom",
            fontsize=pt or matplotlib.rcParams["font.size"], color="black")
    ax.set_ylim(lo, max(hi, y + t + 0.09 * span))


def save(fig, stem: str | Path, width: str = "single", dpi: int = 600,
         tiff: bool = True, audit: bool = True, archetype: str | None = None) -> dict:
    """Write the PNG preview and the TIFF print master, then audit the artists.

    `stem` has no extension: save(fig, "project/05_figures/out/Figure1").
    `archetype` is recorded in the sidecar so qc.py can check the archetype's mandatory
    elements; if omitted it is read from artifact_plan.json by qc.py instead.
    """
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    written = {}

    png = stem.with_suffix(".png")
    fig.savefig(png, dpi=dpi, format="png")
    written["png"] = str(png)

    if tiff:
        try:
            tif = stem.with_suffix(".tiff")
            fig.savefig(tif, dpi=dpi, format="tiff", pil_kwargs={"compression": "tiff_lzw"})
            written["tiff"] = str(tif)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! TIFF master not written ({exc}). Pillow is required for TIFF output.")

    w_in, h_in = fig.get_size_inches()
    written.update({
        "width_class": width,
        "size_mm": [round(w_in / MM, 2), round(h_in / MM, 2)],
        "dpi": dpi,
        "pixels": [int(round(w_in * dpi)), int(round(h_in * dpi))],
    })
    print(f"wrote {png.name}"
          + (f" + {Path(written['tiff']).name}" if "tiff" in written else "")
          + f"  {written['size_mm'][0]}x{written['size_mm'][1]} mm @ {dpi} dpi")

    if audit:
        written["artist_audit"] = audit_figure(fig, stem, archetype=archetype)
    return written


# ---------------------------------------------------------------------------
# artist-level audit: things only the live figure object knows
# ---------------------------------------------------------------------------
def audit_figure(fig, stem: str | Path, archetype: str | None = None) -> str:
    """Everything only the live figure object knows; written to a sidecar JSON.

    Font sizes, line widths, panel overlap, clipping, missing glyphs, tick-label
    collisions, and which archetype elements are present. Called automatically by save();
    qc.py merges these sidecars into qc_report.json, which the S11 gate reads.
    """
    from . import elements as el

    stem = Path(stem)
    glyphs = el.glyph_warnings(fig)          # this performs the draw pass
    renderer = fig.canvas.get_renderer()
    phantom = _phantom_tick_labels(fig)

    def real_texts():
        for t in fig.findobj(match=matplotlib.text.Text):
            if id(t) in phantom or not t.get_visible():
                continue
            if (t.get_text() or "").strip():
                yield t

    fonts, widths = [], []
    for t in real_texts():
        fonts.append(round(float(t.get_fontsize()), 2))
    for ln in fig.findobj(match=matplotlib.lines.Line2D):
        if ln.get_visible() and ln.get_linestyle() not in ("None", "none", ""):
            widths.append(round(float(ln.get_linewidth()), 3))
    for sp in fig.findobj(match=matplotlib.spines.Spine):
        if sp.get_visible():
            widths.append(round(float(sp.get_linewidth()), 3))

    fig_bbox = fig.bbox
    clipped = []
    for t in real_texts():
        try:
            bb = t.get_window_extent(renderer)
        except Exception:  # noqa: BLE001
            continue
        if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fig_bbox.width + 1 or bb.y1 > fig_bbox.height + 1:
            clipped.append({"text": t.get_text()[:40],
                            "bbox": [round(v, 1) for v in (bb.x0, bb.y0, bb.x1, bb.y1)]})

    boxes = []
    for i, ax in enumerate(fig.get_axes()):
        try:
            bb = ax.get_tightbbox(renderer)
        except Exception:  # noqa: BLE001
            continue
        if bb is not None:
            boxes.append((i, bb))
    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            dx = min(a.x1, b.x1) - max(a.x0, b.x0)
            dy = min(a.y1, b.y1) - max(a.y0, b.y0)
            if dx > 1.0 and dy > 1.0:
                overlaps.append({"axes": [boxes[i][0], boxes[j][0]],
                                 "overlap_px": round(dx * dy, 1)})

    report = {
        "figure": stem.name,
        "archetype": archetype,
        "n_axes": len(fig.get_axes()),
        "min_font_pt": min(fonts) if fonts else None,
        "max_font_pt": max(fonts) if fonts else None,
        "min_line_pt": min(widths) if widths else None,
        "text_clipped_at_edge": clipped,
        "axes_tightbbox_overlaps": overlaps,
        "glyph_warnings": glyphs,
        "tick_label_collisions": el.tick_label_collisions(fig, renderer),
        "interior_voids": el.interior_voids(fig, renderer),
        "elements": el.detect_all(fig),
        "figure_text": sorted({(t.get_text() or "").strip() for t in real_texts()
                               if (t.get_text() or "").strip()}),
    }
    out = stem.parent.parent / "qc" / f"{stem.name}.artist.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if overlaps:
        print(f"  ! {len(overlaps)} panel bounding-box overlap(s) - fix the layout, not the labels")
    if clipped:
        print(f"  ! {len(clipped)} text element(s) clipped at the figure edge")
    if glyphs:
        print(f"  ! {len(glyphs)} missing-glyph warning(s) - a character has no glyph in this "
              f"font and will print as a box")
    if report["tick_label_collisions"]:
        print(f"  ! {len(report['tick_label_collisions'])} tick-label collision(s) - rotate the "
              f"labels or reduce the tick count")
    return str(out)


def _phantom_tick_labels(fig) -> set[int]:
    """Tick labels for ticks outside the current view limits.

    Matplotlib keeps these artists alive and reports a window extent for them even
    though nothing is drawn, which otherwise shows up as a false 'clipped text' report.
    """
    skip: set[int] = set()
    for ax in fig.get_axes():
        for axis, lim in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
            lo, hi = sorted(lim)
            span = (hi - lo) or 1.0
            for tick in list(axis.get_major_ticks()) + list(axis.get_minor_ticks()):
                loc = tick.get_loc()
                if loc is None or not (lo - 1e-9 * span <= loc <= hi + 1e-9 * span):
                    for lbl in (tick.label1, tick.label2):
                        if lbl is not None:
                            skip.add(id(lbl))
    return skip
