# S07 - Artifact inventory and reader-ready display plan

Before writing or expensive production, search recent literature (initially the latest24 months)
and inspect about5–10 close published full texts, including actual figures, tables and captions.
Record their real dates, display counts/types/purposes and analysis choices in the existing
benchmark. Sparse-field/older-paper exceptions need actual search evidence and scientific
reasons; difficulty obtaining a necessary PDF means exhaust real retrieval then ask the author.
Seal project-specific coverage/display choices with that benchmark. Abstract-only
comparisons and fixed numerical quotas are insufficient. Use the source-scoped clinical
labels and reversible physical presentation profile already in artifact_plan.json.

For EACH table/figure state its clinical question, population/comparison, measure/unit and
denominator, placement, overlap with other displays and likely reader misunderstanding.
Required scientific reader tasks determine displays. Do not treat "focused", "compact" or
"nonredundant" as grounds to omit an applicable main selection flow or primary-result view.
Map actual comparator figure/table pages to adopted/modified/omitted roles in the existing
benchmark. Prototype with real complete data, without refitting approved results to draw.
If this study has fewer main figures than the comparator median, explain actual scientific
differences and reader-task coverage in count_comparison. Cost, convenience and a generic
claim that2–3 figures are enough do not justify an otherwise thin Original article.
New statistical graphics default to managed R; record a real exception for Python.

Write substantive legends/captions that decode the actual display without repeating Results.
No magic word such as "footnote" certifies notes: S10 inspects every real workbook's notes.
Keep crowded abbreviations centralized, with necessary clinical definitions at point of use.
Do not infer units, endpoint components or confidence level from an internal variable name.

For schema, benchmark commands and prototype acceptance, use the full procedure below.

## Full procedure, read once when needed
`reference/stage_details/S07_artifacts.md` (`tools/wf.py card S07_artifacts --details`).
On first execution read the applicable detailed procedure; later local corrections reuse
already-read guidance and go directly to affected owner rules. After compaction use
`tools/wf.py handoff`, then retrieve only missing context. The CLI shows the applicable gates.
`reference/structural-quality.md` v1.17 explains runtime fixes and preserved boundaries.

## Outputs
- `01_protocol/artifact_benchmark.md`
- `01_protocol/artifact_plan.json`
- `05_figures/legends.md`
- `04_tables/table_captions.md`
- `01_protocol/display_review.json`
- low-cost previews under `01_protocol/prototypes/`

## Close
Run `tools/wf.py check` (or the active scoped revision check). Fix actual failures before
`tools/wf.py advance --note "<actual completed work>"`. Stages are not turn boundaries.
Review stages still require the real author statement; generic continuation is not approval.
