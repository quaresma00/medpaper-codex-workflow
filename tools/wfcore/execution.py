"""Bounded task-owned processes with full local logs; never kill unrelated Office sessions."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .readiness import atomic_json


def run_logged(command, *, project, timeout=180, cwd=None, env=None, heartbeat=25, operation=None):
    if timeout<=0 or heartbeat<=0: raise ValueError("Positive task timeout and heartbeat required")
    env={**os.environ,**(env or {}),"PYTHONIOENCODING":"utf-8","PYTHONUTF8":"1"}
    project=Path(project).resolve();job=uuid.uuid4().hex
    log=project/".wf/processes"/(job+".log");log.parent.mkdir(parents=True,exist_ok=True)
    record=project/".wf/processes"/(job+".json")
    started=time.monotonic()
    started_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    context={}
    state_file=project/".wf/state.json"
    if state_file.is_file():
        try: context=json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError,ValueError): pass  # Observability never changes scientific state.
    process=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             text=True,encoding="utf-8",errors="replace",
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    metadata={"job":job,"pid":process.pid,"executable":Path(str(command[0])).name,
              "cwd":str(Path(cwd or os.getcwd()).resolve()),"timeout_seconds":timeout,"log":str(log),"status":"running",
              "operation":operation or "subprocess", "stage":context.get("current"),
              "revision_round":context.get("active_revision_round"), "started_at":started_at,
              "finished_at":None,"duration_seconds":None,"resource_usage":None}
    atomic_json(record,metadata)
    def finish(status):
        atomic_json(record,{**metadata,"status":status,"returncode":process.returncode,
                            "finished_at":datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                            "duration_seconds":round(time.monotonic()-started,6)})
    try:
        while True:
            remaining=timeout-(time.monotonic()-started)
            if remaining<=0: raise subprocess.TimeoutExpired(command,timeout)
            try:
                stdout,stderr=process.communicate(timeout=min(remaining,heartbeat,30))
                break
            except subprocess.TimeoutExpired:
                if time.monotonic()-started>=timeout: raise
                print(f"Task running: {metadata['executable']} pid={process.pid}; {int(time.monotonic()-started)}s elapsed; job={job}. Completion is pending.",file=sys.stderr,flush=True)
    except subprocess.TimeoutExpired:
        process.kill()  # Only the child created above; no taskkill by global process name.
        stdout,stderr=process.communicate();log.write_text(stdout+stderr,encoding="utf-8")
        finish("timeout")
        raise ValueError(f"Task process timed out; previous deliverable preserved; full log: {log}")
    except BaseException:
        if process.poll() is None: process.kill()  # Only our own immediate child.
        stdout,stderr=process.communicate(); log.write_text(stdout+stderr,encoding="utf-8")
        finish("interrupted")
        raise
    log.write_text(stdout+stderr,encoding="utf-8")
    finish("complete" if process.returncode==0 else "failed")
    result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
    result.log_path=log
    return result
