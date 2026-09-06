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

This is a repeatable review loop, not a one-time checkpoint. The user may provide several
rounds of feedback. Remain in, or return to, S19 until the user explicitly approves the
scientific manuscript.

## Procedure
1. Summarise the independent verdict and list only the revisions that materially affect
   publishability. Link the four artifact groups above for direct inspection.
2. When feedback is received, preserve it verbatim and interpret it once into atomic items in
   `project/temp/revision_plan.json` using `reference/rework-routing.md`. Each item must name
   its kind, true source files and observable acceptance criteria. If an item is ambiguous or
   needs a scientific choice, ask one concise question rather than guessing. Start the batch:
```
.\.venv\Scripts\python.exe tools/rework.py batch --plan project\temp\revision_plan.json
.\.venv\Scripts\python.exe tools/rework.py status
```
   The tool rewinds once to the earliest owner across the whole batch and persists the plan
   under `.wf/revisions/`. If the context compacts, resume from `tools/rework.py status`; do
   not reinterpret the conversation or silently reduce the requested work.
3. Update each earliest source of truth, then rebuild only its true dependants. Unchanged raw
   data, results, verified references, tables, figures and journal evidence are reused when
   their dependency did not change. A meaning-preserving copyedit updates its owning component
   Markdown; never patch `full_manuscript.md` alone. A changed number reruns the producing
   analysis and every dependent prose/table/figure. Token pressure, runtime and context size
   never justify omitting an item or skipping a gate.
4. Run `tools/manuscript/assemble.py --check`, then re-run manuscript structure, citation,
   number-provenance and artifact-reference checks. The S19 gate requires the canonical
   manuscript to match its component sources exactly.
5. When the workflow returns to S19, compare every item against its acceptance criteria. Mark
   the final changed source files and completed gates/inspections, then close the round:
```
.\.venv\Scripts\python.exe tools/rework.py mark --item <RNNN-NN> --changed-file <path> --validated-by "<gate or inspection>" --summary "<resolution>"
.\.venv\Scripts\python.exe tools/rework.py close --summary "<all requested items completed and revalidated>"
```
   Present the revised artifacts again. New user feedback opens the next round; there is no
   fixed round limit.
6. Write or append `project/07_manuscript/human_review.md` with headings `Materials presented`,
   `Independent verdict`, `User-requested revisions`, `Revalidation`, `Approval to proceed`.
   Keep a concise round-by-round summary and do not paste the entire manuscript or feedback
   history into this file.
7. Only after every revision round is closed and the user explicitly confirms, record:
```
.\.venv\Scripts\python.exe tools/wf.py decide manuscript_human_reviewed YES --why "<what the user reviewed and what was revised>"
```

## Outputs
- `07_manuscript/human_review.md`

## Hard rules
- This is the user's scientific review point, before author information is requested.
- Do not treat the independent review as the user's approval.
- Do not change a number without rerunning the analysis that produced it.
- Do not edit the assembled manuscript as a detached file. Every revision is recorded inside
  the workflow and applied to the source owned by the routed stage.
- Do not ask the user to repeat earlier feedback after compaction; the active round is durable.
- Efficiency comes from scoped reading and dependency-based rebuilding, never from reducing
  analyses, references, checks, independent review or visual QA.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "user reviewed full manuscript, supplement and tables; revisions=<summary>; approved to select journal"
```

