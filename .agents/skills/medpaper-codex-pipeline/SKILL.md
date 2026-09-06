---
name: medpaper-codex-pipeline
description: Run a gated, resumable medical or clinical research-paper workflow from feasibility and data analysis through verified references, journal-native artifacts, manuscript sections, journal selection, and a submission-ready package. Use for medical research projects and manuscript production in this repository; do not use it for reviewing an unrelated finished paper or for non-medical writing.
metadata:
  version: "1.3.8"
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
`tools/rework.py status` after context compaction. Route the batch to its earliest owning
stage, update the source of truth, rebuild only actual dependants, and close the round only
after every atomic item has a final-file hash and validation record. Preserve unaffected
approved evidence, but never omit an affected gate, request, analysis, file or review to save
tokens or context. There is no fixed revision-round limit. Never patch `full_manuscript.md` or
narrative text inside a DOCX as a detached file. At S24, a Word-only edit is permitted only
when `tools/package_content.py verify` proves that visible text is unchanged.

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
  and independently re-fetches the records live at S13 and every later manuscript/submission
  checkpoint through the final audit. Never hand-write or patch
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

## Safety and completion

Keep patient-level/private data local unless the user explicitly authorizes an external
transfer. Inspect every rendered visual artifact before recording its visual-review decision.
At a stage requiring a material user choice, such as the target journal or private-data
access, ask once and wait; otherwise keep working until the gate passes and the stage advances.

