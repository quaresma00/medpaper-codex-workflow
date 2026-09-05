"""Chart recipes for the archetypes that have hard mandatory elements.

Two rules distinguish these from a generic plotting helper:

1. **Estimators come from established libraries.** Kaplan-Meier goes through lifelines,
   which gives the confidence band, the median survival and the log-rank test that the
   km_survival archetype demands. Hand-rolling a product-limit estimator for a clinical
   figure is not worth the risk, even when the arithmetic happens to be right.
2. **Statistics are passed as values, not as display strings.** Every recipe takes numbers
   and formats them itself. A `hr_text="HR 1.87"` parameter would let a hand-typed number
   onto a figure, which is exactly what the numeric-provenance gate exists to prevent.
   Read the values out of 03_analysis/results/*.json and pass them in.

Each recipe returns (fig, panels) and is built so the archetype's `requires` elements are
present by construction.
"""
from __future__ import annotations

import matplotlib
import numpy as np
from matplotlib.ticker import ScalarFormatter

from .style import GREY, LIGHT_GREY, figure, significance  # noqa: F401


def _fmt_p(p: float) -> str:
    if p is None:
        return ""
    return "P < 0.001" if p < 0.001 else (f"P = {p:.3f}" if p < 0.01 else f"P = {p:.2f}")


def _fmt_ci(est, lo, hi, dp=2) -> str:
    return f"{est:.{dp}f} ({lo:.{dp}f}\u2013{hi:.{dp}f})"


