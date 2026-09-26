# S09 - Results

## Purpose
Write the Results section against the approved artifact plan, before the artifacts are
rendered. The plan fixes what each display contains, so the prose can be written from the
result JSONs and then reconciled at S12 once the files exist.

## Inputs
- `01_protocol/artifact_plan.json` - the display items and what each one shows
- `03_analysis/results/*.json` - every number
- `05_figures/legends.md`, `04_tables/table_captions.md` - so the prose does not repeat them

## Procedure
1. Organize Results around the clinical question: who was studied, the principal outcome,
   and clinically meaningful supporting findings. Cohort/flow, characteristics, primary,
   secondary and sensitivity results are useful conventions, not mandatory headings.
   Retain all prespecified outcomes, including null or unfavorable findings; place lengthy
   technical checks in appropriate supplements, never suppress them to improve the story.
   Do not use the order of scripts, model runs or pipeline stages as the narrative structure.
2. Write `project/07_manuscript/results.md`. Every display item in the plan must be cited
   at least once, in order, as `(Figure 1)`, `(Table 2)`, `(Figure S1)`, `(Table S1)`.
   The gate rejects citations to items not in the plan, and items never cited.
3. Report effects the way the design demands: point estimate, 95% CI, then the p-value -
   never a bare p. Copy the values from the result JSONs; do not re-round to look tidier
   than the analysis was.
4. Do not interpret. No "importantly", no "consistent with prior work", no mechanism.
   Those belong in the Discussion.
5. Do not restate a table row by row. The prose carries the findings the reader must not
   miss; the table carries the rest.
6. For each reported estimate confirm the source field AND population/comparison, endpoint,
   unit, denominator, adjustment set and time window. Equal numeric values in a JSON pool
   are not proof that a sentence refers to the right clinical result. Keep this mapping in
   the existing analysis notes, not as cryptic provenance tags in the published prose.

## Outputs
- `07_manuscript/results.md`

## Hard rules
- ONE section file this stage.
- Every number traceable to results JSON.
- Every figure/table citation matches `artifact_plan.json` exactly, including
  supplementary numbering.
- No claim about a result you did not compute. If a reviewer would ask "where is the
  test for that", either run it (loop to S05) or do not claim it.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "results drafted; primary: <estimate, CI, p>; all <n> display items cited"
```
