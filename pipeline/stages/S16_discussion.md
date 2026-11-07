# S16 - Discussion

Write a medical interpretation, not a second Results section. Use continuous paragraphs;
subheadings are optional when the design/current journal examples actually justify them.

## Prepare the writer's materials

The executor reads the actual accepted findings and selected full-text notes, then prepares
supported narrative points in the EXISTING sources:

- `01_protocol/study_facts.json`: `main_finding`, `clinical_relevance`, `cannot_claim`.
- `03_analysis/notes.md`: actual `Discussion points` or `Comparison with prior work`,
  `Possible mechanisms` (or `Possible explanations`) and `Limitations` including bias direction.
- Selected `06_refs/deepread/*.md`: the actual `How this supports or contradicts our finding`
  comparison points. Retain necessary source passages, not copied statistical tables.

A source-supported statement that mechanisms cannot be tested or net bias direction is
uncertain is valid. If a needed point is absent, inspect the actual design/literature and
add that supported point to the existing notes; do not invent a mechanism, limitation or direction.
Then run:

```powershell
.\.venv\Scripts\python.exe tools/manuscript/discussion.py prepare
```

It creates `.wf/discussion_materials.md`, a plain-language writing packet with no result
table, figure/table identifier, code payload or internal file path. Actual Results identity
is bound backstage so old summary material cannot silently certify changed findings.
An unchanged packet preserves the outline; this step never reruns an analysis.

## Outline, then draft

Before prose, write `.wf/discussion_outline.md` as six short working points:

- Principal finding
- Comparison with prior work and reasons for differences
- Possible mechanisms
- Clinical implications
- Limitations and direction of bias
- Conclusion

Use those labels as short bullets with concrete points, or as headings in this backstage
outline. This is not a requirement for six headings in the final Discussion. Validate/bind it:

```powershell
.\.venv\Scripts\python.exe tools/manuscript/discussion.py outline
```

For the first draft, if the executor has already read Results/tables/figures, use ONE narrow
Codex writing worker with `fork_turns="none"` when that capability is available. Supply ONLY
the plain-text packet, completed outline, short Discussion writing rules and necessary actual
published-source passages/citekeys. Limit its write to `07_manuscript/discussion.md`. Do not
pass the analysis chat, `results.md`, workbooks, figures, display numbers or protocol-change logs.
The writer does not run analysis, retrieve own-study result files, execute stage gates or
advance the workflow; it returns the single draft to the executor for those checks.
This is one S16 writing task, not a new reviewer or multi-round writer process. Routine feedback
edits only affected paragraphs; it does not automatically start another writing worker.
If a clean worker is unavailable, retain the same materials whitelist and separate factual
read-back, but do not claim clean-context isolation was achieved or open a new user-visible chat.

Briefly state the principal finding; compare with genuinely read research and explain
differences in population, measurement, follow-up, adjustment or setting. Distinguish plausible
mechanisms from demonstrated evidence. Explain clinical meaning and what this design cannot
establish. Give study-specific limitations and a defensible bias direction, or honestly explain
why it cannot be determined. Conclude at the certainty the evidence supports. Do not default
to an analysis inventory, display walkthrough, generic future work or exaggerated novelty.

## Executor check after drafting

The executor now separately reads the completed Discussion against actual Results and cited
source passages. Input isolation is not a waiver of factual verification. No new own-study
result is introduced; necessary numerical comparison with prior studies uses existing exact-source
bindings. Update only the affected source/draft and bindings.

```powershell
.\.venv\Scripts\python.exe tools/manuscript/discussion.py check
.\.venv\Scripts\python.exe tools/wf.py check
```

Clear near-whole sentence copies/numerical recaps of Results are blocked. A short reminder
of the main finding and shared statistical terminology are allowed. A supplementary-display
walkthrough is blocked; lesser reference concentration prompts actual reading. Do not raise
configuration thresholds or merely swap synonyms to turn transcription into a green result.
These diagnostics do not prove that comparisons, mechanisms or medical interpretation are good.
Read those dimensions in the existing executor acceptance and S18/S25 review.

Complete the existing benchmark argument/passages and selected deep-read coverage. A paper
that no longer supports the argument is removed from the selected index with its real reason,
not cited merely to fill the chapter. Preserve actual uncertainty, post-hoc status and sources.

## Outputs and closure

The only paper section is `07_manuscript/discussion.md`. Writing materials/outline remain
backstage under `.wf/` and are not submission uploads. Their dependencies use the existing
build receipts, not a second workflow or approval system. New v1.27-pinned work uses this path;
completed older-pinned work is not rewound, and explicit adoption stays scoped.

```powershell
.\.venv\Scripts\python.exe tools/wf.py advance --note "Discussion interprets the accepted finding; six-point outline completed; source comparisons and actual reader checks addressed"
```
