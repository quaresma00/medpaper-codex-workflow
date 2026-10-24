---
name: medpaper-codex-pipeline
description: Run the gated medical-research, manuscript and submission pipeline in this repository, including repeated user revisions. Not for unrelated finished-paper review or non-medical writing.
metadata:
  version: "1.17.0"
  entrypoint: ".\\.venv\\Scripts\\python.exe tools\\wf.py status"
---

# Repository medpaper workflow

This workspace's `pipeline/pipeline.toml` and stage cards are authoritative.
If its virtual environment is missing, use `uv run --python 3.13 python bootstrap.py`.

## Work inside the existing gates

Read `reference/project-benchmarking.md` at S07/S13-S17 and S20-S23: genuine full-text
comparison shapes project evidence/display choices before writing; complete the executor's
own current-file acceptance before independent/user delivery. Never lower quotas or pad
references/displays to make a gate green. Retired numeric quality targets are ignored.

After initialization, read the workspace `AGENTS.md` completely. It owns the detailed
validity, review, typography, privacy and capability rules; do not duplicate or replace them.
Run `tools/wf.py status` before work and after compaction, then read `tools/wf.py card`.
Complete active-stage work, run `tools/wf.py check`, then `tools/wf.py advance --note "..."`
using the workspace's `.venv/Scripts/python.exe`. Stages are quality gates, not turn boundaries.
Do not create future outputs, reset completed history for a local edit, or bypass failed gates.

For revisions, read `reference/rework-routing.md` and `reference/efficient-quality.md`.
Record verbatim feedback once with `rework.py batch`; a complete apply-now request permits
`--sealed`. Otherwise collect until the user ends the batch. Keep S19/S24 as the checkpoint,
execute owner rules in place, and run actual `rework.py check` before marking/closing.
Resume with compact `rework.py status`; `--full` retrieves completed items.
An affected file list is a recheck scope, not an instruction to rewrite everything.
After an artifact-plan edit, `rework.py refresh` can narrow observed entry-only changes.
Use `rework.py depend --input ... --output ... --why ...` for a newly found consumer,
without rewriting feedback. Mark inspected unchanged sources with `--checked-file`.
Read `reference/source-aligned-validation.md` for composed builds, journal reorganisation,
versioned snapshots and final Word cleanup. Unchanged check receipts are reused, not relabelled.
Unmapped dependencies remain conservative. Preserve unrelated edits and frozen sources.

## Read the relevant reference, not every reference

- S04 acquisition: `reference/data-acquisition-integrity.md`.
- S05/S06 exports and S09/S10/S17 findings: `reference/numeric-claims.md`.
  Resolve concise facts with `tools/manuscript/readiness.py facts`; bind Results/Abstract
  prose and table cells to actual source objects. Keep binding metadata out of the paper.
- S06/S07, revisions and package production: `reference/efficient-quality.md`.
- Methods: `reference/methods-structure.md`.
- S03/S05 language choice and S07/S11 graphics: `reference/r-first.md`. New medical
  statistical figures default to R; processing may use Python. Select mature implementations
  deliberately, preserve approved results/legacy figures, and never refit merely to draw.
- Other skills/plugins inside a stage: `reference/codex-integration.md`.

## Essential boundaries
For post-freeze revisions and S20-S25, read `reference/content-aware-amendments.md`.
Proven presentation amendments keep prior approval without an S19 rewind, new subagent
round or user re-confirmation; run actual scoped content/meaning/format checks and report
the delta once. New science still needs original review. `journal-format` differs from
`journal-switch`. Completed-stage added presentation gates are pinned until `wf migrate`.
Author final-copy handoff is explicit and never a claim of new independence.


Do not default ordinary database-mining/retrospective studies to public registration or
preselected reporting checklists. Follow AGENTS.md: applicable registration exceptions are
study-specific; reporting forms are prepared only when the selected journal explicitly
requires them after S20. Do not create extra paperwork or confirmation stops.

Acquire the entire protocol-defined data universe; no unauthorized sampling, truncation,
first-N retrieval or page caps for speed. Never fabricate references, source records,
verification receipts, findings, completed QA or independent verdicts. Bibliographic metadata
must come through bundled PubMed verification. A local boolean or successful compilation is
not evidence. Never hand-write the formal reference library/verification/export files.
Data/reference integrity, bound numeric findings, approvals and freezes cannot be forced.

Scientific facts and the reader's medical interpretation take priority over token savings.
Keep manuscript-facing prose, tables and figures journal-native and comprehensible to people;
technical provenance stays backstage. Preserve necessary analyses, uncertainty and limitations.
Use approved low-cost prototypes before expensive output. R figures use the managed R renderer;
Tavotto applies only to Matplotlib exceptions, not R output. ImageGen may critique,
not regenerate scientific plots. Required rendered visual QA remains mandatory.

S17 chooses an accurate title and assembles the paper before S21 author administration.
S18 gives the frozen manuscript, supplement, tables and actual rendered figures to exactly
one independent read-only subagent. Follow `reference/review-rounds-and-word-tables.md`:
S19/S24 use version-bound subagent rounds, not review ZIPs. Apply safe findings through
scoped owner rules, report changes/unadopted reasons once, ask whether another round is wanted,
and wait for explicit no-further-review
approval. Generic "continue" is not approval. Freeze the scientific master before journal
selection; all journal-specific edits belong in `08_submission/integration/`.
A real scientific correction needs renewed S19 review/freeze, then scoped S24 package updates,
not replaying S20-S23. Preserve unrelated author edits when merging that delta.

At S24 present the actual uploads and obtain explicit user OK/request for final review.
S25 uses exactly one independent read-only subagent on that frozen package and the current
official instructions: reader comprehension, editorial errors and submission compliance.
An unchanged freeze is not repeatedly audited. Missing independent review stays pending.
Do not draft AI-use disclosure content unless the user explicitly requests it.
Keep patient/private data local unless external transfer is explicitly authorized.

Use selective rebuilding and valid check reuse, never reduced evidence or skipped review.
Ask only for a material missing decision/authorization/source; otherwise finish unblocked work.

For current sequencing, source-specific declarations, prior-study numeric evidence, soft size budgets,
optional third-party copies and exact-version approval, read `reference/quality-before-writing.md`.

At S07-S11/S17 and journal acceptance use `reference/medical-reader-presentation.md`.
Keep clinical meaning and legitimate method terminology; decode actual tables/figures and
bind final Word-rendered layout observations inside the existing acceptance, not another audit.

Read `reference/structural-quality.md` for S07 clinical vocabulary/production profile,
percentage denominators, all-finding review closure and read-only revision preview.



