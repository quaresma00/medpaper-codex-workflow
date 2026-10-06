# R-first medical methods and graphics

Read at S03/S05 and S07/S11. This is an implementation policy inside the same pipeline.

## Language choice

- Python remains suitable for acquisition, large-file processing, cleaning, joins and
  automation. Select analyses by the method and mature implementation, not the agent's habit.
- Default new medical statistical figures to R: ggplot2, patchwork/grid and relevant medical
  packages. Evaluate R first for survival/competing risks, imputation, mixed models, clinical
  regression/validation and meta-analysis when its implementation fits the required assumptions.
  Examples: survival/survminer, cmprsk, mice, lme4, rms, meta/metafor. This is not a mandatory
  package list or a claim that one language is superior for every task.
- Keep one statistical producer per finding. R reads already-approved Python result JSON/
  full-precision plot data; it does not refit a model just to draw it. R-produced statistics
  write the same result schema/provenance. R table summaries still pass existing three-line
  workbook and journal Word checks. Never retype statistics or use rounded Excel display data.
- Preserve approved Python figures/user edits. A genuine Python-only requirement or explicit
  user preference may use Python with a concrete reason in the existing plan. Missing R
  packages are a repair task, not permission for a silent language switch.

Record engine/packages and the method-specific reason in the existing protocol/analysis log.
Preserve seed, complete inputs, factor levels/reference groups, missingness, denominator,
units and full-precision output. CSV needs an explicit codebook; JSON missing values are null.
No extra language-choice approval stop or duplicate Python/R fitting is introduced.

## Environment

Check Rscript and required namespaces before expensive work. Use project-local renv where
restoration is needed; snapshot the working environment once and restore it rather than
upgrading on each revision. Record actual R/package versions. Do not modify the user's global
R library or recreate an environment for a label change. With --vanilla explicitly source
<workspace>/renv/activate.R when present; the managed runner already does so.

## Plan, prototype and production

New S07 entries declare renderer="R", a literal .R script beside PNG/PDF under 05_figures/out,
width, source_results and the existing archetype/reader contract. Python exceptions declare
renderer="Python" plus renderer_reason. Unmarked legacy plans remain readable.
Prototype in R under 01_protocol/prototypes with the same full data and semantic layout.
Use explicit plot/size in ggplot2::ggsave at low resolution. Reuse that expression at S11.

A production script uses real project results:

```r
source(file.path(Sys.getenv("MEDPAPER_ROOT"), "tools/figures/r_style.R"))
library(ggplot2)
r <- medpaper_result("03_analysis/results/primary.json")
# Convert the actual result object's full-precision values to the required plotting data.
# Build p with the study's clinical labels, units, uncertainty and required figure elements.
p <- p + medpaper_theme()
medpaper_save(p, "05_figures/out/Figure1", width="double", height_mm=75)
```

This illustrates the export interface, not a standalone study or fabricated result schema.
Run only the affected figure:

```powershell
.\.venv\Scripts\python.exe tools/figures/render_r.py --figure "Figure 1"
.\.venv\Scripts\python.exe tools/figures/qc.py --figure "Figure 1"
```

Python here orchestrates/validates files only; R draws the graph. Staging preserves prior
outputs on R errors/timeouts, refuses undeclared inputs/out-of-scope managed outputs, and
uses atomic file replacement. Warnings fail instead of silently dropping observations.
The sidecar records actual runtime versions and source/script/render hashes. PNG+PDF are
default; declare TIFF only when needed. Pass panels=list(p1,p2,...) for actual component
ggplots in patchwork/grid composites. Dedicated packages may supply ggplot/grid exports.
Native base/grid-only graphics require a measured structural adapter, not invented PASS
fields, a changed archetype to evade checks, or a silent switch back to Python.

## QA and local edits

QC measures PNG resolution/content and actual SVG font/stroke/text positions and inspects
built ggplot layers. SVG text widths are measured; text heights/collision boxes are conservative
estimates. PDF font fallback, glyph coverage, clipping paths and complex grid layout still
require actual visual inspection. Unknown measurements are stated, never reported as passed.
Warnings need attention during visual review; blocking defects must be corrected in R.
Keep themes/dimensions/layout parameters centralized. Use patchwork/grid rather than repeated
pixel nudges. A formatting edit changes the relevant R source and rerenders just that figure,
not cleaning/imputation/models. Preserve unrelated figures and the frozen scientific originals;
journal-specific scripts/exports belong in integration. Tavotto applies only to Matplotlib
exceptions, not R figures. No automated check replaces rendered-figure review.

Primary sources checked 2026-10-06:
- [ggplot2 export](https://ggplot2.tidyverse.org/reference/ggsave.html)
- [ragg PNG device](https://ragg.r-lib.org/reference/agg_png.html)
- [patchwork layout](https://patchwork.data-imaginist.com/articles/guides/layout.html)
- [renv project environments](https://rstudio.github.io/renv/articles/renv.html)
