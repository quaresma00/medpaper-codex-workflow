# Clinical presentation, complete review closure and low-cost correction (v1.16)

Read at S06/S07, percentage reporting, review rounds and rework. This is an extension of
existing readiness, medical-reader acceptance and source-owned revisions, not another
orchestrator, report dossier or mandatory reviewer. Never copy another engine's finding
as an established fact about this engine or an unprovided paper.

## Evidence from this implementation

Codex already has full-data acquisition and numeric/source binding, separate scientific
and journal copies, presentation-amendment lineage, real managed build dependencies,
guarded builder outputs and scoped validation. Analysis replay hashes only actual producer
code/data/results, not manuscript prose; don't rerun it for wording. Existing S18 already
reads as a medical reader. Inspect its actual complete report, not just a priority summary.

The remaining structural gaps addressed here are a shared clinical vocabulary, complete
finding dispositions, publication-label numbering, early physical production assumptions,
flowchart axis exemptions and percentage denominator-basis checks.

## One clinical vocabulary in the existing S07 plan

Use `artifact_plan.json.display_dictionary` only for internal IDs/ambiguous labels actually
used. Each row has unique `key`, `internal`, medical `label`, one-sentence `definition` and
`scope` (source/cohort or `all`). Empty is fine if all names are already clinical. Keys are
backstage, never replacement headings in the paper. Prefer clinical names; letters and
accepted method terms are not universally banned. Define composites at point of use.

Python `clinicalpresentation.label(value, project, scope=...)` maps an exact key/internal
name. `journalspec.label_text` and the table writer use it; managed R supplies the same
keys to `medpaper_label`, which can also be used explicitly for discrete-scale labels.
Use unique keys when one internal name has different definitions across sources; never
silently choose a different cohort's label. Do not rename raw variables/model factors or
alter numeric facts to improve labels. Claims can use the unambiguous clinical display
name of their original fact. Review actual rendered output, including raster figures.

Keep source-specific model diagnostics/aggregation steps in supplementary tables unless
they materially affect interpretation in the main table. A reviewer request to disclose
something does not automatically mean "add a main-table column". Retain necessary main
Methods principles and genuine limitations. Don't turn data-derived or post-hoc rules
into prespecification, or rewrite post hoc as a claim about an unknown discovery date.

## Reversible production assumptions before final journal selection

At S06/S07 choose `presentation_profile` in the existing plan: `figure_font_pt_min` (default
at least 8 pt at actual final size), optional `figure_font_pt_max`, `figure_dpi_min`,
`column_width_mm_single`, `column_width_mm_double`, `number_format`, and `basis` explaining
the assumptions/comparator fit. This is NOT a confirmed journal, no extra author decision.
Use readable prototypes at planned physical size before expensive production. Retain old
approved graphics rather than rerendering them solely for a new default.

S20 confirms actual journal rules; integration plan/profile may override via
`target_journal.figure_requirements` with `figure_rule_source`. QC uses the actual R SVG/
Matplotlib measurements and planned physical width; R rendering uses the same widths.
Recheck effective font size if embedding scales an image in Word; text inside an image is
not a Word run. Do not call missing measurements a verified font floor.

Flow diagrams require their actual boxes/counts and meaningful connections/exclusions,
not arbitrary x/y axis titles. Statistical plots retain their appropriate axes. Counting
units may legitimately change from records/versions to unique reports/patients, but must be
explicitly distinguished and linked; do not falsely relabel parser rows or ban all version
counts regardless of purpose. Mathematical closure is not proof of clinical unit identity.

The table component's 300-character guard applies to BODY cells, not individual footnotes.
The old 1500-character total footnote heuristic is now advisory; actual Excel cell capacity
still blocks truncation. Write coherent decoding notes, not one sentence per row to game a
limit. Do not collapse zero, missing, not fitted, nonestimable and unbounded states.

Keep the user's centralized abbreviations and full XML cleanup policy. Do not restore
keepNext/keepLines or duplicate large local abbreviation lists on this feedback's authority.
Use necessary local clinical expansions, allowed geometry/section breaks or journal-directed
separate legend pages. S17 may use a risk-triggered/requested representative Word preview;
do not automatically build full DOCX on every review round. Reuse unchanged preview pages.
Final S23/S25 still inspect actual Word-rendered pages under the existing v1.15 acceptance.

## Every review observation closes, not only the must-fix subset

