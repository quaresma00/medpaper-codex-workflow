# S23 - Build and visually verify the submission package

## Purpose
Produce the exact files required by the chosen journal. All uploadable prose is delivered
as Word, with deterministic typography and no residual Pandoc/Word theme defects. This stage
builds the package; S24 is the user's final content/format review and S25 is the independent
journal-guideline audit.

## Procedure
1. Freeze the journal-required item list from `guidelines_extract.md`; do not add generic
   extras. Write the journal-specific cover letter source outside the bundle at
   `project/08_submission/cover_letter.md`.
2. Before building the title page, synchronize any existing reference-count field with the
   distinct citekeys actually used in `full_manuscript.md`:
```
.\.venv\Scripts\python.exe tools/manuscript/reference_count.py sync
```
   Use `sync --add` only when the official title-page instructions require that field. Do not
   derive it from the candidate literature-library size.
3. Build every prose upload with `tools/manuscript/build_docx.py`. At minimum:
```
.\.venv\Scripts\python.exe tools/manuscript/build_docx.py build --kind manuscript --input project/07_manuscript/full_manuscript.md --output project/08_submission/bundle/manuscript.docx --style-config project/08_submission/docx_style.json --bibliography project/06_refs/refs.bib --csl <journal.csl>
.\.venv\Scripts\python.exe tools/manuscript/build_docx.py build --kind title_page --input project/07_manuscript/title_page.md --output project/08_submission/bundle/title_page.docx --style-config project/08_submission/docx_style.json
.\.venv\Scripts\python.exe tools/manuscript/build_docx.py build --kind cover_letter --input project/08_submission/cover_letter.md --output project/08_submission/bundle/cover_letter.docx --style-config project/08_submission/docx_style.json
```
   If supplementary Methods exists, build it (or the journal-mandated combined supplement)
   as `.docx`. Convert every other narrative upload to `.docx`; do not leave cover letters,
   methods supplements or declarations as Markdown in the bundle. A journal-supplied fixed
   form may remain in the exact PDF/XLSX/DOCX format the journal requires.
4. The builder applies journal-specified size and spacing, with the recorded fallback only
   where the guide is silent. It forces all text black, removes hyperlinks, uses one
   font family throughout, and maps Markdown section headings to the Normal-based
   `SectionHeading` paragraph style. Across every Word XML part it removes `outlineLvl`,
   `keepNext`, `keepLines` and `pageBreakBefore`; visible headings therefore have neither a
   collapsible hierarchy marker nor the left-side black-square control indicator.
   It also converts Shift+Enter/text-wrapping controls to ordinary paragraphs and rejects the
   literal down-arrow character. Use blank lines for paragraph boundaries in Markdown and
   natural wrapping within paragraphs; never pad layout with manual line breaks.
5. Confirm manuscript order: Abstract then Keywords; explicit References heading before
   the bibliography; concise Figure legends as the final section. There must be exactly one
   `Figure legends` section title, exactly one heading per figure, and the legend body must
   not repeat `Figure N` immediately after its heading. Build separate figure
   legend Word files only when the journal explicitly asks, but the legends always remain
   in the manuscript.
6. Add figures and tables in the exact editable/separate forms required by the journal.
   Never omit the supplementary file. Supplementary Methods must contain prose only and no
   Markdown horizontal rules. Put every supplementary table in the separate three-line
   workbook under `04_tables/supplementary/` and list that workbook as a table upload; the
   supplementary-Methods DOCX audit rejects embedded Word tables. Write
   `SUBMISSION_CHECKLIST.md` and `manifest.json`;
   every bundle file is listed with its role and the guideline rule that requires it.
7. Run the structural Word audit:
```
.\.venv\Scripts\python.exe tools/manuscript/build_docx.py audit --manifest project/08_submission/bundle/manifest.json --style-config project/08_submission/docx_style.json
```
8. Render every final DOCX with Microsoft Word or the Codex document workflow and inspect
   the title/abstract, heading transitions, first/last pages, references, figure legends,
   tables, symbols, page breaks and missing glyphs. Fix the source or builder and rebuild
   only affected files.
9. After visual corrections are complete and the manifest and all DOCX files are final, bind
   their visible text to this legitimate S23 build:
```
.\.venv\Scripts\python.exe tools/package_content.py capture --project project
```
   When S23 is being rerun after a source-routed correction, use `--replace`. Capture is refused
   outside S23. This baseline permits later Word layout edits while detecting any direct text
   edit or an upstream source change that was not rebuilt.
10. Write `submission_qc.md` with `Rendered files inspected`, `Citation and cross-reference
   checks`, `Typography and hyperlinks`, `Tables and figures`, `Defects resolved`. Record
   `submission_files_visually_confirmed YES`, then clean temporary/orphaned files.

## Outputs
- `08_submission/cover_letter.md`
- `08_submission/bundle/SUBMISSION_CHECKLIST.md`
- `08_submission/bundle/manifest.json`
- `08_submission/package_content_baseline.json`
- `08_submission/submission_qc.md`
- the journal-required Word, figure, table and supplementary upload files

## Hard rules
- Pipeline-authored bundle-facing narrative files are DOCX, never Markdown; journal-supplied
  fixed forms retain their mandated non-Markdown format.
- All text is black; no external hyperlinks; no Aptos/theme-font leakage when the selected
  font is Times New Roman; no outline numbering, `outlineLvl`, `keepNext`, `keepLines`,
  `pageBreakBefore`, paragraph-border residue or collapsible heading level in any Word XML.
- `References` and `Figure legends` must be visible in the manuscript.
- Any title-page reference count must equal the distinct citations actually used in the
  canonical manuscript; both the Markdown source and generated Word title page are checked.
- Figure legends only identify and decode the display; they do not restate result direction
  or numerical findings. Crowded abbreviation lists appear once under `Declarations and
  Statements > Abbreviations`, unless an explicitly sourced journal rule requires them local.
- Never invent reviewer contact information or an AI-use disclosure.
- Do not infer final user approval from this build/QA stage. Present the complete package at
  S24 and preserve any user edits made there.
- Never recapture the visible-text baseline merely to accept a content edit made directly in
  Word. Route content changes to their source; use the baseline only to permit format-only edits.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "submission package built and visually verified; Word typography/link/heading audit passed; ready for user package review"
```

