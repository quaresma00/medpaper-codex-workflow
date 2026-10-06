# S11 - Render figures, then actually look at them

## Production boundary
Read `reference/r-first.md`, `reference/efficient-quality.md` and `reference/figure-standards.md`.
New medical statistical figures default to R. Reuse the approved S07 data, semantics and
prototype expression. Keep a literal .R script beside vector PDF/PNG in 05_figures/out.
Use mature clinical R packages and ggplot/grid/patchwork outputs as appropriate, with one
statistical source per result. Do not refit or rerun imputation to adjust a graph.
Retain an approved legacy Python graph or a concrete documented Python exception.
Missing R packages require repair, not an unannounced Python fallback.

## Procedure
1. Confirm Rscript and the actual required packages/environment. Put renderer="R" in each
   new figure entry, plus its .R script, PNG/PDF paths, width, source_results and archetype.
   A Python exception declares renderer="Python" and a substantive renderer_reason.
   No additional routine user approval stop is introduced.
2. Write one source per figure. Source tools/figures/r_style.R and read declared executed
   results with medpaper_result(). Centralize theme, font, physical size, palette and panel
   layout. Use medpaper_theme() and medpaper_save(); pass actual component ggplots in
   panels=list(p1,p2,...) for composites. Use patchwork/grid instead of repeated pixel nudges.
   The plot expression is the source of truth; labels and uncertainty come from real results.
3. Run only the requested figure:
```powershell
.\.venv\Scripts\python.exe tools/figures/render_r.py --figure "Figure 1"
.\.venv\Scripts\python.exe tools/figures/qc.py --figure "Figure 1"
```
   Python in the runner does not draw the plot. R uses explicit objects/physical sizes and
   generates PNG+vector PDF; TIFF is opt-in. Render warnings fail instead of silently
   dropping observations. Staging preserves existing outputs on failed R builds.
4. Read actual QC findings. R QC inspects SVG font/stroke/text positions and built ggplot
   layers, PNG resolution/content and bound script/results/render identities.
   Text-height/collision estimates are conservative; glyph coverage, PDF font fallback,
   clipping paths and complex layouts remain visual-review items, not fabricated PASS.
   Some specialized base/grid graphics need a measured adapter. Keep the appropriate R
   tool; do not relabel a chart or fabricate elements to evade checks.
5. Open the actual rendered PNG and inspect font/glyphs, overlap/clipping, clinical labels,
   reference groups, units, denominator/time window, uncertainty, axes, risk tables,
   panel alignment, colour/greyscale readability, margins and resolution. For complex
   layouts also open the vector PDF. Use one <=1280px, <=500KB preview per tool round.
   Warnings must be resolved or substantively addressed in the existing review.
6. Correct only the affected producing script/config, rerender that figure and rerun its
   QC. Do not redo cleaning/models or unchanged figures for a visual-only correction.
   A substantive statistical correction follows the existing scientific revision route.
7. Keep explanatory prose backstage or in its proper Methods destination. Figure legends
   only decode the display, panels, symbols and necessary test/error-bar definitions.
   They do not repeat Results directions/effect estimates. Preserve journal-mandated risk
   tables, flow counts, units and essential source-bound statistics. Use the existing
   legend word ceiling; record moved material in 05_figures/moved_to_legend.md.
8. Write 05_figures/manifest.json with actual renderer, script, source_results, png/pdf,
   width/size_mm/dpi, R/package versions or the Python exception, and review_rounds.
   SVG/rmeta/artist sidecars are backstage QC, not submission uploads.
9. Mark visual_reviewed in qc_report.json and record the figures_visually_confirmed decision
   only after genuine image inspection. Automated QC never supplies this approval.
10. Clear task scratch. Journal-specific adaptations after S19 use integration copies and
    preserve the accepted scientific script/output.

## Python exceptions
For an existing approved Matplotlib figure or concrete exception, retain its source and
tools/figures/style.py + recipes.py. Use the installed Tavotto skill and desktop handoff
only for Matplotlib, never for R graphs. No R-to-Matplotlib conversion is needed.
ImageGen may critique readability but never redraw or edit statistical content; fix source
code and inspect the deterministic new render.

## Outputs
- 05_figures/manifest.json
- 05_figures/qc/qc_report.json
- 05_figures/moved_to_legend.md
- Co-located producing scripts and PDF/PNG; legacy separated scripts remain supported.

## Hard rules
No invented results, fabricated inspection or skipped source checks. Keep all data.
Do not fix a layout defect by shrinking below the font floor. Correct the layout structure.
No gratuitous 3-D/gridlines or unplanned figures. Missing inspection is pending, not PASS.

## Close
```powershell
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "Declared R/Python outputs rendered; measured QC and actual visual review completed; unresolved items stated."
```