# ---------------------------------------------------------------------------
def km_survival(groups, time_points=None, width="single", height_mm=95.0,
                risk_table_frac=None, ylabel="Overall survival", xlabel="Time (months)",
                hr=None, hr_ci=None, logrank_p=None, show_ci=True, show_median=True,
                colors=None, min_at_risk=10):
    """Kaplan-Meier curves with a number-at-risk table, via lifelines.

    groups: [{"name": str, "time": array, "event": array(0/1)}, ...]
    hr, hr_ci, logrank_p: values from your results JSON. If logrank_p is omitted and
        exactly two groups are given, it is computed here from the data.
    min_at_risk: truncate the x axis once any group's risk set falls below this. Set to 0
        to draw the full follow-up, but a curve past that point is not interpretable and
        the tail will swing to 0 on a single event.

    Satisfies km_survival's mandatory elements: step curves, censoring marks, risk table,
    legend and in-figure statistics. Also draws the CI band and reports median survival
    with its CI, which the archetype lists as expected.
    """
    try:
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "lifelines is required for the km_survival recipe.\n"
            "  uv pip install --python .venv/Scripts/python.exe lifelines"
        ) from exc

    if len(groups) < 1:
        raise ValueError("km_survival needs at least one group")

    if risk_table_frac is None:
        # Size the table panel to its contents rather than a fixed fraction. A panel
        # taller than its rows leaves dead space below the last row, which shows up as
        # an asymmetric bottom margin in QC.
        row_mm = 1.55 * matplotlib.rcParams["font.size"] / 72.0 * 25.4
        needed_mm = 1.4 * row_mm + len(groups) * row_mm
        risk_table_frac = min(0.45, max(0.10, needed_mm / height_mm))

    # One SubFigure holding two axes that SHARE the x axis. Two sibling SubFigures would
    # each solve their own layout, so their axes could not be guaranteed to line up - and a
    # number-at-risk table that is not column-aligned with the curve is worse than none.
    fig, panels = figure(width=width, height_mm=height_mm, panels=(1, 1), letters=False)
    sf_km, _placeholder = panels[0]
    _placeholder.remove()
    ax, ax_tab = sf_km.subplots(
        2, 1, sharex=True,
        # hspace is a fraction of the mean axes height, so a value tuned for equal-sized
        # panels becomes a large void here. 0.10 leaves room for the table header and
        # nothing more; the layout engine floors the gap at roughly 0.03 anyway.
        gridspec_kw={"height_ratios": [1 - risk_table_frac, risk_table_frac], "hspace": 0.10},
    )
    palette = colors or [f"C{i}" for i in range(len(groups))]

    fitted = []
    for i, grp in enumerate(groups):
        t = np.asarray(grp["time"], float)
        e = np.asarray(grp["event"], int)
        kmf = KaplanMeierFitter(label=grp["name"]).fit(t, e)
        fitted.append((grp, kmf))
        c = palette[i % len(palette)]

        sf_vals = kmf.survival_function_
        xs = np.asarray(sf_vals.index, float)
        ys = np.asarray(sf_vals.iloc[:, 0], float)
        ax.step(xs, ys, where="post", color=c, lw=1.1, label=grp["name"])

        if show_ci:
            ci = kmf.confidence_interval_
            ax.fill_between(np.asarray(ci.index, float),
                            np.asarray(ci.iloc[:, 0], float),
                            np.asarray(ci.iloc[:, 1], float),
                            step="post", color=c, alpha=0.13, lw=0)

        # censoring ticks: mandatory for this archetype
        cens_t = t[e == 0]
        if len(cens_t):
            cens_s = np.asarray([float(kmf.predict(x)) for x in cens_t], float)
            ax.plot(cens_t, cens_s, linestyle="None", marker="|", markersize=3.2,
                    markeredgewidth=0.7, color=c)

    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    ax.set_ylim(0, 1.02)
    ax.set_xlim(left=0)
    ax.legend(loc="lower left")

    if logrank_p is None and len(groups) == 2:
        a, b = groups
        logrank_p = float(logrank_test(np.asarray(a["time"], float), np.asarray(b["time"], float),
                                       np.asarray(a["event"], int), np.asarray(b["event"], int)
                                       ).p_value)
    lines = []
    if hr is not None and hr_ci is not None:
        lines.append(f"HR {_fmt_ci(hr, hr_ci[0], hr_ci[1])}")
    if logrank_p is not None:
        lines.append(f"{_fmt_p(logrank_p)}, log-rank")
    if show_median:
        for grp, kmf in fitted:
            med = kmf.median_survival_time_
            if np.isfinite(med):
                try:
                    from lifelines.utils import median_survival_times
                    ci = median_survival_times(kmf.confidence_interval_)
                    lo, hi = float(ci.iloc[0, 0]), float(ci.iloc[0, 1])
                    lines.append(f"{grp['name']}: median {med:.1f} ({lo:.1f}\u2013{hi:.1f})")
                except Exception:  # noqa: BLE001
                    lines.append(f"{grp['name']}: median {med:.1f}")
            else:
                lines.append(f"{grp['name']}: median not reached")
    if lines:
        ax.text(0.97, 0.97, "\n".join(lines), transform=ax.transAxes,
                ha="right", va="top", color="black", linespacing=1.45)

    # ---- number at risk ----
    tp = list(time_points) if time_points is not None else list(ax.get_xticks())
    tp = [x for x in tp if x >= 0]

    # Truncate where the risk set is too small to interpret, which the archetype asks for.
    if min_at_risk:
        all_t = np.concatenate([np.asarray(g["time"], float) for g in groups])
        keep = [x for x in tp if min(int(np.sum(np.asarray(g["time"], float) >= x))
                                    for g in groups) >= min_at_risk]
        cutoff = max(keep) if keep else float(all_t.max())
        ax.set_xlim(0, cutoff)
        tp = [x for x in tp if x <= cutoff]

    ax_tab.set_ylim(len(groups) - 0.5, -0.5)
    for s in ax_tab.spines.values():
        s.set_visible(False)
    ax_tab.tick_params(axis="x", length=0)
    ax_tab.tick_params(axis="y", length=0)
    ax_tab.set_ylabel("")
    # x labels belong to the table (the bottom axes); the curve above shares the scale.
    ax.tick_params(axis="x", labelbottom=False)
    ax.set_xlabel("")
    ax_tab.set_xlabel(xlabel)

    # Group names as y tick labels, not hand-placed text. Constrained layout then reserves
    # room for them, so they cannot run into the count at t=0.
    ax_tab.set_yticks(range(len(fitted)))
    ax_tab.set_yticklabels([g["name"] for g, _ in fitted])
    for lab, (_, _) in zip(ax_tab.get_yticklabels(), fitted):
        lab.set_fontweight("bold")
    for lab, c in zip(ax_tab.get_yticklabels(),
                      [palette[i % len(palette)] for i in range(len(fitted))]):
        lab.set_color(c)

    ax_tab.set_title("Number at risk", loc="left", fontweight="bold", color="black", pad=3)
    lo_x, hi_x = ax.get_xlim()
    for i, (grp, _) in enumerate(fitted):
        t = np.asarray(grp["time"], float)
        for x in tp:
            # Centre-align except at the axis ends, where half the number would spill into
            # the row label on the left or past the frame on the right.
            ha = "left" if abs(x - lo_x) < 1e-9 else ("right" if abs(x - hi_x) < 1e-9 else "center")
            ax_tab.text(x, i, str(int(np.sum(t >= x))), ha=ha, va="center", color="black")
    ax_tab.set_xticks(tp)
    return fig, (ax, ax_tab)


