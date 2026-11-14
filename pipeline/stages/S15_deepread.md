# S15 - Deep-read the papers that carry the Discussion

Registration also checks the acquired article's own identity. Do not accept a DOI found
in a bibliography as proof. For PDF/title-only cases, inspect the actual first page and
get explicit reader confirmation; `fulltext.py confirm --citekey KEY --confirmed-by NAME
--identity-note "concrete title/authors/identifier evidence"` records that confirmation,
not an automatic AI verdict. Wrong identities block; never invent user confirmation.

## Purpose
Read the sources needed for real method/result comparisons and competing explanations.
Reuse the S07 full texts already read; obtain further sources only for unresolved arguments.
There is no fixed deep-read quantity; substantive coverage, source identity and notes matter.

## Procedure
1. Select the papers that the Discussion genuinely depends on. Typically:
   - the closest prior study on the same question (whatever the direction of its result),
   - the study that most disagrees with your finding,
   - the methodological reference your approach stands on,
   - the largest or most authoritative study in the area,
   - the paper a reviewer will ask "why does your result differ from this one".
   Selection is by argumentative need, not by impact factor.
2. Fetch actual full text, reusing valid prior files. For visual/full-PDF reading use `--require-pdf`:
```
.\.venv\Scripts\python.exe tools/pubmed/fulltext.py fetch --citekey smith2023 --citekey lee2021
```
   It tries Europe PMC / PMC, Unpaywall and OpenAlex, saves the PDF or XML to
   `06_refs/fulltext/`, and records the route, access basis and file hash in
   `06_refs/fulltext/retrieval_manifest.json`.
3. If built-in routes fail, continue through available scansci-pdf sources, publisher/author
   repositories and user-authorized institutional/browser access. For this user's expressly
   requested Sci-Hub route use the exposed download tool with `scihub_enabled=true`,
   `strategy="scihub_only"`, `use_tor=false`, `use_vpnsci=false`; do not install networking
   components or extract cookies as an unrequested fallback. A failed unchanged route is not
   retried blindly. Inspect the actual tool outcome; never invent download/reading success.
   Register the acquired local copy before reading it:
```
.\.venv\Scripts\python.exe tools/pubmed/fulltext.py register --citekey smith2023 --file "C:\path\paper.pdf" --access oa --source-url "https://publisher.example/article" --route scansci-pdf
```
   For institutional access, use `--access authorized --authorization-note "<basis>"`.
   For an external copy whose OA/institutional basis is unestablished, use `--access external`
   with `--authorization-note` recording the real user-selected route; that is not a claim
   about its license. All article identity/hash/body checks remain. Browser login or cookie
   access still needs actual authorization. Record an actual failed external attempt with
   `fulltext.py attempt --citekey KEY --route <actual-route> --outcome <actual-outcome> --note
   "<concrete outcome>"`. If the needed PDF remains missing, ask for its exact title/DOI and
   the argument/display it supports. Pause only dependent writing; do not silently omit a
   key comparison or replace it merely to pass. HTML/XML can support genuine text reading,
   but cannot satisfy a requested PDF or inspection of inaccessible figures.
4. Read each registered local full text and write structured notes to
   `06_refs/deepread/<citekey>.md`:
```markdown
# <citekey> - <short title>
## Design and population
## What they did differently from us
## Their key numbers
## How this supports or contradicts our finding
## What a reviewer would take from this
```
   Notes must be substantive; the gate rejects notes under 400 characters as evidence that
   no real read happened.
5. Index them in `project/06_refs/deepread/deepread_index.json`:
```json
{"selected": [{"citekey": "", "pmid": "", "reason": "why this paper carries part of the Discussion",
  "access": "oa|authorized|external", "fulltext": "06_refs/fulltext/<file>.pdf",
  "notes": "06_refs/deepread/<citekey>.md"}]}
```
6. Update `03_analysis/notes.md` -> `Discussion points` with what the deep reads changed.
   If a deep read overturned an assumption, that is the most valuable output of this stage.

## Outputs
- `06_refs/deepread/deepread_index.json`
- (plus per-paper notes and fetched full texts)

## Hard rules
- Every selected citekey must already be in `library.json`.
- Every selected file must have a matching retrieval-manifest record and unchanged hash.
- Every selection needs a recorded reason. "Highly cited" is not a reason.
- If a paper turns out not to matter, remove it from the index and record why - the gate at
  S16 requires every indexed paper to be cited in the Discussion.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "<n> deep reads: <citekeys>; changed my view on: <...>"
```
