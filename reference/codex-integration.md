# Codex capability integration

The pipeline is the only orchestrator. Skills, plugins, browser tools, and local applications
are capability providers inside the active stage; they never replace its state, paths, or
gate. This rule avoids maintaining a brittle blacklist of product names.

The user-level `$medpaper` Skill is the global launcher. Once a workspace exists, this
repository's `medpaper-codex-pipeline` Skill and `AGENTS.md` carry the same stage loop. The
repository Skill disables implicit invocation so it does not compete with the global launcher;
it remains available for explicit use and as the workspace-local operating contract.

## Literature and full text

PubMed/Crossref records produced by `tools/pubmed/` are the authoritative metadata trail.
Scholarly-search skills, deep-research tools, SciSpace, Consensus, or similar services may
surface candidates, but their titles, identifiers, abstracts, and claims are discovery input
only. Re-fetch every selected record with the pipeline client, cache the raw response, add it
to `library.json`, and run `tools/pubmed/verify.py` before citing it.

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

## Tables, figures, documents, and PDFs

- S10: generate XLSX files with `tools/tables/threeline.py`. Then use the standalone
  spreadsheet workflow to render and inspect every sheet. Fix the source data or writer,
  regenerate, and record `tables_visually_confirmed=YES`; do not hand-format around a defect.
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
- S23: build each journal-required narrative upload with
  `tools/manuscript/build_docx.py`, including the cover letter and supplementary Methods.
  The builder wraps Pandoc/citeproc, applies the sourced journal style (Times New Roman
  fallback), forces black text, removes hyperlinks, and replaces Word outline headings with
  non-collapsible manuscript styles. Use the document workflow and Microsoft Word to render
  and inspect every DOCX. If the journal requires a PDF, use the PDF workflow for rendering
  and QA. Record defects and resolutions in `08_submission/submission_qc.md`; do not change
  facts during layout repair.
- S24: present the complete upload bundle and guideline extract to the user. Preserve manual
  edits, reconcile scientific-content changes to their canonical sources, rerun affected QA,
  ask for explicit `OK`, then use `tools/package_review.py freeze` to hash the exact package
  and evidence accepted for final review.
- S25: verify the freeze and spawn exactly one independent read-only subagent. It must inspect
  the actual files against the cached official journal guide, identify omissions and
  cross-file mismatches, and write the declared audit report. A changed freeze or non-`PASS`
  verdict returns to S24; do not repeatedly audit an unchanged package.

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
