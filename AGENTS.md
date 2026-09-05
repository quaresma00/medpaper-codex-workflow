# medpaper pipeline — Codex repository instructions

This repository is a gated medical-paper workflow. The pipeline CLI, not the conversation
history and not another skill, determines the current stage, allowed outputs, and gate.

## Start and resume

Before doing project work, run:

```powershell
.\.venv\Scripts\python.exe tools\wf.py status
```

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

1. Never invent or recall bibliographic facts. A citable record must be present in
   `project/06_refs/verified.json` with `verified: true`.
2. Every manuscript number must already exist in `project/03_analysis/results/*.json`,
   produced by executed analysis code. Never calculate a result in prose.
3. Create only active-stage outputs. Scratch belongs in `project/temp/` and is removed before
   advancing. Raw user data are immutable.
4. Deterministic checks do not replace visual QA. Open rendered figures, tables, DOCX, and PDF
   outputs when their stage requires it, then record the decision with a substantive reason.
5. Keep patient-level/private data local. Do not upload it to web services or plugins without
   explicit authorization and a de-identification decision.
6. Do not draft or insert an AI-use disclosure. If a journal requires one, record it as a
   user-controlled compliance item; the user decides whether and how it is written.
7. A red gate means fix the cause. Use `--force` only for a deliberate, user-authorized
   exception recorded in the handoff log.
8. Assemble and present the full scientific paper before asking for author information.
   Author/affiliation administration is deferred to S21.
9. Figure legends decode figures without repeating Results. At S17 consolidate crowded
   display-item abbreviation lists under `Declarations and Statements > Abbreviations`, unless a
   sourced journal rule requires local definitions. Final DOCX files contain neither the
   literal U+2193 down arrow nor manual text-wrapping break controls.
10. A built package is not final approval. After the user edits it, require an explicit request
    for the final independent review, freeze the exact files, and complete the S25 reader,
    editor and journal-compliance audit. Any post-confirmation change invalidates the freeze
    and returns the workflow to S24.
11. A user-requested revision remains inside the workflow. Read `reference/rework-routing.md`
    and run `tools/rework.py` before editing. Update the earliest owning source and rebuild its
    true dependants. Never patch assembled Markdown or Word narrative content as detached final
    files; S24 permits Word-only layout changes only when the S23 visible-text baseline passes.

User instructions take precedence over this workflow. If a missing user choice would
materially change the scientific result, target journal, private-data handling, or external
action, stop and ask one concise question.
