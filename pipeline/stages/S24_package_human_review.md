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

This is a repeatable package-review loop. The user may request any number of correction
rounds; do not freeze the package until the current round is closed and the user explicitly
approves the exact visible files.

## Procedure
1. Wait while the user performs the requested manual content and formatting review. Do not
   overwrite user-edited DOCX, table, figure, supplement or checklist files by rebuilding
   them blindly.
2. Preserve each feedback message verbatim and interpret it once into atomic items in
   `project/temp/revision_plan.json`; name each item's revision kind, source files and
   acceptance criteria. Start or extend the persisted round:
```
.\.venv\Scripts\python.exe tools/rework.py batch --plan project\temp\revision_plan.json
.\.venv\Scripts\python.exe tools/rework.py status
```
   A content change routes to its earliest Markdown, analysis, table, figure, reference,
   title-page or package source; rebuild its true dependants and return through S23. Never edit
   narrative content only in DOCX. Format-only work stays at S24. Preserve every unrelated
   user edit and modify only the affected Word file or deterministic style/build source.
   If context compacts, resume from `tools/rework.py status` rather than re-reading the entire
   feedback history. Token pressure is not permission to reduce or skip requested work.
3. When the user has already edited files, identify which bundle files changed and run:
```
.\.venv\Scripts\python.exe tools/package_content.py verify --project project
```
   A passing visible-text baseline proves a DOCX change was formatting-only. If it fails,
   reconcile the changed wording back to its owning source, route the workflow there, rebuild
   the DOCX at S23 and capture a new baseline there. Never recapture at S24 to bless drift.
4. Re-run `bundle_complete`, `docx_bundle_ready`, `package_content_matches_baseline`, the
   standalone Word manifest audit and
   visual QA for every changed file. Recheck filenames, upload roles, word/keyword/reference
   limits, figure/table/legend numbering, supplements, declarations and cross-file facts
   against the chosen journal's official guideline snapshot. If a title-page reference count
   is present, verify that both the canonical source and the user-edited DOCX still equal the
   number of distinct citekeys actually used in `full_manuscript.md`, not the library size.
5. At S24, verify each atomic request against its acceptance criteria. Mark the final changed
   files and checks, then close the revision round with `tools/rework.py close`. Present the
   resulting package again; later feedback opens a new round without a fixed round limit.
6. Write or append `project/08_submission/package_human_review.md` with headings `Package presented`,
   `User modifications`, `Revalidation`, `User confirmation`, `Frozen package`.
7. After all revision rounds are closed and the user's edits have been revalidated, ask exactly one clear confirmation question:
   **“投稿包已按您的修改重新校验。是否确认 OK，并调用一个独立子代理，以普通读者和期刊编辑的视角终审当前冻结版本？”**
   Continue only after an explicit affirmative answer such as `OK`, `确认` or `可以`.
8. Freeze the exact reviewed bundle and its journal/source evidence:
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
- A direct Word content edit can never be classified as format-only. Visible-text drift blocks
  freezing until it is applied to the owning source and rebuilt through S23.
- Never infer or rewrite user-owned authorship, affiliation, funding, ethics or conflict data.
- Do not trade away a requested correction, full validation, independent review or visual QA
  to save tokens. Save tokens by reading the persisted item and its dependency closure only.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "user reviewed and explicitly confirmed the final package; changed files=<...>; freeze=<timestamp and file count>"
```

