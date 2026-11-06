# S22 - Journal-specific, fact-preserving polish

After wording changes update only affected `08_submission/integration/claim_bindings.json`
entries under `reference/numeric-claims.md`; never alter frozen scientific facts to match prose.

## Purpose
Give the journal-specific integration copy one language pass without changing a number,
citekey, figure/table reference or scientific claim. The accepted scientific master remains
unchanged.

## Procedure
1. Snapshot before editing:
```
.\.venv\Scripts\python.exe tools/text/polish.py snapshot
```
   The tool snapshots `08_submission/integration/full_manuscript.md` plus its supplementary
   Methods and administrative files. It never snapshots or edits the frozen S19 sources.
2. Run `tools/text/polish.py lint`, resolve actual structural/house-style defects, assess
   wording prompts in their medical context, and align
   abstract structure, spelling, word/reference limits and permitted headings with the
   chosen journal. Preserve medical-journal prose: continuous narrative, calibrated claims,
   concise Methods in the main paper, and detailed implementation only in the supplement.
3. Keep Keywords immediately after the Abstract. Use the actual selected journal's keyword
   count and final-output separator, already recorded in the target profile. The scientific
   source's 3-6 comma-delimited convention does not override that journal. Preserve the
   explicit References heading and concise Figure legends at the end.
4. Run `tools/text/polish.py diff` and `tools/text/polish.py lint` again. Restore and redo
   any wording edit that loses or adds a number, citation or artifact reference.
5. Keep the existing `polish_log.md` concise: actual changes, retained context-dependent
   terminology and substantive reading findings. Do not write a justification per harmless word.
   New lint reports bind current sources, linter and exceptions; rerun only this cheap check
   when those inputs change, never analysis or an unrelated Word build.
6. Reread the complete manuscript and optional supplementary Methods, then record
   `polish_reviewed YES` with a concrete reason.

## Outputs
- `08_submission/integration/polish_report.json`
- `08_submission/integration/polish_log.md`

## Hard rules
- Wording only. Never change a number, citekey, artifact reference or conclusion strength.
- Never edit `07_manuscript/full_manuscript.md` or any other frozen scientific-master file to
  meet one journal's requirements. All such presentation changes stay inside
  `08_submission/integration/` and the resulting bundle.
- Do not re-take the snapshot to hide a failed fact-preservation diff.
- Do not add content or an AI-use disclosure during polishing.

## Close
Complete journal preproduction executor acceptance from the same-journal benchmark and actual
integration sources: `benchmark.py accept --layer journal --review <findings.json>`.
Resolve Methods/Discussion organization, declaration order, main/supp legends and sourced
limits before expensive Word. Use explicit prototype/source_file paths for unbuilt journal
displays, never pretend a future output was inspected. Final-upload acceptance remains S23.

```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "journal polish complete; facts preserved; abstract/main/reference limits pass; read by eye"
```
