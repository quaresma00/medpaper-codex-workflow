# S25 - Independent reader, editor and compliance audit of the confirmed package

## Purpose
Give the exact package approved by the user one final fresh reading immediately before
submission. The same independent reviewer must judge it from three complementary positions:
an ordinary scientific reader trying to understand the paper without backstage context, a
journal editor screening for avoidable defects, and a submission-compliance reviewer applying
the chosen journal's current official instructions.

## Procedure
1. Before delegation, verify that the package still matches the user's freeze:
```
.\.venv\Scripts\python.exe tools/package_review.py verify --project project
.\.venv\Scripts\python.exe tools/manuscript/scientific_freeze.py verify
.\.venv\Scripts\python.exe tools/manuscript/journal_workspace.py verify
```
   Stop and return to S24 if any package file was added, removed or changed. If the scientific
   master changed, return to its owning scientific stage and require renewed S19 review before
   rebuilding the package.
2. Spawn exactly one independent read-only subagent for this frozen package revision. Do not
   give it the intended verdict, prior reviewers' conclusions, or ask it to edit files. Tell
   it to read the actual package in normal submission order before consulting backstage QA.
   Give it:
   - `08_submission/package_review_freeze.json` and every upload file in its read-only `release_dir`;
   - the selected journal metadata, `guidelines_extract.md`, and the cached official author
     instructions;
   - `bundle/manifest.json`, `evidence/SUBMISSION_CHECKLIST.md`, `portal_fields.json`, and `submission_qc.md`.
   - `07_manuscript/scientific_master_freeze.json` and
     `08_submission/integration/journal_workspace.json`, to prove that journal changes were
     isolated from the accepted scientific master.
3. Require the reviewer to inspect the actual upload files rather than trusting the manifest
   or earlier QA. It must perform all three lenses and report exact locations for every
   actionable finding:
   - **Reader comprehension:** passages, terminology, abbreviations, referents, transitions,
     methods, tables, figures or legends that cannot be understood from the submitted files;
     contradictions, unexplained logic jumps and claims whose evidence is hard to locate;
   - **Editorial screening:** typographical, grammatical and punctuation errors; duplicated,
     missing or unfinished text; template residue and placeholders; inconsistent spelling,
     capitalization, tense, units, decimals, statistical notation, headings, numbering,
     citations, labels and terminology; title/abstract/keywords that misstate or obscure the
     paper; and any obvious issue likely to trigger an avoidable query or desk rejection;
   - **Journal compliance:** compare the frozen package with the official guide and report:
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
   `Verdict`, `Reader comprehension`, `Editorial screening and low-level errors`,
   `Guideline compliance`, `Required files and omissions`, `Cross-file consistency`,
   `Formatting and technical checks`, `Issues requiring correction`, `Final recommendation`.
   Under `Verdict`, write the exact `Freeze ID: <freeze_id>` from
   `package_review_freeze.json`, plus `Audit context ID: <audit_context_id>` from
   `08_submission/evidence/evidence_manifest.json`. This binds the verdict to the actual
   uploads and the journal rules, without treating cache/log changes as author revisions.
   Every finding names the affected file and, where available, page plus heading, paragraph,
   table cell or figure panel; include only a short identifying fragment rather than rewriting
   the manuscript. Classify it as `BLOCKING`, `MINOR` or `PREFERENCE`, and cite the exact
   official rule or cross-file evidence when applicable. Use `PASS` only when there is no
   objective low-level error, reader-comprehension problem, material omission, noncompliance
   or unexplained mismatch. Use `REVISE` for any correctable `BLOCKING` or `MINOR` defect and
   `BLOCKED` when a required fact or file can only come from the user or journal portal.
   Pure preferences do not prevent `PASS` and must be clearly separated from defects.
5. Verify the freeze again after the reviewer returns. Then record the actual verdict:
```
.\.venv\Scripts\python.exe tools/wf.py decide submission_package_independent_audit "PASS|REVISE|BLOCKED" --why "<concise evidence-based basis>"
```
6. For `REVISE`, summarise the findings, return to S24, correct the package, revalidate it and
   obtain a new explicit user confirmation before auditing the changed freeze:
```
.\.venv\Scripts\python.exe tools/wf.py loop --to S24_package_human_review --why "<material audit defects requiring correction and renewed user confirmation>"
```
   For `BLOCKED`, ask only for the missing user-owned fact/file. If the package changes, use
   the same S24 loop. Do not repeat an independent audit of an unchanged freeze.
   For any correction, use `tools/rework.py` to route content to its source; only a verified
   visible-text-preserving layout edit may remain solely in Word at S24.

## Outputs
- `08_submission/independent_submission_audit.md`

If an independent agent is unavailable, perform a clearly labelled preliminary local check,
preserve the pending independent audit and report the exact blocker. Never claim independence
or final PASS for that fallback. Reuse an audit of unchanged upload bytes/context; repeat only
when the package/context changes or a material defect warrants it. Verify release hashes and
read-only attributes immediately before actual upload; preview working copies must not
replace the release.

## Hard rules
- The independent subagent is read-only and audits exactly the user-confirmed frozen files.
- Earlier S18 publishability review and S23 automated/visual QA do not substitute for this
  journal-specific final audit.
- A checklist assertion is not evidence; inspect the actual file and official rule.
- Read as a first-time reader and editor; do not treat prior automated QA or scientific review
  as proof that the prose is understandable or free of elementary errors.
- The subagent reports defects but never edits the frozen package. Corrections occur only after
  returning to S24, followed by renewed user confirmation and a new freeze.
- A reference-count field is optional when the journal is silent, but if present it must match
  the actual citation set in both the integration title page and frozen Word file.
- `PASS` is required to complete the pipeline. Portal-only user tasks may be listed, but an
  unmet required local upload or unresolved cross-file mismatch is not a pass.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "independent final submission audit=PASS; frozen package unchanged; remaining portal-only user tasks=<none or list>"
```
