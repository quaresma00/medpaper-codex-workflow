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

### Current prose context, not merely matching digits

For new projects pinned to 1.26+ (or an older binding explicitly opting in), add
`context_evidence` keyed by the claim's own fact IDs. `readiness.py facts` now returns
each resolved finding's `fingerprint`; `wfcore.claims.fingerprint(exact_claim_text)` computes
the clause fingerprint. These identities bind the actual source/pointer/context/values and
exact current sentence. Do not derive them from guessed manuscript values or edit a source
result to match the prose. Unrelated findings or export whitespace do not expire this proof.

Each fact entry contains `fact_fingerprint`, `claim_fingerprint` and `observations` for
applicable `population`, `comparison`, `model`, `timepoint`. Source-explained N/A is allowed;
an unknown or an unsupported waiver is not N/A. This is backstage attribution: the paper
does not repeat all context dimensions or expose these metadata fields.

- A common observation is simply an exact phrase in the finding sentence. It must align
  with the actual source context value or the existing clinical display dictionary's label.
  Word boundaries distinguish `adjusted model` from `unadjusted model`.
- Inherited context uses `{mode: "literal", scope: "section", quote: "<actual short passage>"}`.
  The source-aligned passage must occur before/in the claim in that same Abstract or Results
  section. An abstract's population cannot silently certify a different main Results cohort.
- Nonliteral wording uses `{mode: "read_back", reviewer: "executor", scope: "claim" or
  "section", quote, interpretation, reason}`. Record what the actual words mean and why the
  selected executed finding supports that interpretation (at least 30/60 characters respectively).
  This is a real executor observation, not an independent verdict, copied source value or
  `judgement: pass`. State `mode: "pending"`/`"needs_review"` when unresolved; it blocks until
  the existing executor/author judgement is completed, without adding another reviewer/stage.

Mechanically distinct alternative contexts already present in the result catalog are flagged
when attributed to the wrong finding. Broad/shorthand terms still need appropriate read-back;
neither a lexical match nor a metadata object proves clinical meaning. S18/S25 continue to
read the actual populations, contrasts, models and time windows against the sources.
Update only affected observations after a real sentence/finding change. Assembly and initial
journal copying preserve valid evidence; current-section anchors must still match after
reorganisation. Older pinned projects remain historical until explicit migration or opt-in;
this addition does not rewind completed stages or rerun analysis.

Write the natural medical paragraph first. Never insert every metadata dimension into each
sentence merely to satisfy literal matching. Generate the binding JSON and fingerprints in
the deterministic source/build code using the existing `readiness.py facts` output; do not
hand-copy large metadata objects through chat. Reuse genuine applicable context and record
only unresolved nonliteral meaning as an actual executor observation. This does not license
automatic refresh of an old read-back after its sentence or finding has changed.

Repeated text needs per-occurrence binding: use `section: ["Results", "<actual subsection>"]`
and, only if still ambiguous inside that scope, a 1-based `occurrence`. Missing/ambiguous
locations fail instead of letting one entry cover every identical sentence. Assembly keeps
separate Abstract/Results bindings. Inherited context comes from the current subsection and
its ancestor introductions, never a sibling subgroup's paragraph; a later Validation section
cannot borrow Discovery context. If changed headings make a locator stale, repair only that
binding and its actual context observations. No new scientific analysis is implied.

Do not bind a whole section or use all facts as a global whitelist. The guard verifies signed
numbers, rounded values and P thresholds against the claim's own facts. Common CI confidence
levels and figure/table labels are not findings; small numbers and P values are not exempt.
Constants in Methods need the typed source-bound constant entry specified by quality-before-writing.md, not a free number allowlist or fabricated results.

At S10 the table builder appends cell bindings to the same file: `path`, `sheet`, `cell`,
`text` (exact string value returned by the workbook reader), `fact_ids`, and `label_cells`
(actual worksheet cells identifying the outcome). Keep the statistical result and the cell
binding in the same deterministic build path. Never alter a table to match a guessed result.

For v1.26-pinned tables, a reported count percentage must carry `proportions` evidence,
not merely a value present somewhere in its fact. Each entry identifies `fact_id`, the actual
`numerator_key`, `denominator_key`, and exact displayed `reported` percentage. The executed
fact supplies `percentage_basis` (population/available-case rule, unit and time). The check
recomputes the displayed proportion with its actual precision. Both `64.2%` and the ordinary
`n (%)` column's `102 (64.2)` are covered; no percentage sign in the cell is needed for the
latter. Update this binding alongside the existing deterministic table build, not a second file.
Missing/invalid denominators block; counts, N/A and a CI confidence level do not require a
fictitious ratio. Existing pinned tables are preserved; an explicit proportion entry is always
validated, including in older projects. New/changed percentage cells should use this evidence.

A percentage-valued continuous measurement or percentage-point difference is not a patient
count proportion. Its executed context may identify `percentage_kind: "measurement"` or
`"percentage_point_difference"`, the actual percentage unit, and a substantive `percentage_basis`.
That source-supported distinction avoids inventing numerator/denominator counts; ordinary
source/value and medical interpretation checks still apply. A claim-side exemption cannot
replace the source type. Weighted, relative-change and probability results retain their real
basis and statistical method; this check does not establish that the analysis is valid.

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

For source-scoped labels, early physical production assumptions, all-observation review
closure, percentage denominator-basis checks and safe trial routing, also use
`reference/structural-quality.md`. Existing completed stages/evidence remain historical;
new scoped work does not imply a complete analysis or manuscript rebuild.


