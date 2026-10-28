# Data, engine and review isolation (v1.18)

Read at intake/S04-S06, scientific revisions and repeat review. Two anonymized runtime
retrospectives motivated these changes; do not follow their study paths or copy their
acquisition scripts, author details, judgments, prose or results. Medical validity and
complete protocol-defined data remain required. Isolation is scoped to this study.

## Reference originals, don't duplicate them

If the user already supplied a local data root/file, register that exact authorized location:

```powershell
.\.venv\Scripts\python.exe tools/data_sources.py add --name local --path "<actual-authorized-absolute-path>" --why-file "<actual-request-utf8-file>"
.\.venv\Scripts\python.exe tools/data_sources.py show
```

The registry is project-local `.wf/data_sources.json`; no global active-study pointer or
automatic sibling-project search. File roots use `data:local`; directory roots use
`data:local/<relative-file>`. Unknown sources, traversal, escaping symlinks and another
study's root are rejected. Never register a workspace/parent directory to widen access.
Paths may be given without inventing a new work location: keep the user's chosen study
workspace and place declared outputs in its project namespace.

Python producers use `from analysis.datasources import open_data, source_path`:
`with open_data("data:local/input.csv", "r", encoding="utf-8") as handle: ...`.
`source_path` is for readers such as `ZipFile` that need a filename. Stream complete archive
members where possible; it creates no file. R sources `tools/analysis/results.R` and uses
`medpaper_data_path("data:local/input.csv")`. Both result writers declare the SAME logical
reference in `inputs`, together with actual local helpers/configuration.

`data_manifest.py sync` includes the complete registered file inventory in the raw hash
bundle. Count/pagination evidence may point to a hashed local raw receipt or a registered
`data:` file. Full totals, recounted rows, exclusions and source-record spotchecks still
apply. Availability of a reference does not prove full acquisition. Never synthesize a
source-total receipt or use a registration to excuse sampling/truncation.

Registered read handles reject write modes. This API and hash checking are not a hostile-code
OS sandbox: filename-based R/Python readers run with the host's rights. The executor must not
write originals or use hard links/junctions as supposedly independent writable copies. Hard
links share bytes; deleting one name does not isolate writes to the other names. We do not
change original ACLs/attributes or create aliases. Source mutation invalidates evidence.

## Reproduce true producers, not whole directories

`analysis/reproduce.py replay` still selects only stale/missing producer proofs; a newly
added script does not force an old producer to rerun. A downstream producer gets each
complete declared upstream result as input, including unchanged proven output. Declare
actual helper/config dependencies; do not guess shared-library consumers by function name.
An actual shared helper change may correctly affect multiple producers. An MD codebook that
is really parsed is an input; unrelated notes/acquisition transport code are not inputs merely
because of their directory. Don't hide scientific inputs by blanket suffix exclusions.

Local script/config/derived inputs are copied into an owned project-local
`.wf/replay_sandboxes/run_*/` directory. Registered original datasets are read in place and
copy zero dataset bytes. Default per-call local-copy budget is 200 MiB (`--copy-limit-mb`),
checked BEFORE copying a producer's input set. If legacy inputs exceed it, stop and convert
the real producer's data access in a scoped scientific revision; never silently raise the
budget, truncate, claim no copying while `copy2` remains, or change approved scripts ad hoc.

One replay runs at a time per project. Managed waits preserve the task's real exit status,
UTF-8 logs under the actual project's `.wf/processes`, and bounded stderr heartbeat. Timeout
is explicit (`--timeout`, default 3600 seconds per producer), not a fixed shell-idle cutoff.
Use the host's running-session/completion wait. Do not kill and restart a valid long task
just to edit code, nor poll sleep/logs every few seconds. Batch intended scientific changes
before a single affected replay. Equal results establish repeatability, not unbiased inference.

Normal failure, timeout and interruption clean task-owned sandboxes. A hard OS kill cannot
run `finally`; next replay inspects owned remnants. `reproduce.py cleanup` previews them;
`cleanup --apply` removes only exact registered directories with dead owner/recorded child
processes. Live, unknown, corrupted-owner and symlink/junction targets stay untouched.
Never sweep shared temp folders or kill processes by name. Historical proof files use
content-derived names so a later failed producer cannot overwrite a prior passing replay.

