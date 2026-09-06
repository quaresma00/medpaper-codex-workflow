"""Data-acquisition completeness and anti-truncation gate."""
from __future__ import annotations

from .. import dataproof
from . import Ctx, Result, check


@check("data_acquisition_complete")
def data_acquisition_complete(ctx: Ctx) -> Result:
    outcome = dataproof.validate(ctx.project, ctx.state)
    if not outcome.ok:
        return Result(
            False,
            "data_acquisition_complete",
            "; ".join(outcome.problems[:8]),
            [
                "Run tools/data_manifest.py sync after acquiring every page/file, then re-run this gate.",
                "Do not use LIMIT, head(), sample(), a fixed page count, or a first-N slice to save time or compute.",
                "If the external source truly blocks full access, ask the user before recording partial_data_authorized=YES.",
            ],
        )
    return Result(
        True,
        "data_acquisition_complete",
        f"{outcome.sources} source(s), {outcome.records_received} received record(s), "
        f"{outcome.raw_files} hashed raw file(s); total-count and terminal-page evidence verified",
    )
