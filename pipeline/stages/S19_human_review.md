# S19 - User review of the complete paper

## Purpose
Give the user one coherent scientific package to inspect and revise before journal-specific
formatting or administrative author collection begins.

## This stage needs the user
Present clickable paths to:
- `07_manuscript/full_manuscript.md`;
- `07_manuscript/supplementary_methods.md`, if present;
- every main and supplementary table workbook;
- `07_manuscript/independent_publishability_review.md`.

Do not ask for authors, affiliations, ORCIDs, correspondence, funding or other title-page
administration here. Ask only for manuscript/table corrections or confirmation that this
scientific version can proceed to journal selection.

## Procedure
1. Summarise the independent verdict and list only the revisions that materially affect
   publishability. Link the four artifact groups above for direct inspection.
2. Apply the user's scientific edits to the canonical `full_manuscript.md` and affected
   source tables/results only as instructed. If a requested change alters an analysis,
   loop to the analysis source and regenerate its true dependants; never patch a reported
   number directly in prose or a workbook.
3. Re-run manuscript structure, citation, number-provenance and artifact-reference checks.
4. Write `project/07_manuscript/human_review.md` with headings `Materials presented`,
   `Independent verdict`, `User-requested revisions`, `Revalidation`, `Approval to proceed`.
5. After explicit user confirmation, record:
```
.\.venv\Scripts\python.exe tools/wf.py decide manuscript_human_reviewed YES --why "<what the user reviewed and what was revised>"
```

## Outputs
- `07_manuscript/human_review.md`

## Hard rules
- This is the user's scientific review point, before author information is requested.
- Do not treat the independent review as the user's approval.
- Do not change a number without rerunning the analysis that produced it.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "user reviewed full manuscript, supplement and tables; revisions=<summary>; approved to select journal"
```
