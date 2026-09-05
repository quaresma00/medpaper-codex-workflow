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

The workflow chooses one title automatically, assembles `full_manuscript.md`, and presents
that file together with supplementary Methods, tables and the independent verdict at S19.
Author and affiliation details are intentionally deferred until S21. S23 converts every
narrative upload—including the cover letter and supplementary Methods—to DOCX. The chosen
journal's explicit typography rules win; where it is silent the recorded fallback is Times
New Roman 12 pt, double spaced, black, with no hyperlinks or collapsible heading hierarchy.
S24 does not advance until the user explicitly confirms the revalidated package is `OK`.
S25 requires an independent three-lens `PASS`; a changed or deficient package loops back to
S24 for correction and renewed confirmation.

## Verify or rebuild the package

```powershell
.\.venv\Scripts\python.exe tools\wf.py doctor
.\.venv\Scripts\python.exe tools\selftest.py
.\.venv\Scripts\python.exe tools\package.py --output ..\medpaper-codex-ready.zip
```

Packaging refuses non-placeholder credentials and personal email addresses, runs the doctor
and offline tests, and excludes `.venv`, run state, caches, and user project data.
