"""Explicit project-local references to authorized data, with no copies or writable aliases."""
import json,os
from pathlib import Path,PurePosixPath
import re
from .packagefreeze import _safe_path,_sha256
from .readiness import atomic_json

REGISTRY=".wf/data_sources.json"
PREFIX="data:"
NAME=re.compile(r"[a-z][a-z0-9_-]{0,40}")


def load(project):
    path=Path(project)/REGISTRY
    if not path.is_file(): return {}
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("schema_version")!=1 or not isinstance(data.get("sources"),dict): raise ValueError("Invalid data-source registry; never silently ignore damaged declarations")
    for name,row in data["sources"].items():
        if not NAME.fullmatch(name) or not isinstance(row,dict) or row.get("kind") not in {"file","directory"} or row.get("read_only") is not True or not Path(row.get("path","")).is_absolute():
            raise ValueError("Malformed authorized data-source record")
    return data["sources"]


def register(project,name,path,why):
    project=Path(project).resolve(); path=Path(path).expanduser()
    if not NAME.fullmatch(name) or not path.is_absolute() or not path.exists() or len(why.strip())<12:
        raise ValueError("Give a stable lowercase source name, exact existing absolute data path and actual authorization/scope")
    path=path.resolve()
    if project==path or project.is_relative_to(path): raise ValueError("A data root must not contain the project/workspace")
    from .paths import repo_root
    if path.is_relative_to(repo_root()) and not path.is_relative_to(project): raise ValueError("Engine files are not a research data source")
    for parent in (path,*path.parents):
        if (parent/".wf/state.json").is_file() and parent!=project:
            raise ValueError("Another study is outside this project's authorized data scope; no sibling-project reuse")
    sources=load(project)
    row={"path":str(path),"kind":"file" if path.is_file() else "directory","read_only":True,"authorization":why}
    if name in sources and sources[name]!=row: raise ValueError("Source name already exists with different scope; choose a new name instead of silently redirecting it")
    sources[name]=row
    atomic_json(project/REGISTRY,{"schema_version":1,"sources":sources})
    return PREFIX+name


def resolve(project,reference):
    if not isinstance(reference,str) or not reference.startswith(PREFIX): raise ValueError("Expected an explicit data:<source>/<relative-file> reference")
    name,sep,relative=reference[len(PREFIX):].partition("/")
    if not NAME.fullmatch(name): raise ValueError("Invalid data source name")
    sources=load(project)
    if name not in sources: raise ValueError("Data source is not authorized in this project")
    row=sources[name]
    if row.get("read_only") is not True or row.get("kind") not in {"file","directory"}: raise ValueError("Data reference must be read-only")
    root=Path(row["path"]).resolve()
    if not root.exists(): raise ValueError("Registered data source is unavailable")
    if row["kind"]=="file":
        if sep or not root.is_file(): raise ValueError("A registered file is referenced by data:<name>, without a child path")
        return root
    part=PurePosixPath(relative)
    if not sep or not relative or "\\" in relative or part.is_absolute() or ".." in part.parts or ":" in relative:
        raise ValueError("Data child must stay inside its registered directory")
    path=(root/part).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise ValueError("Data child escapes its authorized root or is missing")
    for parent in (path.parent,*path.parent.parents):
        if parent==root: break
        if (parent/".wf/state.json").is_file(): raise ValueError("Nested study data are not authorized by a parent data root")
    return path


def input_path(project,reference):
    return resolve(project,reference) if reference.startswith(PREFIX) else _safe_path(Path(project),reference)[1]


def open_readonly(project,reference,mode="rb",**kwargs):
    if mode not in {"r","rb"}: raise ValueError("Registered data handles are read-only; never write through a shared source")
    return resolve(project,reference).open(mode,**kwargs)


def files(project):
    for name,row in sorted(load(project).items()):
        root=Path(row["path"])
        if row["kind"]=="file": references=[PREFIX+name]
        else:
            # This is the explicitly authorized data root, never a workspace-wide search.
            references=[]
            for directory,dirs,files in os.walk(root,followlinks=False):
                base=Path(directory)
                if (base/".wf/state.json").is_file(): raise ValueError("A registered data tree contains a study; narrow the authorized data root instead of reading it")
                dirs[:]=[d for d in dirs if not (base/d).is_symlink() and not (hasattr(base/d,"is_junction") and (base/d).is_junction())]
                references.extend(PREFIX+name+"/"+(base/f).relative_to(root).as_posix() for f in sorted(files) if f!=".gitkeep")
        for reference in references:
            path=resolve(project,reference)
            yield reference,path


def inventory(project):
    return [{"path":reference,"sha256":_sha256(path),"bytes":path.stat().st_size} for reference,path in files(project)]
