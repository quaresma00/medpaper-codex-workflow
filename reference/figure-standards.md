# Medical/SCI figure standards - synthesis

Loaded on demand by S11. The numbers here are what `tools/figures/style.py` encodes and
`tools/figures/qc.py` enforces, so change them here and there together.

Two kinds of source are mixed below and kept distinct on purpose:
**publisher requirements** (binding, verify against your target journal) and
**community tooling conventions** (useful defaults, not rules).

---

## 1. Publisher requirements

Always re-check the target journal at S20. These are the common denominators.

| Property | Requirement | Notes |
|---|---|---|
| Width, single column | 80-90 mm | Design at final size; never scale afterwards |
| Width, 1.5 column | ~140 mm | Not offered by every journal |
| Width, double column | 170-180 mm | 180 mm is the safe upper bound |
| Max height | ~230 mm | Must leave room for the legend on the page |
| Resolution, halftone/photo | >= 300 dpi | At final printed size |
| Resolution, combination art | >= 500-600 dpi | Line art plus photo in one figure |
| Resolution, pure line art | 600-1200 dpi | Vector is better than any raster here |
| Formats accepted | TIFF (LZW), EPS, PDF | Some accept high-res PNG for review only |
| Colour mode | RGB for online, CMYK if print-charged | Resolve at S20; CMYK conversion shifts colours |
| Minimum line width | >= 0.3 pt (0.1 mm) | Below this, lines drop out in print |
| Minimum font size | 6-8 pt at final size | 7 pt is a safe working default |
| Fonts | Arial / Helvetica / Times | Embed them; avoid exotic families |
| File naming | `Figure1.tiff`, one figure per file | Some portals reject anything else |

