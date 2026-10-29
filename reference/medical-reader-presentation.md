# Medical meaning before surface polish

Use at S07 before production, S08 prose, S10 tables, S11 figures, S17 acceptance and
S22/S23 journal adaptation; S18/S25 independent readers apply the same questions.
These are general principles, not a template for one database or one published paper.
Unverified external feedback identifies risks; it does not establish that its diagnosis,
arithmetic or proposed substitute is true. Read actual artifacts in the executing project.

## Read the paper as medicine, without the execution record

Use the existing benchmark and acceptance once; do not commission an extra writer or audit.
Before production, decide what a medical reader must learn about the population, clinical
question, comparison, outcome and uncertainty. Keep these decisions in the existing clinical
story/display plan. Write from those verified facts, not by narrating the sequence of scripts.
For basic/omics work the scientific unit may be tissue, a sample or a public dataset: do not
invent a clinical cohort or treatment implication to make the prose sound more medical.

At S17/S22 and the independent S18/S24/S25 reading, first read the submitted narrative and
displays without the backstage files. Explain the actual question, eligible unit/comparison,
principal finding and limits in the existing Reader comprehension section. If understanding
requires a script, result-key dictionary or workflow history, locate and fix the missing
explanation at its earliest source. Then consult evidence to verify that interpretation.

- Introduction motivates the clinical/scientific gap and the study objective; Methods
  describes the study rather than a job log; Results follows the agreed table/figure story;
  Discussion interprets magnitude, uncertainty, prior evidence and limitations in connected
  prose. Do not default to contribution lists, algorithm architecture, bullet conclusions,
  a subheading per paragraph or repeated generic claims of robustness/novelty.
- Retain a technical method, algorithm diagram or unusual structure when it is genuinely
  needed and supported by the close medical comparators/current journal. Explain its
  scientific purpose, assumptions and limitations. Word replacement must never hide a
  design weakness or promote an association into causality or clinical utility.
- A table must be intelligible from its title, body and notes; a figure from its labels,
  marks and concise legend. Inspect every planned main/supplement display at its publication
  size. Ask what population/comparison it shows, what the numbers/marks mean and what a reader
  could wrongly conclude. Use real clinical labels and essential local definitions while
  keeping long abbreviation lists centralized. Do not copy the same generic finding per item.
- Supplements are also medical writing, not a bin for debug logs, raw variable names or
  opaque procedural labels. Keep only reproducibility details that a researcher needs;
  internal receipts, paths, code keys and execution status stay outside the upload package.

These are content/reader acceptance criteria, not an AI-authorship detector or a forbidden-
word score. Automated diagnostics locate risks; substantive reading and actual figure/page
inspection remain necessary. No numeric quality score or stock rewrite certifies a manuscript.

