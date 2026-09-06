# S19 - User review of the complete paper

## Purpose
Give the user one coherent scientific package to inspect and revise before journal-specific
formatting or administrative author collection begins.

## This stage needs the user
Create a versioned third-party review ZIP and present its clickable path. Also present
clickable paths to every directly reviewable artifact group:
- `07_manuscript/full_manuscript.md`;
- `07_manuscript/supplementary_methods.md`, if present;
- `04_tables/main/` and `04_tables/supplementary/`;
- `05_figures/out/` and `05_figures/legends.md`;
- `06_refs/refs.bib` and `06_refs/refs.ris`;
- `07_manuscript/independent_publishability_review.md`;
- the exact ZIP printed by `tools/manuscript/review_package.py build`.

The ZIP contains the current manuscript, optional supplementary Methods, XLSX tables,
rendered PNG figures, legends/captions, verified bibliography exports, the independent
verdict, a human-readable review guide and a hash manifest. It excludes patient-level data,
credentials, full-text literature
files and internal analysis code. Each scientifically changed version receives a new
versioned ZIP; an unchanged source set reuses the already verified ZIP rather than creating a
duplicate.

Do not ask for authors, affiliations, ORCIDs, correspondence, funding or other title-page
administration here. Tell the user that they can review the materials now, send the ZIP to a
third party, or provide revisions directly. Then use this explicit prompt:

> 可审核材料和第三方审核 ZIP 已准备好，位置如下。您可以现在逐项审核、把 ZIP
> 转交第三方，或直接告诉我修改意见。若确认不再需要继续审核，请明确回复：
> “无需继续审核，可以进入下一步”。在收到这一明确确认前，工作流将停留在 S19。

Do not interpret silence, thanks, file delivery, “continue”, “looks fine”, or completion of one
revision request as no-further-review approval. A semantically explicit statement that no
further review is needed is required.

This is a repeatable review loop, not a one-time checkpoint. The user may provide several
rounds of feedback. Remain in, or return to, S19 until the user explicitly states that no
further review is needed.

## Procedure
1. Build and verify the review package before asking the user to inspect anything:
```
.\.venv\Scripts\python.exe tools/manuscript/review_package.py build
.\.venv\Scripts\python.exe tools/manuscript/review_package.py verify
```
   Summarise the independent verdict and list only revisions that materially affect
   publishability. Show the exact ZIP path and all review-material locations listed above.
   Never merely say that files are “in the project”.
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
   Rebuild the versioned S19 ZIP after closing the round, verify it, and present the revised
   artifacts and new ZIP path again. New user feedback opens the next round; there is no fixed
   round limit.
6. Write or append `project/07_manuscript/human_review.md` with headings `Materials presented`,
   `Independent verdict`, `User-requested revisions`, `Revalidation`, `Approval to proceed`.
   Record each presented ZIP revision, package ID and path. Keep a concise round-by-round
   summary and do not paste the entire manuscript or feedback history into this file.
7. Only after every revision round is closed, the latest review ZIP passes its current-source
   gate, and the user explicitly says that no further review is needed, record the normalized
   decision:
```
.\.venv\Scripts\python.exe tools/wf.py decide manuscript_human_reviewed NO_FURTHER_REVIEW --why "<quote or closely preserve the explicit confirmation; include the exact ZIP revision and at least the first 12 characters of its package_id>"
```

## Outputs
- `07_manuscript/human_review.md`
- `07_manuscript/review_packages/latest_review_package.json`
- versioned `07_manuscript/review_packages/S19-review-vNNN-<package-id>.zip`

## Hard rules
- This is the user's scientific review point, before author information is requested.
- Do not treat the independent review as the user's approval.
- Do not advance merely because the review files or ZIP were delivered. Offer review, give
  exact locations, wait, and require explicit no-further-review confirmation.
- Every changed S19 version must have a newly built and verified versioned ZIP. Never package
  stale sources or include patient-level/private data.
- The S19 release gate is non-overridable and binds the user's confirmation to the exact
  current package ID. A confirmation for v001 cannot release v002.
- Do not change a number without rerunning the analysis that produced it.
- Do not edit the assembled manuscript as a detached file. Every revision is recorded inside
  the workflow and applied to the source owned by the routed stage.
- Do not ask the user to repeat earlier feedback after compaction; the active round is durable.
- Efficiency comes from scoped reading and dependency-based rebuilding, never from reducing
  analyses, references, checks, independent review or visual QA.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "user was shown exact review paths and ZIP revision=<vNNN/package-id>; revisions=<summary>; explicitly stated that no further review is needed"
```

