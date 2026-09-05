# S01 - Intake: normalize the research idea

## Purpose
Turn the user's free-form idea document into a machine-readable spec, so that every
later stage argues against the same target instead of a remembered paraphrase.

## Inputs
- The user's research idea file. It belongs in `project/00_input/`. If the user pasted
  it into chat instead, save it there first (`project/00_input/idea_source.md`).

## Procedure
1. Read the idea file in full. Do not summarize from the filename or a partial read.
2. Extract the study skeleton. Where the idea is silent, write `null` and add the gap to
   `open_questions` - never fill a gap with a plausible guess.
3. Write `project/01_protocol/idea.json`:

```json
{
  "title_working": "",
  "design": "cross-sectional | cohort | case-control | RCT | diagnostic accuracy | prognostic model | meta-analysis | secondary analysis of <db>",
  "population": {"who": "", "setting": "", "inclusion": [], "exclusion": []},
  "exposure": {"name": "", "definition": null, "measurement": null},
  "comparator": {"name": "", "definition": null},
  "outcomes": {"primary": [{"name": "", "definition": null, "timing": null}], "secondary": []},
  "covariates_proposed": [],
  "claimed_novelty": "one sentence: what is not yet known that this would establish",
  "data_source_candidates": [{"name": "", "access": "public | licensed | institutional | to-be-collected", "why": ""}],
  "reporting_guideline_candidate": "STROBE | CONSORT | STARD | TRIPOD+AI | PRISMA | CARE | ...",
  "open_questions": ["every ambiguity you had to leave unresolved"]
}
```
4. Create `project/03_analysis/notes.md` with these four headings and a first pass at each.
   This file is the ONLY legitimate source for Introduction and Discussion framing later:

```markdown
# Notes
## Introduction points
## Discussion points
## Limitations
## Surprises / must-not-forget
```
5. If `open_questions` contains anything that would change the design, ask the user now.
   Do not proceed on assumptions about population, exposure definition, or outcome timing.

## Outputs
- `01_protocol/idea.json`
- `03_analysis/notes.md`

## Hard rules
- No literature search yet. That is S02, and it must be recorded through the PubMed client.
- Do not write any manuscript prose in this stage.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "idea normalized; design=<x>; unresolved: <...>"
```
