# S10 - Build the tables

## Purpose
Render the planned tables as three-line xlsx files a reader and a reviewer can use.
Generated from result JSONs by code, never retyped.

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
    header=["Characteristic", "Group A (n=123)", "Group B (n=456)", "P value"],
    rows=[["Age, years, mean (SD)", "62.1 (11.4)", "61.7 (12.0)", "0.62"]],
    footnotes=[
        "Data are n (%) unless stated otherwise.",
        "Abbreviations: SD, standard deviation; BMI, body mass index.",
        "P values from the two-sided t test for continuous and chi-square for categorical variables.",
    ],
)
```
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
- A table is a reader-facing object, not an analysis dump. No model diagnostics, no
  console output, no paragraph-length cells. The gate rejects cells over 300 characters
  and footnote blocks over 1500 characters.
- Every numeric cell must trace to `03_analysis/results/*.json` (gate:
  `numbers_have_provenance source=tables`). Do not retype from the Results prose.
- Titles are self-contained and short. Footnotes carry abbreviations, units and tests.
- Keep a short abbreviation list in the table footnote initially. At S17, if the manuscript
  has more than eight display-item abbreviations or a local list exceeds 50 words, move all definitions to the single
  `Declarations and Statements > Abbreviations` list, remove repeated local blocks from the
  table-building source, regenerate the affected workbooks, and visually recheck them.
- Do not add a table that is not in the plan. If one is needed, loop to S07.
- Structural checks alone are insufficient; the visual-review decision is mandatory.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py advance --note "K main + M supp tables built; all values traced to results JSON"
```
