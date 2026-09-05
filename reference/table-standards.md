# Table standards

Loaded on demand by S10. Enforced by `tools/tables/threeline.py` (writer) and the
`tables_threeline` gate (verifier, via `tools/wfcore/xlsxlite.py`).

## Three-line (booktabs) format

```
Table 1. Baseline characteristics of the study population.        <- title, unruled
------------------------------------------------------------      <- rule 1 (above header)
Characteristic        Group A (n=642)   Group B (n=642)   P
------------------------------------------------------------      <- rule 2 (below header)
Age, years, mean (SD) 62.14 (11.42)     61.73 (12.05)     0.62
Male, n (%)           311 (48.4)        298 (46.4)        0.47
------------------------------------------------------------      <- rule 3 (below last row)
Data are n (%) unless stated otherwise.                           <- footnotes, unruled
Abbreviations: SD, standard deviation.
P values from the two-sided t test for continuous variables.
```

Exactly three horizontal rules. No vertical rules. No interior horizontal rules. The gate
checks each of those, plus that row 1 holds a title and that at least one footnote row
exists beneath the bottom rule.

A spanning sub-header may add a fourth partial rule under the spanned columns only; if you
need one, add it deliberately and note the exception in the handoff.

## Files

- **Main tables**: one xlsx per table, `04_tables/main/Table1.xlsx`, sheet named `Table 1`.
- **Supplementary tables**: a single workbook,
  `04_tables/supplementary/supplementary_tables.xlsx`, one sheet per table, sheets named
  `Table S1`, `Table S2`, ... The gate rejects supplementary tables spread across files.

## A table is for the reader, not a dump of the analysis

Hard limits the writer enforces:
- no cell longer than 300 characters
- footnotes totalling no more than 1500 characters
- title must begin `Table N.` or `Table SN.`
- footnotes are mandatory

What does not belong in a table: model diagnostics nobody asked for, console output,
convergence messages, every covariate when only the adjusted estimate matters, a paragraph
of interpretation, or a repeat of the Results prose.

## Content conventions

- **Title**: self-contained. A reader who sees only the table knows the population, the
  grouping and what is being compared.
- **Footnotes**: data format (`Data are n (%) unless stated otherwise`), a short abbreviation
  list in alphabetical order, the test used, the meaning of any symbol, and the
  adjustment set for adjusted estimates.
- **Crowded abbreviations**: when more than eight defined abbreviations occur across figures
  and tables, or any local list exceeds 50 words or dominates its footnote, define them once
  at S17 in `Declarations and Statements > Abbreviations`; remove the
  repeated local abbreviation rows from the table source and regenerate the workbook.
  An explicitly sourced journal requirement for local definitions overrides this preference.
- **Symbol order** for footnote markers: `*`, `†`, `‡`, `§`, `¶`, `#`, then doubled.
  Reserve `*` for significance if you also use it that way in figures - do not use one
  symbol for two purposes in the same paper.
- **Units** go in the row label or the column header, never repeated in every cell.
- **Effect estimates**: `1.87 (1.34 to 2.61)` - use "to" rather than a hyphen so a negative
  lower bound is unambiguous. `threeline.ci()` does this.
- **P values**: `<0.001` for anything smaller; three decimals below 0.01, two above.
  Never `0.000`. Never a bare `p<0.05`. `threeline.p_value()` does this.
- **Decimals**: consistent within a column. Keep trailing zeros (`0.50`, not `0.5`).
  Do not report more precision than the measurement supports.
- **Missing data**: a single convention, stated in the footnote. `-` for not applicable,
  and give the n with data per variable if missingness varies.
- **Denominators**: put n in the column header (`Group A (n=642)`); if a row has a
  different denominator, give it in that row.
- **Row order**: follow the order the Methods introduced the variables, not descending
  significance.

## Building them

```python
import sys; sys.path.insert(0, "tools")
from tables.threeline import write_table, write_workbook, fmt, p_value, ci

write_table(
    path="project/04_tables/main/Table1.xlsx",
    sheet="Table 1",
    title="Table 1. Baseline characteristics of the study population.",
    header=["Characteristic", "Group A (n=642)", "Group B (n=642)", "P value"],
    rows=[["Age, years, mean (SD)", "62.14 (11.42)", "61.73 (12.05)", p_value(0.62)]],
    footnotes=["Data are n (%) unless stated otherwise.",
               "Abbreviations: SD, standard deviation."],
)
```

Every value must come from `03_analysis/results/*.json`. The
`numbers_have_provenance source=tables` gate reads every numeric cell out of the finished
xlsx and rejects anything absent from the result files, so retyping from the Results prose
fails.
