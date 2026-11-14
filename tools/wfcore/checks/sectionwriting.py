"""Medical writing is read and polished before its section stage closes."""
from . import check,Result


@check("section_medical_polished")
def section_medical_polished(ctx):
    from .. import sectionwriting
    try:
        errors=sectionwriting.problems(ctx.project,ctx.spec.get("paths",[]),ctx.spec.get("optional",[]))
        return Result(not errors,"section_medical_polished","; ".join(errors) or
                      "Current section medical reading recorded; this is not an AI detector or proof of semantic correctness",
                      ["Use section_writing.py begin before editing; read actual prose/sources, then accept. Assembly checks cohesion only."] if errors else [])
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return Result(False,"section_medical_polished",str(exc))
