# Quality-preserving execution

Use this at S06/S07, when collecting feedback, and when producing a journal package.
Keep the 25 stages. A checkpoint does not authorize reducing scope or ending an unblocked task.

## Before writing: S06

At S05, transient diagnostic plots may be used to evaluate fit, bias or data quality via
`temp/diagnostics/`; keep durable numerical diagnostics in result JSONs and conclusions in
the analysis log. This does not authorize manuscript/production graphics before GO.

`01_protocol/analysis_contract.json` holds the final scientific rules in nine fields:
`population_and_period`, `eligibility`, `unit_and_denominators`, `outcomes`,
`missing_duplicates_outliers`, `validation_and_adjudication`, `models_and_sensitivity`,
`exploratory_vs_confirmatory`, `evidence_boundaries`. Use substantive text or structured values;
for inapplicable items give a reason. Do not invent a validation exercise or label post-hoc
choices as prespecified. Protocol v1 and its deviations remain the historical record.

`01_protocol/study_facts.json` holds four short statements: `clinical_question`, `main_finding`,
`clinical_relevance`, `cannot_claim`, plus `result_sources` pointing to executed result JSONs.
These are concise internal facts, not a prematurely drafted abstract. The clinical story must
be intelligible in three or four sentences. A passive report count is not an incidence rate;
an association is not a causal effect. Missing clinical adjudication cannot be supplied by AI.

After the existing convergence and GO decisions, run `tools/manuscript/readiness.py freeze`.
Its hashes bind the contract, story, protocol, acquisition manifest, analysis code and results.
`writing_ready` fails on later drift. Return to the scientific owner and refreeze after a real
change. An existing project's new fields must be reconstructed from actual evidence, never
backfilled with invented facts or discarded old artifacts.

## Display prototypes: S07

Create low-cost previews under `01_protocol/prototypes/`: Markdown/CSV tables and low-resolution
figures. Retain full underlying data; low rendering resolution never means sampling the data.
Use `artifact_plan.json` as the one display inventory. Every planned main/supplementary display
has one primary clinical question. Reuse the prototype's script and semantic layout at S10/S11.
Do not build Word, formatted workbooks or journal-specific TIFF files at this checkpoint.

Record `01_protocol/display_review.json` with `items`, one per planned display:

```json
{
  "id": "Table 1",
  "preview": "01_protocol/prototypes/Table1.md",
  "preview_sha256": "<computed SHA-256>",
  "source_hashes": {"03_analysis/results/baseline.json": "<computed SHA-256>"},
  "question": "The single clinical question this display answers",
  "reader_explanation": "What the reviewer understood from the display and its caption alone",
  "denominator_units_missingness": "Actual population, denominator, units and missing-data labels checked",
  "encoding_overlap": "Meaning of colours/symbols or non-exclusive categories; applicability explained",
  "layout": "Row/column hierarchy, expected physical width and orientation",
  "reviewer": "Actual reviewer identity/role; label an AI reader simulation honestly",
  "verdict": "PASS"
}
```

Open each preview. A target-specialty reader should be able to explain it in roughly one minute
without reading Methods. A documented agent simulation may screen readability; it is not a
human clinician's validation. Ask for clinical judgment only when it is necessary to resolve
meaning. Do not add a mandatory user-approval stop for routine layout choices. Record defects,
fix the preview, then record its actual hash. `tools/manuscript/readiness.py displays` checks
coverage, source binding and substantive reader accounts; it cannot prove comprehension itself.

Use natural-language labels, explicit denominators/units/missingness, restrained precision,
non-exclusive-category footnotes and readable physical sizing. Engineering metadata belongs
backstage. Full regular expressions or implementation specifics belong in a supplement only
when scientifically needed, not merely because they exist in code.

## Production and Tavotto