# ---------------------------------------------------------------------------
def forest_plot(rows, width="double", height_mm=None, null_value=1.0, log_x=True,
                effect_label="Hazard ratio (95% CI)", left_label="Favours treatment",
                right_label="Favours control", summary=None, heterogeneity=None):
    """Forest plot for subgroups or a meta-analysis.

    rows: [{"label": str, "estimate": float, "ci": (lo, hi), "n": int|None,
            "p_interaction": float|None, "weight": float|None}, ...]
    summary: {"estimate": float, "ci": (lo, hi)} draws the pooled diamond.
    heterogeneity: {"i2": float, "p": float} printed under the summary.

    Satisfies forest_plot's mandatory elements: null line, error bars, in-figure statistics.
    """
    n = len(rows) + (1 if summary else 0)
    height_mm = height_mm or max(45.0, 8.0 * n + 24.0)
    fig, panels = figure(width=width, height_mm=height_mm, panels=(1, 1), letters=False)
    _, ax = panels[0]

    ys = list(range(len(rows)))[::-1]
    weights = [r.get("weight") for r in rows]
    wmax = max([w for w in weights if w] or [1.0])

    for y, r in zip(ys, rows):
        lo, hi = r["ci"]
        est = r["estimate"]
        size = 16.0 if not r.get("weight") else 8.0 + 34.0 * (r["weight"] / wmax)
        # errorbar rather than three plot() calls: it is the semantic artist for an
        # interval, so the CI is machine-detectable rather than three anonymous lines.
        ax.errorbar(est, y, xerr=[[est - lo], [hi - est]], fmt="s", markersize=np.sqrt(size),
                    color="C0", ecolor="black", elinewidth=0.7, capsize=2.0,
                    capthick=0.7, zorder=3)

    if summary:
        lo, hi = summary["ci"]
        est = summary["estimate"]
        y = -1
        ax.fill([lo, est, hi, est], [y, y + 0.16, y, y - 0.16],
                color="C1", zorder=3, lw=0.5, edgecolor="black")
        ys = ys + [y]
        rows = rows + [{"label": summary.get("label", "Overall"), "estimate": est, "ci": (lo, hi)}]

    ax.axvline(null_value, color=GREY, lw=0.6, ls="--", zorder=1)

    lows = [r["ci"][0] for r in rows]
    highs = [r["ci"][1] for r in rows]
    if log_x:
        ax.set_xscale("log")
        # Default log ticks render as 10^0 / 2x10^0, which no clinician reads. Force plain
        # numbers at the decade and minor positions.
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.xaxis.set_minor_formatter(ScalarFormatter())
        ax.ticklabel_format(axis="x", style="plain")
        span = max(highs) / min(min(lows), null_value)
        ax.set_xlim(min(min(lows), null_value) / span ** 0.18,
                    max(highs) * span ** 0.10)
    else:
        pad = 0.12 * (max(highs) - min(min(lows), null_value))
        ax.set_xlim(min(min(lows), null_value) - pad, max(highs) + pad)

    ax.set_yticks(ys)
    ax.set_yticklabels([r["label"] for r in rows])
    ax.set_ylim(min(ys) - 0.8, max(ys) + 0.8)
    ax.set_xlabel(effect_label)
    ax.set_ylabel("Subgroup")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    # Direction labels at the axes corners, not both hung off the null line, where they
    # collide whenever the null sits near an edge.
    for frac, txt, ha in ((0.0, f"\u2190 {left_label}", "left"),
                          (1.0, f"{right_label} \u2192", "right")):
        ax.annotate(txt, xy=(frac, 0), xycoords="axes fraction",
                    xytext=(0, -26), textcoords="offset points",
                    ha=ha, va="top", color="black", annotation_clip=False)

    trans = ax.get_yaxis_transform()
    for y, r in zip(ys, rows):
        lo, hi = r["ci"]
        parts = [_fmt_ci(r["estimate"], lo, hi)]
        if r.get("n"):
            parts.insert(0, f"n={r['n']}")
        if r.get("p_interaction") is not None:
            parts.append(_fmt_p(r["p_interaction"]) + " (interaction)")
        ax.text(1.02, y, "   ".join(parts), transform=trans, ha="left", va="center", color="black")
    if heterogeneity:
        ax.text(1.02, min(ys) - 0.6, f"I\u00b2 = {heterogeneity['i2']:.0f}%, "
                                     f"{_fmt_p(heterogeneity.get('p'))}",
                transform=trans, ha="left", va="center", color="black")
    return fig, ax


