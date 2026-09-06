# Install and operate medpaper-codex

## Requirements

- Windows PowerShell
- `uv`
- Python 3.13 (installed or provisionable by `uv`)
- Network access for current literature, indexing, journal, and open-access checks
- Pandoc and Microsoft Word for final DOCX rendering/visual QA; R is optional unless an analysis uses it

## Bootstrap

From the extracted repository root:

```powershell
uv run --python 3.13 python bootstrap.py
```

Bootstrap creates `.venv`, installs the pinned packages, initializes `project/`, runs
`wf doctor`, and runs the offline regression suite. It returns a non-zero exit code if a
required step fails.

Set credentials in the process or user environment, never in repository files:

```powershell
$env:NCBI_API_KEY = "<your NCBI API key>"
$env:NCBI_API_EMAIL = "you@example.org"
```

`NCBI_API_KEY` is optional. `NCBI_API_EMAIL` is needed for Unpaywall requests. Restart Codex
after changing persistent environment variables.

## Codex discovery

Codex discovers the repository-local Skill at
`.agents/skills/medpaper-codex-pipeline/SKILL.md` and the repository instructions in `AGENTS.md`.
Open the repository root as the Codex project and invoke `$medpaper-codex-pipeline` explicitly.

For machine-wide use, install the companion user Skill as
`%USERPROFILE%\.agents\skills\medpaper`. It carries this clean ZIP as a versioned asset and
can initialize a new `medpaper-study` workspace under any current Codex project without
depending on this source checkout. Restart Codex after installing or updating a user Skill.

## Start or resume

Place the idea Markdown file in `project/00_input/`, then ask Codex:

```text
$medpaper-codex-pipeline
Start or resume this project. Run status first and follow only the active stage card.
The research idea is in project/00_input/idea.md.
```

From any other project or task, use the global starter:

```text
$medpaper Start a new pipeline for: <research idea>
```

The literal text `/medpaper pipeline <research idea>` is also routed to `$medpaper` by the
global Codex instructions on this machine. It is a text alias, not a native slash-menu entry;
the supported explicit invocation remains `$medpaper` (or selecting it from `/skills`).

The command loop is:

```powershell
.\.venv\Scripts\python.exe tools\wf.py status
.\.venv\Scripts\python.exe tools\wf.py check
.\.venv\Scripts\python.exe tools\wf.py advance --note "specific handoff note"
```

Use `loop --to <stage> --why "..."` for a deliberate return to an earlier stage. Use
`clean` to report undeclared files; inspect the report before using `clean --apply`.

At S04, a raw file is not enough to prove complete acquisition. The stage creates and checks
`02_data/acquisition_manifest.json`:

```powershell
.\.venv\Scripts\python.exe tools\data_manifest.py init
.\.venv\Scripts\python.exe tools\data_manifest.py sync
.\.venv\Scripts\python.exe tools\data_manifest.py verify
```

Every source must reconcile a machine-readable source total with the received raw payloads
and show terminal pagination. The workflow rejects convenience sampling, first-N retrieval,
fixed page caps and silently narrowed queries. This evidence gate cannot be waived with
`--force`; changing a census to a scientific sample and accepting a genuine external access
limit each require a separate explicit user authorization.

## Capability conflicts

The pipeline owns sequencing, paths, and gates. Other Skills or plugins may assist inside
the active stage only. Follow `reference/codex-integration.md`:

- scholarly-search or research tools discover candidates; pipeline retrieval and
  verification make them citable;
- external PDFs must come from open-access or explicitly authorized institutional routes
  and be registered locally;
- spreadsheet, document, and PDF workflows render and visually inspect artifacts without
  starting a second manuscript workflow;
- ImageGen may offer a second visual critique of rendered scientific figures, but it must
  not redraw them; accepted fixes are made in plotting code and re-rendered;
- one independent subagent reviews the frozen full manuscript, optional supplementary
  Methods and tables at S18; it reviews only and does not rewrite the source;
- after S23 builds the journal package, S24 lets the user edit its content and formatting,
  obtains an explicit request for the final review, and freezes the exact reviewed revision;
  S25 then uses one separate read-only subagent to read the package as a first-time scientific
  reader, screen low-level errors as an editor, and audit the freeze against the official
  journal guide for omissions, noncompliance and cross-file mismatches;
- patient-level/private data stay local unless the user explicitly authorizes transfer.

Formal references are fail-closed. Candidate-search tools may suggest papers, but only
`tools/pubmed/verify.py` may create the verification receipt. It performs a fresh PubMed
EFetch and records the raw-XML hash, parsed-record fingerprint, and exact `library.json`
hash. S13 and every later manuscript/submission checkpoint separately re-fetch the PMIDs
live. A handwritten `verified: true`, a locally
fabricated DOI, or a green Pandoc build cannot satisfy these gates, and `wf advance --force`
cannot waive them.

The workflow chooses one title automatically, assembles `full_manuscript.md`, and presents
that file together with supplementary Methods, tables and the independent verdict at S19.
Author and affiliation details are intentionally deferred until S21. S23 converts every
narrative upload—including the cover letter and supplementary Methods—to DOCX. The chosen
journal's explicit typography rules win; where it is silent the recorded fallback is Times
New Roman 12 pt, double spaced, black, with no hyperlinks or collapsible heading hierarchy.
All Word XML parts are stripped of `keepNext`, `keepLines`, `pageBreakBefore`, `outlineLvl`,
and paragraph borders; headings use the Normal-based `SectionHeading` style. Figure legends
have one section title and one title per figure. Supplementary Methods is prose-only: its
tables are delivered in the separate three-line supplementary workbook and Markdown thematic
rules are rejected before conversion.
S24 does not advance until the user explicitly confirms the revalidated package is `OK`.
S25 requires an independent three-lens `PASS`; a changed or deficient package loops back to
S24 for correction and renewed confirmation.

User-requested revisions do not bypass the pipeline. `tools/rework.py` routes each change to
the earliest source-owning stage described in `reference/rework-routing.md`. Repeated feedback
is persisted as a batch at S19 for scientific content or S24 for the journal package. Run
`tools/rework.py status` after context compaction; it restores the exact feedback,
interpretation, atomic items, affected files and acceptance criteria without rereading the
entire conversation. Rebuild only the true dependency closure and reuse unchanged verified
evidence, but do not drop an affected gate or requested item for token efficiency. S19
requires the assembled manuscript to match its component Markdown. S23 captures DOCX
visible-text hashes with `tools/package_content.py`; S24 accepts a Word-only change as
formatting only when those hashes still match.

## Verify or rebuild the package

```powershell
.\.venv\Scripts\python.exe tools\wf.py doctor
.\.venv\Scripts\python.exe tools\selftest.py
.\.venv\Scripts\python.exe tools\package.py --output ..\medpaper-codex-ready.zip
```

Packaging refuses non-placeholder credentials and personal email addresses, runs the doctor
and offline tests, and excludes `.venv`, run state, caches, and user project data.

