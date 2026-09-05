# User-requested revision routing

All revisions remain inside the medpaper state machine. Reading or editing files directly is
an implementation step, not permission to bypass the owning stage, source of truth or gates.

Before changing an artifact after it has been presented for review, run:

```powershell
.\.venv\Scripts\python.exe tools/rework.py plan --kind <kind> --why "<requested change>"
.\.venv\Scripts\python.exe tools/rework.py start --kind <kind> --why "<requested change>"
```

Use the earliest stage that owns the changed fact or artifact:

| Revision kind | Owning stage |
|---|---|
| study question, population or design | `study-design` -> S03 |
| raw/derived data | `data` -> S04 |
| model, estimate, numerical result or analysis meaning | `analysis` -> S05 |
| final protocol decision | `final-protocol` -> S06 |
| display inventory or substantive legend plan | `artifact-plan-or-legend` -> S07 |
| Methods or supplementary Methods content | `methods` -> S08 |
| Results wording with unchanged analysis | `results-wording` -> S09 |
| table content | `tables` -> S10 |
| figure content or rendering | `figures` -> S11 |
| Introduction | `introduction` -> S14 |
| Discussion | `discussion` -> S16 |
| title, abstract, keywords or initial assembly | `title-abstract-keywords` -> S17 |
| meaning-preserving copyedit | `manuscript-copyedit` -> S19 before journal polish, otherwise S22 |
| target journal or its rules | `journal` -> S20 |
| title page or declarations | `title-page-or-statements` -> S21 |
| cover letter, filename, upload list or package composition | `cover-letter-or-package-structure` -> S23 |
| Word layout with absolutely no visible-text change | `word-format-only` -> S23/S24 |

For S19 copyedits, update the owning component Markdown and rerun
`tools/manuscript/assemble.py`; `full_manuscript.md` must still match its components. A change
to a claim, interpretation, method, number, table or figure is not a copyedit and must use its
earlier route.

At S23, capture `package_content_baseline.json` after all DOCX files and `manifest.json` are
final. S24 may preserve manual Word formatting only while the visible-text hash is unchanged.
If Word text changes, reconcile the requested wording to its Markdown/data/table/figure source,
run the owning route, rebuild the true dependants and capture a new baseline at S23. Never
recapture a baseline at S24 merely to bless an edited DOCX.

Every rewind invalidates downstream decisions. After corrections, progress through the gates,
present the revised artifact again, obtain the required user confirmation, freeze the new
package and run one new independent audit. Unchanged artifacts may be reused; rebuild only
the changed artifact and its actual dependants.
