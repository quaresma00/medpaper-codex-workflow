# S02 - Feasibility: real literature scan + go/no-go #1

## Purpose
Decide whether this idea can be published at all, using retrieved literature rather
than impressions. A wrong GO here wastes the entire pipeline.

## Procedure
1. Derive at least 4 distinct search strategies from `01_protocol/idea.json`:
   the exact claim, the broader claim, the population alone, the exposure-outcome pair,
   and (if relevant) the same question in an adjacent population or database.
2. A scholarly search skill or plugin may help discover terms or candidate records, but
   it is not evidence for this workflow. Run every formal strategy through the bundled
   client. It caches the raw payload and appends to the manifest, which is what the gate
   inspects:
```
.\.venv\Scripts\python.exe tools/pubmed/client.py search --query "<strategy>" --retmax 100
.\.venv\Scripts\python.exe tools/pubmed/client.py search --query "<strategy>" --retmax 100 --years 5
```
3. Fetch records for the most relevant hits so you are reading real abstracts:
```
.\.venv\Scripts\python.exe tools/pubmed/client.py fetch --ids 12345678,23456789 --with-abstract
```
4. Judge saturation honestly:
   - How many papers already answer this exact question?
   - Is the novelty only "new country / new hospital / new database"? Say so plainly.
   - Is there a systematic review that closes the question?
   - Could the study plausibly fit at least one legitimate, currently SCIE-indexed journal
     with a current JCR quartile (Q1-Q4) and no material integrity warning? At this stage,
     name candidates but do not claim verified status; S20 performs current verification.
5. Write `project/01_protocol/feasibility.md` with exactly these headings:
   `Search strategy`, `What is already published`, `Gap this study claims`,
   `Saturation risk`, `Verdict`.
   Cite everything you assert with pandoc markers `[@pmid12345678]` using the citekeys
   the client generated. Full verification comes at S13; unverified keys are tolerated
   here but every key must come from a retrieved record, never from memory.
6. Record the verdict:
```
.\.venv\Scripts\python.exe tools/wf.py decide go_nogo_1 GO --why "<what the gap is, how many papers cover it, why a journal would still want this>"
```
   `PIVOT` = the question must change. `STOP` = tell the user it is not publishable and why.

## Outputs
- `01_protocol/feasibility.md`
- `06_refs/cache/scan_manifest.json` (written by the client)

## Hard rules
- Never state a PMID, title, journal, year, or finding you did not retrieve this session.
- A "GO" needs a concrete gap, not optimism.
- A "GO" also needs a plausible publishability path to an eligible journal. Q3/Q4 is
  acceptable; an unindexed or integrity-flagged outlet is not.
- If the verdict is PIVOT or STOP, stop and talk to the user. Do not advance.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "go_nogo_1=<...>; N papers screened; gap = <...>"
```
