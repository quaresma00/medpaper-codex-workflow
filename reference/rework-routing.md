# User-requested revision routing

All revisions remain inside the medpaper state machine. Reading or editing files directly is
an implementation step, not permission to bypass the owning stage, source of truth or gates.

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

Feedback can also arrive at any other stage. Record it immediately and route it to the
earliest owner; the review loop to return to is the active S19 or S24 round.

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
      "kind": "methods",
      "request": "Shorten the main Methods while retaining the reproducible detail in supplementary Methods.",
      "affected_sources": ["07_manuscript/methods.md", "07_manuscript/supplementary_methods.md"],
      "acceptance_criteria": ["Main Methods retains every design-critical fact", "Supplement contains no tables"]
    },
    {
      "kind": "figures",
      "request": "Increase label legibility in Figure 2 without changing data geometry.",
      "affected_sources": ["05_figures/code/fig2.py", "05_figures/out/Figure2.png"],
      "acceptance_criteria": ["Deterministic figure QC passes", "Fresh render is visually inspected"]
    }
  ]
}
```

If `ambiguous_or_requires_user_decision` is non-empty, ask one concise question and do not
guess. Otherwise start or extend the current round:

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
new items and run `batch` again; it is appended to the same active round and rewinds farther
only when necessary after it is sealed. Identical feedback is deduplicated.
`rebuild_files` records actual file dependencies. Read `reference/efficient-quality.md` for
build scope, risk-proportionate QA and backstage control maintenance.

After all affected sources and true dependants have been rebuilt and the workflow has
returned to S19 or S24, record the final files and completed checks for each item:

```powershell
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

Before changing an artifact after it has been presented for review, run:

```powershell
.\.venv\Scripts\python.exe tools/rework.py plan --kind <kind> --why "<requested change>"
.\.venv\Scripts\python.exe tools/rework.py start --kind <kind> --why "<requested change>"
```

Use the earliest stage that owns the changed fact or artifact:

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

At S23, capture `package_content_baseline.json` after all DOCX files and `manifest.json` are
final. S24 may preserve manual Word formatting only while the visible-text hash is unchanged.
If Word text changes, reconcile the requested wording to its Markdown/data/table/figure source,
run the owning route, rebuild the true dependants and capture a new baseline at S23. Never
recapture a baseline at S24 merely to bless an edited DOCX.

The legacy single-kind `start` command conservatively invalidates every downstream decision;
the preferred batch-round command invalidates only decisions whose evidence may have changed.
After corrections, progress through the gates, present the revised artifact again, obtain the
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