Sources: [Wiley figure preparation guidelines](http://authorservices.wiley.com/author-resources/Journal-Authors/Prepare/manuscript-preparation-guidelines.html/figure-preparation.html)
(80-180 mm width, 300-600 dpi, one file per figure);
[Springer submission guidelines](https://link.springer.com/journal/11673/submission-guidelines)
(minimum 0.1 mm / 0.3 pt line width, 1200 dpi for bitmap line drawings);
[IEEE graphics guidelines](https://www.scribd.com/document/536185333/eic-guide)
(300 dpi photos, 600 dpi line art, TIFF/EPS/PS/PDF);
[ASPET digital art guidelines](http://aspetjournals.org/sites/default/files/ASPET_Digital_Art_Guidelines.pdf)
and [the same publisher-standard art guide hosted by AAP](https://www.perio.org/wp-content/uploads/2019/08/Digital-Art-Guidelines.pdf)
(line art needs higher resolution than photographs);
[Nature artwork guidance](https://www.nature.com/npp/authors-and-referees/artwork-figures-tables)
(sequential numbering, legends on a separate page after the references, every figure cited in the text);
[Canadian Science Publishing figure preparation](https://cdnsciencepub.com/authors-and-reviewers/preparing-figures)
(brightness/contrast adjustments must be uniform across the whole image, never selective).
Content was rephrased for compliance with licensing restrictions.

### Image-integrity rules that get papers retracted
- Adjust brightness, contrast and colour balance **uniformly across the entire image**.
  Selective enhancement of one region is misconduct, not styling.
- Never clone, splice, or erase features. If lanes or fields are assembled from separate
  acquisitions, the join must be visible and stated in the legend.
- Keep the unprocessed original. Journals increasingly ask for it.

---

## 2. Community tooling - what exists and what to take from it

The GitHub landscape is mostly *matplotlib style sheets*, not medical-specific standards.
None of them encodes clinical-journal rules, so this pipeline uses its own style module
and borrows the conventions below.

| Project | What it is | What is worth taking |
|---|---|---|
| [SciencePlots](https://github.com/garrettj403/SciencePlots) and forks such as [SciencePlot-for-Publication](https://github.com/skydvn/SciencePlot-for-Publication) | The canonical `.mplstyle` collection for papers | Style-sheet approach; serif/sans variants per venue; IEEE-width preset |
| [tueplots](https://github.com/pnkraemer/tueplots) | Figure/font sizing helpers keyed to venues | Its core thesis: size the figure to the column and never rescale |
| [publication-plot-settings](https://github.com/md-arif-shaikh/publication-plot-settings) | Minimal rcParams for papers | Save at the final physical size so fonts stay correct |
| [cnsplots](https://github.com/faridrashidi/cnsplots) | Cell/Nature/Science-flavoured plotting | Keeping output editable in Illustrator (TrueType fonts) |
| [pubfig](https://github.com/Galaxy-Dawn/pubfig) | Panel-first assembly, common plot families | Panel-first composition; export clean panels then assemble |
| [ExtensysPlots](https://github.com/mcekwonu/ExtensysPlots) | Single style for papers/presentations | Separate presentation and print styles |
| [matplotlib_for_papers](https://github.com/jbmouret/matplotlib_for_papers) | Tutorial handout | Rationale for removing chartjunk; box-plot conventions |
| [AcademicForge scientific-visualization skill](https://github.com/HughYau/AcademicForge/blob/master/skills/scientific-visualization/SKILL.md) | Agent skill for journal-ready plots | Explicit colour-blind-safe palettes; PDF/EPS/TIFF export step |
| [academic-figure-skill](https://github.com/TingxiYu/academic-figure-skill) | Agent skill, data to journal-format output | Treating figure production as a pipeline with a format gate |

Verdict: adopt their conventions, not their code. A style sheet cannot enforce
"no explanatory text in the panel", cannot check effective dpi against the target column
width, and cannot verify that anyone looked at the result. That is what `qc.py` and the
S11 gate are for.

---

## 3. What this pipeline enforces

Encoded in `tools/figures/style.py`:
- Physical sizing from `WIDTHS_MM = {single: 90, 1.5: 140, double: 180}`; `savefig` writes
  the exact figsize (`pad_inches=0`) so the printed width is the designed width.
- 7 pt base font, 8 pt axis labels, 9 pt panel letters; 0.6 pt spines and ticks,
  1.0 pt data lines.
- Top and right spines off, ticks outward, no grid, legend without a frame.
- Okabe-Ito palette by default (`#0072B2 #D55E00 #009E73 #CC79A7 #E69F00 #56B4E9 #F0E442
  #000000`) - the only palette here distinguishable under all common colour-vision
  deficiencies and in greyscale. Journal house palettes are available via
  `apply_style(palette="nejm" | "lancet" | "jama" | "jco" | "nature")`; those contain
  red/green pairs, so `apply_style` warns and you must add a second visual channel
  (marker or line style).
- Grey (`#4D4D4D`) reserved for non-data elements only: reference lines, error bands,
  non-significant points. Never for text.
- `pdf.fonttype=42`, `ps.fonttype=42`, `svg.fonttype=none` so text stays editable;
  `axes.unicode_minus=False` so a negative sign never renders as a missing-glyph box.
- Vector PDF master plus PNG preview from one `save()` call. Export a LZW-compressed TIFF
  only if the chosen journal requires it; specify the journal's actual resolution.

Checked by `tools/figures/qc.py`:

| From the rendered PNG | From the live figure object |
|---|---|
| `effective_dpi` (pixel width / target column width) | `min_font_size`, `min_line_width` |
| `not_clipped`, `no_excess_whitespace` | `no_panel_overlap`, `no_text_clipped` |
| `margins_symmetric` | `no_missing_glyphs` (glyph warnings during rasterization) |
| `no_grey_footnote_text` | `no_tick_label_collision` (adjacent tick-label bboxes) |
| `publication_master` | `no_interior_void` (dead bands between panels) |
| | `bar_baseline_zero` |
| | `element:*` for the declared archetype |

The two halves catch different things. Pixel analysis sees whitespace and resolution;
artist introspection sees fonts, glyph coverage and which chart elements exist. Neither can
tell you whether the figure is readable - that still needs someone to open the PNG.

The glyph-warning capture and the tick-collision test are adapted from
[quaresma00/medical-sci-figure-skill](https://github.com/quaresma00/medical-sci-figure-skill)
(MIT), which credits scipilot-figure-skill for the originals.

---

## 4. Panel-first composition

A multi-panel figure is built as independent panels, then composed. Not as one shared
axes grid positioned by hand.

```python
fig, panels = figure(width="double", height_mm=80, panels=(1, 2))
(sfA, axA), (sfB, axB) = panels
```

`figure()` creates a constrained-layout figure, divides it with a gridspec, and puts a
`SubFigure` in each cell. Each SubFigure is its own layout domain, so a long tick label
can only compress its own panel. Contrast that with `add_axes` / `subplots_adjust` /
pixel coordinates, where a longer y-tick label silently pushes into the neighbouring
panel and every data change re-breaks the arrangement.

Rules that follow from this:
- Panel letters are drawn on the SubFigure at its top-left corner, offset inward by the
  layout pad - not inside the axes, where they collide with titles and y-labels.
- A panel title spanning the whole panel is `sf.suptitle(...)`, not `ax.set_title(loc="left")`.
  The latter starts after the y-axis decorations and overflows on long titles.
- A shared legend or caption strip gets its own axes-free SubFigure row, not a
  `bbox_to_anchor` legend dangling off one panel.
- Bitmap panels (histology, radiographs, schematics) go in their own SubFigure with
  `imshow` + `axis("off")` so their aspect ratio does not drag the neighbours around.
- To fix a layout problem, change the gridspec ratios, the panel spans, or the
  composition. Do not nudge individual label coordinates, and do not shrink fonts below
  the floor to make room.

## 5. Archetypes: the per-chart-type rules

Every figure in `artifact_plan.json` declares an `archetype`. The full registry lives in
`reference/archetypes.toml` - 18 chart types across five domains, each with the elements
that make that chart type complete.

This is not documentation. S11 reads the registry, detects which elements are actually
present in the rendered figure (`tools/figures/elements.py`), and fails the gate on a
missing mandatory element. "A Kaplan-Meier curve needs a number-at-risk table" is checked,
not merely advised.

| Domain | Archetypes |
|---|---|
| Group comparison | `bar_dot`, `box_jitter`, `violin_raincloud`, `paired_dotline` |
| Survival | `km_survival`, `longitudinal_trajectory` |
| Trials and evidence | `flow_diagram`, `forest_plot`, `roc_curve`, `nomogram_calibration`, `bland_altman` |
| Omics | `volcano_plot`, `clustered_heatmap`, `dimension_reduction`, `enrichment_bubble`, `manhattan_plot` |
| Blots and imaging | `western_blot`, `histopathology` |
| Fallback | `other` (requires an `archetype_rationale`) |

Each entry declares `requires` (detected; a miss fails the gate), `advisory` (reported for
you to confirm by eye), and `notes`. Read the entry for your chart type before writing the
script - it is shorter than this file and more specific.

The rules that recur across archetypes:

- **Bar baselines start at zero.** Detected and enforced. For a box or dot plot of a
  physical quantity a non-zero baseline is defensible, but make it deliberate.
- **Show the individual points** when n < 10, and preferably when n < 30. A bar with an
  error bar and no points is a dynamite plot; reviewers ask for the data.
- **Never a box plot at n <= 5.** Quartiles of five observations are noise.
- **Error bars must be labelled** as SD, SE or 95% CI in the legend. Unlabelled error bars
  cannot be interpreted, and the three differ by more than a factor of two.
- **Ratio measures get a log axis** and a null line at 1.0.
- **A physical scale bar, not a magnification.** "400x" in the caption is meaningless once
  the figure is resized; the bar scales with the image.

Recipes for the archetypes with the strictest requirements are in `tools/figures/recipes.py`
(`km_survival`, `forest_plot`, `roc_curve`, `volcano_plot`). They are built so the mandatory
elements are present by construction, they take statistics as numbers rather than as display
strings, and Kaplan-Meier goes through `lifelines` rather than a hand-rolled estimator.

The archetype taxonomy and its mandatory-element lists are adapted from
[quaresma00/medical-sci-figure-skill](https://github.com/quaresma00/medical-sci-figure-skill)
(MIT), which synthesises SciencePlots, ggsci and ggprism conventions. The element lists here
were reduced to what is mechanically verifiable, and the detectors are original.
Content was rephrased for compliance with licensing restrictions.

## 6. Text in panels - the line

**In the panel** (structural, needed to read the plot): axis titles and units, tick labels,
panel letters, group and category labels, legend entries, significance markers, key data
values (n, HR with CI, AUC, r), and guideline-mandated content such as Kaplan-Meier risk
tables, CONSORT/PRISMA/STARD box text, scale bars and axis-break marks.

**In the legend** (only what decodes the figure): a concise descriptive title, panel
descriptions, essential statistical/error-bar/threshold definitions, what a reference line
or symbol means, and a short abbreviation clause when needed. Full adjustment sets, cohort provenance,
software versions, interpretation, result direction, repeated numerical results and general caveats belong in
Methods, supplementary Methods or the main Results/Discussion. A legend is not a second
Methods section; target 40-140 words and keep it below 180 words unless the selected journal
explicitly requires otherwise.

When more than eight defined abbreviations accumulate across figures and tables, or a local
list exceeds 50 words or dominates its legend, define
them once under `Declarations and Statements > Abbreviations` and remove repeated local
definition blocks. Retain local definitions only when the chosen journal's official guide
explicitly requires them. Apply this at S17 before independent and user review. Thresholds
are workflow defaults; medical clarity remains the criterion. Never use the literal down-arrow
character as shorthand.

Test: delete the text. If it is still needed to decode an axis, group or symbol, retain it
locally. Otherwise route methods detail to Methods, findings to Results and interpretation
to Discussion; do not move every removed panel sentence into the legend.

All panel text is black or near-black (`#000000`-`#1a1a1a`) at or above the size floor.
Greying text down is not a way to keep explanation in the figure. Every removal is logged
to `05_figures/moved_to_legend.md` with its actual destination and reconciled in the same edit.