At S10/S11 reuse approved semantics. Prefer vector PDF plus a PNG preview; create TIFF only
when the chosen journal requires it at S23. Use co-located literal filenames for each Matplotlib
script and PDF under `05_figures/out/` (legacy separated scripts remain readable). Keep Python
as the source of truth. For user-facing Matplotlib figures use the installed `tavotto-figure`
skill and its desktop handoff after rendering and visual QA; resolve the skill's actual path.
The user's desktop-first instruction overrides the skill's default embedded canvas. Read the
handoff JSON: success requires `ok: true`, `parameterizable: true`, `launch: "desktop"`.
Call MCP health only when using MCP capabilities; lack of an authorized embedded canvas must
not block desktop handoff. Report structured desktop failures and the recovery step. Never
substitute a browser. Nonstructural visual changes stay in Tavotto overrides; data, axes and
artists change in Python. Store journal-specific scripts/overrides/exports in integration,
preserving the frozen scientific figures. Internal diagnostics do not require desktop handoff.

## Feedback and incremental work

Read `rework-routing.md`. `batch` collects without rewinding/building; `seal --why` records
the user's end-of-batch/apply-now instruction and activates scoped work at the review checkpoint. A complete request to implement
the supplied feedback already permits `batch --sealed`; do not invent another confirmation.
Deduplicate identical requests; merge overlapping acceptance criteria without losing a request.
New feedback reopens collection. Do not mark/close a collecting batch.

`rebuild_files` is the file dependency closure, not all files after a stage number. Bundle
manifest items should declare `source_files` for their actual inputs; this is especially
important for figure/table copies, combined supplements and blinding variants. Source paths
are project-relative. If an input affects a document, list it even if its role has a default.
An administrative edit must propagate to every document actually containing that fact; a
layout edit should touch only that file. Control-only maintenance uses its own deterministic
tool (for example `package_review.py sync-evidence`), with no artificial human revision round.
Result JSONs may declare `source_files` plus their `script`/`built_by` producer. With legacy
unmapped data inputs or analysis helpers, the closure conservatively includes all analysis
results; do not infer that absent dependency metadata means no downstream effect. This list
is a rebuild/recheck plan, not permission to overwrite user-edited or frozen files blindly.
The engine now enforces output scope and protects unrelated files. Shared builders need a
selective output option; otherwise editing one shared script conservatively affects its
declared consumers. Field-level pruning is not supported: never infer independence from a
missing JSON-field mapping. Use the saved `validation_stages` without navigating backwards.

## Medical reader-facing acceptance

Benchmark actual medical prose/tables/figures, not only display counts. Keep one primary
clinical message per display, natural clinical labels, interpretable reference groups,
explicit units/denominators and appropriate uncertainty. Store the five-field
`reader_contract` (population, comparison, measure, denominator_and_units, interpretation_limit)
inside each artifact-plan entry. Resolve abbreviation placement at S07 so S17 does not
deliberately undo and rebuild table footnotes. Methods is concise design-adapted prose;
Results follows the clinical question, not scripts or every analysis block. Retain null
prespecified findings and clinically required model-performance/diagnostic evidence.

Technical paths, receipt IDs, QA scores, pipeline states and JSON schemas stay backstage.
They may be useful in internal notes but are not manuscript headings, figure annotations
or table columns. Preserve scientifically necessary definitions and limitations in normal
medical language. A value merely found somewhere in result JSON is insufficient: verify
its endpoint, population, comparator, units, denominator, time window and adjustment set.

S18 reads actual rendered figures as well as the prose and tables. Use
`readiness.py review-inputs` and bind its hashes inside the existing independent report,
alongside Reader comprehension and Medical presentation findings. No second report or
additional mandatory agent is introduced. Automated coverage cannot certify human-like
understanding; the independent reviewer must actually inspect the files and explain defects.

Editorial basis: ICMJE, Preparing a Manuscript for Submission to a Medical Journal
(checked 2026-09-26): https://www.icmje.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html .

