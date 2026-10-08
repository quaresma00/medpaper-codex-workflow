# S03 - Protocol v1 + data acquisition plan

Read `reference/r-first.md` when choosing implementation: processing may use Python; use
R where its established package better fits the method. Record this in the existing protocol,
without another approval stop or duplicate analysis.

## Purpose
Document the research question, analysis intentions and complete acquisition plan locally.
Distinguish genuinely prospective plans from exploratory or already-inspected-data choices;
a local protocol does not imply public preregistration.

## Procedure
1. Fix the actual study design and analysis scope, not a reporting-checklist label.
   Ordinary data mining, secondary analysis and retrospective centre data need no default
   public registration, platform search, registration number or registration deliverable.
   For a systematic review/meta-analysis or actual prospective interventional trial only,
   check applicable registration requirements and timing from current primary sources.
   Distinguish required from recommended and record the real situation briefly in this
   protocol. Do not register externally, invent a registration or backdate completed work.
2. Write `project/01_protocol/protocol_v1.md` with exactly these headings:
   `Objective`, `Design`, `Population and eligibility`, `Variables`,
   `Statistical analysis plan`, `Sample size / power`, `Ethics`.
   - `Variables`: for every exposure, outcome and covariate give the operational
     definition, the source field, the unit, and the handling of missing values.
     If a cutoff is used, say where the cutoff comes from (cite it).
   - `Statistical analysis plan`: name the primary model, the primary estimand, how
     confounders were chosen, how missing data is handled, what sensitivity analyses
     will run, and what constitutes the primary result. State what was planned versus
     decided after inspecting data; do not call a retrospective plan preregistered.
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
     If the research design itself would sample from a larger accessible eligible population,
     show the sampling frame, method, target size, precision/power rationale and bias tradeoff
     to the user. Do not choose sampling autonomously. Continue only after their explicit
     approval is recorded:
```powershell
.\.venv\Scripts\python.exe tools\wf.py decide protocol_sampling_authorized YES --why "<the user-approved design and why a census is not the chosen scientific design>"
```
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
- Record analysis intentions before the reportable analyses. If data was already inspected,
  describe that honestly in the protocol and the S06 deviations, rather than demanding a
  retrospective registration or pretending the decisions were prospective.
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
.\.venv\Scripts\python.exe tools/wf.py advance --note "local analysis plan fixed; primary model=<y>; data route=<z>"
```
