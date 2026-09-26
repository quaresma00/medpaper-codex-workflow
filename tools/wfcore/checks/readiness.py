"""Writing, prototype, feedback and final-file gates."""
from . import Ctx, Result, check
from ..readiness import verify_writing, verify_displays


@check("reader_review_coverage")
def reader_review_coverage(ctx: Ctx) -> Result:
    from ..readiness import verify_reader_review
    problems = verify_reader_review(ctx.project)
    return Result(not problems, "reader_review_coverage", "; ".join(problems[:8]) or
                  "independent reader report binds actual prose, tables and rendered figures; semantic judgment remains with the reviewer")


@check("writing_ready")
def writing_ready(ctx: Ctx) -> Result:
    problems = verify_writing(ctx.project)
    return Result(not problems, "writing_ready", "; ".join(problems[:8]) or
                  "analysis contract and clinical story match the S06 freeze")


@check("display_prototypes_reviewed")
def display_prototypes_reviewed(ctx: Ctx) -> Result:
    problems = verify_displays(ctx.project)
    return Result(not problems, "display_prototypes_reviewed", "; ".join(problems[:8]) or
                  "all planned displays have source-bound previews and reader explanations")


@check("feedback_batch_sealed")
def feedback_batch_sealed(ctx: Ctx) -> Result:
    import json
    active = ctx.state.data.get("active_revision_round")
    if active:
        doc = json.loads((ctx.state.dir / "revisions" / f"{active}.json").read_text(encoding="utf-8"))
        if doc.get("status") == "collecting":
            return Result(False, "feedback_batch_sealed",
                          f"{active}: feedback collection is open; wait for the user's end-of-batch instruction")
    return Result(True, "feedback_batch_sealed", "no open feedback collection")


@check("portal_fields_current")
def portal_fields_current(ctx: Ctx) -> Result:
    from ..submission import verify_portal
    problems = verify_portal(ctx.project)
    return Result(not problems, "portal_fields_current", "; ".join(problems[:8]) or
                  "portal fields were computed from the current final DOCX and administrative facts")
