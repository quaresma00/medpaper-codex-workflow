# Independent scientific reading before Abstract

Use at S12, after actual tables/figures and Results, before further manuscript writing. This
adds no stage and creates no external-review ZIP. The review's purpose is to avoid spending
on a complete paper when the design, findings or displays cannot support the intended SCIE
Original article. Legitimate low-impact/Q3/Q4 journals are acceptable; acceptance is uncertain.

## Prepare, actually delegate, preserve the real reply

```powershell
.\.venv\Scripts\python.exe tools/early_review.py start --executor-id <actual-current-executor-id>
```

Use returned `reviewed_artifacts` paths/hashes and `report_destination`. Exactly one separate
read-only subagent receives the actual protocol, Methods, executed analysis code and result
JSONs, Results, real table/figure files, legends and recent comparator evidence. Do not pass
only the executor's interpretation of those materials. Do not require Abstract/full manuscript
or expose patient records unnecessarily. No input may change while it reads. Its only write
is the designated report under `.wf/review_inbox/`. If it cannot write, persist its complete
returned report verbatim there. A reviewer identity in JSON records real delegation; it cannot
prove a tool call or replace actual independence. Never invent a successful review.

Required prose sections are `Methods and validity`, `Results and uncertainty`, `Figures and
tables`, `Original article suitability`, `Further analysis value`, `Required revisions`.
Ask whether the data/model/clinical question support the claims, uncertainty is honest,
necessary comparisons/validation/selection are present, and the actual display story is as
complete as recent close Original articles. Do not manufacture RCT registration, prospective
claims, unavailable analyses or obligatory reporting forms for retrospective database work.
Assess whether extra analysis is likely to change the scientific or publication decision;
explicitly distinguish a correctable issue from an irreparable barrier or a likely research note.

In one fenced JSON object retain `early_review_version:1`, exact `review_id`, exact
`reviewed_artifacts`, `reviewer:{role:independent_subagent,agent_id:<actual-id>}`,
`article_type:original_article`, `verdict:GO|REVISE|NO_GO`, and
`marginal_analysis_value:material|low|none`. Inventory every actionable observation using the
existing `[finding:ID]`, `findings`, `finding_inventory_complete:true` and `section_verdicts`
format (section, actual locator, issue text, category and affects_science). No invented PASS.

```powershell
.\.venv\Scripts\python.exe tools/early_review.py attach --report <actual-complete-report.md>
.\.venv\Scripts\python.exe tools/early_review.py check
```

## What happens to its opinion

Show the author the verdict, main reasons and actual report path immediately. A GO supports
writing; it does not mean journal acceptance. REVISE blocks expansion until true-source fixes
and actual necessary independent revalidation. NO_GO, inability to support an Original article,
or a remaining route with negligible decision value calls for a candid author pivot/stop
discussion now. Do not keep adding analyses solely to consume a workflow stage or avoid a stop.

Use one scoped correction batch at S12. Resolve only the identified scientific/method/text/
display sources and their real consumers; do not reset a stage or generate Introduction,
Discussion, Abstract, Word or submission files as part of this repair. After material scientific
changes, `start` prepares the changed inputs and the next designated report. Supply the concise
delta plus unchanged context to a real reviewer; focus revalidation on what actually changed.
If inputs and actual report are unchanged, `start` reuses the existing record rather than
commissioning another agent. Container timestamp changes alone are not a scientific change;
proven presentation amendments can use the existing meaning-preserving dependency path.

S18 later reads the complete medical argument, prose, citations, limitations and final display
comprehension. It reuses the early scientific opinion and tests whether writing overstates it.
Reopen scientific review only for material new evidence or changed scientific inputs. The S19
author confirmation and S25 journal/reader/editor review keep their own existing purposes.
