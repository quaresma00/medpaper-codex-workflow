# Source-aligned incremental validation

Read for composed submission documents, discovered dependencies, journal reorganisation or
Word postprocessing. Keep the existing 25 stages and scientific/human approval boundaries.

## Separate scientific facts from presentation

Science uses the approved protocol/results/master. Journal presentation uses the derived
`08_submission/integration/` manuscript, optional artifact plan and actual upload manifest.
New journal workspaces copy the approved artifact plan; renumbering, moving displays to
supplements and journal heading/legend layout belong there, not in the scientific master.
Legacy studies may add this derived plan in their existing scoped journal revision; do not
replace their edited integration workspace just to obtain the new plan. Real scientific
changes still need scoped source correction and renewed S19 approval.

Managed builders persist observed inputs, output bytes/content, direct entrypoints and
parameters in `.wf/build_receipts.json`, even outside a feedback round. This is not an OS
file-I/O tracer: custom scripts must explicitly register every real input/output. Never
forge receipts for a manually edited document. Each upload declares `source_files` and, for
a composed source, `build_entrypoint` (or `source`). Do not substitute a guessed role default
for the actual combined Markdown. Existing role defaults are legacy fallback only.

For a discovered consumer before writing it:

```powershell
.\.venv\Scripts\python.exe tools/rework.py depend --input 08_submission/integration/combined.md --output 08_submission/integration/preview.md --why "This preview reads the already affected combined source and is a true consumer."
```

This augments the same round, preserves verbatim feedback and invalidates its check proof.
It cannot authorize frozen-science edits from S24 or analysis edits from a presentation task.
Use `mark --changed-file` for actual changes and `--checked-file` for unchanged inspected
sources. Do not modify a correct source merely to provide a changed-file receipt.

## Explicit presentation migration

Before the next round's edits, `polish.py snapshot --new-round` creates a round-bound snapshot
and retains the previous facts index under `.wf/polish_snapshots/`. It requires a different
active round and unedited current-round sources. `--force` cannot reset a failed same-round
comparison. Legacy snapshots remain readable; do not discard historic evidence.

Only when moving/renumbering content, declare `integration/presentation_map.json` with:
`snapshot_id`, optional `renumbering` such as `{"Figure 1":"Figure S1"}`, and `moves` with
`from`, `to`, exact pre-edit `text`, and optional exact current `after`. Both passages must
exist in their real source/destination. Numerical facts/P values/citation identities must
survive at package level, and the moved passage must preserve its own facts. The actual
journal artifact plan and reference checks still apply; a map is not a waiver.

An optional `additions` entry (`source`, `to`, `text`) can describe already-approved method
detail only when that exact passage comes from a currently hash-bound scientific-freeze
source. Unapproved/invented methods or results are not presentation additions. All semantic
interpretation still needs reader/editor review; token matching cannot certify meaning.

Without an explicit map, ordinary polishing retains its per-file preservation checks.
Main and supplementary legends may use separate sources; declare actual `legend_scope`
(`main`, `supp`, `all`) per upload and pass it to the Word builder. Do not force all
supplementary legends into the main manuscript if the journal requires separation.

## Incremental checks and final Word chain

An unrelated layout/administrative/meaning-preserving revision does not reacquire/replay
analysis or rehash the entire raw population. The unchanged scientific sources still bind
to writing/science freezes; unplanned raw/manifest drift blocks the round. A real scientific
input/result change requires its original integrity checks. Exact round check proofs can
be reused for 24 hours only with unchanged files/rules/configuration/decisions/evidence.
Reusing never extends freshness. S13/S25 live checks are not skipped. Close verifies the
proof and final drift rather than redoing the entire study; new evidence is revalidated.

Freeze sources -> build -> necessary Word layout repair -> `build_docx.py finalize` ->
render the final file -> capture content baseline/portal -> user confirmation/freeze.
Postprocessing uses staging, checks content equivalence and preserves the old file on
failure. Content identity includes headers, footnotes/endnotes, tables and embedded media,
not just the main paragraph strings. Pure whitespace/page-number layout may differ; text
or scientific-image drift may not. Word cleanup disables automatic picture compression.
Reference numbering delimiter, when explicitly configured by the journal, is inspected in
the actual Word text; unobservable numbering needs Word/CSL inspection, not an invented PASS.

Managed Pandoc/R jobs have timeouts, task-owned PID/status and full `.wf/processes/` logs.
Check exit codes and stop on failure before downstream capture. Never terminate unrelated
Office processes or save previews over approved releases. Ignore Office locks as uploads;
the release copies exactly manifest uploads, not the entire folder. Arbitrary Office/third-
party automation still needs its own bounded, ownership-safe adapter; do not imply the
managed runner controls an already-open user's Word instance.

`readiness.py facts` defaults to a bounded display-only preview and writes the complete
resolved catalog to `.wf/resolved_facts.json`. Query `--fact-id`, `--fields`, `--offset` and
`--limit`; `--full` is explicit. This does not sample analysis data or reduce evidence.
Use bounded PNG previews for screening, original-size critical-page inspection for final QA.
Report generated/content-checked/layout-checked/user-approved/submitted as distinct states.
Generating files is never a claim of actual journal submission.
