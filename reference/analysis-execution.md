# Executed results and targeted reproduction

Read at S05/S06 and when a scientific revision changes a result producer. Keep this
infrastructure backstage; it is not a manuscript section or a reason to refit for labels.

## One producer, real execution

New/revised producers use `tools/analysis/results.py::write_results` or
`tools/analysis/results.R::medpaper_write_results`. Declare every actual input/config/helper
by project-relative path; use the complete acquired data, not a test subset. Set the seed
before stochastic work and pass that same seed. Persist full-precision findings separately
from the writer's observed `environment`. Do not hand-write, repair, or backfill receipts.
Existing result schemas remain usable; wrap the actual producer, not a new metadata-only script.
Legacy unreceipted results are explicitly not claimed to have been reproduced.
New `wf init` projects require executed receipts before writing; deleting a receipt is
not a migration mechanism. Existing studies retain their compatibility state.

Run a single producer from the project directory:

```powershell
.\.venv\Scripts\python.exe tools/analysis/reproduce.py run --script 03_analysis/code/primary.py
# The same command accepts a real primary.R; it binds Python for streaming hashes.
.\.venv\Scripts\python.exe tools/analysis/reproduce.py replay --output 03_analysis/results/primary.json
.\.venv\Scripts\python.exe tools/analysis/reproduce.py check
```

Python imports `from analysis.results import set_seed, write_results` through the managed
runner. `write_results("primary.json", result_object, seed=37, inputs=[...])` runs at the
end of the actual scientific producer. R sources the helper through `MEDPAPER_ROOT`, sets
`set.seed(37)` before analysis, and calls `medpaper_write_results` with the same arguments.
For R arrays of length one use `I(...)` when the schema needs an array, not a scalar.
Activate the study's pinned renv environment explicitly when applicable; do not silently
install/upgrade the full medical package catalogue. Missing values are explicit JSON null;
never round statistics for storage or silently discard missing observations.

## Reuse without redoing the whole study

Replay copies the complete declared inputs and one producer into a temporary isolated
project, executes that producer, and compares actual output values, counts, seeds and
environment exactly. It ignores only the receipt's write time, not scientific timestamps.
It retains matched replay evidence under `.wf/`, not in the manuscript or submission bundle.
The writing-readiness gate rechecks source/output hashes and actual retained comparison;
a `verified=true` flag is insufficient. It does not rerun models at every manuscript stage.

After an input/producer change, rerun that producer and its true dependent producers in
their declared dependency order, then replay only their outputs. No filename-order guessing,
automatic reacquisition, whole-folder replays, data truncation or downstream-stage rewind.
For a manuscript/figure-format change reuse current result evidence without any refitting.
Declare imported project helpers as inputs so changes invalidate the right outputs.

An exact replay mismatch is a scientific implementation issue to investigate; do not
increase tolerance merely to turn a gate green. Methods with unavoidable numerical
nondeterminism need a reviewed, method-specific comparison before adopting this interface;
do not manufacture an exact proof. Reproduction establishes repeatability, not unbiased
methods, valid inference, complete data acquisition or publication fitness. Those existing
checks and human review remain necessary. Hashes guard accidental drift, not a malicious
local actor who controls both results and evidence.
