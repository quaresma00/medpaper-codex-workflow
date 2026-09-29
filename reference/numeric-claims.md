# Source-bound reported findings

Use at S05/S06 when exporting results, S09/S10/S17 when reporting them, and for affected
revisions. This is backstage provenance, not a table or paragraph for the submitted paper.
Never fabricate data or manually edit result JSON to make a claim pass. Correct and execute
the analysis producer. Do not add analyses solely to populate metadata.

## One fact, one scientific context

Executed analysis JSON exports a small object for each reportable finding. Its `context`
contains `outcome`, `population`, `comparison`, `model`, `timepoint`, `unit`, `denominator`.
Use exact reader-facing outcome wording and explicit reasons where a dimension does not apply.
Its `values` contains named numerical results (for example `estimate`, `ci_low`, `ci_high`,
`p_value`, `n`). P values use `p`, `p_value`, `pvalue`, `adjusted_p` or `q_value` as keys.
Do not put unrelated cohorts/outcomes into one fact to borrow each other's values.

Before the S06 writing freeze, extend the existing `01_protocol/study_facts.json`:

```json
{
  "numeric_facts": {
    "mortality_primary": {
      "source": "03_analysis/results/primary.json",
      "pointer": "/reported/mortality_primary",
      "context": {
        "outcome": "all-cause mortality",
        "population": "protocol-defined eligible cohort",
        "comparison": "exposed versus unexposed",
        "model": "prespecified adjusted model",
        "timepoint": "protocol-defined follow-up",
        "unit": "hazard ratio",
        "denominator": "eligible participants with observed follow-up"
      }
    }
  }
}
```

This is a schema example, not study evidence. Preserve the existing clinical-story fields.
The context must exactly match the actual result object's context. `readiness.py facts`
resolves JSON pointers and prints only these small facts, not the full dataset/result library.
The result object's values, not a duplicated hand-entered value in this catalog, are authoritative.

## Bind the reported text/cells

At S09 create `07_manuscript/claim_bindings.json` with `schema_version: 1` and `claims: []`.
Each reported numeric finding in Results and Abstract needs an entry with:

- `path`: project-relative manuscript path.
- `text`: the exact short finding sentence/clause, including its actual outcome label.
- `fact_ids`: only the relevant identifiers in `numeric_facts`.

Do not bind a whole section or use all facts as a global whitelist. The guard verifies signed
numbers, rounded values and P thresholds against the claim's own facts. Common CI confidence
levels and figure/table labels are not findings; small numbers and P values are not exempt.
Constants in Methods need a justified existing number-allowlist entry, not fabricated results.

At S10 the table builder appends cell bindings to the same file: `path`, `sheet`, `cell`,
`text` (exact string value returned by the workbook reader), `fact_ids`, and `label_cells`
(actual worksheet cells identifying the outcome). Keep the statistical result and the cell
binding in the same deterministic build path. Never alter a table to match a guessed result.

At S17 bind Abstract claims. `assemble.py` carries matching Abstract/Results bindings into
the assembled manuscript without inserting markers, identifiers or internal prose into it.
Initial journal-workspace creation derives `integration/claim_bindings.json`; journal edits
update only affected text bindings there. Bindings are not submission uploads or S19 ZIP items.

The guard checks source identity, exact context, outcome labels and numerical correspondence.
It cannot prove clinical interpretation, automatically understand every synonym, or establish
that the original analysis is scientifically valid. S18/S25 still check outcome, comparison,
model, timepoint, denominator, units, uncertainty and interpretation against the resolved facts.
Prefer natural medical wording; use the same accurate outcome name consistently rather than
adding technical IDs to prose to satisfy the checker.

## Existing projects

Missing bindings fail with an actionable message; they are not silently bypassed. Reconstruct
them from actual executed results, never from manuscript numbers. Keep the review checkpoint
and use scoped source updates. If an already-frozen scientific source must change, obtain the
normal renewed S19 approval; do not silently rewrite a frozen master or restart the stage tail.
