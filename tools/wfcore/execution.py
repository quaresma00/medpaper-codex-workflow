"""Bounded task-owned processes with full local logs; never kill unrelated Office sessions."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .readiness import atomic_json


def run_logged(command, *, project, timeout=180, cwd=None, env=None, heartbeat=25):
    if timeout<=0 or heartbeat<=0: raise ValueError("Positive task timeout and heartbeat required")
    env={**os.environ,**(env or {}),"PYTHONIOENCODING":"utf-8","PYTHONUTF8":"1"}
    project=Path(project).resolve();job=uuid.uuid4().hex
    log=project/".wf/processes"/(job+".log");log.parent.mkdir(parents=True,exist_ok=True)
    record=project/".wf/processes"/(job+".json")
    process=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             text=True,encoding="utf-8",errors="replace",
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    metadata={"job":job,"pid":process.pid,"executable":Path(str(command[0])).name,
              "cwd":str(Path(cwd or os.getcwd()).resolve()),"timeout_seconds":timeout,"log":str(log),"status":"running"}
    atomic_json(record,metadata)
    started=time.monotonic()
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
        atomic_json(record,{**metadata,"status":"timeout","returncode":process.returncode})
        raise ValueError(f"Task process timed out; previous deliverable preserved; full log: {log}")
    except BaseException:
        if process.poll() is None: process.kill()  # Only our own immediate child.
        stdout,stderr=process.communicate(); log.write_text(stdout+stderr,encoding="utf-8")
        atomic_json(record,{**metadata,"status":"interrupted","returncode":process.returncode})
        raise
    log.write_text(stdout+stderr,encoding="utf-8")
    atomic_json(record,{**metadata,"status":"complete" if process.returncode==0 else "failed","returncode":process.returncode})
    result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
    result.log_path=log
    return result
