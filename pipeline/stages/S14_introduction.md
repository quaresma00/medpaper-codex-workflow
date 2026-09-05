# S14 - Introduction

## Purpose
Write the Introduction from the verified library's abstracts plus `notes.md`. One file,
this stage only.

## Inputs
- `06_refs/library.json` (abstracts - read them, do not recall them)
- `03_analysis/notes.md` -> `Introduction points`
- `01_protocol/feasibility.md` -> the gap argument, already reasoned once
- `01_protocol/protocol_final.md` -> the objective, stated exactly

## Procedure
1. Four moves, in order, and nothing else:
   1. The clinical problem and why it matters (burden, consequence).
   2. What is established. Cite the strongest evidence, not the most convenient.
   3. What is not established - the specific gap, narrow enough to be closable by this
      study. This is the sentence the reviewer tests the whole paper against.
   4. The objective. One sentence, matching `protocol_final.md` word for word in substance.
2. Write `project/07_manuscript/introduction.md`. Cite with pandoc markers `[@key]`, keys
   from `refs.bib` only.
3. Check the count targets:
```
.\.venv\Scripts\python.exe tools/wf.py config list        # intro_words_min/max, intro_refs_min/max
.\.venv\Scripts\python.exe tools/wf.py check
```
   If the target journal turns out to want something different, change the target rather
   than padding: `.\.venv\Scripts\python.exe tools/wf.py config set intro_words_max 600`.

## Outputs
- `07_manuscript/introduction.md`

## Hard rules
- ONE section file this stage. No Discussion, no Abstract.
- Every citation verified. Every claim attributable to an abstract you read.
- No results in the Introduction. No hypothesis stated as if already confirmed.
- No stock openers: not "In recent years", not "has attracted increasing attention",
  not "plays a crucial role". The gate flags these.
- Do not restate the whole field. Three to five paragraphs, tightest possible path to the
  gap.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py advance --note "introduction drafted; <n> words, <k> refs; gap sentence: <quote it>"
```
