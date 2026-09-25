# S05 - Method scan + exploratory analysis (no publication figures)

## Purpose
Find out what the data actually says, using methods the literature accepts for this
design, and dump every number to disk so writing can never invent one.

This stage is deliberately loopable. Iterate here as long as needed; do not
half-finish it and move on.

## Procedure
1. **Method scan.** Search for how comparable papers analysed this design - the model
   family, the confounder strategy, the sensitivity analyses, the standard reported
   metrics. Discovery tools may suggest candidates, but method claims and citations must
   resolve to records retrieved by the bundled client. Run at least 5 distinct formal
   queries through the client (the gate counts them):
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
   ran, what came out, what you decided next and why. Include dead ends - they become the
   sensitivity analyses a reviewer asks for.
5. **Keep the notes.** Update `03_analysis/notes.md` under all four headings. This is the
   only sanctioned input to Introduction and Discussion framing, so it must be substantive.
6. Delete scratch scripts and abandoned outputs from `project/temp/`. Also delete result
   JSONs from analyses you abandoned - a stale file becomes a fake provenance source.

## Outputs
- `03_analysis/method_scan.md`
- `03_analysis/analysis_log.md`
- (plus scripts in `03_analysis/code/` and result JSONs in `03_analysis/results/`)

## Hard rules
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
When the analysis has converged (no further analysis would change the conclusions):
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "primary result: <effect, CI, p>; K result files; open: <...>"
```
To iterate again later from a downstream stage: `.\.venv\Scripts\python.exe tools/wf.py loop --to S05_analysis --why "..."`
