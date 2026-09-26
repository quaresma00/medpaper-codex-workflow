# S18 - Independent publication-readiness review

## Purpose
Test the frozen complete manuscript, supplementary Methods, every table and rendered figure before the user
edits them. This is an independent scientific/editorial audit, not another writing pass.

## Procedure
1. Freeze the inputs for this audit: `07_manuscript/full_manuscript.md`,
   `07_manuscript/supplementary_methods.md` when present, every workbook under
   `04_tables/main/` and `04_tables/supplementary/`, every planned rendered figure, legends,
   table captions, and `01_protocol/artifact_plan.json`.
   Run `tools/manuscript/readiness.py review-inputs` for the exact paths and hashes. Supply
   those real files, not a textual description of images. The reviewer opens figures and
   inspects tables; if its tools cannot read them, mark the review incomplete, not PASS.
   Do not change them while the reviewer is working.
2. Spawn exactly one independent subagent. Give it the frozen paths and ask it to review
   only; it must not edit files or rewrite the paper. The reviewer must judge whether the
   study could be published in a legitimate current SCIE journal, including a realistic
   low-impact/Q3/Q4 venue, rather than whether it belongs in a top journal.
3. Require the reviewer to check scientific validity, internal consistency, reporting
   completeness, whether the Methods support reproducibility without bloating the main
   text, whether tables/supplement agree with the manuscript, claim strength, fatal versus
   correctable problems, and the likely acceptance ceiling. It must distinguish data or
   design barriers from presentation defects.
   Check legend meaning in context: panel mapping and decoding information must suffice
   without repeating Results, including paraphrased findings that a phrase check cannot catch.
   Verify that centralized abbreviation definitions cover the terms used in the figures and
   tables, including mixed-case medical terms; do not treat every uppercase label as an acronym.
4. Preserve the review in `project/07_manuscript/independent_publishability_review.md`
   under these exact headings: `Verdict`, `Critical barriers`, `Scientific validity`,
   `Reporting completeness`, `Tables and supplementary material`, `Journal suitability`,
   `Required revisions`, `Post-revision outlook`, `Reader comprehension`, `Medical presentation`.
   Include the `reviewed_artifacts` JSON from the handoff in one fenced JSON block inside
   this existing report after verifying the files actually reviewed are unchanged.
   Under Reader comprehension explain the clinical question, population/comparison,
   principal result and what cannot be inferred in plain language; identify ambiguous
   displays by ID. Under Medical presentation judge whether prose, table labels/footnotes,
   figure encodings and legends work for a medical reader without pipeline knowledge.
   Review numeric identities, not merely whether the same number exists somewhere in JSON.
   Hash coverage proves the input version, not actual understanding or scientific validity.
5. Record one decision:
```
.\.venv\Scripts\python.exe tools/wf.py decide independent_publishability "READY|REVISE|NOT_READY" --why "<one-sentence basis from the independent review>"
```
   `READY` means ready for the user's review and realistic SCIE targeting; `REVISE` means
   potentially publishable after listed corrections; `NOT_READY` means a material validity
   barrier remains. The workflow may still advance so the user can inspect the evidence.

## Outputs
- `07_manuscript/independent_publishability_review.md`

## Hard rules
- One independent reviewer only; no review committee and no repeated audit of unchanged
  material.
- The reviewer receives the full manuscript, optional supplementary Methods, tables and actual figures,
  not isolated excerpts.
- For scientific revisions, supply the frozen current package plus the concise revision
  delta; focus the renewed audit on changed claims/displays and their consistency with the
  whole paper. Meaning-preserving layout/copyedits reuse the prior independent verdict and
  require local visual/content checks; do not falsely claim that the old reviewer saw new files.
- Do not let the reviewer silently edit the frozen source or manufacture missing evidence.
- A low impact factor is not a defect when the journal is current SCIE and a realistic fit.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "independent verdict=<READY|REVISE|NOT_READY>; critical barriers: <none or list>; frozen files unchanged"
```
