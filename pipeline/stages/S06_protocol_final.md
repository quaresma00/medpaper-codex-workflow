# S06 - Final protocol + go/no-go #2

Follow `reference/analysis-execution.md` for converged outputs. Writing readiness verifies
current receipted results against retained real replay evidence without rerunning models.
If sources changed, repair/replay their producers and true dependents; do not fake a pass.

Before freezing, follow `reference/numeric-claims.md` to add source-bound quantitative facts
to the existing clinical-story file. Keep this provenance backstage; do not draft the paper.

## Purpose
Reconcile what was planned with what was done, then re-judge publishability now that
the effect size and the data's limits are known. This is the last cheap exit.

## Procedure
1. Write `project/01_protocol/protocol_final.md` - same headings as v1 plus
   `Deviations from protocol v1`. The deviations section is the important one:
   for each change, state what changed, why, when it was decided and how it affects inference.
   Data-driven does not automatically mean invalid and a cited method does not automatically
   make a change stronger; preserve actual timing and judge its scientific consequences.
   Reconcile the actual control, denominator and endpoint choices with the S03 design/method
   precedents. Keep their applicability and departures in the existing sections; do not
   re-search unchanged evidence or add a default registration/reporting form.
2. Write `project/01_protocol/protocol_diff.md` - a plain list of v1 -> final changes,
   one line each. This becomes the honest basis for any "pre-specified" claim in Methods.
3. Before decisions, read `reference/efficient-quality.md`. Persist the scientific rules in
   `01_protocol/analysis_contract.json` and the four-part clinical story in
   `01_protocol/study_facts.json`; link findings to executed result JSONs. Resolve material
   clinical ambiguity, preserve relevant null/contradictory findings and reconcile every
   planned primary/secondary outcome with its result or explained limitation. Do not invent
   validation or silently replace a failed primary question with a favourable exploratory one.
4. Confirm required analysis and validity work are complete:
```
.\.venv\Scripts\python.exe tools/wf.py decide analysis_converged YES --why "<required questions resolved; remaining optional work and why it does not block the current inference>"
```
   If a material task remains, correct its source through the existing scoped owner rules;
   do not claim YES or repeat unrelated analyses. No requirement to test every conceivable model.
5. Re-judge publishability against the real result, not the hoped-for one:
   - Is the primary result interpretable (direction, magnitude, precision)?
   - What effects remain compatible with the interval, and does this address the clinically
     relevant question? Nonsignificance alone proves neither no effect nor unpublishability.
     Do not manufacture a clinical importance threshold or run post-hoc power to defend a p value.
   - What do the required sensitivity analyses reveal? Explain contradictions and their impact
     rather than requiring every variant to support the preferred conclusion.
   - Has the gap from S02 changed now that you know the effect size?
```
.\.venv\Scripts\python.exe tools/wf.py decide go_nogo_2 GO --why "<the finding, its precision, why a journal takes it, which journal tier is realistic>"
```

6. These two judgments bind the actual scientific inputs when recorded. If those inputs
   subsequently change, reassess the judgments on the new version; do not simply recapture
   a freeze using stale GO. This is executor scientific judgment, not an extra author-confirmation
   stop. After convergence and GO:
```
.\.venv\Scripts\python.exe tools/manuscript/readiness.py freeze
```
   Writing remains blocked if those sources later drift. A PIVOT or STOP does not advance.

## Outputs
- `01_protocol/protocol_final.md`
- `01_protocol/protocol_diff.md`
- `01_protocol/analysis_contract.json`
- `01_protocol/study_facts.json`
- `01_protocol/writing_readiness.json`

## Hard rules
- Do not retro-fit the protocol to make the result look pre-specified. The diff file
  exists so that this is impossible to do accidentally.
- A `STOP` here is a real outcome. Report it to the user with the reasoning; do not
  soften a dead result into a "hypothesis-generating" paper without saying so.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "protocol final; K deviations; go_nogo_2=<...>; realistic tier=<...>"
```

## v1.14 execution update

Read `reference/quality-before-writing.md` at this checkpoint. Its sequencing, source-based
declarations, no free numeric whitelist, soft size budgets and exact current-version confirmation
supersede older conflicting instructions. Do not create external-review materials by default.

## Structural quality and bounded rework

Read `reference/structural-quality.md`. Use clinical display names and physical-size assumptions
before production. Percentage claims bind numerator, denominator and source percentage basis.
Every actionable point in every review section needs a stable ID and disposition, not only
the must-fix subset. Review neutral actual artifacts; don't prime with the writer's conclusion.
Use read-only rework preview and actual scoped checks; never infer scientific change from a
publication label number or silently invalidate author approval. Existing privacy, freezes,
centralized abbreviations, Word cleanup and final actual-page inspection remain in force.


