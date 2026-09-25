# medpaper pipeline — Codex repository instructions

This repository is a gated medical-paper workflow. The pipeline CLI, not the conversation
history and not another skill, determines the current stage, allowed outputs, and gate.

## Start and resume

Before doing project work, run:

```powershell
.\.venv\Scripts\python.exe tools\wf.py status
```

`status` is compact/local. Read `tools/wf.py card` for active-stage instructions; use
`status --full` only for diagnostics. Read `reference/efficient-quality.md` at S06/S07,
when processing feedback and before building/finalizing a journal package.

If the virtual environment does not exist yet, run
`uv run --python 3.13 python bootstrap.py`. After a context compaction, run `status` again.
Complete only the active stage, then run `check` and `advance --note "..."`. Never infer or
skip a stage.

## Orchestration and capability routing

- `medpaper-codex-pipeline` is the sole workflow orchestrator in this repository. A different
  workflow skill must not create a competing project layout, manuscript, reference library,
  analysis plan, figure set, or submission package.
- Other skills and plugins may supply a capability inside the active stage. They must write
  to the paths declared by `wf status`, preserve provenance, and pass the same gate.
- For scholarly discovery or permitted full-text acquisition, follow
  `reference/codex-integration.md`. A record becomes citable only after the pipeline clients
  re-fetch and verify its metadata. An externally acquired full text must be registered by
  `tools/pubmed/fulltext.py register`.
- Use the spreadsheet workflow at S10 to render and visually inspect the pipeline-generated
  XLSX files. At S18, give the frozen complete manuscript, optional supplementary Methods
  and tables to exactly one independent read-only subagent for publication-readiness review.
  At every initial or revised S19 presentation, run `tools/manuscript/review_package.py build`
  and `verify`, show clickable locations for every review artifact and the exact versioned ZIP,
  and invite the user or a third party to review it. Stay at S19 until the user explicitly says
  no further review is needed; do not infer approval from delivery, silence, thanks, completion
  of one revision, or a generic instruction to continue.
  Use the document/PDF workflows at S23 to render and inspect submission files.
  At S24, present the actual upload package for the user's content/format edits and explicit
  request for final review; freeze that revision. At S25, give only that frozen package and
  the official journal instructions to one independent read-only subagent. It reads as a
  first-time scientific reader, screens as an editor for low-level errors, then audits final
  completeness, compliance and cross-file consistency.
  These are QA helpers; the stage card remains authoritative.
- At S11, ImageGen may participate as an optional second visual critic. It may identify
  readability or layout defects, but it must never redraw or edit a statistical figure.
  Implement accepted fixes in plotting code, re-render, and inspect the new output.

## Non-negotiable validity rules

1. Acquire the entire S03 protocol-defined data universe before analysis whenever the source
   makes it available. Preserve source-total and received-count receipts, exhaust every
   page/cursor, hash all raw/acquisition files with `tools/data_manifest.py`, and reconcile
   received records to the analysis rows. Never add `LIMIT`, `TOP`, `head()`, `sample()`,
   first-N slicing, a fixed page cap or a narrower query for speed, tokens, download volume or
   compute. A pilot is non-analytic and must be followed by full acquisition. Source-imposed
   partial access requires the user's explicit recorded authorization. A scientific sampling
   design also requires explicit user authorization; the agent may not silently replace a
   census with a sample. The gate is not waivable with `--force`; follow
   `reference/data-acquisition-integrity.md`.
2. Never invent or recall bibliographic facts. `verified: true` alone is not evidence. A
   citable record must be produced by a fresh `tools/pubmed/verify.py` EFetch, bound to hashed
   raw PubMed XML and the exact library hash, match PMID/DOI/metadata on recomputation, and
   pass independent live PubMed gates from S13 through the final audit. Never write the four reference-library files
   with an ad-hoc script; their integrity gates cannot be bypassed with `--force`.
3. Every manuscript number must already exist in `project/03_analysis/results/*.json`,
   produced by executed analysis code. Never calculate a result in prose.
4. Create only active-stage outputs. Scratch belongs in `project/temp/` and is removed before
   advancing. Raw user data are immutable.
5. Deterministic checks do not replace visual QA. Open rendered figures, tables, DOCX, and PDF
   outputs when their stage requires it, then record the decision with a substantive reason.
