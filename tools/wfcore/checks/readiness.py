"""Writing, prototype, feedback and final-file gates."""
from . import Ctx, Result, check
from ..readiness import verify_writing, verify_displays


def _evidence_result(name, run, success):
    try:
        problems = run()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems = [str(exc)]  # Expected missing/invalid evidence is a normal failed gate.
    return Result(not problems, name, "; ".join(problems[:8]) or success)


@check("medical_benchmark")
def medical_benchmark(ctx: Ctx) -> Result:
    from ..benchmark import verify_benchmark, display_fit
    layer = ctx.spec.get("layer", "science")
    return _evidence_result("medical_benchmark", lambda: verify_benchmark(ctx.project, layer) + display_fit(ctx.project, layer),
                            "registered close full texts constrain project structure, evidence roles and nonredundant displays; counts are advisory")


@check("literature_coverage")
def literature_coverage(ctx: Ctx) -> Result:
    from ..benchmark import coverage
    return _evidence_result("literature_coverage", lambda: coverage(ctx.project, ctx.spec.get("section"), library_only=ctx.spec.get("library_only", False)),
                            "planned arguments bind their real source keys/passages; semantic support still requires reading")


@check("executor_acceptance")
def executor_acceptance(ctx: Ctx) -> Result:
    from ..benchmark import verify_acceptance
    return _evidence_result("executor_acceptance", lambda: verify_acceptance(ctx.project, ctx.spec.get("layer", "science"), final=ctx.spec.get("final", False)),
                            "executor findings bind actual current manuscript/displays; not an independent or human verdict")


@check("reader_review_coverage")
def reader_review_coverage(ctx: Ctx) -> Result:
    from ..readiness import verify_reader_review
    problems = verify_reader_review(ctx.project)
    return Result(not problems, "reader_review_coverage", "; ".join(problems[:8]) or
                  "independent reader report binds actual prose, tables and rendered figures; semantic judgment remains with the reviewer")


@check("writing_ready")
def writing_ready(ctx: Ctx) -> Result:
    problems = verify_writing(ctx.project,validate_analysis=not ctx.spec.get("reuse_analysis",False))
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
