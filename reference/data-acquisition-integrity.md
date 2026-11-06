# Full-data acquisition integrity

## The acquisition universe

`full_protocol_defined_universe` means every record that belongs to the source population
and filters fixed in S03. It is not necessarily every record held by the source. For a
pre-specified probability sample, nested case-control design, case-cohort design, or another
scientifically sampled study, the complete protocol-defined sample is the acquisition
universe. The agent may not make that universe smaller after seeing cost, size, runtime, or
results.

The default is a census of that universe. Convenience sampling, first-N retrieval, a shorter
date window, selected pages, selected sites, selected variables needed only for the first
model, or a "representative" subset chosen by the agent are not acceptable substitutes.

## What S04 must prove

`02_data/acquisition_manifest.json` is the machine-readable receipt. For each source it binds:

- the exact source locator, release or query and retrieval time;
- a source-reported total count preserved in a raw file;
- a count recomputed from the received raw payload or page payloads;
- expected, requested and received counts;
- pagination completion and the terminal cursor/response;
- hashes and byte sizes of every raw and acquisition-code file;
- reconciliation from the primary received count to the analysis dataset rows.

Supported count evidence is intentionally mechanical: delimited-file rows, JSON/JSONL array
lengths, an integer reached through a JSON pointer, or a raw text integer. For an API, preserve
the count response and every returned page under `02_data/raw/`. For a static file, the same
file may prove both the source total and the received count. Run:

```powershell
.\.venv\Scripts\python.exe tools\data_manifest.py init
.\.venv\Scripts\python.exe tools\data_manifest.py sync
.\.venv\Scripts\python.exe tools\data_manifest.py verify
```

`sync` calculates the raw/code inventory and raw-bundle hash; it does not invent source
counts or declare completion. Copy its exact raw-bundle hash into
`03_analysis/results/dataset_summary.json` as `source_hash`.

Evidence objects use these forms:

```json
{"path":"02_data/raw/cohort.csv","kind":"delimited_rows","header":true}
{"path":"02_data/raw/response.json","kind":"json_pointer_integer","pointer":"/total"}
{"path":"02_data/raw/page_001.json","kind":"json_pointer_length","pointer":"/records"}
{"path":"02_data/raw/records.json","kind":"json_array_length"}
{"path":"02_data/raw/records.jsonl","kind":"jsonl_rows"}
{"path":"02_data/raw/source_total.txt","kind":"text_integer"}
```

`received_count_evidence` is an array; for paginated responses its recomputed counts are
summed. `source_total_evidence` is one source-returned count receipt. Do not handwrite or edit
a receipt to make counts agree: preserve the verbatim API response, repository metadata,
static source file, or code-produced result of the exact source-side count query.

## Pagination and chunking

A page size, database chunk size, streaming batch, or partitioned download is allowed because
it changes transport rather than scope. The retrieval must continue until the source's
terminal condition is met. The sum of machine-counted page payloads must equal the preserved
source total. A fixed `max_pages`, silently ignored next cursor, or stopping after "enough"
records is truncation.

## Pilots and scientific sampling

A small connection/schema pilot is allowed only when it is excluded from analysis and a full
fetch follows. The limited code line may carry `MEDPAPER_PILOT_ONLY` only when the manifest
records all three facts: the pilot was used, its output was excluded, and full acquisition
subsequently completed.

Sampling that is part of the study design must be pre-specified in the protocol. A limiting
line may carry `MEDPAPER_PROTOCOL_SAMPLING` only when the manifest links it to that protocol
and explains the scientific sampling design. Because the agent must not silently convert a
census into a sample, the user must explicitly approve and record
`protocol_sampling_authorized=YES` before the sampling design can pass. Neither annotation
makes a partial convenience fetch acceptable.

## Genuine source restrictions

If licensing, authorization, provider export limits, source failure, or another external
restriction makes the full protocol universe unavailable, the agent must stop and ask the
user. It must preserve the provider's restriction receipt, explain the change in population
and likely bias, and still retrieve the entire accessible subset. Only the user's explicit
recorded `partial_data_authorized=YES` decision permits
`source_limited_user_authorized`. Time, tokens, context length, download volume, memory,
compute, or convenience are never external source restrictions.

The `data_acquisition_complete` gate is non-overridable. It runs before analysis, at the
second publishability decision, at manuscript assembly, and again before package/final audit
checkpoints so a partial or altered data foundation cannot silently reach submission.

## Actual complex joins: rows are not analysis units

Only `analysis_dataset.relationship="complex_join"` uses this path. Ordinary
`one_record_per_analysis_row` retains its existing received = analysed + excluded proof.
For a new/explicitly migrated 1.26 project, a narrative alone is insufficient. Describe
material unit-changing/selection checkpoints in the same manifest's `analysis_dataset`:

```json
{"relationship":"complex_join","n_rows":123,"planned_analysis_unit":"patients",
 "explanation":"actual join and exclusion logic",
 "join_steps":[{"id":"cohort_medications","operation":"join","relationship":"one_to_many",
   "explanation":"actual clinical and key relationship for this checkpoint",
   "inputs":[
     {"path":"02_data/raw/cohort.csv","unit":"patients","unit_key":["patient_id"],"join_key":["patient_id"]},
     {"path":"02_data/raw/medications.csv","unit":"medication records","unit_key":["medication_id"],"join_key":["patient_id"],"output_key":["medication_id"]}],
   "output":{"path":"02_data/processed/cohort_medications.csv","unit":"patients","unit_key":["patient_id"]}}]}
```

The number/path above illustrate shape, not facts or a ready-to-use receipt. Supply only
actual existing data paths, authorized `data:` references and actual column names. Include
`output_key` when an input unit maps to different column names in the output. Other material
operations may be `filter`, `aggregate` or `reshape`; sequential steps must connect through
their actual outputs. Do not duplicate original datasets or create every temporary merge
as a separate retained file just for an audit; choose scientifically material checkpoints.
If the existing data format lacks a reader, implement/test its real adapter rather than
handwriting a pass. Current readers cover CSV/TSV, JSON/JSONL, Parquet (its installed engine)
and explicitly named XLSX sheets. Counts read complete files/selected key columns in place.

```powershell
.\.venv\Scripts\python.exe tools/data_manifest.py audit-joins
.\.venv\Scripts\python.exe tools/data_manifest.py verify
```

`audit-joins` computes each input/output's actual row count, unique units, missing-unit rows,
source hash and input units absent from output; it does not execute the join or alter source
files. Declared one-sided unique join relationships reject actual duplicate keys. `verify`
independently recounts and detects modified/stale `observed` values; the final rows must match
the analysis summary. Planned versus final units must be explained and reconciled with the
existing analysis contract. Missing matches are not automatically clinical exclusions, and
key/row agreement does not prove the scientific validity of a join or a cohort definition.
Record the actual exclusion/denominator meaning in existing provenance/protocol notes and
retain normal scientific review. No patient keys are written to the count evidence.

Completed older pins keep their historical proof. An explicit new join_steps audit can be
used without rewinding the project; genuine changed science still follows existing scoped
owner/review rules. No extra agent, full-analysis replay or generic data-join report is added.
