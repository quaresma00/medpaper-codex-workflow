# S07 - Artifact inventory and reader-ready display plan

Before writing or expensive production, read the actual full-text medical comparators and
seal project-specific coverage/display choices with the existing benchmark. Abstract-only
comparisons and fixed numerical quotas are insufficient. Use the source-scoped clinical
labels and reversible physical presentation profile already in artifact_plan.json.

For EACH table/figure state its clinical question, population/comparison, measure/unit and
denominator, placement, overlap with other displays and likely reader misunderstanding.
Do not add a figure merely to answer an editorial request if an existing display can carry
it clearly. Prototype with real complete data, without refitting approved results to draw.
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
`tools/wf.py handoff`, then retrieve only missing context. The actual gates remain unchanged.
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
