---
name: medpaper-codex-pipeline
description: Run a gated, resumable medical or clinical research-paper workflow from feasibility and data analysis through verified references, journal-native artifacts, manuscript sections, journal selection, and a submission-ready package. Use for medical research projects and manuscript production in this repository; do not use it for reviewing an unrelated finished paper or for non-medical writing.
metadata:
  version: "1.6.0"
  entrypoint: ".\\.venv\\Scripts\\python.exe tools\\wf.py status"
---

# Medpaper pipeline

The workflow lives in `pipeline/pipeline.toml` and `pipeline/stages/*.md`. Do not reconstruct
it from memory or from the conversation.

## Required loop

Run this before project work and again after context compaction:

```powershell
.\.venv\Scripts\python.exe tools\wf.py status
```

`status` is compact and local; read `tools/wf.py card` before acting. Use `status --full`
only for complete diagnostics and `check` for current validation.

If `.venv` is absent, run `uv run --python 3.13 python bootstrap.py` first. Then complete only
the active card's declared outputs:

```powershell
.\.venv\Scripts\python.exe tools\wf.py check
.\.venv\Scripts\python.exe tools\wf.py advance --note "what was produced, decided, and remains open"
```

Never infer the stage, create future-stage artifacts, or bypass a red gate.

When the user requests a revision after an artifact has been presented, keep it inside the
repeatable S19 scientific-review loop or S24 journal-package loop. Read
[revision routing](../../../reference/rework-routing.md), save the verbatim feedback and its
single interpretation as one persisted batch with `tools/rework.py batch`, and run
`tools/rework.py status` after context compaction. Keep the review checkpoint; owning stages
supply checks, not navigation targets. Follow its rebuild/check/reuse lists, update canonical
sources and rebuild only actual dependants. Run `rework.py check` before marking/closing;
typed validation labels alone cannot close a round. Preserve unaffected
approved evidence, but never omit an affected gate, request, analysis, file or review to save
tokens or context. There is no fixed revision-round limit. Never patch `full_manuscript.md` or
narrative text inside a DOCX as a detached file. At S24, a Word-only edit is permitted only
when `tools/package_content.py verify` proves that visible text is unchanged.
After a late scientific correction and renewed S19 approval, resume scoped package work at
S24 without replaying S20-S23. Merge the science delta into existing journal copies; preserve
unrelated user edits and rebind with `journal_workspace.py rebase`. Read the routing reference.

For reader-facing work, benchmark actual medical prose and displays, not counts alone.
Use S07's reader contracts and early abbreviation policy. S18 reviews real rendered figures
as well as tables and prose, with bound input hashes and substantive reader-comprehension
findings. Metadata checks cannot replace the independent reviewer's actual understanding.

## Evidence and fact integrity

- Data acquisition means every record in the S03 protocol-defined universe, not a convenient
  subset. Before analysis, follow every page/cursor, preserve machine-countable source-total
  and received-payload receipts, register every raw/acquisition file with
  `tools/data_manifest.py`, and pass the non-overridable `data_acquisition_complete` gate.
  Never add `LIMIT`, `TOP`, `head()`, `sample()`, first-N slicing, a fixed page cap or a
  narrower query to save time, tokens, download volume or compute. A non-analytic pilot must
  be followed by the full acquisition. Converting a census to a scientific sampling design
  requires the user's explicit `protocol_sampling_authorized=YES` decision; a genuine
  source-imposed restriction requires `partial_data_authorized=YES`. Read
  [data acquisition integrity](../../../reference/data-acquisition-integrity.md).
- A bibliographic fact is usable only after the bundled verifier performs a fresh PubMed
  EFetch. `verified: true` alone is never evidence: the gate reparses hashed raw PubMed XML,
  binds it to the exact `library.json`, compares PMID and DOI as well as bibliographic fields,
  and checks independent live evidence at S13 and later manuscript/submission checkpoints,
  with hash-bound reuse inside the configured short freshness window. Never hand-write or patch
  `library.json`, `verified.json`, `refs.bib` or `refs.ris`; reference-integrity gates cannot
  be waived with `--force`.
- A full text acquired through an open-access or explicitly authorized institutional route
  must be registered with `tools/pubmed/fulltext.py register`; paywalled abstracts do not
  count as deep reads. Never use illicit sources or transfer login cookies without explicit
  authorization.
- Every reported number must originate in executed analysis code and already exist in
  `project/03_analysis/results/*.json`. Language edits may not change numbers, citekeys, or
  figure/table references.
- Do not draft an AI-use disclosure unless the user explicitly requests that content.

## Working with other skills and plugins

This skill owns sequencing, output paths, and gates. Other capabilities may help only inside
the active stage:

