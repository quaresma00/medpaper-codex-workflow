# S04 - Acquire data, codebook, provenance

## Purpose
Get the real data in place with an auditable trail, and describe it before analysing it.

## Procedure
1. Execute the full retrieval from `02_data/acquisition_plan.md`. Retrieval scripts and exact
   queries live under `project/02_data/acquisition/`; raw payloads and source count/page
   receipts land in `project/02_data/raw/` and are then treated as read-only. Never edit a
   raw file.
   - Request the source-reported total first, then acquire every record in the
     protocol-defined universe. Exhaust all pages/cursors and retain the terminal response.
   - Never introduce a convenience cap such as SQL `LIMIT`/`TOP`, `head()`, `sample()`,
     a literal first-N slice, `nrows`, a fixed maximum page count, or a narrower date range.
     A page size is not a cap only when the code continues to the terminal page.
   - A pilot is allowed only to test connectivity/schema. Mark the relevant code line
     `MEDPAPER_PILOT_ONLY`, exclude pilot output from analysis, and complete the full fetch.
     Protocol-defined scientific sampling must already exist in S03 and is marked
     `MEDPAPER_PROTOCOL_SAMPLING`; neither marker can excuse incomplete acquisition.
2. Any cleaning, recoding, post-acquisition eligibility exclusion or merging happens in a
   script under `03_analysis/code/`
   that writes to `02_data/derived/`. No manual spreadsheet edits.
3. Write `project/02_data/provenance.md`: where each raw file came from, the URL or
   query, the retrieval timestamp, the release/version, the file hash, the licence, and
   who is allowed to see it.
4. Generate the codebook. For every variable: role, type, units, level meanings,
   range or quantiles, and missingness. If a coded variable's level meanings are unknown,
   mark it `[NEEDS DICTIONARY]` - do not infer what `2` means.
   Write it to `project/02_data/codebook.md`.
5. Create the machine-verifiable acquisition proof:
```powershell
.\.venv\Scripts\python.exe tools\data_manifest.py init
# Fill the protocol population, source entries, count evidence, pagination and reconciliation.
.\.venv\Scripts\python.exe tools\data_manifest.py sync
```
   Write `project/02_data/acquisition_manifest.json` using the generated template. For every
   source it must bind these facts to raw, hashed receipts:
   - exact locator/query/release and timezone-aware retrieval time;
   - `source_total_expected`, `records_requested`, and `records_received`;
   - machine-countable total evidence and received-payload evidence;
   - pagination applicability, pages received, terminal-page status, and empty final cursor;
   - `complete: true` and `truncation_applied: false`.

   `requested_scope` is always `full_protocol_defined_universe`: this means the whole set
   defined at S03, including the whole pre-specified sample when sampling is the actual study
   design. It does not mean "all records on earth" and does not permit a convenience subset.

   If the source itself blocks part of that universe, preserve machine-readable evidence of
   the external restriction and first ask the user. Only an explicit user response may be
   recorded as:
```powershell
.\.venv\Scripts\python.exe tools\wf.py decide partial_data_authorized YES --why "<what the source blocks, what remains available, and the scientific consequence>"
```
   Then use status `source_limited_user_authorized` and still acquire the entire accessible
   subset. Time, tokens, context, download size, compute or convenience are not source limits.
6. Dump the machine-readable summary from executed code to
   `project/03_analysis/results/dataset_summary.json`:
```json
{
  "n_rows": 0, "n_cols": 0,
  "variables": [{"name": "", "role": "", "type": "", "missing_pct": 0.0}],
  "missingness": {"any_missing_rows_pct": 0.0},
  "study_period": {"start": null, "end": null},
  "source_hash": "exact raw_bundle_sha256 printed by tools/data_manifest.py sync",
  "acquisition_scope": "full_protocol_defined_universe",
  "acquisition_status": "complete",
  "built_by": "03_analysis/code/<script>",
  "built_at": ""
}
```
   Include the study period here even if it is just calendar years: every number that
   later appears in the manuscript must exist in a results JSON, dates included.
   Reconcile its `n_rows` against records received and explicit post-acquisition exclusions
   in `acquisition_manifest.json`. Complex joins require a substantive reconciliation note.
7. Run the standalone verifier, then delete scratch files from `project/temp/`:
```powershell
.\.venv\Scripts\python.exe tools\data_manifest.py verify
```

## Outputs
- `02_data/acquisition_manifest.json`
- `02_data/codebook.md`
- `02_data/provenance.md`
- `03_analysis/results/dataset_summary.json`

## Hard rules
- If the data contains identifiers, de-identify before any of it reaches a prompt, and
  record what was removed in `provenance.md`.
- Do not analyze a pilot, partial page set, convenience sample, preview export or silently
  narrowed query as if it were the complete dataset.
- The data-completeness gate re-counts raw evidence, verifies file hashes and pagination,
  scans acquisition code for common caps, and is not waivable with `--force`.
- No plotting in this stage.
- Never hand-type a count into the codebook; read it from the summary JSON.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "n=<rows>x<cols>; source=<x>; blockers=<missingness/dictionary gaps>"
```
