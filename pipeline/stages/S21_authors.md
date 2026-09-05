# S21 - Collect authors and administrative statements

## Purpose
Collect user-owned authorship and compliance facts only after the scientific manuscript has
been assembled, independently reviewed, user-reviewed and matched to a journal.

## This stage needs the user
Ask once for the exact author order and names, affiliations, ORCIDs, corresponding-author
details, funding/grants, conflicts, ethics/consent, data/code availability,
acknowledgements, CRediT roles, preprint and prior presentation. Never infer a missing item.

Write the response faithfully to `project/00_input/author_info.json`, then create:
- `project/07_manuscript/title_page.md` using the already selected title without offering
  new title options;
- `project/07_manuscript/statements.md` headed `Declarations and Statements`, containing
  user-supplied facts, the exact sections required by the selected journal, and the verified
  master abbreviation list when consolidation is triggered.

If the chosen journal requires administrative declarations in the manuscript file, merge them
into the existing Declarations and Statements section between Discussion and References;
otherwise package administrative facts separately. Keep the centralized Abbreviations subsection
in the manuscript, and respect author blinding for administrative content. Do not move Keywords,
References or Figure legends, or duplicate the Declarations and Statements heading.

Preserve the verified abbreviation list prepared at S17. Reconcile any later additions
across figure legends, table captions and finished workbooks. When there are more than eight
unique defined terms or a local list exceeds 50 words, keep `## Abbreviations` under
`# Declarations and Statements`, define every term once, remove all repeated
`Abbreviations:` blocks from legends/captions and the table-building script, regenerate and
visually check affected workbooks, and insert the Declarations and Statements section
between Discussion and References in `full_manuscript.md`. If the journal explicitly
requires local definitions, retain them only when `target_journal.json` records
`abbreviation_placement=local_required` and the official rule URL.

## Outputs
- `00_input/author_info.json`
- `07_manuscript/title_page.md`
- `07_manuscript/statements.md`

## Hard rules
- Never invent an author, affiliation, ORCID, email, ethics number, funding source or
  contribution.
- Do not alter the selected scientific title merely to accommodate the title page.
- Do not draft or insert an AI-use disclosure unless the user explicitly requested that
  exact content.
- Do not use the literal down-arrow character or manual line breaks as visible layout marks.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "author/admin facts supplied; title page and required statements assembled; missing user-owned fields=<none or list>"
```
