# S13 - Build the verified reference library

## Purpose
Assemble roughly 50 real references with real abstracts, verified against the source APIs.
Everything the Introduction and Discussion say about the literature comes from here.

## Procedure
1. Plan the coverage before searching. The library needs to support: the clinical problem
   and its burden, what is already known, the prior work this study extends, the
   methodological citations already used in Methods, the papers your findings agree with,
   the papers they disagree with, and the guideline/definition sources.
2. Build it. Discovery tools may suggest titles, DOI values or queries, but they do not
   populate the formal library. The script searches, fetches full records, generates
   citekeys, drops records with no abstract, and caches every raw payload:
```
.\.venv\Scripts\python.exe tools/pubmed/build_library.py --topic "<core topic>" --target 50
.\.venv\Scripts\python.exe tools/pubmed/build_library.py --add-query "<gap area>" --target 50
.\.venv\Scripts\python.exe tools/pubmed/build_library.py --add-ids 12345678,23456789
```
   Anything already cited in `feasibility.md`, `method_scan.md` or `methods.md` is pulled in
   automatically so no existing citekey is orphaned.
3. Verify every entry against the source of record. This is what makes a citekey usable:
```
.\.venv\Scripts\python.exe tools/pubmed/verify.py
```
   It re-fetches each PMID/DOI, compares title/journal/year/authors, and writes
   `06_refs/verified.json`. Entries that fail are quarantined, not patched.
4. Export both formats from `library.json` - never hand-edit them:
```
.\.venv\Scripts\python.exe tools/pubmed/build_library.py --export
```
5. Read the abstracts. Update `03_analysis/notes.md` (`Introduction points`,
   `Discussion points`) with what the literature actually says, tagging each point with the
   citekey that supports it. The Introduction is written from these notes plus the
   abstracts, so vague notes here become vague prose later.

## Outputs
- `06_refs/library.json`
- `06_refs/verified.json`
- `06_refs/refs.bib`
- `06_refs/refs.ris`

## Hard rules
- **No abstract, no entry.** A record without a retrievable abstract is removed from the
  library. Do not write a summary and call it the abstract.
- Never invent, guess or "reconstruct" a citekey, PMID, DOI, title, journal or year.
- A plugin result becomes citable only after the bundled tools independently fetch and
  verify it into `library.json` and `verified.json`.
- Do not pad to hit the count. If genuine coverage is 42 papers, lower the target:
  `.\.venv\Scripts\python.exe tools/wf.py config set reflib_min 40`.
- Retracted or expression-of-concern records must be flagged in `library.json` and not
  cited as evidence.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "library: <n> verified entries with abstracts; coverage gaps: <...>"
```
