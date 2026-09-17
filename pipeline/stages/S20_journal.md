# S20 - Select the most realistic current SCIE journal

## Purpose
Choose a legitimate current SCIE venue that maximises realistic acceptance probability,
then freeze its actual author instructions and Word-format rules.

## Procedure
1. Read the user-reviewed full manuscript and the independent review. Search for journals
   that recently published studies of the same design, scale and topic; this is stronger
   scope evidence than a generic aims-and-scope match.
2. Build a current eligibility screen. A candidate is eligible only if it is currently
   SCIE-indexed, has a current JCR quartile Q1-Q4, and has no active warning, delisting
   concern or material integrity signal. Verify title and ISSN from current sources. The
   chosen journal's SCIE, JCR, integrity and author-guide checks must be no more than 90
   days old when this gate closes; future-dated evidence also fails.
3. Write `project/08_submission/journal_shortlist.md` with `Eligibility screen`, `Ranking
   basis`, `Shortlist`, `Reject-fallback cascade`. Include 5-8 candidates with fit evidence,
   realistic acceptance reasoning, APC and turnaround when currently verifiable, and the
   main rejection risk. Rank by acceptance probability and study fit. Q3/Q4 and low-impact
   journals are fully acceptable and should outrank prestige targets with poor odds.
4. Present the shortlist and wait for the user's choice. Do not default to the highest
   impact factor.
5. Fetch the chosen journal's current official author instructions, snapshot the raw page
   under `project/08_submission/cache/`, and write `target_journal.json` with the required
   SCIE, JCR, integrity and retrieval fields.
6. Write `guidelines_extract.md` with sourced sections for word limits, abstract, keywords,
   references, figures and legends, tables, supplements, statements, cover letter, required
   upload items and formatting.
   Record the journal's abbreviation-placement rule. Set `abbreviation_placement` in
   `target_journal.json` to `central` by default. Use `local_required` only when the official
   guide explicitly requires definitions within every table/figure, and put the exact guide
   URL and rule in `abbreviation_rule_source`.
7. Write `project/08_submission/docx_style.json`. Use the journal's explicit requirements
   for font size, spacing, margins and paper size. All text is always black and external
   hyperlinks are always removed. If the journal is silent, use these medical-manuscript
   fallbacks and record them under `fallbacks`: Times New Roman, 12 pt body, 12 pt bold
   section headings, 12 pt bold subsection headings, double spacing, 0 pt paragraph-after,
   1-inch margins, A4 paper. If a journal explicitly mandates a different font, its
   instruction overrides the fallback and `source` must quote it.
```
{
  "font_family": "Times New Roman",
  "body_font_pt": 12,
  "title_font_pt": 14,
  "section_heading_font_pt": 12,
  "subsection_heading_font_pt": 12,
  "line_spacing": 2.0,
  "paragraph_spacing_after_pt": 0,
  "margins_in": 1.0,
  "paper_size": "A4",
  "all_text_black": true,
  "external_hyperlinks": false,
  "source": "<official guideline URL and quoted rule, or journal silent>",
  "fallbacks": ["font_family", "body_font_pt", "title_font_pt", "section_heading_font_pt", "subsection_heading_font_pt", "line_spacing", "paragraph_spacing_after_pt", "margins_in", "paper_size"]
}
```
8. Derive a pristine journal-specific integration workspace from the accepted scientific
   freeze after the target journal, guideline snapshot and style file are final:
```
.\.venv\Scripts\python.exe tools/manuscript/journal_workspace.py init
.\.venv\Scripts\python.exe tools/manuscript/journal_workspace.py verify --require-pristine
```
   This copies the accepted manuscript, optional supplementary Methods, legends, captions and
   abbreviation statements into `project/08_submission/integration/`. All journal-specific
   content changes now occur there, never in `project/07_manuscript/`.

## Outputs
- `08_submission/journal_shortlist.md`
- `08_submission/target_journal.json`
- `08_submission/guidelines_extract.md`
- `08_submission/docx_style.json`
- `08_submission/integration/journal_workspace.json`

## Hard rules
- Never state indexing, quartile, fees, turnaround or format rules from memory.
- Current SCIE status and a current JCR quartile are eligibility requirements; impact
  factor is not the ranking objective.
- The user chooses the journal.
- Formatting defaults are used only where the chosen journal is silent and are documented.
- `fallbacks` lists only the canonical JSON keys whose rules are silent; every other style
  value must be supported by the official `guidelines_url`, which is included in `source`.
- The S19 scientific freeze must verify unchanged before journal selection closes.
- For a later journal, run `journal_workspace.py init --replace`; the tool preserves the
  previous generated integration and bundle under `08_submission/journal_archives/`, then
  derives the new target from the same frozen scientific master.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py decide journal_chosen "<journal>" --why "<user choice and acceptance-fit rationale>"
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "target=<journal>; current SCIE/JCR verified; Word rules frozen; journal deltas=<...>"
```

