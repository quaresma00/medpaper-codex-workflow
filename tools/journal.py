#!/usr/bin/env python3
"""Current-journal guide acquisition, rule binding and scoped transfer helpers."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from wfcore import journalcontext as jc, guides, guidelinerules as gr, journalportal, paths
from wfcore.readiness import load


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path)
    subs=parser.add_subparsers(dest="command",required=True)
    begin=subs.add_parser("begin",help="new confirmed target; preserve old attempt and accepted science")
    begin.add_argument("--target-file",required=True,type=Path)
    begin.add_argument("--revision-item",help="exact pending journal switch item if several are eligible")
    fetch=subs.add_parser("fetch",help="capture current official page/PDF; auto browser fallback when available")
    fetch.add_argument("--url",required=True);fetch.add_argument("--mode",choices=["auto","http","browser"],default="auto")
    register=subs.add_parser("register",help="register genuine official download/browser export, retaining its actual provenance")
    register.add_argument("--url",required=True);register.add_argument("--file",required=True,type=Path);register.add_argument("--why",required=True)
    register.add_argument("--retrieved-at",required=True,help="actual retrieval date, not today's registration date")
    register.add_argument("--source-kind",choices=["guide","portal"],default="guide")
    show=subs.add_parser("show",help="bounded current-source search; complete text remains in the saved file")
    show.add_argument("--source",required=True);show.add_argument("--find",default="");show.add_argument("--full",action="store_true")
    show.add_argument("--links",action="store_true",help="observed source links; bounded by default, --full lists all")
    csl=subs.add_parser("csl",help="fetch an exact chosen style id and resolve its independent parent")
    csl.add_argument("--id",required=True)
    template=subs.add_parser("template",help="register a genuine official DOCX reference template")
    template.add_argument("--file",required=True,type=Path);template.add_argument("--url",required=True)
    template.add_argument("--retrieved-at",required=True);template.add_argument("--why",required=True)
    handoff=subs.add_parser("browser-handoff",help="record an observed native-browser login/CAPTCHA; only actual guide capture resolves it")
    handoff.add_argument("--url",required=True);handoff.add_argument("--reason",choices=["captcha","login"],required=True)
    handoff.add_argument("--tab-ref",default="",help="actual tab reference only; no credentials/cookies")
    handoff.add_argument("--source-kind",choices=["guide","portal"],default="guide")
    conflict=subs.add_parser("portal-conflict",help="link two actual required clauses; then reconcile configuration and reseal")
    conflict.add_argument("--guide-rule",required=True);conflict.add_argument("--portal-rule",required=True)
    conflict.add_argument("--reason-file",required=True,type=Path)
    deliver=subs.add_parser("deliver",help="prepare a journal/date-named author working copy of current manifest uploads")
    deliver.add_argument("--mode",choices=["editable","read-only"],default="editable",help="filesystem mode of the author copy; frozen releases are separate")
    attach=subs.add_parser("attach-format",help="add one auxiliary format to the author copy without changing upload roles")
    attach.add_argument("--upload",required=True,help="exact project-relative linked upload path in the current manifest")
    attach.add_argument("--file",required=True,type=Path,help="actual alternate file, absolute or relative to the project root")
    inventory=subs.add_parser("delivery-files",help="discover current upload roles, author-copy paths and recorded sources")
    inventory.add_argument("--upload",help="limit to this exact manifest path and inspect its Office edit settings")
    subs.add_parser("seal",help="bind real guide clauses to the actual current configuration")
    subs.add_parser("status",help="bounded context/source status; never a scientific quality verdict")
    subs.add_parser("check",help="verify current guide/context/configuration, without rebuilding")
    review=subs.add_parser("review",help="record actual rendered final-file inspection for a manual rule")
    review.add_argument("--rule",required=True);review.add_argument("--file",action="append",required=True)
    review.add_argument("--render",required=True);review.add_argument("--observation-file",required=True,type=Path)
    args=parser.parse_args();project=args.project.resolve() if args.project else Path(os.environ.get("MEDPAPER_PROJECT") or paths.project_dir()).resolve()
    try:
        if args.command=="begin": result=jc.begin(project,json.loads(args.target_file.read_text(encoding="utf-8-sig")),revision_item=args.revision_item)
        elif args.command in {"fetch","register"}:
            result=guides.capture(project,args.url,file=getattr(args,"file",None),mode=getattr(args,"mode","auto"),why=getattr(args,"why",""),retrieved_at=getattr(args,"retrieved_at",None),source_kind=getattr(args,"source_kind","guide"))
        elif args.command=="csl": result=guides.fetch_csl(project,args.id)
        elif args.command=="template": result=guides.register_template(project,args.file,args.url,args.why,args.retrieved_at)
        elif args.command=="browser-handoff": result=guides.browser_handoff(project,args.url,args.reason,args.tab_ref,args.source_kind)
        elif args.command=="portal-conflict": result=journalportal.resolve(project,args.guide_rule,args.portal_rule,args.reason_file.read_text(encoding="utf-8-sig"))
        elif args.command=="deliver": result=journalportal.deliver(project,args.mode)
        elif args.command=="attach-format": result=journalportal.attach_format(project,args.upload,project/args.file)
        elif args.command=="delivery-files": result=journalportal.delivery_files(project,args.upload)
        elif args.command=="seal": result=jc.seal(project)["seal"]
        elif args.command=="review": result=gr.record_review(project,args.rule,args.file,args.render,args.observation_file.read_text(encoding="utf-8-sig"))
        elif args.command=="show":
            context=jc.current(project);source=context["sources"][args.source]
            if args.links:
                links=source.get("discovered_links",[])
                print(f"Observed links: {len(links)}; full inventory in {project/jc.CONTEXT}")
                print("\n".join(links if args.full else links[:15]));return 0
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
            result.update(sources=[{**{k:r.get(k) for k in ("id","url","mode","text","fetched_at","source_kind")},
                                    "link_count":len(r.get("discovered_links",[]))} for r in context["sources"].values()],
                          sealed=bool(context.get("seal")),browser_handoff=context.get("browser_handoff"),delivery=journalportal.delivery_status(project))
        else:
            failures=jc.problems(project)
            print("\n".join(failures) if failures else "Current journal, actual sources and executable configuration agree")
            return 2 if failures else 0
        if args.command=="deliver":
            result=_delivery_summary(result)
        elif args.command=="status" and isinstance(result.get("delivery"),dict):
            result["delivery"]=_delivery_summary(result["delivery"])
        elif args.command in {"fetch","register"} and "discovered_links" in result:
            result={**{k:v for k,v in result.items() if k!="discovered_links"},"link_count":len(result["discovered_links"])}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f"Journal context not ready: {exc}",file=sys.stderr);return 2


def _delivery_summary(row):
    return {**{key:value for key,value in row.items() if key not in {"files","auxiliary"}},
            "upload_files":len(row.get("files",{})),"auxiliary_files":len(row.get("auxiliary",{}))}


if __name__=="__main__": raise SystemExit(main())