Before expensive production record `rework.py build --scope full --why <batch purpose>` or
`--scope targeted --why <changed files>`. After two full builds identify the unstable input,
freeze it and switch to targeted corrections. This is not a cap on requested revisions or QA.
Run cheap checks first, content checks next, then one complete overview plus first/last,
changed and structurally critical pages in detail. Inspect unchanged pages again only when
new evidence warrants it. Keep summaries in the existing round and stage notes, not new dossiers.

## Journal submission

At S20 freeze `08_submission/submission_requirements.json` from current official instructions:
`article_type`, `required_upload_roles` (a list), `blinding`, and `word_count` with
`include_sections`, `limit`, `abstract_limit`, `source`. Use null limits when the guide is silent
and record that fact in `source`; do not invent journal limits. Optional `section_aliases` maps
actual DOCX headings (lowercase) to standard section names. Freeze the actual upload roles,
not a generic list of every possible submission asset.

At S21 collect only required administrative facts in one request, reusing answers already given.
`00_input/author_info.json` is the sole administrative source; do not duplicate it as a second
editable submission-facts file. Derive title page, declarations, cover letter and portal fields
from it. Missing/unknown ethics, funding, author or conflict information must not be inferred.
AI disclosure remains user-controlled under the standing instruction.

At S23 write `bundle/manifest.json` with each upload's `role`, `file`, `required_by` and
`source_files`. Keep renders, human handoff checklist and QA under `08_submission/evidence/`.
After final DOCX construction run `tools/manuscript/submission_fields.py`. It extracts the actual
DOCX title, abstract and keywords, computes counts using the recorded section scope, and binds
`portal_fields.json` to final bytes plus the administrative source. It refuses unresolved track
changes or over-limit text. Its explicit Unicode tokenizer is not advertised as Word's UI
count; if the journal/portal requires Microsoft Word's own count, check that in Word and
resolve the discrepancy before confirmation. Do not use draft Markdown counts as final counts.

At S24 after explicit user confirmation, record the OK decision first and run
`tools/package_review.py freeze`. This creates an upload-only SHA-256 identity and a read-only
`08_submission/releases/<freeze_id>/` with the exact files plus `upload_manifest.json`.
The working bundle is retained for revisions. Read-only attributes prevent accidental edits,
not deliberate tampering; `verify` checks both file content and attributes. Any changed upload
requires a new approval/release. Evidence refreshes do not change upload identity. Changes to
official requirements do require targeted compliance revalidation and a current audit context.

At S25 the independent reviewer reads the release files and official instructions. Its verdict
must bind both `Freeze ID` and the current `Audit context ID` from `evidence_manifest.json`.
Audit an unchanged release/context at most once unless a material defect warrants re-review.
If delegation is unavailable, make a clearly labelled local preliminary review and preserve
the pending independent audit; never relabel the main agent as independent or issue final PASS.
Before actual upload run `package_review.py verify`. Preview/portal working copies must never
be saved over the release. Portal-only actions and the final submission remain user-controlled.

## Reference identity

Verification schema 3 binds PMID, DOI, PMCID, the complete ordered author list, collective names,
given names, initials and suffixes to raw PubMed records. BibTeX protects collective authors as
literals; comma-form personal names retain surname particles. Export checks compare complete
BibTeX/RIS output, not just citekey counts. Identity verification does not establish that a
paper supports a claim: read the relevant source at S14-S16 and include support/limitations in
existing deep-read notes. Verify rendered author names and numbering during final Word QA.

S13 and S25 always perform a fresh independent live check, never trusting the reusable cache.
Other gates reuse hashed live XML for at most 24 hours when every current identity
still matches; changed identities or expired/invalid evidence require a fresh request and fail
closed on network failure. `status` never triggers network checks. Ordinary `check` prints
failures plus a summary; `--full` reveals diagnostic detail. These changes save repeated work
without allowing a fabricated boolean or stale record to become evidence.

Technical format references: NCBI PubMed XML DTD (retrieved 2026-09-26)
https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_250101.dtd and CSL name variables (checked 2026-09-25)
https://docs.citationstyles.org/en/stable/specification.html#name-variables .
