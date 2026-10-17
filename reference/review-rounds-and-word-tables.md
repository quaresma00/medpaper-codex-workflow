# Independent review rounds and native Word tables

v1.13: first review and changed science use these rounds. Proven post-approval presentation
changes follow `content-aware-amendments.md`: no new review round or re-confirmation, but
actual scoped checks/visual QA and an explicit presentation delta.

Adapted from user-maintained Kiro v1.8.1, commit
`1c49c93b9899368811849867ae382ed86c691229` (retrieved 2026-10-17).
Codex uses its actual subagent API, project paths, scoped revisions and build receipts;
Kiro agent names/configuration are not executable Codex APIs.

## One round, one report to the user, one question

S18 starts manuscript M001, delegates once and attaches the genuine report before edits.
S19 applies safe findings at their source, validates true dependants, records corrections
and unadopted reasons, closes, reports once and asks whether another round is needed.
S24 does the same for the actual journal package. Only the explicit user no-further-review
answer records approval for the current round; generic continuation is not approval.
No review ZIP is generated or required. Installation/distribution ZIPs are unrelated.

Use `review_round.py start|attach|close|decide|status --scope manuscript|package`.
Use `--delta` on a requested later round. Added/deleted inputs and dependency closure are
tracked; uncertain dependency parsing widens to full reading, not silently skipped checks.
The complete current paper remains available to the reviewer. For material scientific fixes,
obtain actual independent revalidation of current inputs and attach with `--revalidation`;
preserve the original report. Cosmetic changes need current local QA, not invented re-review.
If sources drift during reading, recover the actual unchanged version or explicitly restart
the failed review with `review_round.py restart --scope <scope> --why <specific-reason>`;
the abandoned round/report remains as history. Never relabel old evidence with new hashes.

The main executor may reject a preference with a concrete scientific/journal rationale.
It cannot waive objective errors, fabricate evidence, guess author facts or approve itself.
Codex read-only instructions are not an OS sandbox: verify input versions before and after
review and protect scientific freezes/releases separately. All user feedback stays in
`rework.py` scoped revisions; review rounds do not rewind stage history.

Existing legacy review archives/freezes remain verifiable. New freezes bind the actual
approved round and its immutable report, not a shared history file that later package rounds
would change. Do not delete user archives or require analysis replay solely for an upgrade.

## Native Word tables only when required for the selected journal

Scientific XLSX remains the source; do not paste screenshots or convert pipe tables via
Pandoc. Supply a project-local JSON, usually in `08_submission/integration/`:

```json
{"tables": [{"id": "Table 1", "file": "04_tables/main/Table1.xlsx",
             "sheet": "Table1", "header_start": 2, "header_end": 2,
             "body_end": 20, "orientation": "auto"}]}
```

Use actual sheet names/ranges, not these example row numbers. `body_end` can be omitted only
when one unambiguous fully ruled last-body row exists. Captions default to cell A1; optional
`caption` overrides in the journal layer. Titles and notes remain outside the Word grid.
Merged headers are preserved, repeat across pages, and cannot cross header/body boundaries.
No numeric cells or extra sheets are silently ignored: each intended sheet is declared;
ambiguous data/footnote boundaries fail for explicit resolution. Formula sources require
real calculated values; never publish an unexecuted formula as a clinical result. For numeric
XLSX display formats such as percentages, decimals and dates, provide explicit approved
display text (as the standard medical table writer does). Conversion refuses ambiguous raw
storage values rather than silently turning 12% into 0.12 or changing decimal precision.

Pass `--tables-json <path>` to `build_docx.py build` with the actual journal Markdown entry
and appropriate `--kind manuscript|tables`. All sheet sources/specs and conversion code are
recorded as real build dependencies. Declare the same `source_files` in upload manifest.
Supplementary tables use a separate table document, not supplementary-Methods prose.

Explicit cell-level top/bottom borders produce 1.5/0.75/1.5 pt rules, no verticals or internal
grid. Each table starts its own next-page section. `auto` uses column count/estimated width;
`portrait` or `landscape` overrides follow actual journal requirements. No auto-shrinking
font to force a wide table onto a portrait page. Native table audits check the actual OOXML,
and final Word rendering checks wrapping, split headers, note placement and legibility.
Mixed orientations survive final cleanup; shared PAGE footers do not restart numbering.
The final table ends in its own orientation without an added blank portrait page; if adding
subsequent narrative, start a portrait section first. Journal-sourced page-number rules
override the default continuous footer via `docx_style.json.page_numbers`.
Numeric bibliography leads default to one ordinary space, not TAB or hanging indentation;
an actual journal rule may set `reference_separator: "tab"`. Punctuation/citation identity
is preserved. This is separate from `reference_number_separator`, which controls label
punctuation such as a period or bracket. Verify the actual final reference text, not config alone.

## Actual-file checks and reviewer reading copies

After final cleanup/render/portal fields, run `tools/submission_qc.py measure`. It checks
actual listed uploads, native-table XML, fonts/controls/legends, continuous PAGE fields and
actual final-DOCX portal/typed limits. The marked checklist block stays under `evidence/`,
never becomes an automatic journal upload. Visual acceptance remains a real separate task,
not an automatic PASS from file generation. Missing/empty manifests fail closed.
`verify` reuses unchanged measurements bound to current source and converter rules; it does
not reread raw clinical data or redo analyses. Changes invalidate only this relevant evidence.

`review_round.py start` generates complete DOCX/XLSX text copies with source and extraction
hashes. `reader-copies --scope package` refreshes them before S25. Workbook copies name every
sheet. Keep copies local/backstage, do not print whole extracts to the conversation. Actual
rendered pages/figures are mandatory for layout/visual review. A text extraction cannot prove
that a table fits a page or a figure is understandable.
