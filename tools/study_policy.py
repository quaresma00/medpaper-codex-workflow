"""Assess available study facts; print only the specific unresolved questions."""
import argparse
import json
from pathlib import Path
from wfcore import paths, studypolicy
from wfcore.revision import guard_outputs

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--project",type=Path)
    parser.add_argument("--apply",action="store_true",help="S21 only: fill missing supported declaration fields, never overwrite author facts")
    args=parser.parse_args(); project=(args.project or paths.project_dir()).resolve()
    try:
        guard_outputs(project,[project/studypolicy.REPORT]); result=studypolicy.save(project)
        if args.apply:
            from wfcore.state import State
            from wfcore.readiness import atomic_json
            if State(project).load().current!="S21_authors": raise ValueError("Declaration merge belongs to S21")
            derived=studypolicy.declarations(project); path=project/"00_input/author_info.json"
            facts=json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            conflicts=[key for key,value in derived.items() if facts.get(key) and facts[key]!=value]
            if conflicts: raise ValueError("Reconcile existing author declarations without overwriting: "+", ".join(conflicts))
            guard_outputs(project,[path]); atomic_json(path,{**facts,**derived})
        print(json.dumps({"assessment":studypolicy.REPORT,"specific_unresolved":result["unresolved"]},ensure_ascii=False))
        return 2 if result["unresolved"] else 0
    except (OSError,ValueError,KeyError) as exc: print(str(exc)); return 2
if __name__=="__main__": raise SystemExit(main())
