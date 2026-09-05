# S07 - Artifact inventory (benchmarked) + legends written first

## Purpose
Decide exactly what the paper displays, benchmarked against what comparable papers
actually display, and write every legend before anything is drawn. Legends written
first keep panels from filling up with explanatory text later.

## Procedure
1. **Benchmark.** Retrieve comparable papers - same design, same field, the kind of
   journal you are targeting - and count what they display. A scholarly search helper may
   find candidates, but every comparator used in the benchmark must be retrieved through
   the bundled client:
```
.\.venv\Scripts\python.exe tools/pubmed/client.py search --query "<design> <topic>" --retmax 100
.\.venv\Scripts\python.exe tools/pubmed/client.py fetch --ids <...> --with-abstract
```
   Write `project/01_protocol/artifact_benchmark.md` with headings
   `Comparable papers surveyed`, `Figure/table counts observed`, `Chosen inventory and why`.
   Record the observed range (e.g. "4-6 main figures, 2-3 main tables, n=8 papers"), and
   justify your inventory against it. Fewer, better displays beat padding.
2. **Plan.** Write `project/01_protocol/artifact_plan.json`. Every entry needs a
   `source_results` list pointing at the result JSONs it is built from - an artifact with
   no numeric source cannot be built:
```json
{
  "main_figures": [
    {"id": "Figure 1", "slug": "flow", "title": "",
     "content": "what the reader learns from it, in one sentence",
     "archetype": "flow_diagram",
     "panels": ["A", "B"], "width": "single|1.5|double",
     "script": "05_figures/code/fig1_flow.py",
     "file": "05_figures/out/Figure1.png",
     "tiff": "05_figures/out/Figure1.tiff",
     "source_results": ["03_analysis/results/dataset_summary.json"]}
  ],
  "main_tables": [
    {"id": "Table 1", "slug": "baseline", "title": "",
     "content": "", "file": "04_tables/main/Table1.xlsx", "sheet": "Table 1",
     "source_results": ["03_analysis/results/baseline.json"]}
  ],
  "supp_figures": [],
  "supp_tables": [
    {"id": "Table S1", "slug": "", "title": "", "content": "",
     "file": "04_tables/supplementary/supplementary_tables.xlsx", "sheet": "Table S1",
     "source_results": []}
  ],
  "supp_files": [{"id": "Supplementary File 1", "file": "", "what": ""}]
}
```
   Structural requirements the gate enforces: sequential numbering with no gaps; each
   main table in its own xlsx; **all supplementary tables in a single xlsx, one sheet
   each**; every figure has a `width`, a `script` and an `archetype`.
   If the reporting guideline requires a flow diagram (STROBE/CONSORT/STARD/PRISMA),
   it is Figure 1.

3. **Declare each figure's archetype.** Pick it from `reference/archetypes.toml` and read
   that entry before planning the figure - it lists the elements that chart type must have,
   and S11 checks the rendered figure for them. Choosing `km_survival` commits you to a
   number-at-risk table and censoring marks; choosing `histopathology` commits you to a
   physical scale bar. Pick the archetype that matches what the data needs, then accept its
   requirements. `other` is available but demands an `archetype_rationale`, and it turns off
   the domain checks, so prefer a real archetype.
4. **Legends.** Write `project/05_figures/legends.md`, one compact block per figure, each
   headed `Figure N.` / `Figure S1.` Use medical-journal form: a brief descriptive title;
   one clause or sentence per panel; only essential visual encodings; sample size/error-bar
   definition/statistical test only when the figure cannot be interpreted without it; then
   a short abbreviations clause when needed. Target 40-140 words and never exceed the
   configured 180-word ceiling. Describe what is drawn and how to decode it; do not state
   which group was higher or lower, repeat effect estimates, or retell the Results.
   Do not repeat cohort acquisition, complete model specification, software versions,
   interpretation, numerical Results or generic caveats already stated elsewhere.
5. **Table captions.** Write `project/04_tables/table_captions.md`, one block per table,
   headed `Table N.` Each needs a title line plus the footnote content: abbreviation
   expansions, units, the test used, what a dagger/asterisk marks. Short abbreviation lists
   may remain local at this stage. If more than eight different abbreviations accumulate
   across figures and tables, or a local list exceeds 50 words, S17 will move the complete list into `Declarations and
   Statements` and regenerate the affected tables without repeated abbreviation blocks.

## Outputs
- `01_protocol/artifact_benchmark.md`
- `01_protocol/artifact_plan.json`
- `05_figures/legends.md`
- `04_tables/table_captions.md`

## Hard rules
- Do not draw anything yet. No xlsx, no png.
- Do not plan a display item you have no result JSON for.
- Detailed methods, cohort provenance and general caveats belong in Methods or
  supplementary Methods, not in panels and not automatically in every legend.
- Do not use the literal down-arrow character. Express direction in words outside legends;
  legends themselves describe the display without claiming the direction of a result.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "inventory: <F main / T main / F supp / T supp> vs benchmark <range>; legends written"
```
