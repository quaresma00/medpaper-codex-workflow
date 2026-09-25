# S06 - Final protocol + go/no-go #2

## Purpose
Reconcile what was planned with what was done, then re-judge publishability now that
the effect size and the data's limits are known. This is the last cheap exit.

## Procedure
1. Write `project/01_protocol/protocol_final.md` - same headings as v1 plus
   `Deviations from protocol v1`. The deviations section is the important one:
   for each change, state what changed, why, and whether the change was driven by the
   data (which weakens it) or by a method-scan finding (which strengthens it).
2. Write `project/01_protocol/protocol_diff.md` - a plain list of v1 -> final changes,
   one line each. This becomes the honest basis for any "pre-specified" claim in Methods.
3. Confirm the analysis is finished:
```
.\.venv\Scripts\python.exe tools/wf.py decide analysis_converged YES --why "<what was the last analysis, why nothing further would change the conclusion>"
```
   If it is not converged: `.\.venv\Scripts\python.exe tools/wf.py loop --to S05_analysis --why "..."`.
4. Re-judge publishability against the real result, not the hoped-for one:
   - Is the primary result interpretable (direction, magnitude, precision)?
   - A null result is publishable if the question mattered and the study was adequately
     powered to answer it. Say which of those two conditions holds.
   - Does the finding survive the sensitivity analyses?
   - Has the gap from S02 changed now that you know the effect size?
```
.\.venv\Scripts\python.exe tools/wf.py decide go_nogo_2 GO --why "<the finding, its precision, why a journal takes it, which journal tier is realistic>"
```

5. Before writing, read `reference/efficient-quality.md`. Persist the scientific rules in
   `01_protocol/analysis_contract.json` and the four-part clinical story in
   `01_protocol/study_facts.json`; link the main finding to executed result JSONs. Resolve
   any material clinical ambiguity; do not invent validation. After convergence and GO:
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
