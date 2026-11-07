# S23 - Build and verify only actual journal uploads

Use `reference/journal-adaptation.md`: verify the sealed current guide, selected CSL/template
and actual upload list. Inspect manual guide clauses in the final rendered QA and measure
uploads once. A successful build alone does not prove compliance.

Freeze content, author/blinding facts, official rules and the exact upload list before
expensive builds. Keep one source/dependency path; compose from the real build entrypoint.
Resolve routine medical prose, table/figure meaning and reference coverage before building.
Apply the current `submission_layout` policy: nonblinded author front matter from author_info;
separate title page only if required/blinded; images separate by default; tables after
References, each on a new page, then final legends. Only explicitly required guide clauses
override those positions, with image and caption placement handled separately. Name actual
supplements `Supplemental_File_<n>_<description>.<ext>` unless the guide mandates otherwise.
Build the necessary DOCX/supplements/figures once, then correct only affected dependants.

Use managed R rendering then matching figure QC sequentially. Pending jobs/IO locks remain
incomplete. Keep process logs in .wf/processes or .wf/logs, outside disposable scratch.

Apply necessary layout repair -> final XML cleanup -> final rendering -> visible-content
baseline and measured portal fields. Inspect a complete overview plus changed/critical
pages. Preserve the user's full XML-control cleanup, black text, journal fonts/sizes, no
manual soft breaks/hyperlinks, three-line tables, concise legends and separate supplementary
tables. Sourced journal line_numbers is audited in actual main-manuscript XML.

Only manifest-listed uploads enter the bundle/release. No directory-wide ZIP, previews,
Office lock files or internal evidence. Do not draft AI-use disclosure text. S24 is actual
author package review; this build creates no approval. Never recapture a failed baseline
or fabricate successful independent/visual checks. Follow scoped revision rules for changes.

Use full details for builder/finalize/preview commands, Word style and manifest schemas.

## Full procedure, read once when needed
`reference/stage_details/S23_package.md` (`tools/wf.py card S23_package --details`).
On first execution read the applicable detailed procedure; later local corrections reuse
already-read guidance and go directly to affected owner rules. After compaction use
`tools/wf.py handoff`, then retrieve only missing context. The actual gates remain unchanged.
`reference/structural-quality.md` v1.17 explains runtime fixes and preserved boundaries.

## Outputs
At handoff list portal-only tasks separately: actual upload slots/article type, coauthor
approvals, unresolved user-owned compliance items and final Submit. Never mark these done
merely because local files exist; never draft an AI-use disclosure without the exact request.

- A journal-requested reporting checklist only if explicitly required in the sourced upload
  list; complete that specific current form from actual integration content, with truthful
  locations/inapplicability. Otherwise create no reporting checklist. This is separate from
  the small internal SUBMISSION_CHECKLIST.md used to hand off the actual upload files.
- `08_submission/cover_letter.md`
- `08_submission/evidence/SUBMISSION_CHECKLIST.md`
- `08_submission/portal_fields.json`
- `08_submission/bundle/manifest.json`
- `08_submission/package_content_baseline.json`
- `08_submission/submission_qc.md`
- the journal-required Word, figure, table and supplementary upload files

## Close
Run `tools/wf.py check` (or the active scoped revision check). Fix actual failures before
`tools/wf.py advance --note "<actual completed work>"`. Stages are not turn boundaries.
Review stages still require the real author statement; generic continuation is not approval.