## Installed engine identity and maintenance

The clean ZIP carries `.medpaper-engine.json` hashes of its versioned engine files. Managed
entrypoints and builders refuse changed files. New study state records when this protection
is required; removing its baseline does not silently turn that study into a legacy one.
The global launcher verifies an installed baseline before overwriting engine files during
upgrade. User data, state, environments and unrelated helpers are preserved.

This detects accidental/unauthorized engine drift; it is not an OS tool-write interceptor or
cryptographic defense against someone controlling both source and baseline. Codex's actual
host permissions remain authoritative. Do not install Kiro-specific hooks or claim they run
here. Study executors must not edit tools/pipeline/reference/global skills or engine-owned
state to pass a gate. Report a minimal reproducible defect for explicit workflow maintenance.
This maintenance checkout may lack an installed baseline; never call that proof of immutability.

## Scientific methods, medical language and bounded review

For ordinary retrospective mining, keep initial plans, internal deviations and why the AI
changed its workflow under `01_protocol`, not as mandatory Methods/Discussion/cover-letter
boilerplate. State the actual research methods, material limitations and real exploratory/
post-hoc timing. Never turn post-hoc analysis into prespecification. Actual RCT/review or
selected-journal requirements remain applicable, based on current authoritative evidence.

Polish each authored section now; S22 harmonizes the journal version rather than doing the
first medical-language check. Existing diagnostic/acceptance covers supplementary Methods,
real table cells/notes, legends and extracted figure text as well as main prose. Warnings
about coined processing labels are prompts to explain clinical purpose and source units,
not a forbidden-word list. Preserve necessary algorithm definitions and model limitations.
Do not replace correct `analyzed`, `analyses`, `characteristics`, CRediT roles or approval IDs
merely to satisfy an imprecise lint. For table identifiers use `identifier_columns` with
actual header names or zero-based indices; quantities retain journal number formatting.

Independent review reads originals and may write ONLY the round's `report_destination`.
It must not change study inputs or engine state. If report writing is unavailable, the parent
persists the complete returned report verbatim; attach then archives its exact bytes/hashes.
No session-history scraping, truncated verdict substitution or main-agent invented review.
No extra default writer/reviewer agent or third-party ZIP is introduced.

Novel analyses are proposals, not automatic tasks. Judge whether they can change validity,
the main scientific story or publishability; batch accepted changes. Human coding questions
apply only when people really code/judge observations. Do not invent a two-person requirement
for deterministic extraction, fabricate human review, or confuse AI manuscript QA with human
record adjudication. A genuinely unresolved validity issue still requires author handling.

To retain an author decision across repeat OPTIONAL recommendations, the original independent
finding and the new one may carry `optional_method: true`, identical `proposal_id`, exact
`proposal_text`, and `proposal_basis` mapping actual scientific file paths to current SHA-256.
The first round still needs the real version-bound author adjudication. A later
`--author-decisions` JSON row can specify `reuse_from: {scope, round, finding}`. The engine
verifies the original closed round, unchanged actual report, author words, exact recommendation
and unchanged basis. No re-asking solely because wording/format changed. Changed evidence,
different proposals, objective errors or chained reuse cannot inherit a refusal; reference
the original actual decision. This metadata does not replace reviewer scientific judgment.

## Classify before expensive journal rebuilding

Plan with `rework.py preview --plan ...`, edit the owning source, then run
`rework.py classify` on actual bytes before full DOCX/PDF builds. This is read-only, with no
approval invalidation (exit 0 presentation / 3 meaning review needed / 2 scientific).
Uncertain figure layout may need a targeted preview before a true meaning review. Only then
build/finalize/render affected outputs and run real `rework.py check`; renew baselines only
through the existing observed source-build/visible-content path. Do not hand-edit baseline
JSON or use recapture to bless drift. No automatic S19 rewind or phase-tail replay.

Exact adjacent duplicate whole sentences/paragraphs can be removed without invented new
science. Nonadjacent repeated numbers, altered denominators/qualifiers and NEW disclosure
of a previously unreported result are not automatically cosmetic, even if its value exists
in result JSON. Use source/meaning evidence and the appropriate scientific owner. Keep the
accepted scientific master separate from journal-adapted files, including figure/supplement
reallocation. Preserve existing upload slots, real dependencies and frozen review lineage.
