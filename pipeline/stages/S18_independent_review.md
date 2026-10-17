# S18 - Independent publication-readiness review

Give the reviewer the registration/reporting boundary from AGENTS.md: no default public
registration or prefilled reporting checklist for ordinary mining/retrospective studies.
Judge actual methodological completeness and validity, not missing nonrequired paperwork;
selected-journal reporting forms are handled later. Never invent a registration or method.

## Purpose
Test the frozen complete manuscript, supplementary Methods, every table and rendered figure before the user
edits them. This is an independent scientific/editorial audit, not another writing pass.

## Procedure
Start M001 before delegation: `tools/review_round.py start --scope manuscript`.
Use its exact `reviewed_artifacts` hashes, including bibliography exports when present.
Attach the actual report with `tools/review_round.py attach --scope manuscript --report
project/07_manuscript/independent_publishability_review.md` before changing inputs.
M001 remains open for safe executor correction at S19; do not ask for user decisions per
finding. Follow S19 for close, one report, one question and the actual user answer.

1. Freeze the inputs for this audit: `07_manuscript/full_manuscript.md`,
   `07_manuscript/supplementary_methods.md` when present, every workbook under
   `04_tables/main/` and `04_tables/supplementary/`, every planned rendered figure, legends,
   table captions, and `01_protocol/artifact_plan.json`.
   Include the source-bound `01_protocol/artifact_benchmark.md`. Evaluate whether the real
   comparator-derived plan adequately covers the clinical argument, not fixed numeric quotas.
   Use `tools/review_round.py start --scope manuscript` once for the exact paths/hashes. Supply
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
   Include the `reviewed_artifacts` JSON from review_round.py in one fenced JSON block inside
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
   Do not hand known routine citation/display/writing defects to the user as a finished
   delivery. At the S19 checkpoint, correct safely resolvable QA findings through the same
   scoped owner rules before presenting materials; label their origin as executor/independent
   QA, never invented user feedback. Preserve the original independent verdict and record
   actual primary revalidation; renewed independent review is for material changed science,
   not another automatic audit of unchanged files. Ask only if author judgment/authority is
   genuinely needed. The user's explicit S19 approval still cannot be inferred.

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
