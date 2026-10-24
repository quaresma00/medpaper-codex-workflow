"""Serialize a single figure's renderer and QC; never mistake an in-flight build for proof."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import uuid


class FigureBusy(ValueError):
    pass


def marker(project,figure_id):
    key=hashlib.sha256(str(figure_id).strip().casefold().encode("utf-8")).hexdigest()[:24]
    return Path(project)/".wf/figure_jobs"/(key+".lock")


@contextmanager
def job(project,figure_id,operation):
    path=marker(project,figure_id); path.parent.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex
    payload={"pid":os.getpid(),"token":token,"figure":str(figure_id),"operation":operation}
    try:
        with path.open("x",encoding="utf-8") as stream:
            json.dump(payload,stream); stream.flush()
    except FileExistsError as exc:
        raise FigureBusy(f"{figure_id}: figure job pending; owner metadata: {path}. Wait for that task's completion, then retry. A crash orphan needs explicit owner/process verification before removing this exact marker; never treat it as QC passed.") from exc
    try:
        yield
    finally:
        # Remove only our own marker, including on failed render/QC. Never kill a PID.
        if path.is_file() and json.loads(path.read_text(encoding="utf-8")).get("token")==token:
            path.unlink()