# ---------------------------------------------------------------------------
def roc_curve(curves, width="single", height_mm=None, diagonal=True,
              xlabel="1 - specificity", ylabel="Sensitivity", operating_points=None):
    """ROC curve(s) with the chance diagonal and AUC with CI in the legend.

    curves: [{"name": str, "fpr": array, "tpr": array, "auc": float,
              "auc_ci": (lo, hi)|None}, ...]
    operating_points: [{"fpr": float, "tpr": float, "label": str}, ...]

    Satisfies roc_curve's mandatory elements: reference diagonal, legend, in-figure
    statistics, equal axis spans.
    """
    fig, panels = figure(width=width, height_mm=height_mm or 90.0, panels=(1, 1), letters=False)
    _, ax = panels[0]
    if diagonal:
        ax.plot([0, 1], [0, 1], ls="--", lw=0.6, color=GREY, zorder=1)
    for c in curves:
        label = c["name"]
        if c.get("auc") is not None:
            ci = c.get("auc_ci")
            label += (f" (AUC {c['auc']:.3f}, 95% CI {ci[0]:.3f}\u2013{ci[1]:.3f})"
                      if ci else f" (AUC {c['auc']:.3f})")
        ax.plot(np.asarray(c["fpr"], float), np.asarray(c["tpr"], float), lw=1.1, label=label)
    for op in operating_points or []:
        ax.scatter([op["fpr"]], [op["tpr"]], s=18, zorder=4, color="black")
        ax.annotate(op.get("label", ""), xy=(op["fpr"], op["tpr"]),
                    xytext=(6, -8), textcoords="offset points", color="black")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc="lower right")
    return fig, ax


# ---------------------------------------------------------------------------
def volcano_plot(log2fc, neg_log10_p, labels=None, width="single", height_mm=None,
                 fc_cutoff=1.0, p_cutoff=0.05, adjusted=True, annotate=None,
                 up_color="C1", down_color="C0", ns_color=LIGHT_GREY):
    """Volcano plot with both cutoffs drawn and repelled gene labels.

    Satisfies volcano_plot's mandatory elements: threshold lines, individual points.
    `annotate` is a list of label strings to mark; adjustText is used if available.
    """
    fig, panels = figure(width=width, height_mm=height_mm or 90.0, panels=(1, 1), letters=False)
    _, ax = panels[0]
    x = np.asarray(log2fc, float)
    y = np.asarray(neg_log10_p, float)
    thr = -np.log10(p_cutoff)

    sig_up = (x >= fc_cutoff) & (y >= thr)
    sig_dn = (x <= -fc_cutoff) & (y >= thr)
    ns = ~(sig_up | sig_dn)
    ax.scatter(x[ns], y[ns], s=3, color=ns_color, alpha=0.6, lw=0, rasterized=True)
    ax.scatter(x[sig_dn], y[sig_dn], s=5, color=down_color, alpha=0.85, lw=0, rasterized=True)
    ax.scatter(x[sig_up], y[sig_up], s=5, color=up_color, alpha=0.85, lw=0, rasterized=True)

    ax.axhline(thr, ls="--", lw=0.6, color=GREY)
    ax.axvline(fc_cutoff, ls="--", lw=0.6, color=GREY)
    ax.axvline(-fc_cutoff, ls="--", lw=0.6, color=GREY)

    ax.set_xlabel("log\u2082 fold change")
    ax.set_ylabel(("-log\u2081\u2080 adjusted " if adjusted else "-log\u2081\u2080 ") + "P")

    if annotate and labels is not None:
        labels = list(labels)
        idx = [labels.index(a) for a in annotate if a in labels]
        texts = [ax.text(x[i], y[i], labels[i], color="black") for i in idx]
        try:
            from adjustText import adjust_text
            adjust_text(texts, ax=ax,
                        arrowprops=dict(arrowstyle="-", color=GREY, lw=0.4))
        except ImportError:
            print("  note: adjustText not installed; gene labels may overlap. "
                  "uv pip install adjustText")
    return fig, ax
