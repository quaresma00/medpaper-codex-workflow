# S10 - Build the tables

Follow `reference/numeric-claims.md`: the table builder records source-bound cell mappings in
the existing `07_manuscript/claim_bindings.json`, preserving all existing prose bindings.

## Purpose
Render the planned tables as three-line xlsx files a reader and a reviewer can use.
Generated from result JSONs by code, never retyped.

Before acceptance read the actual title, headers, body and footnotes as a medical reader,
including all supplementary tables. Use source-scoped clinical display labels, not dataframe
column names or unexplained model/source codes. Keep the true units, denominator and summary
type. Record one actual wording/location and clinical reading in the existing executor
display finding; see `reference/medical-reader-presentation.md`. Do not add another report.

## Procedure
1. Write `project/04_tables/code/build_tables.py`. It reads
   `03_analysis/results/*.json` and `01_protocol/artifact_plan.json`, and writes every
   table with the shared helper so formatting cannot drift:

```python
import sys; sys.path.insert(0, "tools")
from tables.threeline import write_table, write_workbook

write_table(
    path="project/04_tables/main/Table1.xlsx",
    sheet="Table 1",
    title="Table 1. Baseline characteristics of the study population.",
    header=["Characteristic", "Group A (n=123)", "Group B (n=456)"],
    rows=[["Age, years, mean (SD)", "62.1 (11.4)", "61.7 (12.0)"]],
    footnotes=[
        "Data are n (%) unless stated otherwise.",
        "Abbreviations: SD, standard deviation; BMI, body mass index.",
    ],
)
```
   These numbers illustrate layout only. In a study the script reads executed results and
   records actual source-bound cells; do not copy example values. Select categorical,
   continuous, regression or outcome-table structure from design/analysis and the benchmark.
   Do not add baseline P values by default or infer summary type from a column's storage type.
   Report exported n (%), mean (SD) or median (IQR), actual missing/available counts and
   denominators as appropriate. Effect labels/interval levels, reference groups, adjustment
   sets and analysis populations must match their actual models. S10 formats; it does not
   fit models, run add-on tests or calculate a missing percentage. Follow the optional R
   table route in `reference/r-first.md` only when it improves this project.
2. Layout rules (enforced by the `tables_threeline` gate):
   - Row 1 is the title. Unruled.
   - Exactly three horizontal rules: above the header, below the header, below the last
     data row. No vertical rules. No interior horizontal rules.
   - At least one footnote row beneath the bottom rule.
   - Main tables: one xlsx per table.
   - Supplementary tables: **one** xlsx (`04_tables/supplementary/supplementary_tables.xlsx`)
     with one sheet per table, named exactly as the plan's `sheet` value. Use
     `write_workbook()` for this.
3. Write `project/04_tables/manifest.json`:
```json
{"built_at": "", "built_by": "04_tables/code/build_tables.py",
 "tables": [{"id": "Table 1", "file": "04_tables/main/Table1.xlsx", "sheet": "Table 1",
             "n_rows": 0, "source_results": ["03_analysis/results/baseline.json"]}]}
```
4. Run it, then verify the structure rather than assuming:
```
.\.venv\Scripts\python.exe project/04_tables/code/build_tables.py
.\.venv\Scripts\python.exe tools/wf.py check
```
   The builder must support selecting an affected workbook (for example `--only Table2`).
   A shared supplementary workbook is one rebuild unit; preserve the other sheets' values
   and meaning. A change to one main table must not overwrite other main workbooks.
5. Use the Codex spreadsheet capability to render and visually inspect every worksheet in
   every generated workbook. Check clipping, wrapping, column widths, row heights, title
   and header hierarchy, footnotes, units, decimal precision, missing-value symbols and
   page usability. It is a QA helper only: fix the generating script, regenerate, and
   inspect the affected workbook again; never hand-edit a generated value.
6. After all workbooks pass visual review, record the gate:
```
.\.venv\Scripts\python.exe tools/wf.py decide tables_visually_confirmed YES --why "<workbooks/sheets inspected and defects corrected>"
```
7. Delete scratch files from `project/temp/`.

## Outputs
- `04_tables/code/build_tables.py`
- `04_tables/manifest.json`
- (plus the xlsx files declared in the artifact plan)

## Hard rules
- A table is a reader-facing object, not an analysis dump. No console output or
  paragraph-length cells. Clinically relevant discrimination, calibration, diagnostic
  accuracy or sensitivity results remain when required by the study design; hide engineering
  logs and redundant model-debugging output, not necessary scientific evidence.
  The writer rejects body cells over 300 characters. A 1500-character footnote block is an
  advisory prompt to remove unnecessary detail, not permission to truncate essential notes.
- Every numeric cell must trace to `03_analysis/results/*.json` (gate:
  `numbers_have_provenance source=tables`). Do not retype from the Results prose.
- Titles are self-contained and short. Footnotes carry abbreviations, units and tests.
- Follow S07's abbreviation policy on the first build. Use the central glossary when planned,
  retaining only the local decoding information needed to understand the table. S17 checks
  consistency; regenerate only a table with an actual newly discovered defect.
- Add a necessary table through a scoped S07-owned plan correction and its true consumers;
  stay at the revision checkpoint rather than looping or rebuilding unrelated tables.
- Structural checks alone are insufficient; the visual-review decision is mandatory.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py advance --note "K main + M supp tables built; all values traced to results JSON"
```


## Medical-reader presentation

Read `reference/medical-reader-presentation.md`: check actual clinical labels, counting units,
denominators, statistical marks and state distinctions, table footnotes and figure decoding.
Retain necessary methods; do not imply prespecification or change counts by renaming units.
Use the existing acceptance/review, not an additional audit. At S23 verify actual rendered
Word pages and journal-directed legend/figure placement; don't reintroduce forbidden controls.

## Structural quality and bounded rework

Read `reference/structural-quality.md`. Use clinical display names and physical-size assumptions
before production. Percentage claims bind numerator, denominator and source percentage basis.
Every actionable point in every review section needs a stable ID and disposition, not only
the must-fix subset. Review neutral actual artifacts; don't prime with the writer's conclusion.
Use read-only rework preview and actual scoped checks; never infer scientific change from a
publication label number or silently invalidate author approval. Existing privacy, freezes,
centralized abbreviations, Word cleanup and final actual-page inspection remain in force.



# v1.22 medical content and actual production reading

Use clinical variable headings and indented category rows, not repeated "Sex distribution:"
or other exported field prefixes. Descriptive tables normally report n (%) with an explicit
report/patient/available-case denominator and appropriate continuous summaries plus missingness.
Use only actual exported numbers; do not calculate in prose. `write_table`/`write_workbook`
support zero-based `group_rows` and `indent_rows` without changing supplied values or adding
interior borders. Group rows have a label and empty statistic cells. Keep source/sender
identity when relevant, with its real clinical purpose; do not rename records as patients.
Follow `reference/project-benchmarking.md` to bind actual saved workbook AND rendered sheet
pages in existing `display_review.json.final_reviews`. Prototype/three-line/numeric PASS
cannot certify medical content. The v1.22 production gate must pass before Results writing.

