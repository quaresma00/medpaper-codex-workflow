"""Bounded task-owned processes with full local logs; never kill unrelated Office sessions."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from .readiness import atomic_json


def run_logged(command, *, project, timeout=180, cwd=None, env=None):
    project=Path(project).resolve();job=uuid.uuid4().hex
    log=project/".wf/processes"/(job+".log");log.parent.mkdir(parents=True,exist_ok=True)
    record=project/".wf/processes"/(job+".json")
    process=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             text=True,encoding="utf-8",errors="replace",
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    metadata={"job":job,"pid":process.pid,"executable":Path(str(command[0])).name,
              "cwd":str(Path(cwd or os.getcwd()).resolve()),"timeout_seconds":timeout,"log":str(log),"status":"running"}
    atomic_json(record,metadata)
    try:
        stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()  # Only the child created above; no taskkill by global process name.
        stdout,stderr=process.communicate();log.write_text(stdout+stderr,encoding="utf-8")
        atomic_json(record,{**metadata,"status":"timeout","returncode":process.returncode})
        raise ValueError(f"Task process timed out; previous deliverable preserved; full log: {log}")
    log.write_text(stdout+stderr,encoding="utf-8")
    atomic_json(record,{**metadata,"status":"complete" if process.returncode==0 else "failed","returncode":process.returncode})
    result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
    result.log_path=log
    return result
