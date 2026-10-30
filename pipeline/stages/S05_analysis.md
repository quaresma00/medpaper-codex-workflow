# S05 - Method scan + exploratory analysis (no publication figures)

Read `reference/analysis-execution.md`. Export from the actual producer using the shared
Python/R writer, with every complete input/config/helper declared. Execute via the managed
runner, then replay only converged reportable outputs. Do not repeat all analyses for a
wording/formatting revision or create hand-written execution/verification metadata.

Read `reference/numeric-claims.md` before result exports. Export reportable findings with
their actual clinical context and named values from executed code; never retrofit invented
results to satisfy a writing gate.

Read `reference/r-first.md`: do not default every method to Python. R statistical producers
write the same full-precision result JSON/provenance. Keep one producer per finding and
separate S05 statistical computation from S11 display-only R rendering.

## Purpose
Find out what the data actually says, using methods the literature accepts for this
design, and dump every number to disk so writing can never invent one.

Resolve the primary question and actual validity threats. Before adding an analysis, identify
what decision or claim it could change. An available model/package is not a reason to run it.
Complete necessary work; stop adding speculative variants once material questions are resolved.

## Procedure
1. **Method scan.** Search for how comparable papers analysed this design - the model
   family, the confounder strategy, the sensitivity analyses, the standard reported
   metrics. Discovery tools may suggest candidates, but method claims and citations must
   resolve to records retrieved by the bundled client. Reuse relevant S02/S03 retrievals and
   full texts; run a new query for a real uncovered method/assumption, not to reach a count:
```
.\.venv\Scripts\python.exe tools/pubmed/client.py search --query "<design> <outcome> statistical analysis" --retmax 100
.\.venv\Scripts\python.exe tools/pubmed/client.py fetch --ids <...> --with-abstract
```
   Write `project/03_analysis/method_scan.md`: for each candidate method, what it is,
   which retrieved papers use it, and whether it fits our data. Cite with `[@key]`.
2. **Analyse.** Every analysis lives in a script under `project/03_analysis/code/`.
   Scripts must be re-runnable from a clean checkout and must set a seed where relevant.
3. **Dump results as JSON.** Each script writes to `project/03_analysis/results/*.json`.
   One file per analysis block. Structure them so a human can find a value:
```json
{
  "analysis": "primary_model",
  "script": "03_analysis/code/03_primary.py",
  "run_at": "",
  "n_analysed": 0, "n_excluded": 0,
  "estimates": [
    {"term": "", "estimate": 0.0, "ci_low": 0.0, "ci_high": 0.0, "p": 0.0, "scale": "OR|HR|beta"}
  ],
  "model": {"family": "", "covariates": [], "software": ""},
  "diagnostics": {}
}
```
   **Every number that will ever appear in the manuscript, a table, or an abstract must
   be in one of these files.** The gates at S08-S16 reject numbers that are not.
4. **Keep the log.** Append to `project/03_analysis/analysis_log.md` as you go: what you
   ran, what came out, what you decided next and why. Retain failed or contradictory findings
   and distinguish technical failure from a valid null result. A dead end does not automatically
   become another manuscript sensitivity analysis. Say which uncertainty it resolves.
5. **Keep the notes.** Update `03_analysis/notes.md` under all four headings. This is the
   only sanctioned input to Introduction and Discussion framing, so it must be substantive.
6. Clean disposable task-created scratch from `project/temp/`. Preserve valid prespecified
   primary/secondary and relevant null/contradictory results. Genuinely invalid or superseded
   task-created result versions may be moved out of the active result directory to
   `.wf/retired_analysis/` with their original bytes and a concise reason/original path in the
   existing analysis log. Never retire a result merely for its p value or direction. Check and
   reconcile its actual consumers first; do not delete user files or silently drop evidence.
   Retired outputs cannot supply current manuscript numbers or become active facts by copying
   a value. Recompute a genuinely corrected result through its producer when necessary.

## Outputs
- `03_analysis/method_scan.md`
- `03_analysis/analysis_log.md`
- (plus scripts in `03_analysis/code/` and result JSONs in `03_analysis/results/`)

## Hard rules
For new/revised categorical baseline producers, Python/R `baseline_counts` exports every
category (both binary levels), counts by group, missingness and explicit denominators.
Do not infer unexported complementary counts later or replay old analysis solely for this helper.
- **No publication plotting.** Keep computational scripts under `03_analysis/code/`
  free of matplotlib, seaborn, plotly, ggplot and savefig; that separation is gated.
  When needed to judge model fit, missingness or bias, run a small diagnostic-only script
  under `temp/diagnostics/` and inspect its low-cost preview there. Record its numerical
  diagnostics and interpretation in the result JSON/log, then remove only these disposable
  task-created scratch files before closing S05. Do not number or style them as paper
  figures, export high-resolution production formats, or open Tavotto for them. S07 owns
  reader-facing display prototypes; S11 produces the approved scientific figures.
- No p-value computed in prose. If it is not in a JSON file, it does not exist.
- Do not silently switch the primary analysis. If it changes, that is a protocol
  deviation and it gets recorded at S06.
- Analytical skills may help implement the approved analysis, but cannot change the
  protocol, create manuscript prose, bypass results JSON, or advance the stage.

## Close
When required analysis and validity questions are resolved, and no identified material task
remains (not a claim that every possible future analysis would agree):
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "primary result: <effect, CI, p>; K result files; open: <...>"
```
Later scientific corrections use scoped `tools/rework.py` owner rules; do not replay the
completed stage tail or refit unrelated models.

## v1.14 execution update

Read `reference/quality-before-writing.md` at this checkpoint. Its sequencing, source-based
declarations, no free numeric whitelist, soft size budgets and exact current-version confirmation
supersede older conflicting instructions. Do not create external-review materials by default.