New engine-version 1.16 rounds use schema 3; existing open/sealed legacy rounds keep their
history. The reviewer reads originals/current renders, with neutral question/decision-free
instructions. Give scientific context, not the writer's preferred conclusion or expected
defect list. Later rounds default to actual dependency-bound delta; first reading, final
S25 and uncertainty may need full context. Full current materials remain accessible.

In the genuine report JSON include `finding_inventory_complete: true`, `findings` and
`section_verdicts`. Cover every required review section, including Reader comprehension and
Medical presentation; each section says `findings_listed` or `no_actionable_findings`.
Each actionable point has `[finding:ID]` in report prose and a matching JSON row: `id`,
`section`, actual `text`, concrete `locator`, category (numbers/grouping/conclusion_strength/
objective/preference) and boolean `affects_science`. Do not omit inconvenient soft-phrased
defects or confuse a positive observation with an action item. JSON cannot prove honesty;
the reviewer/main agent must actually check prose-to-inventory completeness.

`close --resolutions <JSON>` records every fixed finding as
`ID: {status: fixed, reason: actual correction, files: [changed reviewed inputs]}`. A real
producer-only fix that leaves reader-facing bytes unchanged may instead name its actual
closed `revision_round: RNNN`; that round must have real scoped validation and matching
changed-file receipts. Do not rewrite correct paper text just to manufacture a visible diff. Every
finding must have exactly one fixed disposition or `--kept ID reason`. Missing IDs, unknown
IDs, duplicate dispositions and fictitious fixed-with-no-changed-source claims fail. Review
revalidation retains the initial findings and report history; it cannot drop an old issue
or reuse its ID for a different issue. Numerical/grouping/conclusion issues still require
correction or genuine author adjudication, not self-dismissal as preferences. Unresolved
material issues still block "我确认这一版". This is one existing review report/summary, no
extra external-review package. Preserve the full returned report, not just streamed excerpts.

## Presentation labels, aliases and safe trial routing

`Online Resource 2`, figure/table/appendix identifiers and panel case are not effect sizes.
Recognized label numbering is excluded from numeric-finding comparison, not from artifact
inventory validation. Explicit `display_reference_aliases` may map a real numbered journal
label to `supplementary_methods|supplementary_tables|supplementary_figures` only, with an
official `display_reference_rule_source`. These cannot alias arbitrary scientific numbers.
Heading roles support journal `Statements and Declarations` without changing the canonical
scientific source. A label rename still needs current cross-reference/file-slot checks.

Before editing use `rework.py preview --plan ...`: read-only owner/dependency plan, no approval
invalidation. It does not predict unmade semantics. After edits, actual `check` compares
versions and may request a source-bound meaning assessment. Unexpected classification is
a barrier to investigate, NOT permission for automatic S19 rewind. To seal a truly scientific
late correction, use `--confirm-scientific-route --why <actual author instruction>` after
explaining approval effects; a specific initial authorization can supply this, generic
"continue" cannot. Then renew only affected scientific review, not the completed stage tail.
Same-value number bags or a value appearing in JSON do not prove unchanged scientific meaning.

## Percentages bind denominator concepts as well as values

Each new reported proportion uses a `claim_bindings` row `proportions` list: `fact_id`,
`numerator_key`, `denominator_key` (keys in the executed fact's values), and exact `reported`
percentage. Source context states `percentage_basis`: eligibility, available-case rule,
counting unit and period. Don't manufacture this basis from prose. The guard computes
correspondence without changing the paper, including rounding. Use `percentage_kind`
`relative_change` or `probability` when the actual statistic is not a person/report fraction;
the default is `part_whole`. Rates/percentage-point changes require their true measure,
not a forced patient denominator. Interval confidence levels are not cohort percentages.

Multiple percentages with different source denominator bases require correction or an
explicit `different_percentage_bases` explanation occurring in the actual reported clause.
Table cells with percentage headers should carry the same bindings, not just a coincidentally
matching numeric pool entry. Read medical meaning too: text comparison detection is not a
general natural-language inference engine. Reconstruct missing legacy bindings from existing
results/code without invented counts or an unnecessary refit. A real wrong denominator or
changed claim remains scientific: targeted owner correction and review, never a "new numeric
but harmless" waiver. Formatting changes reuse valid analysis evidence.

Use UTF-8 files and explicit encoding, persisted state under the project .wf directory,
bounded/summary output and the host's running-command session/completion wait. Don't use
fixed one-minute kills or busy sleep/poll loops as workflow requirements. Do not silently
switch to a cheaper model or a fallback language; quality/scope requirements stay intact.
