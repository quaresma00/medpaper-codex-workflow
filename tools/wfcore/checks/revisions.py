"""Gates for source-routed manuscript and submission-package revisions."""
from __future__ import annotations

from . import Ctx, Result, check
from ..packagecontent import verify_baseline


@check("package_content_matches_baseline")
def package_content_matches_baseline(ctx: Ctx) -> Result:
    ok, details, count = verify_baseline(ctx.project)
    if not ok:
        return Result(
            False,
            "package_content_matches_baseline",
            "; ".join(details[:8]),
            [
                "For content edits, run tools/rework.py and rebuild from the owning source stage.",
                "For format-only edits, restore the original visible text; recapture only at S23 after a legitimate rebuild.",
            ],
        )
    return Result(True, "package_content_matches_baseline",
                  details[0] if details else f"{count} DOCX visible-text baseline(s) match")
