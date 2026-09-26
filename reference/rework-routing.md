# Scoped user revisions (v1.6)

All revisions remain inside the medpaper state machine. Reading or editing files directly is
an implementation step, not permission to bypass the owning stage, source of truth or gates.
An owning stage supplies rules, not a navigation target. New revision rounds keep their
review checkpoint and all completed-stage history. Never use `wf loop` for a local edit.

## Where repeated feedback belongs

- **S19 is the repeated scientific-review loop.** Use it for the assembled manuscript,
  supplementary Methods, results, references, tables, figures, legends and scientific
  interpretation. The user may request as many rounds as needed. Do not advance to journal
  selection until the user approves the scientific version.
- **S24 is the repeated journal-package loop.** Use it after journal selection for DOCX/PDF
  appearance, title page, declarations, cover letter, filenames, upload composition and any
  late correction. Journal-specific, meaning-preserving content changes route to the
  `08_submission/integration/` source owned by S21-S23; format-only changes may remain at S24.
  A genuine scientific change still routes back to its pre-S19 source and requires renewed
  S19 review. Do not freeze or start S25 until the user approves the actual package.

Feedback before either review checkpoint is handled inside the current stage and its owning
sources. Do not manufacture an S19/S24 approval or silently invalidate a prior science freeze.

## Multi-item revision rounds

For actual user feedback, prefer one batch round over repeatedly invoking the single-kind
command. Interpret the feedback once and write `project/temp/revision_plan.json`:

```json
{
  "feedback_verbatim": "The user's complete feedback, preserved without paraphrased loss.",
  "interpretation": "A concise explanation of the intended outcome, constraints, and what must remain unchanged.",
  "ambiguous_or_requires_user_decision": [],
  "items": [
    {
      "kind": "methods-wording",
      "change_type": "wording",
      "request": "Shorten the main Methods while retaining the reproducible detail in supplementary Methods.",
      "affected_sources": ["07_manuscript/methods.md", "07_manuscript/supplementary_methods.md"],
      "acceptance_criteria": ["Main Methods retains every design-critical fact", "Supplement contains no tables"]
    },
    {
      "kind": "figure-layout",
      "change_type": "layout",
      "request": "Increase label legibility in Figure 2 without changing data geometry.",
      "affected_sources": ["05_figures/out/Figure2.py"],
      "acceptance_criteria": ["Deterministic figure QC passes", "Fresh render is visually inspected"]
    }
  ]
}
```

If `ambiguous_or_requires_user_decision` is non-empty, ask one concise question and do not
guess. Otherwise start or extend the current round. The four change types are `layout`,
meaning-preserving `wording`, `administrative`, and `scientific`. Changed data, denominator,
outcome, model, comparison, interpretation or claim is scientific even if only one line.
Do not downgrade it to avoid checks. Declare every edited source, including supplementary
Methods when moving text there:

```powershell
.\.venv\Scripts\python.exe tools\rework.py batch --plan project\temp\revision_plan.json
.\.venv\Scripts\python.exe tools\rework.py status
```

The batch command stores the verbatim feedback, its SHA-256, the interpretation, atomic
items, acceptance criteria and earliest owning stage under `.wf/revisions/RNNN.json`. It
initially remains `collecting`, without invalidation or expensive construction. When the
user finishes the batch, run `tools/rework.py seal --why "<user end/apply instruction>"`.
An explicit request to implement a complete set of feedback permits `batch --sealed` directly.
Sealing invalidates only decisions whose evidence can change and preserves unrelated approvals. If
new feedback arrives before the round finishes, create another small plan containing only the
new items and run `batch` again; it extends the scope without resetting stage completion.
Identical feedback is deduplicated. `rebuild_files` identifies sources and actual dependants;
`validation_stages` identifies rules to recheck in place; `reuse_files` identifies files to
preserve. Owner rules do not authorize rerunning every subsequent stage. Read `reference/efficient-quality.md` for
build scope, risk-proportionate QA and backstage control maintenance.

After affected sources and true dependants have been rebuilt, still at S19 or S24, run
the actual scoped checks and record final files and visual inspections for each item:

```powershell
.\.venv\Scripts\python.exe tools\rework.py check
.\.venv\Scripts\python.exe tools\rework.py mark --item R001-01 `
  --changed-file 07_manuscript/methods.md `
  --changed-file 07_manuscript/supplementary_methods.md `
  --validated-by "S08 gates" --validated-by "assembly and citation checks" `
  --summary "Implemented the requested Methods restructuring and preserved all design-critical facts."

.\.venv\Scripts\python.exe tools\rework.py close `
  --summary "All requested items were rebuilt from their owning sources and passed the applicable gates."
