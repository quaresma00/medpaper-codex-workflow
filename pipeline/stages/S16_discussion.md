# S16 - Discussion

Use the already-read close medical comparators to settle the narrative before Word build.
Default to connected paragraphs, not a subheading for every argument. Add subheadings only
when the actual design, target-journal examples or explicit author rules support them.

## Purpose
Interpret the finding against the literature you actually read. One file, this stage only.

## Inputs
- `06_refs/deepread/*.md` - argument-bearing full texts, actually read
- `06_refs/library.json` - abstracts for the wider context
- `03_analysis/notes.md` -> `Discussion points`, `Limitations`, `Surprises`
- `07_manuscript/results.md` - what you may interpret (and nothing beyond it)
- `01_protocol/protocol_diff.md` - internal context for material scientific limitations, not a manuscript change log

## Procedure
1. A useful narrative route, not mandatory subheadings or an inflexible order:
   1. **Principal finding** - one paragraph, plain, no hedging, no new numbers.
   2. **Comparison with prior work** - this is where the deep reads earn their place.
      Where you agree, say with whom and why. Where you disagree, name the study and give a
      mechanistic or methodological reason (population, exposure definition, follow-up,
      adjustment set, era). Every deep-read paper must appear here; the gate checks it.
   3. **Interpretation / mechanism** - clearly labelled as inference, not as demonstrated.
   4. **Clinical or research implications** - proportionate to the evidence. A single
      observational study does not change practice.
   5. **Strengths and limitations** - specific and quantified. Include scientifically
      material limitations, residual confounding, generalisability limits,
      power, and measurement error. State the direction each bias would push the estimate.
      Keep internal plan revisions in `01_protocol`; do not narrate every deviation or
      announce an unregistered protocol for ordinary retrospective mining. Preserve true
      post-hoc/exploratory status and any specifically applicable protocol reporting.
   6. **Conclusion** - two or three sentences, no stronger than the Results support.
2. Write `project/07_manuscript/discussion.md` with pandoc citations `[@key]`.
3. Complete Discussion argument/passages in the sealed benchmark, including contrary evidence
   where relevant. Run `tools/wf.py check` for actual coverage and cited deep reads, not fixed
   chapter counts. Keep a coherent medical argument, not a separate heading per analysis.

## Outputs
- `07_manuscript/discussion.md`

## Hard rules
- ONE section file this stage.
- No new results. Any number here must already be in `results.md` and in a results JSON.
- No causal language for an observational design. "Associated with", not "leads to".
- Limitations are not a list of generic caveats. "Single-centre design" alone is not a
  limitation section; say what it does to the estimate.
- Do not claim a finding is "the first" unless S02's search supports it, and cite that.
- No stock closers: not "further studies are warranted" as the whole future-work paragraph,
  not "paves the way", not "holds promise".

## Close
```
.\.venv\Scripts\python.exe tools/wf.py advance --note "discussion drafted; <n> words, <k> refs; disagreements addressed: <citekeys>"
```
