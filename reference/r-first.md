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
Analysis and figure runners share the same selection: project-local renv first, otherwise
the workspace environment. Activation failure does not fall back to global packages. Both
record the actual activation/lockfile identity; an environment change invalidates only its
affected result/render evidence. Figure staging keeps earlier outputs on activation failure.

## Plan, prototype and production

For the relevant clinical plot, source `tools/figures/r_recipes.R` after the
shared theme. These consume approved numeric coordinates, never refit/drop observations.
Use `medpaper_forest`, `medpaper_roc`, or `medpaper_calibration` only when the archetype
fits; add the study's required statistics, labels, uncertainty and layout before export.
Missing elements still fail ordinary figure QC. Do not use a recipe as a waiver.

The shared clinical recipes apply the approved display dictionary through discrete axis/key
label functions (and flow-box text), without renaming data values, factor levels or groups.
Numerical axes/statistical side columns keep their actual values. Ambiguous source-internal
aliases are not guessed: use the dictionary's unique source key or a precise clinical
definition in the study-specific display. If overriding a discrete scale, retain its
`labels=medpaper_label` where that declared mapping is intended. Actual rendered reading and
source agreement remain necessary; automatic label formatting is not medical acceptance.

### Ready-to-draw clinical results

Select only figures justified by the study/comparators. The expanded taxonomy is not a
list of mandatory analyses or a reason to add plots. These helpers draw every supplied
row and stop on incomplete/invalid values instead of fitting, smoothing or dropping rows.

| Helper | Actual source fields and decisions |
|---|---|
| `medpaper_selection_flow(nodes, edges)` | Nodes: unique `id`, concise clinical `label` including counting unit, actual `n`, layout-only `x,y`; edges: actual `from,to` ids. Declare each exclusion/final count from results. No count subtraction, invented exclusion categories or trial labels. Inspect branch logic, source/period and count reconciliation separately. |
| `medpaper_dose_response(data, x_label, y_label, null)` | Approved `exposure,estimate,lower,upper,group`; explicit exposure unit, effect scale and reference. A restricted-cubic-spline analysis must already have been fitted and exported at its owner. |
| `medpaper_decision_curve(data)` | Approved `threshold,net_benefit,group`; include only analysed strategies at actual decision thresholds. Do not calculate net benefit or add treat-all/none lines at plotting time. |
| `medpaper_balance(data, threshold, absolute)` | Approved `variable,smd,group`; declare signed/absolute display and the study's justified threshold, or omit a threshold. No new weighting or balance calculation. |

