# S12 - Reconcile artifacts and review Original-article viability before Abstract

Tables and figures are already final enough to support Results: S10 tables -> S11 figures ->
S09 Results. This checkpoint reconciles actual outputs and obtains the early independent
scientific judgment, before Introduction/Discussion/Abstract and expensive full assembly.
Use `reference/early-scientific-review.md`; no new workflow stage or review ZIP is created.

## Reconcile the real sources

1. Read actual Methods, Results, each workbook and real main/supplement figure previews.
   Verify populations, denominators, groups, effect measures, interval meaning, panel mapping,
   labels and captions against executed analysis. Mechanical value checks do not prove meaning.
2. Correct the earliest source. Invoke affected S05/S08/S09/S10/S11 rules in a scoped correction
   at S12; rebuild only real consumers. Do not use `wf loop`, reset stages, generate future
   sections early or independently alter several surface numbers. Never delete an otherwise
   necessary sentence just to hide a mismatch.
3. Write `07_manuscript/reconciliation.md` with checked display locations and actual
   discrepancies/corrections. Generation or QC receipts do not replace looking at the files.

## Independent science review before further writing

Run `tools/early_review.py start --executor-id <actual-id>`. Delegate exactly one separate
read-only subagent using the returned actual files and report destination. It reads protocol/
Methods, executed code/results, tables, rendered figures and recent full-text comparators;
neither Abstract nor a complete paper is needed. Do not substitute a simulated self-review.

Attach its complete report with `tools/early_review.py attach --report <actual-report>`.
It judges `original_article` with GO/REVISE/NO_GO and the marginal value of more analysis.
Show its practical opinion and exact report path to the author promptly.

- GO permits writing; it means plausible publication, not promised acceptance.
- REVISE: report exact barriers, fix true sources in scope and obtain actual focused
  scientific revalidation where material inputs changed.
- NO_GO or no useful analytical route: tell the author now. Explain whether validity,
  Original-article scope or publication fit is the barrier, stop unproductive expansion,
  and wait for a pivot/stop decision. Do not hide this until a full paper is drafted.

Unchanged versions reuse the real review. S18 later reads the complete medical argument and
expression; it does not repeat this science audit without new evidence.

## Outputs and close

- `07_manuscript/reconciliation.md`
- `.wf/early_review.json` and the designated independent report (backstage controls)

Run `tools/wf.py check`; source/provenance failures and a non-GO early verdict stay blocking.
Advance after actual current findings support GO, without replaying the completed stage tail.
