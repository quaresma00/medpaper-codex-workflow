# Codex capability integration

The pipeline is the only orchestrator. Skills, plugins, browser tools, and local applications
are capability providers inside the active stage; they never replace its state, paths, or
gate. This rule avoids maintaining a brittle blacklist of product names.

The user-level `$medpaper` Skill is the global launcher. Once a workspace exists, this
repository's `medpaper-codex-pipeline` Skill and `AGENTS.md` carry the same stage loop. The
repository Skill disables implicit invocation so it does not compete with the global launcher;
it remains available for explicit use and as the workspace-local operating contract.

## Literature and full text

PubMed records produced by `tools/pubmed/` are the authoritative metadata trail.
Scholarly-search skills, deep-research tools, SciSpace, Consensus, or similar services may
surface candidates, but their titles, identifiers, abstracts, and claims are discovery input
only. Re-fetch every selected record with the pipeline client, cache the raw response, add it
to `library.json`, and run `tools/pubmed/verify.py` before citing it.

Verification is evidence-based and fail-closed. The verifier performs a fresh PubMed EFetch,
stores the raw XML, records its SHA-256 and the parsed record fingerprint, binds the receipt to
the exact current `library.json`, and compares PMID, DOI, title, journal, year, first author,
abstract availability and PubMed status. The S13 `reference_provenance` gate then makes a
second live EFetch and repeats those comparisons independently; the same live gate recurs at
later manuscript, human-review, package and final-audit checkpoints so post-S13 tampering is
also caught. `verified: true` is not
trusted by itself; ad-hoc scripts must never write the library, receipt, BibTeX or RIS files.
The four reference-integrity gates are not waivable with `wf advance --force`. If NCBI is
unavailable, S13 stays blocked instead of accepting a local substitute.

For full text, prefer legal open-access routes. A scholarly-PDF skill may use open-access or
user-authorized institutional access. Never use Sci-Hub or another illicit source. Browser
login, cookies, or institutional credentials require explicit user authorization and must not
be copied into logs or project files. Register an acquired local file with:

```powershell
.\.venv\Scripts\python.exe tools\pubmed\fulltext.py register `
  --citekey <verified-citekey> --file <local-pdf> --access oa `
  --source-url <source-url> --route scansci-pdf
```

Use `--access authorized --authorization-note "..."` for an institutionally obtained file.
Registration copies the file into `06_refs/fulltext/` and writes a hash and retrieval record.
Only registered local full texts with substantive notes count toward S15.

## Data acquisition helpers

Data APIs, database clients, repository downloaders and browser tools may transport data at
S04, but they may not choose a smaller analytical dataset for convenience. The S03 plan fixes
the complete protocol-defined universe and the query/filter scope first. S04 then preserves
the source-total response, every payload/page needed to recount received records, and the
terminal pagination response under `02_data/raw/`; retrieval code belongs in
`02_data/acquisition/`.

Run `tools/data_manifest.py init`, fill the source and count-evidence entries, then run `sync`
and `verify`. The gate recomputes raw and acquisition-code hashes, independently counts the
declared raw evidence, reconciles expected/requested/received counts, checks the last cursor,
and detects common acquisition caps such as `LIMIT`, `head()`, `sample()` and first-N slices.
Chunk or page size is allowed only when all chunks/pages are retrieved. A schema pilot is
non-analytic and must be followed by the full fetch. A protocol sampling design needs the
user's explicit recorded authorization. If the source—not the agent's time,
tokens, context or compute—blocks full access, stop for the user's explicit authorization and
document the resulting population/bias. See `reference/data-acquisition-integrity.md`.

## Tables, figures, documents, and PDFs

- S10: generate XLSX files with `tools/tables/threeline.py`. Then use the standalone
  spreadsheet workflow to render and inspect every sheet. Fix the source data or writer,
  regenerate, and record `tables_visually_confirmed=YES`; do not hand-format around a defect.
  Supplementary tables also belong in this separate three-line workbook, never embedded in
  supplementary Methods.
- S11: generate figures with `tools/figures/`, pass deterministic QC, and open every PNG for
  visual inspection. ImageGen may act as a second critic for legibility, clutter, hierarchy,
  contrast, clipping, text density, and journal-native appearance. Its output is advisory:
  it must not redraw, regenerate, inpaint, or directly edit a statistical plot. Apply accepted
  fixes in plotting code, re-render, and inspect the actual new PNG. Image-generation tools
  are never substitutes for statistical plotting or the required human-visible review.
- S18: spawn exactly one independent subagent to audit the frozen `full_manuscript.md`,
  optional supplementary Methods and every table. It is a read-only publication-readiness
  reviewer, not a second orchestrator or writer. Preserve its verdict for the user's S19
  review.
- S19 and later revisions: read `reference/rework-routing.md`, run `tools/rework.py`, update
  the earliest source-owning stage and rebuild its actual dependants. The assembled manuscript
  must match its component Markdown at S19; do not patch it as a detached final file.
- S23: build each journal-required narrative upload with
  `tools/manuscript/build_docx.py`, including the cover letter and supplementary Methods.
  The builder wraps Pandoc/citeproc, applies the sourced journal style (Times New Roman
  fallback), forces black text, removes hyperlinks, and maps every Markdown heading to the
  Normal-based `SectionHeading` style. Its XML pass removes `keepNext`, `keepLines`,
  `pageBreakBefore`, `outlineLvl`, and paragraph borders from every Word part, eliminating
  the black-square pagination controls and foldable outline. It rejects duplicate Figure
  legends titles, table-bearing supplementary Methods, and Markdown thematic-rule residue.
  Use the document workflow and Microsoft Word to render
  and inspect every DOCX. If the journal requires a PDF, use the PDF workflow for rendering
  and QA. Record defects and resolutions in `08_submission/submission_qc.md`; do not change
  facts during layout repair.
- S24: present the complete upload bundle and guideline extract to the user. Preserve manual
  edits, reconcile scientific-content changes to their canonical sources, rerun affected QA,
  ask for an explicit request to run the final independent reader/editor review, then use
  `tools/package_review.py freeze` to hash the exact package and evidence accepted for review.
  Verify `package_content_baseline.json`: Word-only layout changes are allowed when visible
  text is unchanged; any visible-text drift must return to its source and be rebuilt at S23.
- S25: verify the freeze and spawn exactly one independent read-only subagent. It must inspect
  the actual files first as a new scientific reader for unclear content, then as an editor for
  low-level errors, and finally against the cached official journal guide for omissions and
  cross-file mismatches. It writes the declared audit report without editing the freeze. A
  changed freeze or non-`PASS` verdict returns to S24; do not repeatedly audit an unchanged
  package.

## Analytical and review helpers

Reporting-guideline, study-design, sample-size, de-identification, codebook, statistical, and
peer-review skills may provide advice or code during the matching stage. Their work is valid
only when it is reproducible, stored under the stage's declared paths, and accepted by the
pipeline gate. A helper must not start a separate project, write several manuscript sections
at once, or create a second reference library or submission manifest.

## Plugins

Plugin output follows the same rule as local-skill output. A plugin may help discover sources
or inspect an artifact, but external content is not evidence until it passes the pipeline's
provenance checks. Never send patient-level or private data to a plugin without explicit user
authorization and a documented de-identification decision.
