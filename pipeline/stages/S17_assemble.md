# S17 - Select the title and assemble the complete manuscript

## Purpose
Create the first complete paper before asking for author or affiliation details. The paper
must be readable as one medical-journal manuscript and becomes the canonical scientific
source for review, user editing, polishing and packaging.

## Procedure
1. Read the protocol, final results, finished sections, artifact plan, table captions and
   figure legends. Generate several title candidates internally and select the single best
   one without asking the user. Score for design accuracy, population/exposure/outcome
   specificity, searchability, brevity and freedom from causal or novelty overclaim. Write
   only the selected title to `project/07_manuscript/title.md` as one level-1 heading.
2. Write `project/07_manuscript/abstract.md` after all scientific sections are final. Use
   the structure most appropriate to the design. Every number must already occur in a
   results JSON and every conclusion must agree with the Discussion.
3. Write `project/07_manuscript/keywords.md` as one line:
   `Keywords: term 1, term 2, term 3`. Use 3-6 specific, MeSH-aligned terms where suitable.
   Commas are the only separators: no slash, semicolon, ampersand or conjunction padding.
4. Assemble the exact order with the deterministic tool:
   First, review the display-item abbreviation lists. When they exceed eight unique terms,
   any local list exceeds 50 words, or the lists visibly dominate captions, define the terms
   once in optional `07_manuscript/statements.md` under `# Declarations and Statements`
   and `## Abbreviations`. These thresholds are workflow defaults, not journal standards.
   Use one `term, full expansion` entry per line or semicolon-separated entries, preserving
   mixed-case names such as eGFR. Remove the corresponding `Abbreviations:` blocks from
   legends/captions and the table-building source. Add a short pointer to the central list
   where needed; keep units, symbol meanings and error-bar definitions local. Regenerate
   and visually recheck affected tables. No author/admin details or blank declaration
   sections are needed here. Then run:
```
.\.venv\Scripts\python.exe tools/manuscript/assemble.py
```
   It writes `project/07_manuscript/full_manuscript.md` in this order: selected title,
   Abstract, Keywords, Introduction, Methods, Results, Discussion, References, Figure
   legends, with the optional Declarations and Statements section between Discussion and
   References. Supplementary Methods remains a separate file. The References heading must be
   present even though Pandoc later expands the bibliography beneath it.
5. Read the assembled file from beginning to end. Fix the source section, abstract,
   keywords or legend file and re-run the assembler; do not hand-splice the first build.
   The S17 gate runs `assemble.py --check`, so omissions or manual divergence fail even
   when the visible heading structure still looks valid.

## Outputs
- `07_manuscript/title.md`
- `07_manuscript/abstract.md`
- `07_manuscript/keywords.md`
- `07_manuscript/full_manuscript.md`
- `07_manuscript/statements.md` (optional abbreviation list only; administrative facts wait)

## Hard rules
- Do not ask for or invent authors, affiliations, ORCIDs, grants or correspondence details.
- Do not present title choices. Select the strongest accurate title automatically.
- Keywords appear immediately after the Abstract and nowhere before it.
- `References` and `Figure legends` are explicit level-1 sections; figure legends are the
  final manuscript section.
- `full_manuscript.md` is the canonical manuscript after this stage. Later scientific or
  human edits are made there and checked for provenance.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "full manuscript assembled; selected title: <title>; keywords=<n>; figure legends=<n>"
```
