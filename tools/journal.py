#!/usr/bin/env python3
"""Current-journal guide acquisition, rule binding and scoped transfer helpers."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from wfcore import journalcontext as jc, guides, guidelinerules as gr, paths
from wfcore.readiness import load


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path)
    subs=parser.add_subparsers(dest="command",required=True)
    begin=subs.add_parser("begin",help="new confirmed target; preserve old attempt and accepted science")
    begin.add_argument("--target-file",required=True,type=Path)
    fetch=subs.add_parser("fetch",help="capture current official page/PDF; auto browser fallback when available")
    fetch.add_argument("--url",required=True);fetch.add_argument("--mode",choices=["auto","http","browser"],default="auto")
    register=subs.add_parser("register",help="register genuine official download/browser export, retaining its actual provenance")
    register.add_argument("--url",required=True);register.add_argument("--file",required=True,type=Path);register.add_argument("--why",required=True)
    register.add_argument("--retrieved-at",required=True,help="actual retrieval date, not today's registration date")
    show=subs.add_parser("show",help="bounded current-source search; complete text remains in the saved file")
    show.add_argument("--source",required=True);show.add_argument("--find",default="");show.add_argument("--full",action="store_true")
    csl=subs.add_parser("csl",help="fetch an exact chosen style id and resolve its independent parent")
    csl.add_argument("--id",required=True)
    template=subs.add_parser("template",help="register a genuine official DOCX reference template")
    template.add_argument("--file",required=True,type=Path);template.add_argument("--url",required=True)
    template.add_argument("--retrieved-at",required=True);template.add_argument("--why",required=True)
    handoff=subs.add_parser("browser-handoff",help="record an observed native-browser login/CAPTCHA; only actual guide capture resolves it")
    handoff.add_argument("--url",required=True);handoff.add_argument("--reason",choices=["captcha","login"],required=True)
    handoff.add_argument("--tab-ref",default="",help="actual tab reference only; no credentials/cookies")
    subs.add_parser("seal",help="bind real guide clauses to the actual current configuration")
    subs.add_parser("status",help="bounded context/source status; never a scientific quality verdict")
    subs.add_parser("check",help="verify current guide/context/configuration, without rebuilding")
    review=subs.add_parser("review",help="record actual rendered final-file inspection for a manual rule")
    review.add_argument("--rule",required=True);review.add_argument("--file",action="append",required=True)
    review.add_argument("--render",required=True);review.add_argument("--observation-file",required=True,type=Path)
    args=parser.parse_args();project=args.project.resolve() if args.project else Path(os.environ.get("MEDPAPER_PROJECT") or paths.project_dir()).resolve()
    try:
        if args.command=="begin": result=jc.begin(project,json.loads(args.target_file.read_text(encoding="utf-8-sig")))
        elif args.command in {"fetch","register"}:
            result=guides.capture(project,args.url,file=getattr(args,"file",None),mode=getattr(args,"mode","auto"),why=getattr(args,"why",""),retrieved_at=getattr(args,"retrieved_at",None))
        elif args.command=="csl": result=guides.fetch_csl(project,args.id)
        elif args.command=="template": result=guides.register_template(project,args.file,args.url,args.why,args.retrieved_at)
        elif args.command=="browser-handoff": result=guides.browser_handoff(project,args.url,args.reason,args.tab_ref)
        elif args.command=="seal": result=jc.seal(project)["seal"]
        elif args.command=="review": result=gr.record_review(project,args.rule,args.file,args.render,args.observation_file.read_text(encoding="utf-8-sig"))
        elif args.command=="show":
            context=jc.current(project);source=context["sources"][args.source]
            text=(project/source["text"]).read_text(encoding="utf-8")
            lines=text.splitlines();matches=[(i+1,line) for i,line in enumerate(lines) if not args.find or args.find.casefold() in line.casefold()]
            if args.full: print(text)
            else:
                print(f"Full source: {project/source['text']}; matching lines: {len(matches)}")
                for number,line in matches[:12]: print(f"{number}: {line[:650]}")
            return 0
        elif args.command=="status":
            context=jc.current(project)
            result={k:context.get(k) for k in ("identity","context_id","attempt_id","previous_archive")}
            result.update(sources=[{k:r.get(k) for k in ("id","url","mode","text","fetched_at")} for r in context["sources"].values()],sealed=bool(context.get("seal")),browser_handoff=context.get("browser_handoff"))
        else:
            failures=jc.problems(project)
            print("\n".join(failures) if failures else "Current journal, actual sources and executable configuration agree")
            return 2 if failures else 0
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f"Journal context not ready: {exc}",file=sys.stderr);return 2


if __name__=="__main__": raise SystemExit(main())
