# S12 - Reconcile the rendered artifacts against the text

## Purpose
Results and Methods were written before the tables and figures existed. This stage closes
that gap. It is the cheapest place to catch a number that drifted, a renumbered panel, or
a table the prose describes differently from how it was built.

## Procedure
1. Run the gate first; it does the mechanical part:
```
.\.venv\Scripts\python.exe tools/wf.py check
```
   - `artifact_refs_consistent` with `require_rendered`: every cited item exists on disk,
     every planned item is cited, nothing cited that was not planned.
   - `numbers_cross_match`: every number in a sentence that cites `Table N` actually
     appears in that table.
2. Do the part code cannot. For each display item, open it and compare against what the
   prose and the legend claim:
   - Tables: read the xlsx values against the sentences that cite them.
   - Figures: load the PNG and check the legend describes what is drawn - panel letters,
     group order, axis units, what the error bars are, what the asterisks mean.
3. Fix the source of the discrepancy, not the symptom. If the table is right and the prose
   is wrong, edit the prose. If the analysis changed, loop back to S05 - do not patch the
   number in three places.
4. Write `project/07_manuscript/reconciliation.md`:
   - one line per display item: `Figure 1 | cited in Results L12 | legend matches | values match`
   - a `Discrepancies found and how they were resolved` section
   - a `Checked by looking` section listing which artifacts you actually opened

## Outputs
- `07_manuscript/reconciliation.md`

## Hard rules
- Do not resolve a mismatch by deleting the sentence that exposed it.
- If a number changed, every place it appears must change: Results, tables, figures, and
  later the Abstract. Search for it rather than trusting memory.

## Close
```
.\.venv\Scripts\python.exe tools/wf.py advance --note "reconciled <n> display items; <k> discrepancies fixed: <...>"
```