General basis checked 2026-10-30: [ICMJE manuscript preparation](https://www.icmje.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html)
supports research-appropriate organization and interpreting tables/figures with their legends;
[PLOS Medicine author guidance](https://journals.plos.org/plosmedicine/s/submission-guidelines)
asks for concise, accessible prose. These support reader-oriented judgment, not a universal
template, journal choice, extra reporting checklist or fixed length/count requirement.

## Main Methods and labels

Write for a medically trained reader, not a processing engine. Keep the scientific study
population, eligibility, outcome definitions, exposure ascertainment, deduplication unit,
missingness and statistical methods explicit in main Methods. Implementation-only parsing,
character normalization and string-matching lengths can move to Supplementary Methods when
not central to validity, with a clear main-text pointer. Do not conceal a flawed matching
procedure behind polished wording. If the algorithm is the scientific contribution, explain
it adequately rather than automatically hiding it.

Database names, missingness, common support, penalized regression, confidence intervals,
deduplication, and actual Python/R/package versions are legitimate when relevant. There is
no blanket blacklist for technical words. Define unfamiliar concepts by their clinical role.
Keep execution logs, parser repair messages, hashes and internal branch codes backstage.
Avoid context-dependent labels such as "same", code letters and processing-step numbers.
Prefer clinical endpoint/comparison names, or explain shorthand at the point of use.

Never change "data-derived" or "post hoc" to "predefined/prespecified" to improve style.
Never rename records/reports/visits/specimens as patients without a valid counting identity.
Retain limitations caused by approximate linkage, residual duplicates or sparse data.

## Tables: title, body and footnotes are one statistical statement

- Title accurately describes the actual population, unit, comparison and outcome scope.
  A broad phenotype label must not silently convert clinical manifestations into diagnoses.
- Header and row labels use clinical names. Define source-specific model covariates and
  aggregation rules separately; the same step code need not mean the same model across sources.
  Move implementation-step columns to a supplementary table if they add no medical meaning.
- Describe actual mixed summaries: n (%), mean (SD), median (IQR), estimates and intervals.
  A blanket "numbers of reports" footnote must not describe an age median. Explain whether
  percentages are column/row/available-case and which denominator each stratum uses.
- State available-case calculation and missingness where interpretation needs it. Reconcile
  category totals only for mutually exclusive exhaustive groups; explain overlap otherwise.
- Distinguish observed zero, missing, not applicable, not fitted, nonconvergence, not estimable,
  unbounded interval and display truncation. A point estimate can be nonfinite while an
  interval bound is informative. Do not recompute, round away uncertainty or substitute a
  corrected estimator merely for appearance. A dash is permitted only with an unambiguous
  definition that preserves relevant distinctions.
- Apply journal-specific grouping/precision to actual numerical values, not IDs or dates.
  Tiny nonzero percentages must not become apparent zero; a rounding note must include the
  percent unit and correctly describe its treatment of zero. Don't require thousands commas
  when the journal specifies otherwise.
- Footnotes decode units, denominators, model adjustments and symbols; they are not an
  implementation manual. Put detailed algorithms/derivations in Methods or supplement.

## Figures: actual graphical marks must match the claimed statistic

For each plot identify the unit/person/report distinction, group comparison, endpoint,
measure, denominator (including each sensitivity/subgroup population), and uncertainty.
Axes, markers, numerical side-columns, captions and analysis JSON must agree about whether
a mark is a point estimate, a lower/upper confidence bound, a prediction or a count.
If only a bound is shown, don't label it as the estimated effect. Distinguish a confidence
interval extending beyond the plotted range from an actually unbounded interval, and both
from a large finite estimate. Define arrows and other nonstandard marks explicitly.

Selection flowcharts communicate clinically relevant inclusion/exclusion units and periods,
not how many file lines a parser read. Explain changes in counting unit/version and overlapping
exclusions; arithmetic closure alone cannot prove equivalent units or populations.

Define composite endpoints, source-specific comparison labels and every panel mapping where
the reader uses them. Make each sensitivity label explicit; preserve the actual post-hoc
status. Don't use a code letter, unexplained "source", or an ambiguous "same" as a clinical label.
If a figure carries event counts, label them as such; do not imply group sample sizes.

## Legends, abbreviations and real-page layout

Image + its concise legend should be interpretable without repeatedly opening Methods.
Legends explain panels, populations, units, uncertainty, symbols and nonstandard encodings,
not retell the Results. Sentence-like legends need ordinary punctuation; panel labels and
formulae need not become forced sentences. Default length remains advisory, not a reason
to remove necessary decoding.

Keep the user's centralized Abbreviations policy when lists are crowded. This is not a
reason to leave an endpoint or a bound undefined: expand its essential clinical wording or
provide a precise existing definition pointer without duplicating long abbreviation lists.
Use local abbreviation lists only when short/useful or explicitly required by the journal.

At S23 inspect the actual Word-rendered pages: repeated headers, continuation labeling,
last table rows and footnotes, legend/figure placement, panel correspondence, blank areas,
and first/last and changed pages. Check main and supplementary items actually delivered.
The journal may require separate legend pages and image uploads: do not force adjacency.
Avoid accidental interleaving/split legends or orphan notes. A long table may legitimately
span pages. Shorten only unnecessary notes, adjust allowed geometry/section/page breaks or
use continuation layout; do not shrink away legibility, drop content, or reintroduce
outlineLvl/keepNext/keepLines/pageBreakBefore controls forbidden by the user's Word policy.

## Existing acceptance, not another audit dossier

`benchmark.py style --layer science|journal [--final]` returns bounded risk diagnostics from
current manuscript/captions and actual readable table/figure text. It does not rewrite files,
perform OCR on raster figures or certify semantic/visual correctness. Inspect actual images.
Words alone are not errors. Fix the source; if flagged text is genuinely appropriate, record
`style_resolutions[issue_id]` with `action: retained`, a concrete medical `reason`, and actual
`evidence_location`. An old issue cannot be marked edited while still present unchanged.

Extend the EXISTING executor report, not a new document:

- `medical_style_version: 1`.
- Per `display_findings[ID].medical_checks`: tables use `title_and_labels`,
  `denominators_and_summaries`, `footnotes_and_model_states`; figures use `title_and_labels`,
  `statistic_and_encodings`, `population_and_denominators`. Write concrete observations about
  actual inspected rows/marks/notes. Explain inapplicability; generic copied PASS is not review.
- S23 only, `document_layout` has one row per relevant actual DOCX: `upload`, `source_sha256`,
  existing Word-rendered `render` (PNG/PDF under evidence/), `render_sha256`, substantive page
  `locator` and `observation`. Bind current source/render bytes; do not invent inspection or
  claim unavailable supplements were checked. Existing renders are reused, not regenerated.

Clinical naming, statistic meaning and counting-unit corrections are not automatically cosmetic.
Use scoped source/dependency revisions and existing meaning/freeze checks. A wording-only
change does not refit models or recreate all figures; a misleading measure requires actual
scientific resolution. Finished pinned stages/old reports aren't silently rewritten at upgrade.

For source-scoped labels, early physical production assumptions, all-observation review
closure, percentage denominator-basis checks and safe trial routing, also use
`reference/structural-quality.md`. Existing completed stages/evidence remain historical;
new scoped work does not imply a complete analysis or manuscript rebuild.

