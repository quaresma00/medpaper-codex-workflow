# S25 - Independent audit of the user-confirmed submission package

## Purpose
Independently determine whether the exact package approved by the user complies with the
chosen journal's current official submission instructions, is complete, and is internally
consistent.

## Procedure
1. Before delegation, verify that the package still matches the user's freeze:
```
.\.venv\Scripts\python.exe tools/package_review.py verify --project project
```
   Stop and return to S24 if any file was added, removed or changed.
2. Spawn exactly one independent read-only subagent for this frozen package revision. Do not
   give it the intended verdict or ask it to edit files. Give it:
   - `08_submission/package_review_freeze.json` and every frozen file listed there;
   - the selected journal metadata, `guidelines_extract.md`, and the cached official author
     instructions;
   - `bundle/manifest.json`, `SUBMISSION_CHECKLIST.md`, and `submission_qc.md`.
3. Require the reviewer to inspect the actual upload files rather than trusting the manifest
   or earlier QA. It must compare the package with the official guide and report:
   - required, missing, extra or incorrectly formatted upload items and filenames;
   - article type, title page, abstract, keywords, word/reference limits and reference style;
   - any title-page reference count against the distinct citations actually used in the
     manuscript, never against the candidate-library or bibliography-file size;
   - author/affiliation/correspondence facts, declarations, ethics, funding, conflicts and
     data-availability consistency across all applicable files, without inventing facts;
   - figure/table callouts, numbering, legends/captions, abbreviations, file types, resolution
     and supplement correspondence;
   - mismatched titles, counts, versions, values, labels, citations or statements between
     manuscript, cover letter, title page, tables, figures, supplements and checklist;
   - portal-only tasks that cannot be verified from local files, clearly separated from
     defects in the package.
4. Save the review as `project/08_submission/independent_submission_audit.md` with headings
   `Verdict`, `Guideline compliance`, `Required files and omissions`, `Cross-file consistency`,
   `Formatting and technical checks`, `Issues requiring correction`, `Final recommendation`.
   Under `Verdict`, write the exact `Freeze ID: <freeze_id>` from
   `package_review_freeze.json` so a stale review cannot be attached to a changed package.
   Every finding names the affected file and the exact official guideline rule or cross-file
   evidence. Use `PASS` only when there is no material omission, noncompliance or unexplained
   mismatch; use `REVISE` for correctable defects and `BLOCKED` when a required fact or file
   can only come from the user or journal portal.
5. Verify the freeze again after the reviewer returns. Then record the actual verdict:
```
.\.venv\Scripts\python.exe tools/wf.py decide submission_package_independent_audit "PASS|REVISE|BLOCKED" --why "<concise evidence-based basis>"
```
6. For `REVISE`, summarise the findings, return to S24, correct the package, revalidate it and
   obtain a new explicit user confirmation before auditing the changed freeze:
```
.\.venv\Scripts\python.exe tools/wf.py loop S24_package_human_review --why "<material audit defects requiring correction and renewed user confirmation>"
```
   For `BLOCKED`, ask only for the missing user-owned fact/file. If the package changes, use
   the same S24 loop. Do not repeat an independent audit of an unchanged freeze.

## Outputs
- `08_submission/independent_submission_audit.md`

## Hard rules
- The independent subagent is read-only and audits exactly the user-confirmed frozen files.
- Earlier S18 publishability review and S23 automated/visual QA do not substitute for this
  journal-specific final audit.
- A checklist assertion is not evidence; inspect the actual file and official rule.
- A reference-count field is optional when the journal is silent, but if present it must match
  the actual citation set in both the canonical title page and frozen Word file.
- `PASS` is required to complete the pipeline. Portal-only user tasks may be listed, but an
  unmet required local upload or unresolved cross-file mismatch is not a pass.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "independent final submission audit=PASS; frozen package unchanged; remaining portal-only user tasks=<none or list>"
```
