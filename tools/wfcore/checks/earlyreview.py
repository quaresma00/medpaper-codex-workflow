"""Pre-Abstract scientific review within S12 and its actual downstream consumer."""
from . import check,Result


@check("early_original_article_review")
def early_original_article_review(ctx):
    from ..earlyreview import verify
    problems=verify(ctx.project)
    return Result(not problems,"early_original_article_review","; ".join(problems[:4]) or
                  "Current independent scientific review supports proceeding to an Original article; it is not editorial acceptance or a replacement for manuscript reading")
