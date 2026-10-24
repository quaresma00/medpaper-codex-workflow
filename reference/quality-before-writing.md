# v1.14: validity first, displays before Results, explicit version acceptance

Use at intake/protocol, S05, S07-S09, assembly and review. This supersedes older generic
quota, pre-display Results, blanket author-question and review-copy instructions.
It changes execution, not the requirement for actual scientific evidence or visual QA.

## Early design, provenance and statistics

At S01 write actual `design` and `research_context` in `01_protocol/idea.json`:
`jurisdiction`, boolean `vulnerable_groups`, and `sources`. Each source names its `name`,
`type` (prospective_collection, existing_records, public_database, biospecimens, etc.),
`identifiability` (anonymous, coded, identifiable), `access` route, boolean `third_party`,
and `redistribution` (permitted, restricted, prohibited). Unknown is a question, not a guess.
Include ALL sources: public discovery plus local clinical validation is not public-only.

Before analysis at S03 extend `analysis_contract.json` with `variable_definitions` rows:
`role` (include eligibility/outcome; address exposure/comparator), `source_field`, `definition`,
`unit`, `coding`, `time_window`, `missing_rule`, `source_locator`. Actually compare each with
source codebooks/records. Resolve competing outcome definitions before producing results.
Also record `statistical_reporting`: integer `primary_comparisons`, substantive `multiplicity`,
`effect_measures`, `intervals`, `exploratory_labeling`. Explain no adjustment when justified;
do not choose significance rules after seeing results. S06 retains these in the final contract.

After results, `dataset_summary.json.source_record_check` records `eligible_records`,
`selection_basis`, `reviewer`, `checked_at`, and ten distinct `cases` (all if fewer than ten).
Each case: private local `record_locator`, `source_file`, `source_sha256`, `derived_file`,
`derived_sha256`, `comparisons` (each `variable`, actual `source_value`, actual `derived_value`,
and `resolved_by` explaining legitimate transformations or the verified producer correction).
Actually return to records: ten duplicate labels or a generated PASS are not validation.
Cover groups/outcomes/edge cases with reproducible selection, not just convenient agreement.
This QC sample NEVER replaces full acquisition or full-cohort analysis. Keep identifiers local.
If only aggregates exist, explain the unavailable row-level trace and establish a scientifically
valid source-to-aggregate check with the author; do not invent patient records to meet ten.

## Governance: assess from evidence, ask only the missing fact

Use `tools/study_policy.py` (and `--apply` at S21 to fill missing supported author-info declarations without overwriting existing facts); it saves one concise assessment in `01_protocol/governance.json`.
For each source, record `ethics_applicability`, `consent_applicability`, `applicability_reason`;
official `policy_evidence` has `source` URL/local authority, `retrieved_at`, local text `file`,
`sha256`, and short exact `excerpt`. Use source-specific and applicable institutional/jurisdiction
rules, not a universal country rule. Retrieve official policies before questioning the author.

Ethics: `institutional_review` or `not_required_by_applicable_policy`. Consent: `required`,
`not_required_by_applicable_policy`, `documented_waiver`. Nonpublic/identifiable data, vulnerable
participants, prospective collection and biospecimens need actual institutional determination;
include evidence with `kind: institutional` and actual `institutional_evidence`, never AI-created
approval/exemption/waiver. Anonymity alone is not exemption. State conclusions and their basis.
For mixed-source studies assess every source separately; a public source does not exempt local data.

At S21 reuse this assessment and existing author facts, automatically draft supported availability
from source/access/licence/redistribution constraints, and ethics/consent from the established
policy plus documented institutional facts. Do not promise access "on reasonable request" without
authority. Do not ask authors to repeat known facts. Ask ONLY the unresolved material item,
such as the actual local approval or consent-waiver decision. Authorship/funding/conflicts remain
author-owned. Keep one author_info source for final consumers and bind declarations to it.
Do not silently overwrite an existing author declaration; reconcile actual contradictions.

