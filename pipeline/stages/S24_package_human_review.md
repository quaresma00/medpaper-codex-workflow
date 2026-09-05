# S24 - User review and confirmation of the submission package

## Purpose
Let the user inspect and modify the assembled journal-specific submission files, then obtain
an explicit final `OK` before an independent reviewer sees a frozen package.

## This stage needs the user
Present clickable paths to the complete `08_submission/bundle/`, its
`SUBMISSION_CHECKLIST.md`, `manifest.json`, the rendered previews used for visual QA, and
`guidelines_extract.md`. Tell the user that both content and formatting may be edited. Do not
treat delivery, silence, or an earlier manuscript approval as approval of this submission
package.

## Procedure
1. Wait while the user performs the requested manual content and formatting review. Do not
   overwrite user-edited DOCX, table, figure, supplement or checklist files by rebuilding
   them blindly.
2. When the user says the edits are finished, identify which bundle files changed. Reconcile
   scientific-content changes back to the canonical Markdown/results/table/figure sources
   and their provenance so that later rebuilding cannot silently discard them. Pure Word
   layout edits may remain in the DOCX, but must still pass the journal rules and audits.
3. Re-run `bundle_complete`, `docx_bundle_ready`, the standalone Word manifest audit and
   visual QA for every changed file. Recheck filenames, upload roles, word/keyword/reference
   limits, figure/table/legend numbering, supplements, declarations and cross-file facts
   against the chosen journal's official guideline snapshot. If a title-page reference count
   is present, verify that both the canonical source and the user-edited DOCX still equal the
   number of distinct citekeys actually used in `full_manuscript.md`, not the library size.
4. Write `project/08_submission/package_human_review.md` with headings `Package presented`,
   `User modifications`, `Revalidation`, `User confirmation`, `Frozen package`.
5. After the user's edits have been revalidated, ask exactly one clear confirmation question:
   **“投稿包已按您的修改重新校验。是否确认 OK，并调用一个独立子代理，以普通读者和期刊编辑的视角终审当前冻结版本？”**
   Continue only after an explicit affirmative answer such as `OK`, `确认` or `可以`.
6. Freeze the exact reviewed bundle and its journal/source evidence:
```
.\.venv\Scripts\python.exe tools/package_review.py freeze --project project
```
   Record the package file count, freeze timestamp and `freeze_id` under `Frozen package`,
   then record:
```
.\.venv\Scripts\python.exe tools/wf.py decide submission_package_user_confirmed OK --why "<what the user reviewed or changed, what was revalidated, and that independent audit was explicitly approved>"
```

## Outputs
- `08_submission/package_human_review.md`
- `08_submission/package_review_freeze.json`

## Hard rules
- The confirmation must concern the final journal-specific upload package, not the earlier
  scientific manuscript review.
- No independent final audit starts before explicit user confirmation and a successful
  freeze.
- The user's confirmation is also the explicit request to invoke one independent subagent
  for the final reader/editor/compliance review; an earlier review request does not substitute.
- Any change after confirmation invalidates the freeze and requires this stage's checks and
  confirmation again.
- Never infer or rewrite user-owned authorship, affiliation, funding, ethics or conflict data.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "user reviewed and explicitly confirmed the final package; changed files=<...>; freeze=<timestamp and file count>"
```
