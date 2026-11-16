#!/usr/bin/env python3
"""Begin, accept or check an actual section-local medical editing pass."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from wfcore import sectionwriting as sw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("begin","accept","check"))
    parser.add_argument("--section",required=True)
    parser.add_argument("--source",action="append",default=[])
    parser.add_argument("--review-file",type=Path)
    parser.add_argument("--scientific-reset",action="store_true")
    parser.add_argument("--project",type=Path,default=Path(os.environ.get("MEDPAPER_PROJECT","project")))
    args=parser.parse_args();project=args.project.resolve()
    try:
        from wfcore.engineintegrity import verify_engine
        verify_engine(Path(__file__).resolve().parents[2])
        if args.command=="check":
            from wfcore.medicalstyle import diagnose
            rel=sw.section_path(args.section);path=project/rel
            prompts=diagnose(path.read_text(encoding="utf-8"),rel) if path.is_file() else []
            errors=sw.problems(project,[args.section])
            print(json.dumps({"ok":not errors,"errors":errors,"reading_prompts":prompts[:20],
                              "reading_prompt_total":len(prompts)},ensure_ascii=False))
            return 2 if errors else 0
        from wfcore.dependencies import guard_build
        from wfcore.revision import guard_outputs,permits
        from wfcore.state import State
        guard_build(project);rel=sw.section_path(args.section)
        state=State(project).load();owner=sw.SECTIONS[Path(rel).stem]
        # Assembly owns the source-section cohesion/read-back required by S17.
        # A frozen master still requires the normal scoped revision path.
        assembly_edit = (state.current == "S17_assemble" and
                         not (project/"07_manuscript/scientific_master_freeze.json").exists())
        if state.current!=owner and not assembly_edit and not permits(project,owner):
            raise ValueError("Use the active section stage or its actual scoped revision")
        guard_outputs(project,[project/rel])
        if args.command=="begin": result=sw.begin(project,args.section,args.source,scientific_reset=args.scientific_reset)
        else:
            if not args.review_file: raise ValueError("Read the section and provide its actual --review-file")
            result=sw.accept(project,args.section,json.loads(args.review_file.read_text(encoding="utf-8")))
        print(json.dumps(result,ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("section_writing: "+str(exc),file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
