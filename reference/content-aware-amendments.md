# Content-aware revisions and selected-journal production

Adapted from user-maintained Kiro 1.9.0, commit
`f806de6bea8e15c8adfbaaf1f99c54fc8828be56`, retrieved 2026-10-17.
Read for post-freeze edits, S20-S25 production, author final copies or engine migration.

## Preserve approval for proven presentation changes

Initial S19/S24 review and real scientific changes still require actual independent review
and explicit user approval. Do not manufacture the first approval. For a version already
approved/frozen, a source-owned presentation revision uses `rework.py batch --sealed`,
`check`, `mark` and `close`; no extra review round, S19 rewind or confirmation. Report the
actual changes once. The active batch blocks advancing while validation is pending.

Use `journal-format` for a same-journal rule/CSL/heading/spelling/layout correction. Use
`journal-switch` for another journal; legacy `journal` is an alias. A switch replaces the
derived journal workspace only and requires its actual journal decision and normal package
review, not new scientific analysis or an automatic complete-stage replay. Do not use a
format kind to change journal identity or research facts.

The batch keeps a pre-edit content snapshot. At `check`, unchanged canonical text/Office
content permits presentation classification. Word order, quantities, units, identifiers,
cell coordinates, references and clinical qualifiers remain material; equal number bags
do not prove equal meaning. Data/model/reference-identity changes cannot be cosmetic.
The saved `content_classification` identifies all changed files and any barriers.
For uncertain paraphrases, read actual before/after material and supply an executor assessment
with `rework.py check --meaning-review <JSON>`. This is not another independent subagent.

The JSON names `files` (current project-relative SHA-256 map), `baseline` (corresponding
pre-edit SHA-256 map), `verdict: UNCHANGED_SCIENCE`, and substantive observations for
`population_comparison`, `endpoints_time_units`, `direction_negation_uncertainty`,
`methods_claims`, `rendered_displays`. Include only files listed under `needs_review`.
Read actual files/figures; never fill generic PASS observations. Numerical/citation/negation
or design-claim changes cannot be overridden with this assessment. Genuine science must be
amended at its real source and renewed at S19, without replaying unaffected stage tails.

Once actual scoped checks pass and all items close, `.wf/presentation_deltas.json` records
the old/new file chain and the real validation round. The original scientific approval,
review report and freeze stay intact. New upload bytes get a new read-only release with
its presentation lineage; never overwrite the old release. Prior scientific independent
reading is not falsely described as a reading of new layout. Actual changed-file content,
format, cross-file, blinding and visual checks remain required. New clinical facts are not
an amendment, even if only a word or decimal changed.

Journal-specific edits still belong in `08_submission/integration/`. Do not edit the mother
manuscript merely to satisfy one journal. An explicitly requested, meaning-preserving master
copyedit can use a validated presentation amendment, preserving its historical freeze rather
than making the author approve the same science again.

`mark --deleted-file <path>` proves an actual removal from the batch baseline; never list a
missing file as changed or checked. Deleting scientific content requires explicit migration/
inventory reconciliation, not an automatic no-facts shortcut. Preserve user material unless
the user's request actually authorizes its removal. Drift diagnostics report all locations.

## Deterministic builds and honest provenance

Managed DOCX/XLSX writes normalize ZIP timestamps and known core-properties timestamps.
Clinical dates, authors, cell values, image bytes and arbitrary JSON date fields are NOT
discarded. Managed R PDF/TIFF output normalizes its container metadata without refitting.
PDF uses a real parser, not byte replacement that can invalidate xref offsets. Office
content fingerprints ignore known volatile metadata, not every invisible or sensitive field.
Blinding is checked separately. Immutable approved release files are never normalized in place.

Internal QC/notes/evidence do not alter upload identity. A same-content rebuild may reuse
approval, but a changed official rule must still be validated against actual files. A derived
manifest is not exempt from its substantive input/inventory checks merely because it contains
a timestamp. Do not silently renew failed provenance or turn renewable evidence into trust.

## Typed journal fields drive actual outputs