This is applicability evaluation, not legal advice or an ethics committee's decision. Primary
basis checked 2026-10-24: [ICMJE participant protection](https://www.icmje.org/recommendations/browse/roles-and-responsibilities/protection-of-research-participants.html),
[Helsinki Declaration](https://www.wma.net/policies-post/wma-declaration-of-helsinki/),
[OHRP coded-information guidance](https://www.hhs.gov/ohrp/regulations-and-policy/guidance/research-involving-coded-private-information/index.html).
OHRP is a jurisdiction-specific example, not the default rule for all studies.

## Tables -> figures -> Results -> crosscheck

Execution order is S08 -> S10 tables -> S11 figures -> S09 Results -> S12 crosscheck.
Stable stage IDs preserve historical ownership; ordinal position follows pipeline.toml.
S09 uses finished actual tables and rendered figures plus executed facts. S12 checks rather
than intentionally rewriting all three. Rebuild only a genuinely inconsistent affected source.
New table bindings belong at S10; S09 extends, never discards them. Upgrades skip completed
stages instead of redoing completed Results merely because its position moved.

S07 verifies method-source identities and reads actual support before Methods. Fail immediately
on an invalid source: retrieve a real replacement/rewrite unsupported wording, never forge metadata.
At S20, before adapting prose or expensive exports, recheck journal article-specific figure/table
caps and the inventory. Record `journal_adaptation_reason` in the integration artifact plan:
which displays stay, combine or move and why. Keep frozen science intact; transfer content into
the journal layer with explicit source/destination mapping. Do not delete key evidence to fit.

## Numeric evidence and three-level size management

Own results trace to executed, context-bound facts. Prior-study values are allowed, but each
exact cited clause uses `claim_bindings.json.source_claims`: `path`, `text`, verified `citekey`,
registered `fulltext`, `sha256`, concrete `locator`, exact short `excerpt`, and substantive `support`
describing outcome/population/comparator/time/units and why comparison is defensible. Read original
results/table, not another paper's citation. Bind assembly and journal copies automatically;
update only changed clauses. An unchanged number is not proof of equal clinical meaning.

The old free-number allowlist is closed. Only Methods constants may use
`value<TAB>constant<TAB>local evidence path<TAB>concrete rationale` in the existing TSV;
never use this for findings, prior-study results, tables or arbitrary Discussion values.

Search by missing argument roles, not hit/library quotas. At S17 inspect actual citation and
section counts; 45-60 cited sources is a soft health band, never a retrieval stop/minimum.
Every library entry must be cited or have a concrete `uncited_reasons[citekey]` explanation,
in `06_refs/usage.json` (not verified bibliography), written via `build_library.py --uncited-reason KEY "reason"` rather than editing verified metadata.
Drafts use benchmarked soft word/citation budgets; assembly does a whole-paper size check;
after selection, only explicit article-specific official limits justify mandatory trimming.

Legend length is advisory by default. The official typed
`submission_requirements.json.figure_legend_words` rule uses status/value/source/article_type;
only `required` blocks. Jointly plan necessary within-figure labels and captions: population,
units, symbols, uncertainty and panel decoding must remain understandable. Do not repeat Results.

## Review and approval

Keep genuine read-only independent review and immutable version freezes. Reviewers read current
originals and actual rendered displays; don't automatically create extra extracts, reading ZIPs,
third-party copies or change dossiers. `reader-copies --why` is opt-in if actually requested.
Only an explicit external-review request permits `review_round.py export --scope ... --words
"actual request"`, producing one local read-only copy and one short change page, no ZIP.
Never transfer private data externally without separate explicit authorization.

Reviewer JSON includes `findings` with stable `id`, category (`numbers`, `grouping`,
`conclusion_strength`, `objective`, `preference`), `affects_science` and precise location.
The executor may keep only true non-scientific preferences with a concrete rationale.
Numerical/grouping/conclusion-strength and untyped findings need correction or real author
adjudication. `close --author-decisions <local.json>` binds each adjudication by finding ID to
`report_sha256`, exact current `inputs`, actual `author_words`, substantive `rationale`.
Author judgment cannot fabricate a number or waive provenance/integrity gates.

Present round/file locations and ask: “如确认当前这一版，请回复：我确认这一版；否则请提出修改或要求再审。”
`decide --answer no_further_review --words "我确认这一版"` binds this exact answer to current
files. No interpreting “continue/OK/no further review” as acceptance. Existing historical
approvals stay historical; new confirmations use the explicit token. Proven post-approval
presentation amendments retain the existing no-reconfirmation path.
