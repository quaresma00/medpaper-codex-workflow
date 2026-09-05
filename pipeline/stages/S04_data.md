# S04 - Acquire data, codebook, provenance

## Purpose
Get the real data in place with an auditable trail, and describe it before analysing it.

## Procedure
1. Execute the retrieval steps from `02_data/acquisition_plan.md`. Raw files land in
   `project/02_data/raw/` and are then treated as read-only. Never edit a raw file.
2. Any cleaning, recoding or merging happens in a script under `03_analysis/code/`
   that writes to `02_data/derived/`. No manual spreadsheet edits.
3. Write `project/02_data/provenance.md`: where each raw file came from, the URL or
   query, the retrieval timestamp, the release/version, the file hash, the licence, and
   who is allowed to see it.
4. Generate the codebook. For every variable: role, type, units, level meanings,
   range or quantiles, and missingness. If a coded variable's level meanings are unknown,
   mark it `[NEEDS DICTIONARY]` - do not infer what `2` means.
   Write it to `project/02_data/codebook.md`.
5. Dump the machine-readable summary from executed code to
   `project/03_analysis/results/dataset_summary.json`:
```json
{
  "n_rows": 0, "n_cols": 0,
  "variables": [{"name": "", "role": "", "type": "", "missing_pct": 0.0}],
  "missingness": {"any_missing_rows_pct": 0.0},
  "study_period": {"start": null, "end": null},
  "source_hash": "sha256 of the raw input(s)",
  "built_by": "03_analysis/code/<script>",
  "built_at": ""
}
```
   Include the study period here even if it is just calendar years: every number that
   later appears in the manuscript must exist in a results JSON, dates included.
6. Delete scratch files from `project/temp/`.

## Outputs
- `02_data/codebook.md`
- `02_data/provenance.md`
- `03_analysis/results/dataset_summary.json`

## Hard rules
- If the data contains identifiers, de-identify before any of it reaches a prompt, and
  record what was removed in `provenance.md`.
- No plotting in this stage.
- Never hand-type a count into the codebook; read it from the summary JSON.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "n=<rows>x<cols>; source=<x>; blockers=<missingness/dictionary gaps>"
```