Keep canonical Markdown headings and comma-separated source keywords. `target_journal.json`
may specify sourced `main_text_headings` (canonical body section -> actual label),
`keywords` (`min`, `max`, `separator`), `blinded_main_manuscript`, `spelling`, `number_format`.
Missing bounds are null/unspecified, not invented. Existing typed `submission_requirements`
retain the article-specific word/display caps; at or below 100% of a real cap passes. Near-cap
Word/portal count differences are a warning and a user-controlled portal check, not a hidden
97% hard limit. No fixed paper lengths or reference/display minima are reintroduced.

Spelling defaults to American English for NEW studies. Old unconfigured studies retain
their text. Journal spelling overrides the study setting; US/British prose prefixes are
accepted. `number_format` supports `p_space`, `minus: unicode|hyphen`,
`thousands: ','|''|'thin'`, `interval: ' to '|'–'`, and optional `leading_zero`.
Never round, change units, replace identifiers, alter author/institution names in official
administrative records, or rewrite bibliographic facts to satisfy a style setting.

Builders record actual profile, sources and local patch inputs. Word, table display strings
and R human-readable labels apply these settings; R exposes `medpaper_label` and
`medpaper_number` and preserves custom scales/data/group labels. Final Word section counts
resolve actual journal labels. Double-blind review files include supplements and hidden
metadata; remove author lines in the derived source, never delete legitimate reference names
indiscriminately or silently guess anonymized clinical institutions.

Use `integration/csl_patch.json` (`source`, `changes` of CSL `selector`/`attributes`) or explicit
`build_docx.py --csl-patch`. The staged style is local; the shared CSL/reference library is
unchanged. `csl_check.py --docx ... --examples ...` compares a test bibliography made from
the SAME real official-example entries to `source` plus `examples: [{number, expected}]`.
Do not compare unrelated article text or invent references to make a format example compile.

S12/S17 check first-citation numbering, exact table titles and explicitly declared panels.
Continuous Methods/Results/Introduction/Discussion prose is the default; a justified design/
journal exception is not permission to deliver an engineering report. Baseline producers
can use Python/R `baseline_counts` to export every category (both binary levels), counts by
group, missingness and explicit denominators. Do not fabricate an unexported complementary
count later in prose, or rerun a completed study only because this helper was added.

`checklist_docx.py` requires the selected journal's actual requirement/source and item/location
rows. No named reporting-form catalogue or pre-journal checklist is restored. Keep internal
paths out of upload forms. `preview.py --pdf <Microsoft-Word-exported-PDF> --output ...`
creates a complete contact sheet; use `--pdftoppm` with the verified Poppler path if needed.
It does not pretend to render Word itself. Inspect original changed/critical pages in detail.

## Pinned stages and explicit author-copy handoff

An engine refresh preserves files/history and keeps the added-presentation-gate pin for
completed stages. `wf migrate` explicitly adopts current added gates. Current uncompleted
stages use applicable rules. Data/reference/numeric/approval integrity gates are never pinned
out. `wf check --quiet` and `--summary` reduce output, not work or validation.

Only if the author explicitly chooses to finish upload details by hand: at S25 use
`final_copy.py prepare`, edit the separate `08_submission/final_copy/` files, then
`record --edit ... --words '<actual authorization>'`, `check`, inspect rendered final files,
and `finish`. All uploads must be present. Original freeze and independent PASS remain bound;
missing/unresolved independent review, changed science or private-data leaks cannot be waived.
The final-copy check binds actual files, guide/profile/author context and original audit.
`finish` reruns the applicable S25 gates and records `PASS_AUTHOR_FINAL_COPY` with terminal
mode `AUTHOR_FINAL_COPY_HANDOFF_NOT_SUBMITTED`. It is explicitly an author handoff, not a new
independent reading and not actual portal submission. Final-copy text changes outside proven
presentation transforms route to source rather than silently becoming approved science.

At S23 list remaining portal-only tasks (file slots, article type, coauthor approval, user-owned
disclosure/compliance choices and final submit). Never claim submission from file generation.

For source-scoped labels, early physical production assumptions, all-observation review
closure, percentage denominator-basis checks and safe trial routing, also use
`reference/structural-quality.md`. Existing completed stages/evidence remain historical;
new scoped work does not imply a complete analysis or manuscript rebuild.