6. Keep patient-level/private data local. Do not upload it to web services or plugins without
   explicit authorization and a de-identification decision.
7. Do not draft or insert an AI-use disclosure. If a journal requires one, record it as a
   user-controlled compliance item; the user decides whether and how it is written.
8. A red gate means fix the cause. Use `--force` only for a deliberate, user-authorized
   non-integrity exception recorded in the handoff log. Reference provenance, library,
   BibTeX/RIS consistency and citekey resolution are non-overridable.
9. Assemble and present the full scientific paper before asking for author information.
   Author/affiliation administration is deferred to S21.
10. Figure legends decode figures without repeating Results. At S17 consolidate crowded
   display-item abbreviation lists under `Declarations and Statements > Abbreviations`, unless a
   sourced journal rule requires local definitions. Final DOCX files contain neither the
   literal U+2193 down arrow nor manual text-wrapping break controls. Every Word XML part is
   cleared of `outlineLvl`, `keepNext`, `keepLines`, `pageBreakBefore` and paragraph borders;
   headings use the Normal-based `SectionHeading` style. Supplementary Methods is prose only:
   its tables belong in the separate three-line supplementary workbook, and it contains no
   Markdown thematic rules. Figure legend section/figure titles cannot be duplicated.
11. A built package is not final approval. After the user edits it, require an explicit request
    for the final independent review, freeze the exact files, and complete the S25 reader,
    editor and journal-compliance audit. Any post-confirmation change invalidates the freeze
    and returns the workflow to S24.
12. A user-requested revision remains inside the workflow. Read `reference/rework-routing.md`
    and create or extend a persisted batch with `tools/rework.py batch` before editing. S19 is
    the repeatable scientific-content loop and S24 is the repeatable journal-package loop;
    recover compacted context with `tools/rework.py status`. Update the earliest owning source,
    rebuild only its true dependants, and reuse unaffected hash-matched evidence. Every atomic
    request must retain its acceptance criteria, changed-file hashes and validation before the
    round closes. Token, context or time pressure never permits omitting an affected item,
    output, gate, visual inspection or review. Never patch assembled Markdown or Word narrative
    content as detached final files; S24 permits Word-only layout changes only when the S23
    visible-text baseline passes.
13. S19 is an explicit, repeatable user-review stop. Every scientifically changed version has
    a newly verified third-party review ZIP containing the manuscript, optional supplementary
    Methods, tables, rendered figures, verified BibTeX/RIS exports and independent verdict,
    but no patient-level data,
    credentials, full-text literature or internal analysis code. Record
    `manuscript_human_reviewed=NO_FURTHER_REVIEW` only after the user explicitly states that no
    further review is needed and identify the presented ZIP revision and package ID in the
    rationale. This approval is valid for that package only and cannot be forced.
14. After explicit S19 approval, create and verify
    `07_manuscript/scientific_master_freeze.json`. S20-S25 must not alter a frozen scientific
    source. Initialize the selected journal under `08_submission/integration/` and keep every
    journal-specific wording, structure, title-page, declaration and packaging change there.
    A genuine scientific correction invalidates S19 approval, returns to its earliest owner,
    and requires a new review ZIP, explicit approval and freeze before submission work resumes.
15. At S06 freeze the analysis contract and clinical story; at S07 verify real low-cost display
    prototypes before production. Feedback batches collect before they are sealed and built.
    Rebuild true file dependencies, never an entire stage tail merely because an earlier stage
    owns an edit. After two full builds use targeted correction; quality work remains mandatory.
16. S23 derives portal fields/counts from final DOCX and unified administrative facts. S24 creates
    a read-only release containing actual uploads only. Evidence/caches/control refreshes do not
    require another author confirmation; upload changes do. S25 binds the independent verdict
    to upload identity and current guideline context. Never fabricate independent review.
17. Use the installed Tavotto skill for user-facing Matplotlib figures, with Python beside PDF
    and desktop handoff per the user's instructions. Internal diagnostics are exempt; a missing
    embedded-canvas authorization does not block desktop preview.

User instructions take precedence over this workflow. If a missing user choice would
materially change the scientific result, target journal, private-data handling, or external
action, stop and ask one concise question.
