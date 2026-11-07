---
name: medpaper-codex-pipeline
description: Run the gated medical-research, manuscript and submission pipeline in this repository, including repeated user revisions. Not for unrelated finished-paper review or non-medical writing.
metadata:
  version: "1.27.0"
  entrypoint: ".\\.venv\\Scripts\\python.exe tools\\wf.py status"
---

# Repository medpaper workflow

The workspace pipeline/pipeline.toml and active stage card own execution. If .venv is
absent, use uv run --python 3.13 python bootstrap.py.

Read this workspace's AGENTS.md once, then run tools/wf.py status and tools/wf.py card
with its .venv/Scripts/python.exe. After compaction use wf handoff. Complete active work,
check and advance; stages are gates, not turn boundaries. Reuse already-read guidance.
For drafting read reference/medical-writing.md and actual study sources; do not reload
execution manuals into each writing turn. For a specific operation use AGENTS.md's topic router.
For revisions use reference/rework-routing.md and a persisted batch; keep the review checkpoint,
execute affected owner rules in place, and validate true dependants. No full stage replay.
For S20-S25/transfer use reference/journal-adaptation.md and the exact current context.
Retain full-data acquisition, genuine PubMed/result provenance, actual visual QA and independent
review; never fabricate evidence or bypass integrity gates. Scientific approval is exactly
我确认这一版 for current files. R remains the new-medical-figure default. Public registration
and reporting forms remain design/journal-specific. AI disclosures require the user's request.
Keep private data local and preserve scientific freezes and unrelated author edits.
