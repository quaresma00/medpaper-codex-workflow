# S15 - Deep-read the papers that carry the Discussion

## Purpose
Abstracts are enough to frame the Introduction. They are not enough to compare methods and
effect sizes with prior work. Fetch and read ~5 full texts properly.

## Procedure
1. Select the papers that the Discussion genuinely depends on. Typically:
   - the closest prior study on the same question (whatever the direction of its result),
   - the study that most disagrees with your finding,
   - the methodological reference your approach stands on,
   - the largest or most authoritative study in the area,
   - the paper a reviewer will ask "why does your result differ from this one".
   Selection is by argumentative need, not by impact factor.
2. Fetch open-access full text. Legal open-access routes only:
```
.\.venv\Scripts\python.exe tools/pubmed/fulltext.py fetch --citekey smith2023 --citekey lee2021
```
   It tries Europe PMC / PMC, Unpaywall and OpenAlex, saves the PDF or XML to
   `06_refs/fulltext/`, and records the route, access basis and file hash in
   `06_refs/fulltext/retrieval_manifest.json`.
3. If a scholarly retrieval skill supplies an open-access file, or the user legally
   obtains one through institutional access, register the local copy before reading it:
```
.\.venv\Scripts\python.exe tools/pubmed/fulltext.py register --citekey smith2023 --file "C:\path\paper.pdf" --access oa --source-url "https://publisher.example/article" --route scansci-pdf
```
   For institutional access, use `--access authorized --authorization-note "<basis>"`.
   Do not use Sci-Hub or another unauthorized source. Do not request browser login,
   cookies or credentials unless the user explicitly authorizes that route. If only a
   paywalled link or abstract is available, replace the paper or leave the stage blocked;
   it does not count as a deep read.
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
  "access": "oa|authorized", "fulltext": "06_refs/fulltext/<file>.pdf",
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
