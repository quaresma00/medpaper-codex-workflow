# S03 - Protocol v1 + data acquisition plan

## Purpose
Commit to a design before seeing the data, so that later choices are visibly
pre-specified rather than fitted to whatever happened to be significant.

## Procedure
1. Pick the reporting guideline that governs this design (STROBE, CONSORT, STARD,
   TRIPOD+AI, PRISMA, CARE...). State it explicitly; it dictates what the Methods must
   contain and what the artifact plan must include (e.g. a flow diagram).
2. Write `project/01_protocol/protocol_v1.md` with exactly these headings:
   `Objective`, `Design`, `Population and eligibility`, `Variables`,
   `Statistical analysis plan`, `Sample size / power`, `Reporting guideline`, `Ethics`.
   - `Variables`: for every exposure, outcome and covariate give the operational
     definition, the source field, the unit, and the handling of missing values.
     If a cutoff is used, say where the cutoff comes from (cite it).
   - `Statistical analysis plan`: name the primary model, the primary estimand, how
     confounders were chosen, how missing data is handled, what sensitivity analyses
     will run, and what constitutes the primary result. Pre-specify it now.
   - `Sample size / power`: if the dataset is fixed, state the precision it affords
     rather than pretending to a prospective calculation.
3. Write `project/02_data/acquisition_plan.md` with exactly these headings:
   `Source`, `Access route`, `Licence and ethics`, `Exact retrieval steps`,
   `Expected shape`, `Known limitations`.
   `Exact retrieval steps` must be reproducible commands or a numbered manual procedure
   with URLs and version/release identifiers, not "download the dataset".
4. If the data requires credentials, an application, or an IRB approval the user has not
   mentioned, raise it now.

## Outputs
- `01_protocol/protocol_v1.md`
- `02_data/acquisition_plan.md`

## Hard rules
- Do not look at the data before the analysis plan is written down. If data was already
  inspected, say so in the protocol under `Deviations` at S06 rather than hiding it.
- No figures, no tables, no manuscript prose.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "protocol v1 fixed; guideline=<x>; primary model=<y>; data route=<z>"
```