All are ggplots, exported by the same `medpaper_save` / managed R runner with the existing
result/render identity and actual-page inspection. Flow layout coordinates change placement,
never scientific counts. Large/complex flows need a study-specific measured layout; the helper
does not certify allocation, exclusion logic or a reporting checklist. Specialized trial
diagrams can use [consort](https://github.com/adayim/consort) only when appropriate; its grid
output still needs the measured adapter. No trial/checklist dependency is installed by default.

Optional `medpaper_colours(n, palette="nejm")` (also `lancet`, `jama`, `jco`) uses an already
available `ggsci`; apply explicitly through ggplot manual scales. The default remains the
colourblind-aware palette. Unsupported counts stop rather than recycle. Named palettes do
not establish journal compliance; check contrast, grouping and grayscale/shape decoding.

For approved survival/competing-risk fitted objects, consider `ggsurvfit` / `ggcuminc` and
their matching risk-table inputs; select the actual event explicitly. For precomputed
`cobalt::bal.tab` use `love.plot`; do not pass raw data and silently recalculate at S11.
Meta-analysis funnel plots can use the approved `metafor` object. Existing dcurves output
can supply decision coordinates. No new package bundle or parallel Word/table chain is added.
Primary interfaces checked 2026-11-06: [ggsci](https://nanx.me/ggsci/reference/pal_nejm.html),
[ggcuminc](https://www.danieldsjoberg.com/ggsurvfit/reference/ggcuminc.html),
[cobalt love.plot](https://ngreifer.github.io/cobalt/reference/love.plot.html).
These interfaces are references, not claims of installed versions or tested adapters for every package.

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

### Medical figure routes (use only the relevant route)

| Display | Scientific content to settle before drawing | Production route |
|---|---|---|
| Forest / sensitivity comparison | Actual measure and interval level, comparison direction, null value, population/available counts where needed, model adjustments | `medpaper_forest_table(data, measure, null, log_scale)` adds aligned exact effect/interval text to an inspected ggplot. Use an established specialized package for complex grouped/multiple-column forests when justified. Never invent n or imply event counts are group sizes. |
| Kaplan-Meier | Endpoint, time origin/unit, groups, actual censoring and number-at-risk at stated times, appropriate uncertainty | Use existing analysis exports or its approved fitted object with a suitable survival R implementation. Do not refit to draw; keep risk table and curve times aligned and disable automatic tests not already analysed. |
| ROC | Validation population, outcome definition, curve identity, actual AUC/interval when applicable | Existing `medpaper_roc` draws approved coordinates; supply source-supported curve/statistic labels. Plotting must not calculate a fresh AUC. |
| Calibration | Prediction horizon, validation setting, predicted/observed risk, uncertainty appropriate to the actual method | Existing `medpaper_calibration` draws approved results. Add exported uncertainty where applicable; do not create an unanalysed smoother or bootstrap. |
| Selection flow | Source, period, exclusions, final units and nested/overlapping branches | S07's real counting structure and applicable Figure 1 rule; counts come from executed results, not layout arithmetic. |

The numerical forest helper requires an explicit measure, null and scale. Use linear scale
with null 0 for an appropriate coefficient/difference, log scale with null 1 for an appropriate
ratio; neither is guessed from values. Specify the actual interval label. It preserves all
supplied estimates/rows and reports tiny nonzero values without rounding them to apparent
zero. Inspect physical width and statistics-column clipping in the actual PNG/PDF.
The existing simple forest remains available for compatible approved figures.

For grouped forests, `forestploter` is a possible grid implementation; its non-ggplot content
still needs the existing measured adapter, not false QC metadata. `survminer` can provide
curves/risk tables when the existing analysis inputs support them. These are conditional
choices, not newly installed defaults or a reason to bypass the renderer. A risk table is
supporting information for its curve, not automatically a second clinical panel.

For an R KM figure with genuinely no censoring, keep real curves and the risk table; do not
invent censor ticks. An optional artifact-plan `censoring_not_applicable` reference may point
to its declared, render-hash-matched result object, for example
`{"file":"03_analysis/results/survival.json","pointer":"/censoring_summary"}`.
That object must name `counting_unit`, positive integer `observations`, `events` equal to
observations, and `censored` exactly zero. Any missing/contrary/stale source fails. The exception
applies only to the censor-tick requirement, never risk tables, curve meaning or visual QA.
Confirm that this summary describes the plotted population, follow-up and censor definition
in the existing medical display review; a zero from a different population is not a waiver.

The old Python `recipes.py::km_survival` combines fitting and graphics and has no current
workflow call site. It is retained for legacy compatibility, not an S11 production recipe.
Do not call it to redraw accepted findings: use source-exported approved R results/fitted
objects. Its automatic log-rank and tail defaults are not a statistical plan or an instruction
to analyse. No existing clinical figure is refitted/converter-rewritten by this maintenance.

### Optional medical table route

Keep the present three-line writer for approved Python/R result JSONs. When an analysis
already benefits from `gtsummary`, calculate summaries in S05 and export its approved
statistics/ARD there. At S10 `tbl_ard_summary()` can format a complete precomputed ARD without
calculating missing statistics. Supply explicit labels, summary types, denominator bases and
missingness from the study; do not call raw-data `tbl_summary`, `add_p`, model fitting or
new summary calculations merely to build a table. Missing required facts return as a scoped
analysis/export correction. An ARD is optional and does not replace existing JSON/cell binding.
Map its formatted rows into the existing writer/upload path and inspect the actual output;
do not add competing gt/flextable/modelsummary document chains by default.

Official capability references checked 2026-11-06 (not installed-version guarantees):
[gtsummary precomputed ARD tables](https://www.danieldsjoberg.com/gtsummary/reference/tbl_ard_summary.html),
[survminer plotting interface](https://github.com/kassambara/survminer/blob/master/R/ggsurvplot.R),
[forestploter grid layout](https://adayim.r-universe.dev/forestploter/doc/forestploter-intro.html).
Use the already-recorded project environment; restore only missing selected dependencies.

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
# v1.22 medical multi-panel composition

Create each component as a ggplot, keep clinical titles independent of letters, then use
`p <- medpaper_compose(list(p1,p2), ncol=2)` and
`medpaper_save(p, "05_figures/out/Figure2", width="double", panels=list(p1,p2))`.
This uses patchwork for standalone upper-left A/B tags. Declare the same letters and actual
`panel_layout.columns` in the existing artifact plan. Do not concatenate A/B into facet
titles. A facet can be a panel, but it still needs independent tag placement in the actual
SVG and medical/visual inspection; reading the code or recognizing R style is not acceptance.