- Scholarly retrieval: discovery/acquisition helper; pipeline verification remains decisive.
- Spreadsheets: render and inspect S10 workbooks after the pipeline writer creates them.
- ImageGen: optional second visual critic at S11 only; it may flag layout and readability
  defects but must not redraw or edit scientific plots. Fix plotting code and re-render.
- Independent review: at S18 spawn exactly one read-only subagent for the frozen complete
  manuscript, optional supplementary Methods and tables; preserve its verdict for S19.
- User scientific review: whenever an initial or revised scientific version reaches S19,
  build and verify the versioned third-party ZIP with
  `tools/manuscript/review_package.py`, present clickable locations for the manuscript,
  optional supplementary Methods, tables, figures, verified BibTeX/RIS exports, independent
  verdict and exact ZIP, and
  stop for feedback. Advance only after the user explicitly says no further review is needed;
  delivery, silence, thanks or a generic “continue” is not approval. Bind that decision to the
  exact current package ID; this release gate cannot be bypassed with `--force`.
- Scientific-master freeze: after that explicit S19 approval, run
  `tools/manuscript/scientific_freeze.py freeze`. From S20 onward, the accepted
  `07_manuscript` sources are immutable. Initialize `08_submission/integration/` with
  `tools/manuscript/journal_workspace.py init`; all target-journal wording, abstract
  structure, title-page, statements and package changes stay in that derived layer. A real
  scientific correction routes to its earliest owner and requires a new S19 ZIP, approval
  and freeze. Switching journals derives a new integration layer from the same frozen master.
- Documents/PDF: build, render and inspect S23 submission files without rewriting scientific
  facts. Use the deterministic DOCX builder so typography, links and heading behavior pass.
- Final package review: at S24 let the user inspect and modify the actual upload files, ask
  whether the revalidated package is explicitly `OK` and whether one independent subagent
  should perform the final review, then freeze that exact revision. At S25 give the frozen
  package and official journal guide to exactly one independent read-only subagent. It first
  reads the submission as an ordinary reader, then screens it as a journal editor for unclear
  content and low-level errors, and finally checks compliance, omissions and cross-file
  mismatches. Only `PASS` completes the workflow; changed packages return to S24 for renewed
  confirmation.
- Reporting, de-identification, study-design, or statistical helpers: advisory or code helpers
  whose outputs must land at the active card's declared path and satisfy its gate.

Do not activate a second end-to-end writing, analysis, reference-management, figure, journal,
or submission workflow. Read [Codex integration](../../../reference/codex-integration.md) when
another skill or plugin is relevant.

Figure legends identify the display, map panels and decode symbols; they do not restate the
direction or numerical findings from Results. When display-item abbreviations become crowded,
define them once under `Declarations and Statements > Abbreviations` and remove repeated local
blocks unless the official journal guide explicitly requires them. Final Word files contain no
literal U+2193 down arrow and no text-wrapping/manual line-break controls. Each Word XML part
must also be free of `outlineLvl`, `keepNext`, `keepLines`, `pageBreakBefore` and paragraph
border residue; Markdown headings are flattened to the Normal-based `SectionHeading` style.
Use exactly one Figure legends section title and do not repeat `Figure N` in the legend body.
Supplementary Methods contains prose only: move every table to the separate three-line
supplementary workbook and remove Markdown thematic breaks.

## Quality and efficient execution (v1.6)

Read [quality-preserving execution](../../../reference/efficient-quality.md) at S06/S07, for revisions and submission production.
S06 freezes the analysis contract and four-part clinical story before writing. S07 requires
actual low-cost display prototypes and source-bound reader explanations before formatted work.
Feedback `batch` defaults to collection; seal after the user's apply/end instruction, or use
`--sealed` for an already complete apply-now request. Rebuild the persisted file dependency
closure; after two full build cycles switch to targeted correction, without limiting revisions.
Use Tavotto's desktop handoff for user-facing Matplotlib figures; keep Python beside vector PDF
and respect the user's desktop-first preference. Internal diagnostics are exempt.
S23 derives portal fields and explicit word counts from the final DOCX and the existing unified
`author_info.json`. S24 records user OK before creating a read-only upload-only release.
Caches, rendering evidence and control records are outside the upload freeze; their refresh
is not a new author revision. S25 audits the release and binds both upload and guideline-context
identities. Independent review unavailability is a pending audit, never a fabricated PASS.
Reference verification covers PMID/DOI/PMCID and complete ordered authors. S13/S25 always
make fresh independent live requests. At other gates, reuse independent live XML only when identities/hashes match and it is within the 24-hour freshness window;
otherwise fetch again and fail closed. Renewed evidence alone does not alter scientific facts.

## Safety and completion

Keep patient-level/private data local unless the user explicitly authorizes an external
transfer. Inspect every rendered visual artifact before recording its visual-review decision.
At a stage requiring a material user choice, such as the target journal or private-data
access, ask once and wait; otherwise keep working until the gate passes and the stage advances.
