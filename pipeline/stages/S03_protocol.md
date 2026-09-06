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
   `Source`, `Access route`, `Licence and ethics`, `Protocol-defined data universe`,
   `Exact retrieval steps`, `Pagination and completeness proof`, `Expected shape`,
   `Known limitations`.
   - `Protocol-defined data universe` defines the complete set that should be acquired
     before post-acquisition eligibility exclusions. It may be a scientifically pre-specified
     sample design, but it must not be narrowed later for speed, token use, download size,
     memory or convenience.
   `Exact retrieval steps` must be reproducible commands or a numbered manual procedure
   with URLs, query/filter text and version/release identifiers, not "download the dataset".
   State every server-side eligibility filter. Do not silently add a date restriction,
   field subset, first-N cap, `LIMIT`, `TOP`, `head()`, `sample()`, or maximum page count.
   - `Pagination and completeness proof` names the source's total-count field or count query,
     the raw receipt that will preserve it, the page/cursor termination rule, and how received
     records will be counted from raw payloads. A page-size parameter is allowed only when the
     plan follows every page/cursor until the terminal response.
4. If the data requires credentials, an application, or an IRB approval the user has not
   mentioned, raise it now.

## Outputs
- `01_protocol/protocol_v1.md`
- `02_data/acquisition_plan.md`

## Hard rules
- Do not look at the data before the analysis plan is written down. If data was already
  inspected, say so in the protocol under `Deviations` at S06 rather than hiding it.
- The acquisition target is the entire protocol-defined universe. A small schema/connectivity
  pilot may be planned, but it is never an analysis dataset and must be followed by full
  acquisition before S04 can close.
- If an external source truly prevents full access, do not choose a subset yourself. Record
  the exact restriction and its receipt, ask the user whether a source-limited analysis is
  acceptable, and continue only after the explicit decision required at S04.
- No figures, no tables, no manuscript prose.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "protocol v1 fixed; guideline=<x>; primary model=<y>; data route=<z>"
```
