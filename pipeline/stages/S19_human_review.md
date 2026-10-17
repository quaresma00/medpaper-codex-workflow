# S19 - Scientific subagent review and scoped correction rounds

## Purpose
Deliver a professional medical paper through independent reading and executor correction,
not by asking the user to discover routine defects. No review ZIP is created. Preserve old
archives and legacy freezes; never delete them during an engine update.

## Procedure
Already approved/frozen and only presentation requested? Follow
`reference/content-aware-amendments.md` for a proved scoped amendment, not a fresh review
round/question. The procedure below covers first review, user-requested extra reading or
changed science. Unknown equivalence is not automatically presentation.

1. Continue manuscript round M001 started at S18. Its genuine read-only subagent report must
   already be attached. Later rounds start only after the user's another-round answer:
```
.\.venv\Scripts\python.exe tools/review_round.py start --scope manuscript --delta
```
   An upgraded project already at S19 without a round starts one here; preserve its old
   reports/archives and do not replay data or analyses just to upgrade the engine.
   Give exactly one independent subagent the printed hashes, current complete manuscript,
   optional supplementary Methods, bibliography, workbooks, actual rendered figures and
   legends. Delta mode focuses changed files and true dependants; make the complete current
   context and previous report available. Explicitly examine removed/moved artifacts too.
   Read-only is a task restriction, not a claimed tool sandbox. If delegation is unavailable,
   mark the independent review pending; never substitute the main agent as independent.
2. Save the actual returned report. Include the exact `reviewed_artifacts` JSON selection,
   substantive `Reader comprehension` and `Medical presentation` sections, severity,
   precise locations and correctable versus validity/author-owned barriers. Before editing:
```
.\.venv\Scripts\python.exe tools/review_round.py attach --scope manuscript --report <report.md>
```
   Attaching verifies that inputs did not change during the review. Never manufacture a
   report, input hash claim or independent identity to make a gate pass.
3. The main agent evaluates findings and autonomously fixes safe, evidence-supported defects.
   Follow `reference/rework-routing.md`: one sealed scoped batch, label its origin as actual
   independent/executor QA, update the earliest owning sources, and rebuild/recheck only true
   dependants. Do not navigate backwards or replay completed stages. Do not invent data,
   references, author/ethics facts or scientific decisions. Ask only for a genuinely blocking
   author choice. Record unadopted preferences with a specific reason; an objective defect is
   not a preference. Preserve the original independent report.
4. Run affected owner checks, `assemble.py --check`, and the actual scoped `rework.py check`,
   mark and close commands. Do not close the review round while a source-revision batch is
   still active. Record every changed/removed review artifact and explain unadopted findings:
```
.\.venv\Scripts\python.exe tools/review_round.py close --scope manuscript --change <project-relative-file> "<actual correction>" --kept <finding-ID> "<specific reason>" --unresolved 0
```
   Repeat `--change`/`--kept` as needed; omit when none. Set the actual count of unresolved
   objective defects or missing author facts, not an optimistic zero. They block approval.
   Material scientific corrections need actual independent post-fix revalidation before
   owner checks close: attach its current hash-bound report with `--revalidation`. This may
   be the same reviewer following up in the same round; retain the original report.
5. Report ONCE: independent outcome, corrections, affected files with clickable locations,
   remaining/unadopted items and reasons. Offer manuscript, supplement, tables, figures and
   review report directly. Do not ask for author administration here. Ask one question:

   > 本轮审阅与修改已完成。是否再进行一轮子代理审阅？若无需继续审阅，请回复“无需继续审阅”。

6. Preserve the actual user answer; generic “继续”, silence or file delivery is not approval:
```
.\.venv\Scripts\python.exe tools/review_round.py decide --scope manuscript --answer another_round --words "<actual user answer>"
```
   Or, ONLY after an explicit no-further-review answer, use `--answer no_further_review`.
   The tool binds `manuscript_human_reviewed=NO_FURTHER_REVIEW` to this closed round and its
   current files. It does not interpret user intent for you. Any post-closure file drift
   requires correction/review and renewed confirmation; never overwrite a saved snapshot.
7. After approval and all applicable gates, freeze the exact scientific master:
```
.\.venv\Scripts\python.exe tools/manuscript/scientific_freeze.py freeze
.\.venv\Scripts\python.exe tools/manuscript/scientific_freeze.py verify
.\.venv\Scripts\python.exe tools/wf.py check
.\.venv\Scripts\python.exe tools/wf.py advance --note "current review round explicitly approved; scientific master frozen"
```

## Outputs and boundaries
- `07_manuscript/human_review.md`: concise current handoff; history remains in `.wf/review_rounds/`.
- `07_manuscript/scientific_master_freeze.json`: binds science, report and approved round, not a ZIP.
- Journal adaptation writes only `08_submission/integration/`, never the scientific master.
  Late scientific corrections require a new scoped round/approval and freeze; resume only
  affected S24 package consumers afterwards.
- Additional user-requested review rounds are unlimited. Do not launch extra unchanged
  reviews without such a request or a material defect. Save tokens by delta reading and
  dependency-based work, never by reducing analysis, sources, medical judgment or QA.
