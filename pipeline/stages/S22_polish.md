# S22 - Journal-specific, fact-preserving polish

## Purpose
Give the canonical full manuscript one journal-specific language pass without changing a
number, citekey, figure/table reference or scientific claim.

## Procedure
1. Snapshot before editing:
```
.\.venv\Scripts\python.exe tools/text/polish.py snapshot
```
   When `full_manuscript.md` exists, the tool treats it as the canonical main source and
   snapshots it plus supplementary Methods and administrative files; it does not also
   polish stale component drafts.
2. Run `tools/text/polish.py lint`, fix blocking AI tells and house-style defects, and align
   abstract structure, spelling, word/reference limits and permitted headings with the
   chosen journal. Preserve medical-journal prose: continuous narrative, calibrated claims,
   concise Methods in the main paper, and detailed implementation only in the supplement.
3. Keep Keywords immediately after the Abstract, comma-delimited, 3-6 items. Preserve the
   explicit References heading and concise Figure legends at the end.
4. Run `tools/text/polish.py diff` and `tools/text/polish.py lint` again. Restore and redo
   any wording edit that loses or adds a number, citation or artifact reference.
5. Write `polish_log.md` with `AI patterns removed`, `Language changes by section`, `House
   style decisions`, `Cut to meet journal limits`, `Read by eye`, `Tier-B phrases kept`.
6. Reread the complete manuscript and optional supplementary Methods, then record
   `polish_reviewed YES` with a concrete reason.

## Outputs
- `07_manuscript/polish_report.json`
- `07_manuscript/polish_log.md`

## Hard rules
- Wording only. Never change a number, citekey, artifact reference or conclusion strength.
- Do not re-take the snapshot to hide a failed fact-preservation diff.
- Do not add content or an AI-use disclosure during polishing.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "journal polish complete; facts preserved; abstract/main/reference limits pass; read by eye"
```
