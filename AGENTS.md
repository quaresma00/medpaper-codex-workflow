# Medpaper Codex — current execution policy

`medpaper-codex-pipeline` is the sole workflow orchestrator. The CLI and current stage card
determine work, outputs and checks. User instructions take
precedence. Maintain one workflow, one scientific source and one build chain. Other skills
provide a capability within the active stage; they do not create a second study or manuscript.

## Start, resume and read only what is relevant

Run `.\.venv\Scripts\python.exe tools/wf.py status`, then `tools/wf.py card`.
If the environment is absent, run `uv run --python 3.13 python bootstrap.py`.
After compaction use `wf handoff` and the active card; reuse guidance already read.
Complete active work, run `wf check`, then `wf advance --note "..."`. Gates are not turn
boundaries; continue unblocked work. S10 tables -> S11 figures -> S09 Results -> S12 crosscheck
is the execution order despite stable IDs. Use `card <stage> --details` only when needed.

| Current task | Read when that operation is needed |
|---|---|
| Intake, design, declarations, statistical plan | reference/quality-before-writing.md |
| Data acquisition / in-place originals | reference/data-acquisition-integrity.md / reference/data-and-review-isolation.md |
| Execute/export/replay analysis | reference/analysis-execution.md and reference/numeric-claims.md |
| Medical comparators, display inventory and prototypes | reference/project-benchmarking.md and reference/structural-quality.md |
| Draft Methods/Results/Introduction/Discussion/Abstract | reference/medical-writing.md plus the actual study sources; narrow facts via readiness.py facts |
| Produce/review tables, figures and pages | reference/medical-reader-presentation.md; relevant table/figure standards and reference/r-first.md |
| User feedback and scoped correction | reference/rework-routing.md; reference/efficient-quality.md for rebuilds/check reuse |
| Post-freeze changes or composed Word builds | reference/content-aware-amendments.md and reference/source-aligned-validation.md |
| Current journal/transfer and final compliance | reference/journal-adaptation.md |
| Independent review, exact author confirmation | reference/review-rounds-and-word-tables.md |
| External skill, retrieval capability or plugin | reference/codex-integration.md |

The drafting guide is the writing context, not a waiver of execution checks. Retrieve a
technical schema only while using its tool or investigating a specific problem. Detailed
references each own their topic; this policy contains no historical supersession stack.

## Scientific integrity and boundaries

- Acquire the entire protocol-defined available data universe. Exhaust actual pages/cursors
  and reconcile source totals, received records and analysis units; bind hashes/counts with
  data_manifest.py. No speed-driven LIMIT, first-N, page cap, sampling or truncation. Pilots
  are non-analytic and followed by full acquisition. Source-imposed partial access or a real
  scientific sampling design requires explicit recorded user authorization. This cannot be forced.
- Register authorized user data in place, preserve immutable originals and keep patient/private
  data local. External transfer requires explicit authorization and de-identification decision.
  Follow declared dependencies, replay copy budgets and owned cleanup; never read sibling studies
  or delete/kill resources by broad path/process name. Scratch belongs in project/temp/.
- A citable record comes from the bundled fresh PubMed EFetch verification, hashed raw XML,
  exact library and recomputed PMID/DOI/metadata. Keep independent live gates from S13 onward.
  Never hand-write the four library/verification/export files, invent DOI/metadata or repair a
  failed gate with a boolean. An acquired full text must be registered by
  tools/pubmed/fulltext.py register;
  article identity comes from its own metadata or exact-file reader confirmation, not its references.
