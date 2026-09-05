# S11 - Render figures, then actually look at them

## Purpose
Produce journal-grade figures. This stage has a mandatory two-phase verification:
deterministic QC by code, then visual inspection of the rendered PNG. Reading the
plotting code is not verification.

Read `reference/figure-standards.md` before writing the first script, and read your
figure's entry in `reference/archetypes.toml` - that entry lists the elements the gate will
look for in the rendered figure.

## Procedure
1. **Check for a recipe first.** `tools/figures/recipes.py` covers the archetypes with the
   strictest requirements and satisfies them by construction:
```python
import sys; sys.path.insert(0, "tools")
from figures.style import apply_style, save
from figures.recipes import km_survival, forest_plot, roc_curve, volcano_plot

apply_style()                      # add palette="nejm" if the journal expects its house colours
fig, _ = km_survival(groups, time_points=[0, 12, 24, 36],
                     hr=1.87, hr_ci=[1.34, 2.61])   # values read from results JSON
save(fig, "project/05_figures/out/Figure1", width="single", archetype="km_survival")
```
   Recipes take statistics as **numbers, not display strings**, so read them out of
   `03_analysis/results/*.json`. Never pass a pre-formatted `"HR 1.87"` - that is how a
   hand-typed number reaches a figure.

2. For anything without a recipe, one script per figure under `project/05_figures/code/`,
   named after the plan's `script` field, starting from the shared style:
```python
from figures.style import apply_style, figure, save

apply_style()                      # journal rcParams: fonts, line widths, no top/right spines
fig, panels = figure(width="double", height_mm=90, panels=(1, 2))   # SubFigure-based layout
...
save(fig, "project/05_figures/out/Figure1", width="double", archetype="box_jitter")
```
3. **Multi-panel figures are built panel-first.** Each panel is a `SubFigure` that owns its
   own axes, ticks, labels, legend and colorbar. Never place panels by hand with
   `add_axes`/`subplots_adjust`/pixel coordinates - one panel's tick labels will drift into
   its neighbour's space and every value change re-breaks the layout. Panel letters go at
   `(0, 1)` of the SubFigure, not inside the axes. `figure()` sets this up for you.
   One SubFigure is one *logical* panel: when two axes must stay column-aligned (a survival
   curve above its risk table, a plot above its marginal), put both inside the same
   SubFigure with `sharex=True`. Sibling SubFigures solve their layouts independently, so
   their axes are not guaranteed to line up.
4. **Deterministic QC first.** Fix everything code can detect before spending a look:
```
.\.venv\Scripts\python.exe tools/figures/qc.py --all
```
   From the rendered PNG: effective dpi against the target column width, content bounding
   box and the four margins, margin asymmetry, edge clipping, and mid-grey text-like
   regions (candidate leftover footnotes). From the live figure object via the sidecar
   `save()` writes: minimum font size and line width, panel tight-bbox overlap, clipped
   text, **missing font glyphs**, **tick-label collisions**, **dead bands between panels**,
   **bar baselines at zero**, and **the mandatory elements for the declared archetype**.
   Results land in `project/05_figures/qc/qc_report.json`.
   An `element:<name>` failure means the archetype's registry entry requires something the
   figure does not have - add it, or change the archetype if you picked the wrong one.
5. **Then look.** Open the rendered PNG as an image and inspect it:
   `read_file project/05_figures/out/Figure1.png`. For a suspect panel, crop it first
   (`.\.venv\Scripts\python.exe tools/figures/qc.py --crop Figure1 --panel B`) and look at the crop rather
   than squinting at the whole plate. Check: fonts and missing glyphs; overlapping or
   clipped labels; legend placement and completeness; axis ranges, tick density, units,
   log labelling; colour consistency, colour-blind safety, greyscale legibility; margins
   and stray whitespace; panel alignment and panel-letter placement; line widths; point
   size, overplotting, transparency; significance markers and bracket heights; leftover
   explanatory text; overall resolution and aliasing.
   ImageGen may participate as a second visual critic when available, especially for clutter,
   hierarchy, contrast, clipping, text density and journal-native appearance. Treat its
   comments as review findings only. It must not redraw, regenerate, inpaint or otherwise
   edit a statistical figure, because that could change data geometry, labels or meaning.
   Apply accepted fixes in the plotting script and inspect the new deterministic render.
6. Fix the **script**, re-render, re-run QC, look again. Repeat until clean. Say in each
   round which findings came from QC and which came from looking.
7. **Strip explanatory text from the panels.** Move only information needed to decode the
   figure to the legend: essential test/error-bar/threshold definitions, what a reference
   line means, and only a short abbreviation clause. Detailed adjustment sets, cohort provenance, software
   versions, interpretation and general caveats belong in Methods or supplementary Methods;
   do not dump them into the legend. Log every panel removal in
   `project/05_figures/moved_to_legend.md` as `Figure N | removed text | now in legend`,
   and record its correct prose destination in the same edit. Never fix this by greying the
   text down. Keep each legend within the configured 180-word ceiling. The legend identifies
   the display, maps panels and decodes symbols; it must not repeat which group was higher,
   restate an association, or reproduce effect estimates already reported in Results.
   Panel text that stays: axis titles and units, tick labels, panel letters, group labels,
   legend entries, significance markers, key data values (n, HR with CI, AUC, r), and
   guideline-mandated in-figure content (KM risk tables, CONSORT/PRISMA box text, scale
   bars). All of it black or near-black, at or above the size floor.
8. Write `project/05_figures/manifest.json`:
```json
{"built_at": "", "figures": [{"id": "Figure 1", "script": "", "png": "", "tiff": "",
  "width": "double", "size_mm": [180, 90], "dpi": 600, "review_rounds": 2}]}
```
9. Mark the visual review as done only after you have genuinely looked at every figure:
```
.\.venv\Scripts\python.exe tools/wf.py decide figures_visually_confirmed YES --why "<per figure: what you saw and what you changed>"
```
10. Delete scratch renders from `project/temp/`.

## Outputs
- `05_figures/manifest.json`
- `05_figures/qc/qc_report.json`
- `05_figures/moved_to_legend.md`
- (plus scripts in `05_figures/code/` and PNG+TIFF in `05_figures/out/`)

## Hard rules
- Never claim visual verification without having loaded the image. If the image cannot be
  loaded, say exactly that and report only the deterministic findings.
- ImageGen feedback never satisfies the visual-review decision by itself and never replaces
  source-code correction plus a fresh render.
- Never fix a layout problem by shrinking fonts below the floor or by nudging a single
  label's coordinates. Fix the layout structure (gridspec ratios, panel spans, SubFigure
  composition).
- No 3-D decoration, no gratuitous gridlines, no chartjunk.
- Do not add a figure that is not in the artifact plan.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "K figures rendered; QC clean; visually reviewed (rounds: <...>); moved to legend: <n> items"
```
