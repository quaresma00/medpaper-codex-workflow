"""Discussion preparation and interpretation checks inside the existing stages."""
from . import check, Result


@check("discussion_ready")
def discussion_ready(ctx):
    from .. import discussion
    try:
        if not discussion.enabled(ctx.project):
            return Result(True, "discussion_ready", "Completed older-pinned Discussion retains its original checks; adopt scoped materials explicitly for a new draft")
        errors, warnings = discussion.check(ctx.project,
            discussion_path=ctx.spec.get("path", discussion.DISCUSSION),
            results_path=ctx.spec.get("results_path", discussion.RESULTS),
            presentation_only=ctx.spec.get("presentation_only", False))
        if errors:
            return Result(False, "discussion_ready", "; ".join(x["detail"] for x in errors[:5]),
                          ["Fix the actual Discussion source in scope; do not paraphrase a Results table sentence merely to evade this diagnostic."])
        if warnings:
            return Result(False, "discussion_ready", "; ".join(x["detail"] for x in warnings), severity="warn")
        return Result(True, "discussion_ready", "Current display-free materials and six-point outline checked; no detected Results transcription or supplementary-display walkthrough. Existing medical reading remains required.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return Result(False, "discussion_ready", str(exc))