- Own-study numbers come from executed analysis results under 03_analysis/results/*.json.
  Bind Results/Abstract/table claims to the right population, endpoint, contrast, scale,
  denominator and time, not a pool of matching digits. New/revised producers export/replay
  actual full-precision findings before readiness. Never backfill receipts, calculate in prose,
  refit solely for drawing or call untested legacy findings reproduced. Prior-study numbers
  require exact original passages. Scientific support outranks token/time savings.
- A failed integrity check means fix the cause. Data/reference/numeric provenance, approvals,
  freezes and engine identity cannot be forced. Only an explicitly user-authorized non-integrity
  exception may use --force and its existing handoff record. Installed engine drift stops work;
  study executors never patch shared tools, public engine identity or workflow state ad hoc.
- Ordinary retrospective/database mining has no default public registration/OSF step. For a
  systematic review/meta-analysis or genuine prospective interventional trial, assess actual
  current registration requirements at S03 and timing honestly. Ethics/access remain separate.
  Assess declarations from real source/design/policy evidence and ask only an unresolved material
  fact. Never invent committee approval, waiver, consent or redistribution rights.
- Named reporting checklists/forms are considered only after S20 when the selected journal
  explicitly requires one. Do not prepare a generic catalogue.
  Do not draft or insert an AI-use disclosure without the user's explicit request;
  a required item stays user-controlled.
  External publishing/submission requires the user's instruction.

## Medical outputs and production

- Benchmark actual close medical full texts before writing or expensive production. Let the
  scientific question and reader tasks determine references/displays, not universal quotas,
  cost or a minimum viable set. Never pad references or weaken a target to pass. Applicable
  selection is main Figure 1 with real units/branches; show the population, primary findings
  and necessary comparisons. Resolve heading structure and display purposes before drafting.
- Write a medical paper for readers: design, population, comparison, outcome, magnitude and
  uncertainty. Preserve legitimate statistical terminology, prespecification timing and
  missing/nonestimable/unbounded distinctions. Technical flags and language patterns are
  contextual prompts, never automatic substitutions, AI detection or semantic acceptance.
  Keep reproducibility/control records backstage. Use medical-writing.md for positive examples.
- Tables use clinical hierarchy, appropriate summaries/denominators and three-line formatting;
  baseline P values are not a default. New medical figures default to R; processing may use
  Python. Use the managed R renderer and approved results, preserve R source beside vector PDF,
  and inspect actual PNG/PDF. Missing R dependencies need repair, not silent Python fallback.
  Preserve already-approved Python figures; justified Python exceptions use Tavotto, never R.
  Independent A/B tags belong at panel upper-left corners, separate from clinical titles.
- Tool success does not replace opening/reading the actual tables and rendered figures/pages.
  Read figure labels and actual table titles/headers/cells/notes as a medical reader; map only
  source-authorized display labels, preserving units, denominators and actual statistics.
  Bind actual production renders in display_review.json before Results. ImageGen may act as a
  second visual critic; it must not redraw statistical figures. Apply accepted fixes in source
  code, render again and inspect. Do not infer quality from language/tool.
- S17 selects an accurate title and assembles the complete paper before S21 author administration.
  Keywords follow the abstract. References and Figure legends are explicit sections, with each
  legend identifier/title once. Legends decode the display without repeating Results; consolidate
  crowded abbreviations in Declarations and Statements > Abbreviations unless current journal
  rules require local definitions. Keep essential units/symbol meanings locally understandable.
- S16 uses display-free narrative materials and a short six-topic outline before prose. Use one
  clean-context first-draft writer when available; then separately verify against real findings.
  Routine edits remain local. Do not feed own results tables/display identifiers to that writer.
- At submission, derive nonblinded author front matter from author_info.json; separate title-page
  upload only if explicitly required or blinded. Default to separate images, tables after
  References each on a new page, and final legends. Inline images/tables/captions are independent
  explicit-required-guide exceptions. Number supplements with descriptive Supplemental_File names.
- Supplementary Methods is prose; tables go in separate three-line supplementary tables. No
  Markdown rules remain in Word. Actual journal typography governs size/spacing with medical
  defaults Times New Roman and black. Word contains no literal U+2193, manual wrapping breaks,
  hyperlinks, outlineLvl, keepNext, keepLines, pageBreakBefore or paragraph borders; use flat
  Normal-based SectionHeading. Keep the existing deterministic Word chain and final visual QA.

## Reviews, frozen sources and precise revisions

- S18 gives the complete manuscript, supplement, tables and actual figures to exactly one
  independent read-only subagent. S19/S24 use version-bound genuine review rounds, not review
  ZIPs. Attach the real report before editing, resolve every actionable finding, and report
  changes/unadopted reasons once with exact paths. Objective scientific defects cannot be
  closed as preference. Ask whether another round is wanted and wait for the actual explicit
  statement 我确认这一版 bound to that version. Silence or “continue” is not approval.
- After S19 approval verify the scientific_master_freeze.json. Journal-specific wording,
  structure, declarations, numbering and packaging belong in 08_submission/integration/.
  Begin the exact journal/ISSN/article-type/initial-or-revision context, capture official rules,
  seal configuration and measure actual uploads. Old guides/styles/approval pointers leave the
  active attempt together. Same-context resume preserves author edits. Refreshing the engine
  never silently migrates pinned gates or rewinds completed history.
- At S17/S22/S23 complete the executor's own medical/content/visual acceptance before delivery.
  Read all actual main/supplement materials without backstage context, then verify their meaning
  against sources. Quantity ranges are advisory; source identity/support and explicit journal
  limits are mandatory. Style comparators use the public cache, not changes to accepted science.
- S24 presents actual uploads for author edits and explicit final-review request. Freeze those
  files; S25 uses exactly one independent read-only reader/editor/compliance reviewer with the
  current official instructions. Missing review stays pending. An unchanged freeze is not
  repeatedly audited. Immutable releases contain actual uploads only, not caches/evidence.
- User revisions remain inside a persisted tools/rework.py batch with verbatim requests and
  acceptance criteria. Collect feedback before sealing; a complete apply-now request may seal.
  Stay at S19/S24, call affected owner rules in place, update the earliest real source, and
  rebuild only true dependants. Never reset stages or use wf loop for local revisions. Extend
  newly discovered dependencies within the batch and distinguish inspected unchanged sources.
  Close only after actual scoped checks on final files; reuse only hash/rule/config-matched
  evidence and genuine unchanged optional author adjudications. New evidence/errors stay open.
- Proven meaning-preserving presentation amendments preserve approval lineage without another
  confirmation/audit. Equal digits alone do not prove equal science. A real scientific correction
  needs affected owner work, renewed S19 review, explicit approval and freeze, then scoped S24
  consumer updates instead of replaying S20-S23. Preserve unrelated author edits and prior releases.
  Word-only layout repair requires the visible-text baseline. Never detach-patch final narrative.
- Freeze the S06 analysis/story and test cheap S07 prototypes before production. At S23 derive
  portal fields/counts from final Word and unified author facts. Use actual source/build
  dependencies, bounded handoffs, exact UTF-8 author-text files and isolated figure jobs.
  IO pending is not PASS. After two full builds diagnose cascades and correct incrementally;
  do not omit necessary evidence, outputs or visual QA to save tokens.

Ask one concise question only when a missing choice, source or authorization materially
changes the science, target, private-data handling or external action. Otherwise finish the
authorized unblocked work. Distinguish generated, content-accepted, visually-accepted and submitted.
