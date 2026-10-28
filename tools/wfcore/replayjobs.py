"""Task-owned replay sandboxes. Hard-killed processes are recovered only after liveness checks."""
from contextlib import contextmanager
import json,os,re,shutil,tempfile,uuid
from pathlib import Path
from .packagefreeze import _safe_path
from .readiness import atomic_json

DIRECTORY=".wf/replay_sandboxes"


def alive(pid):
    if type(pid) is not int or pid<=0: return True  # Unknown owner is never safe to delete.
    if os.name=="nt":
        import ctypes
        from ctypes import wintypes
        api=ctypes.WinDLL("kernel32",use_last_error=True)
        api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; api.OpenProcess.restype=wintypes.HANDLE
        api.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        api.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=api.OpenProcess(0x1000,False,pid)
        if not handle: return ctypes.get_last_error()!=87  # Access denied/unknown stays live.
        try:
            code=wintypes.DWORD()
            return not api.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value==259
        finally: api.CloseHandle(handle)
    try: os.kill(pid,0)
    except ProcessLookupError: return False
    except PermissionError: return True
    return True


def children_alive(project,sandbox):
    for path in (Path(project)/".wf/processes").glob("*.json"):
        row=json.loads(path.read_text(encoding="utf-8"))
        cwd=Path(row.get("cwd","/")).resolve()
        if cwd.is_relative_to(sandbox) and row.get("status")=="running" and alive(row.get("pid")): return True
    return False


def cleanup(project,apply=False):
    project=Path(project).resolve(); root=_safe_path(project,DIRECTORY)[1]
    if not root.exists(): return []
    rows=[]
    for path in sorted(root.glob("run_*")):
        if not path.is_dir() or path.is_symlink() or (hasattr(path,"is_junction") and path.is_junction()) or path.resolve().parent!=root: continue
        marker=path/"owner.json"
        if not marker.is_file(): continue
        try:
            owner=json.loads(marker.read_text(encoding="utf-8"))
            if owner.get("project")!=str(project) or owner.get("directory")!=path.name or not owner.get("token"): continue
            removable=not alive(owner.get("pid")) and not children_alive(project,path)
            row={"directory":path.name,"removable":removable,"removed":False}
            if apply and removable:
                shutil.rmtree(path); row["removed"]=True
            rows.append(row)
        except (OSError,ValueError,TypeError): continue  # Unknown/corrupt ownership is preserved.
    active=root/"active.json"
    if apply and active.is_file():
        record=json.loads(active.read_text(encoding="utf-8"))
        name=record.get("directory","")
        if isinstance(name,str) and re.fullmatch(r"run_[A-Za-z0-9_-]+",name) and not alive(record.get("pid")) and not any(r["directory"]==name and not r["removed"] for r in rows) and not (root/name).exists():
            active.unlink()
    return rows


@contextmanager
def sandbox(project):
    project=Path(project).resolve(); root=_safe_path(project,DIRECTORY)[1]; root.mkdir(parents=True,exist_ok=True)
    cleanup(project,apply=True)
    active=root/"active.json"; token=uuid.uuid4().hex
    try:
        with active.open("x",encoding="utf-8") as stream: json.dump({"pid":os.getpid(),"token":token},stream)
    except FileExistsError as exc: raise ValueError("This project's replay is running or ownership is unresolved; wait for completion or inspect replay cleanup, never kill unrelated processes") from exc
    directory=None
    try:
        directory=Path(tempfile.mkdtemp(prefix="run_",dir=root))
        owner={"project":str(project),"directory":directory.name,"pid":os.getpid(),"token":token}
        atomic_json(directory/"owner.json",owner); atomic_json(active,owner)
        yield directory
    finally:
        if directory is not None and directory.exists(): shutil.rmtree(directory)
        if active.is_file() and json.loads(active.read_text(encoding="utf-8")).get("token")==token: active.unlink()
