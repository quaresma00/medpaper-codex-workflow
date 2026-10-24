# S24 - Package subagent review and scoped correction rounds

## Purpose
Independently read actual journal uploads, fix safe defects in the workflow, report once,
then ask whether another round is needed. No review ZIP. User inspection and edits remain
welcome; never overwrite them by blindly rebuilding.

## Procedure
If the package was already explicitly approved and the request is presentation-only, use
the content-aware scoped amendment path; do not start another round or ask again. Verify
actual content/meaning/guide/format/changed-page evidence and report the delta once. Real
science or an explicitly requested additional independent reading still follows below.

1. Start with `tools/review_round.py start --scope package` (later rounds use `--delta`).
   Give one independent read-only subagent actual uploads in `bundle/manifest.json`, actual source documents (extra text copies only when explicitly requested), rendered page images/figures, current official guideline snapshot
   and typed article-specific requirements. Text copies do not replace visual inspection.
   Do not transfer patient data/credentials. Missing delegation means independent review pending.
2. The reviewer reads as a first-time reader and screening editor, then checks files,
   compliance and consistency. Require precise locations, severity and rule/evidence; the
   exact printed `reviewed_artifacts` JSON; substantive `Reader comprehension`, `Editorial
   screening and low-level errors` and `Guideline compliance` sections. Attach before editing:
```
.\.venv\Scripts\python.exe tools/review_round.py attach --scope package --report <actual-report.md>
```
   Returning from S25 REVISE: reuse genuine findings only when input versions match. Map frozen
   release files to byte-identical working uploads, retain original evidence and add the exact
   round hash block. Otherwise obtain a current review, not a stale or invented hash claim.
3. The main agent fixes safe findings through one scoped `rework.py batch --sealed` at S24.
   Journal-only changes stay in `08_submission/integration/`. Visible Word text edits must be
   reconciled to source and legitimately rebuilt; format-only changes may remain when
   `package_content.py verify` proves unchanged visible content. Scientific corrections need
   owner rules, renewed S19 round/approval and freeze, then merge only the delta into journal
   copies, preserving unrelated user edits. Never guess author/ethics/funding facts or insert
   AI-use disclosures. Unadopted preferences need reasons; objective defects cannot be waived.
4. Rebuild affected outputs only, finalize, render and visually inspect changed files, then
   update legitimate baselines/portal fields. Run actual scoped checks and close the source
   revision. Refresh `tools/submission_qc.py measure`. Do not reacquire raw data or reanalyse
   the study for an unrelated formatting change.
5. Run `tools/review_round.py close --scope package`, repeating `--change <file> <why>` for
   each changed/removed review artifact and `--kept <finding-ID> <reason>` as needed. Use the
   actual `--unresolved` count; missing required author facts/objective defects block approval.
6. Report once with exact upload/checklist/preview/report paths, corrections and unadopted
   reasons. Ask ONLY:

   > 本轮审阅与修改已完成。是否再进行一轮子代理审阅？若无需继续审阅，请回复“我确认这一版”。

   Preserve the answer using `tools/review_round.py decide --scope package --answer
   another_round|no_further_review --words "<actual words>"`. Only explicit no-further-review
   binds `submission_package_user_confirmed=OK` to this closed round. Generic “继续” is not
   approval. Never infer a user decision from successful review or building.
7. After approval, create/verify the exact upload-only release, then continue to S25:
```
.\.venv\Scripts\python.exe tools/package_review.py freeze
.\.venv\Scripts\python.exe tools/package_review.py verify
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "package round approved; exact uploads frozen for independent final audit"
```

## Hard boundaries
This does not replace S25 on the confirmed freeze. The reviewer reports only; the main agent
corrects outside immutable releases. New uploads need renewed approval/freeze. Preserve old
rounds, releases and legacy archives. Review cannot create clinical facts, citations, private
data transfer authority or actual journal submission. The portal remains user-controlled.

## v1.14 execution update

Read `reference/quality-before-writing.md` at this checkpoint. Its sequencing, source-based
declarations, no free numeric whitelist, soft size budgets and exact current-version confirmation
supersede older conflicting instructions. Do not create external-review materials by default.

## Structural quality and bounded rework

Read `reference/structural-quality.md`. Use clinical display names and physical-size assumptions
before production. Percentage claims bind numerator, denominator and source percentage basis.
Every actionable point in every review section needs a stable ID and disposition, not only
the must-fix subset. Review neutral actual artifacts; don't prime with the writer's conclusion.
Use read-only rework preview and actual scoped checks; never infer scientific change from a
publication label number or silently invalidate author approval. Existing privacy, freezes,
centralized abbreviations, Word cleanup and final actual-page inspection remain in force.


