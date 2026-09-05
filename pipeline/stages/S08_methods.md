# S08 - Methods

## Purpose
Write a concise, journal-native main Methods section. Create a supplementary Methods file
only when reproducibility requires detail that would obscure the main narrative.

## Inputs
- `01_protocol/protocol_final.md` and `01_protocol/protocol_diff.md`
- `02_data/codebook.md`, `02_data/provenance.md`
- `03_analysis/method_scan.md` (for the methods you cite)
- `03_analysis/results/*.json` (for every number)
- `reference/methods-structure.md` (structure and main-versus-supplement boundary)

## Procedure
1. Read `reference/methods-structure.md`, then re-read the protocol and the study's reporting
   guideline. The guide supplies a flexible architecture, not a mandatory heading template.
   The Methods describes what was actually done, in the order a medical reader needs it.
2. Before drafting, choose and record a compact heading map appropriate to this design. For
   an ordinary original clinical study, prefer about four to seven substantive subsections:
   design/setting; participants or data source; design-specific procedures or measurements;
   outcomes/variables; and statistical analysis. Merge short adjacent topics. Do not create
   a heading merely because a checklist contains an item.
3. Make `Statistical analysis` the final main-Methods subsection for quantitative studies
   (`Data analysis` for qualitative studies; `Evidence synthesis` or equivalent for reviews),
   unless the target journal's current examples clearly use another order. Put prespecified
   sensitivity, subgroup, missing-data and software details inside that subsection when they
   can be stated briefly. Do not append automatic standalone headings for them after it.
4. Write `project/07_manuscript/methods.md`. It must retain the primary design, setting,
   eligibility, exposures/interventions/tests, primary outcomes and primary analysis needed
   to understand validity and interpret the Results.
5. If—and only if—implementation detail is genuinely long, write
   `project/07_manuscript/supplementary_methods.md` and refer to it once from the main Methods.
   Suitable content includes complete search strings, code lists, assay protocols, model
   tuning grids, full imputation or sensitivity specifications, interview guides and a full
   statistical analysis plan. Do not move a core design decision or primary analysis there.
6. Cite methodological choices with pandoc markers `[@key]`—the cutoff you adopted, the
   scoring system, the model, the guideline itself. Keys must come from records already
   retrieved this session.
7. Numbers—study period, follow-up, n screened/excluded/analysed, software versions—must
   already exist in `03_analysis/results/*.json`. If a number you need is not there, go back
   and dump it from code rather than typing it.
8. Do not describe an analysis you did not run, and do not omit one you did. A reporting
   checklist is a completeness audit, not a reason to inflate the prose.

## Outputs
- `07_manuscript/methods.md`
- `07_manuscript/supplementary_methods.md` (optional; only when justified)

## Hard rules
- Write only Methods-stage files. Do not also write Results.
- No default boilerplate subsections after the analysis subsection.
- The optional supplement may extend reproducibility, never hide core validity information.
- Every number traceable to results JSON (gate: `numbers_have_provenance`).
- No placeholders. `TODO`, `TBD`, `xx.x` and friends fail the gate.
- Past tense, declarative. No "we aimed to comprehensively investigate".

## Close
```
.\.venv\Scripts\python.exe tools\wf.py check
.\.venv\Scripts\python.exe tools\wf.py advance --note "methods drafted; heading map: <...>; supplementary Methods: <not needed/path and why>; citations used: <n>"
```
