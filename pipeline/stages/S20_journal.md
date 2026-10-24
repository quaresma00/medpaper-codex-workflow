# S20 - Choose a legitimate current SCIE journal and isolate its adaptation

Verify current official author instructions, article type, indexing and realistic fit. Q3/Q4
are acceptable; do not claim a current JCR quartile from an inaccessible primary source.
Use the existing dated source cache when valid; unresolved indexing or integrity concerns
remain explicit. Do not create a reporting checklist unless this journal requires one.

Verify the scientific master freeze. Journal-only edits go to 08_submission/integration/;
never rewrite accepted science for headings, figure numbers, length or upload slots.
Structure explicit rules by article type and field: mandatory/optional/recommended/unstated;
use null for an unstated cap, and retain the current official source. Recheck main versus
supplementary display allocation before expensive Word/figure production.

Record actual font/width/resolution/heading/keyword/legend rules in the existing journal
configuration. The optional boolean line_numbers applies continuous numbering to the main
manuscript only; do not add line numbers by default. Early production assumptions are
reversible and are not an author-approved journal selection.

For selection evidence, journal schemas and integration initialization, use full details.

## Full procedure, read once when needed
`reference/stage_details/S20_journal.md` (`tools/wf.py card S20_journal --details`).
On first execution read the applicable detailed procedure; later local corrections reuse
already-read guidance and go directly to affected owner rules. After compaction use
`tools/wf.py handoff`, then retrieve only missing context. The actual gates remain unchanged.
`reference/structural-quality.md` v1.17 explains runtime fixes and preserved boundaries.

## Outputs
Before closing, read `reference/project-benchmarking.md`, read same-journal close full texts
and record the resulting structure/display/reference adaptations in
`08_submission/integration/journal_benchmark.md`; bind it to this journal/article type and
seal with `benchmark.py seal --layer journal`. Comparator-only `fulltext.py --pmid` acquisition
must not modify the frozen scientific bibliography. Reuse already read suitable papers.
Store explicit display caps in `submission_requirements.json.display_limits`; null means
unstated. Apply those caps to the derived plan at S22 before Word production, not to the master.

- `08_submission/journal_shortlist.md`
- `08_submission/target_journal.json`
- `08_submission/guidelines_extract.md`
- `08_submission/docx_style.json`
- `08_submission/submission_requirements.json`
- `08_submission/integration/journal_workspace.json`

## Close
Run `tools/wf.py check` (or the active scoped revision check). Fix actual failures before
`tools/wf.py advance --note "<actual completed work>"`. Stages are not turn boundaries.
Review stages still require the real author statement; generic continuation is not approval.