```

`revision_rounds_closed` blocks S19/S24 approval and S25 audit when an item is pending, a
changed source is missing, or its final hash drifted after the round was closed.
Typed `validated-by` labels alone cannot close a round. The actual check is bound to current
files, decisions, engine rules and project configuration. Drift or an age of 24 hours requires
another check. `wf check` dispatches to it while the round is active; `wf advance` and `wf loop`
cannot escape an active round. Builders reject outputs outside its scope; the final check
also detects unrelated file changes by other scripts. This is an accidental-drift guard, not
a security sandbox against a same-privilege agent. Large raw/cache files use file metadata
for scope drift; independent data/reference provenance gates remain unchanged.

Before changing an artifact after it has been presented for review, run:

```powershell
.\.venv\Scripts\python.exe tools/rework.py plan --kind <kind> --why "<requested change>"
.\.venv\Scripts\python.exe tools/rework.py start --plan project/temp/revision_plan.json
```

`start` is now a sealed-batch alias and requires a plan. Use the owning stage's rules:

| Revision kind | Owning stage |
|---|---|
| study question, population or design | `study-design` -> S03 |
| raw/derived data | `data` -> S04 |
| model, estimate, numerical result or analysis meaning | `analysis` -> S05 |
| final protocol decision | `final-protocol` -> S06 |
| display inventory or substantive legend plan | `artifact-plan-or-legend` -> S07 |
| Methods or supplementary Methods content | `methods` -> S08 |
| Results wording with unchanged analysis | `results-wording` -> S09 |
| table content | `tables` -> S10 |
| figure content or rendering | `figures` -> S11 |
| meaning-preserving Methods wording | `methods-wording` -> S08 |
| figure/table layout with unchanged data and meaning | `figure-layout` / `table-layout` -> S11 / S10 |
| reference selection, citation or verified metadata | `references` -> S13 |
| Introduction | `introduction` -> S14 |
| Discussion | `discussion` -> S16 |
| title, abstract, keywords or initial assembly | `title-abstract-keywords` -> S17 |
| meaning-preserving copyedit | `manuscript-copyedit` -> S19 before freeze; at S24, S22 integration copy only |
| target journal or its rules | `journal` -> S20 |
| title page or declarations | `title-page-or-statements` -> S21 |
| cover letter, filename, upload list or package composition | `cover-letter-or-package-structure` -> S23 |
| journal-only figure/table layout | `journal-figure-layout` / `journal-table-layout` -> S23 integration only |
| Word layout with absolutely no visible-text change | `word-format-only` -> S23/S24 |

For S19 copyedits, update the owning component Markdown and rerun
`tools/manuscript/assemble.py`; `full_manuscript.md` must still match its components. A change
to a claim, interpretation, method, number, table or figure is not a copyedit and must use its
earlier route.

After S19 approval, `07_manuscript/scientific_master_freeze.json` is the boundary. S20-S25
must verify it unchanged. The active target journal works only on files derived under
`08_submission/integration/`, and the resulting differences stay in that journal's package.
Changing target journals creates a new integration copy from the same freeze; it does not
rewrite the accepted master. If a user requests a real scientific correction from S24, do
not retain the old `manuscript_human_reviewed` decision: route to the scientific owner,
rebuild, generate a new S19 review ZIP, obtain explicit approval again and replace the freeze.
Package-only items in a mixed batch are retained for later. After the new approval/freeze,
`wf advance` resumes a scoped package round at S24, without replaying S20-S23. Merge only
the changed science into existing journal copies, preserving unrelated user edits, then use
`tools/manuscript/journal_workspace.py rebase --why "<what was merged and preserved>"`.
It rebinds origin hashes but never copies over the journal text. Changed scientific text with
an unchanged journal copy is refused. Review semantic correctness and journal fit separately.
Removed supplements or a different journal require explicit inventory reconciliation;
do not delete user material or silently bless the old package.

At S23, capture `package_content_baseline.json` after all DOCX files and `manifest.json` are
final. S24 may preserve manual Word formatting only while the visible-text hash is unchanged.
If Word text changes, reconcile the requested wording to its Markdown/data/table/figure source,
run the owning scoped task and rebuild the true dependants. A source-based S23 build task
may capture the baseline in-place at S24 only with matching real builder input/output
receipts. Manual Word text edits and layout-only rounds cannot be blessed by recapture.

Existing schema-1 rounds finish through their recorded legacy gates; do not discard their
evidence. All newly opened rounds use scoped revision. Scientific changes require the scoped
S18 review. Cosmetic work reuses the old independent verdict plus current local content/visual
checks, without claiming that the old reviewer saw the new version.
After corrections, present the revised artifact again, obtain the
required user confirmation, freeze the new package and run one new independent audit.
Unchanged artifacts may be reused; rebuild only the changed artifact and its actual dependants.

## Context and token discipline without quality loss

Token use is reduced by avoiding repeated interpretation and irrelevant rereading, not by
reducing the requested work:

1. Preserve the user's exact feedback once, then resume from `tools/rework.py status` after
   context compaction instead of reconstructing it from conversation memory.
2. Read the active item, its declared source files, shared result/reference evidence and the
   specific downstream consumers only. Do not reload every manuscript file for a local edit.
3. Change the earliest source of truth. Reuse immutable raw data, verified literature,
   analysis results, journal snapshots and unchanged artifacts when their hashes/dependencies
   did not change.
4. Rebuild only the dependency closure. A Methods wording change rebuilds manuscript/package
   outputs but does not rerun data acquisition; a changed estimate reruns its analysis and all
   dependent prose/tables/figures.
5. Run cheap structural checks first, targeted scientific/functional checks second, and the
   required final visual or independent review once on the resulting revision.
6. Never cite token limits, context compaction, runtime or convenience as a reason to omit an
   item, shrink the analysis, skip a gate, reduce literature verification or accept a partial
   artifact. If the context compacts, continue from the persisted round until every item is
   complete.
