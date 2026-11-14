# S24 - Author package review, scoped corrections and exact confirmation

S23 already requires executor medical/content/actual-page QA. For new v1.29 projects this
checkpoint presents those real uploads to the author; it does not commission another
independent pre-review by default. S25 still independently reads the exact author-confirmed
freeze. Existing independent P rounds retain their genuine report/closure requirements.

## Procedure

1. Verify the current journal context and actual upload QA. Run
   `tools/review_round.py start --scope package`. New projects return `author presentation`;
   old pinned or already-open independent rounds are not silently converted. Present exact
   bundle, named upload-copy, preview and checklist locations. The named directory is a
   read-only upload copy; edits use managed sources/bundle and the scoped revision path.
2. The author may inspect and modify the package repeatedly. Interpret a feedback batch
   using `reference/rework-routing.md` and `tools/rework.py batch --sealed`.
   once, keep S24 and completed history, call affected owner rules in place, and rebuild only
   actual consumers. Journal wording stays in integration; scientific changes need source
   correction, renewed scientific review/approval and scoped merge. Word-only layout edits
   must retain visible text. Never overwrite unrelated author edits or fabricate author facts.
   Visible Word text edits must be reconciled to integration sources and legitimately rebuilt.
3. Recheck changed files and actual pages; refresh legitimate baselines, portal fields and
   measurements. Close the source revision, then `review_round.py close --scope package`,
   giving `--change <file> <actual reason>` for each changed/removed artifact. Author mode
   checks current executor medical/visual acceptance, measured uploads and source/text
   baseline. Unresolved objective defects block; it never generates an independent verdict.
4. Explain changes and any remaining author-controlled items once. Ask the author to keep
   editing if needed. If this displayed version needs no further changes and may receive the
   final independent reading, request exactly `我确认这一版`. Record the actual reply with
   `review_round.py decide --scope package --answer no_further_review --words "<actual reply>"`.
   Generic continuation and prior scientific approval do not approve this package.
5. Freeze and verify the actual uploads with `tools/package_review.py freeze` and `verify`;
   run the current gates and advance to S25. Successful author confirmation never substitutes
   for S25's real independent reader/editor/current-guide review of that freeze.

## Optional independent pre-review

Only when explicitly requested, use `review_round.py start --scope package --independent`
after completing any current author round and recording its actual answer. Follow the
existing independent P-report, finding-disposition and actual delta-reading mechanics in
`reference/review-rounds-and-word-tables.md`. Never label executor QA as independent.
This extra pre-review is optional; S25 remains mandatory after final confirmation.

For an already approved meaning-preserving presentation correction, use the existing scoped
amendment/approval lineage. Do not add another full review or confirmation automatically.
For a journal switch, read `reference/journal-adaptation.md`: begin the new exact context,
discard old active rules, preserve accepted science and author edits, and adapt true consumers.

## Close

Complete real scoped fixes and current checks, then freeze only the explicitly confirmed
version. Old rounds and releases remain immutable. Do not submit externally, add AI-use
disclosure text, or transfer private data without the user's corresponding instruction.
