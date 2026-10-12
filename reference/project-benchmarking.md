# Project-specific medical-paper benchmarking and proactive acceptance

Read at S07, S13-S17 and S20-S23; retain findings across turns instead of repeating searches.
The engine can prove source identity, bindings, coverage and drift, not that an AI understood
medicine. Actually read/inspect the sources and outputs. A PASS string is never a substitute.
Keep this evidence backstage, outside manuscript headings and submission uploads.

## Two comparison points, not a fixed paper template

At S07, before Methods, final workbooks or production figures, read multiple distinct close
published full texts. Choose by topic, design and analysis relevance; explain mismatches and
access limitations. Examine Methods/Discussion and real display content, not abstracts alone.
Record main/supplement figure/table counts, citation ranges and the roles those citations and
displays play. Judge whether the examples collectively cover this project's clinical story.
Do not impose an arbitrary fixed count of project references/displays or imitate decoration.

Use the bundled clients to seed the genuine comparator/method references at S07:
`build_library.py --add-ids <selected PMIDs>`, then `verify.py`, then `fulltext.py fetch --citekey
KEY --no-stub` (or legal `register`). S13 completes this same library, not a second one.
Do not include every search hit or stop a coverage query because a library count was reached.
`build_library.py --target` is now only a legacy hint, not a query-stopping rule. Formal citations
still require the normal raw-PubMed/live verification and claim-support checks.

At S20, after journal choice and article-type requirements, add same-journal close full-text
examples to `08_submission/integration/journal_benchmark.md`. Never alter the scientific master
or its frozen bibliography to obtain these style comparators. Use `fulltext.py fetch --pmid
<PMID> --pmid <PMID> --no-stub`, or `register --pmid <PMID> ...`. These comparator-only keys
are `benchmark<PMID>`; fresh hashed PubMed payloads stay in the cache/retrieval manifest.
They are NOT manuscript citekeys or verified formal library entries. A PDF title/bibliography
match is not article identity; existing explicit identity confirmation rules still apply.

## One human-readable benchmark with one machine-readable binding

Keep the existing S07 headings. Explain the comparisons and resulting choices in ordinary
language; include one fenced JSON object with `benchmark_version: 1` in that same document.
Use the same schema for the journal comparison. Do not create a second narrative dossier.

- `adequacy_rationale`: how the chosen examples cover this study, and remaining limitations.
- `comparators`: one per distinct read article, with verified `citekey`, registered `fulltext`,
  `sha256`, `relevance` (`topic`, `design`, `analysis`), and `observations`.
- Observations: `methods_outline`, `discussion_structure`, `reference_roles`, `display_roles`;
  observed integer `main_figures`, `main_tables`, `supp_figures`, `supp_tables`; `citations`
  with separate counts for `introduction`, `methods`, `discussion`, `supplementary`.
  Distinguish unavailable supplements from observed zero; obtain them or choose a usable
  comparator rather than invent counts. Local observation is not automatic exact counting.
- `evidence`: short excerpts and concrete locators, `kind: methods|discussion|display`.
  Quotes must occur in the registered full text; use minimal excerpts (no more than 25 quoted
  words per comparator across this record). These locate reading, not publishable quotations.
  PDF extraction uses pinned pypdf; scanned/failed extraction needs readable authorized full
  text, never an abstract substituted for an article. Inspect figure images separately.
- `adaptation.structure`: project-specific `methods`, `discussion`, `main_vs_supplement`,
  `declarations` decisions. Keep validity-critical Methods in main text. Connected Discussion
  paragraphs are the default; headings need actual design/journal justification. Do not invent
  author declarations early; journal order outranks discipline fallback after selection.
- `adaptation.references`: `basis`, advisory `ranges` for the four sections plus `library`
  and `main_total`, and project-specific argument `roles`. Each role has `id`, `section`,
  `claim`, `source_type`, `required`, selected `citekeys`, and later the exact cited `passage`.
  Populate real method-source selections before S08; complete other source selections at
  S13 and passages when the section is written. Cover key prior, contradictory and method
  evidence when applicable, not only easy agreeing papers. A selected key must support the
  actual argument on reading; a citation appearing somewhere else is insufficient.
- `adaptation.displays`: `inventory_rationale`, `essential_questions`, `omissions`. Include
  needed selection/denominator, primary result, validation or sensitivity evidence when
  scientifically applicable. Explicitly explain when a flowchart or extra validation display
  adds nothing; do not silently treat the cheapest inventory as complete. Record null results.
- Journal only: `target_hashes` for `08_submission/target_journal.json` and
  `08_submission/submission_requirements.json`. Same-journal identity comes from PubMed.

Run `tools/manuscript/benchmark.py seal --layer science|journal` at S07/S20. The small internal
lock fixes comparator/adaptation/range/required-role choices before writing or Word builds.
Source selections/passages may be completed without weakening that plan. Do not lower ranges,
remove required arguments or reset the lock to pass. A real replan follows an explicitly scoped
user-feedback round at the owning checkpoint and must explain scientific/comparator evidence;
it does not rewind the completed stage tail. Old projects add genuine missing evidence in
scope; never label historical abstract-only comparisons as completed full-text reading.

## Specific display contracts and executor acceptance

Alongside the existing five reader-contract fields, each display has `question`,
`placement_reason`, `nonredundancy`, `misinterpretation_risk`. Common population wording is fine;
copied purpose/placement explanations are not. Check the actual panel population, comparison,
measure, denominator, error bars and meaning against these claims. Correct misleading
encodings and missing essential evidence before delivery; no schema can certify those facts.

Before S18/user delivery at S17, perform the main executor's content/readability review; after
selection at S22 perform journal preproduction review; at S23 inspect the actual final uploads
and complete final acceptance after cleanup/render/baseline. These are not new independent
agents or user stops. Existing S18/S25 independent review and S19/S24 author decisions remain.

Keep concise executor findings in a temporary `.wf/` JSON with `reviewer` (honest role),
`findings` and `display_findings`, `range_deviations`, `unresolved`. `findings` covers
`methods_logic`, `literature_coverage`, `display_completeness`, `discussion_flow`, `declarations`,
`legends_and_crossrefs`, `reader_comprehension`, each with substantive `observation` and
`verdict`. Explain inapplicability rather than fabricate activity. All routine defects must
be resolved (`unresolved: []`) before PASS. Every display has its own concrete observation,
actual `reviewed_file`, and `contract_hash` (SHA-256 of JSON reader_contract, sorted keys).
Do not copy observations or claim human/independent review when it was an executor simulation.

Use `benchmark.py metrics` to distinguish library size, actually cited main references,
section citations and supplement citations. Out-of-range counts require a coverage-based
`range_deviations` explanation, not padding or a changed locked range. Missing required
argument-source/passages still fail regardless of counts or that explanation.

Bind completed findings with `benchmark.py accept --review <findings.json>` at S17,
`--layer journal` at S22, and `--layer journal --final` at S23. Pre/final receipts are separate;
they bind actual inspected sources/displays/uploads and detect later drift. A journal display
not yet produced must have an explicit existing `preview` or `source_file` for preproduction
review; final review requires the actual planned file. Do not guess its scientific predecessor.
Only explicitly sourced `submission_requirements.json.display_limits` impose figure/table
caps (`main_figures`, `main_tables`, `main_display_items`, `supp_figures`, `supp_tables`),
with article-specific status/value/source like other journal rules. Unspecified means null.

Use unchanged evidence and targeted dependency checks; do not reacquire/replay clinical data
for this editorial work. Report file generation, content acceptance, visual acceptance and
actual submission as different states. A routine executable error stops dependent capture/build.
