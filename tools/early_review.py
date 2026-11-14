#!/usr/bin/env python3
"""Prepare/attach/check the one S12 independent Original-article review."""
import argparse
import json
from pathlib import Path
from wfcore import earlyreview,paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("start","attach","check","status"))
    parser.add_argument("--project",type=Path)
    parser.add_argument("--executor-id",help="Actual current executor identity, not a fabricated reviewer")
    parser.add_argument("--report",type=Path,help="Complete actual independent reviewer Markdown reply")
    parser.add_argument("--reconsider",action="store_true",help="Explicitly obtain a corrected independent opinion on unchanged scientific inputs; never grants GO")
    parser.add_argument("--why",help="Concrete disputed interpretation/clarification for reconsideration, >=40 characters")
    args=parser.parse_args();project=(args.project or paths.project_dir()).resolve()
    if (args.reconsider or args.why) and args.command!="start":
        parser.error("--reconsider/--why are start-only controls; attachment still needs the actual independent report")
    try:
        from wfcore.engineintegrity import verify_engine
        verify_engine(Path(__file__).resolve().parents[1])
        if args.command=="start":
            record=earlyreview.start(project,args.executor_id,reconsider=args.reconsider,why=args.why)
            print(json.dumps({key:record.get(key) for key in ("id","report_destination","reviewed_artifacts","changed_since_previous","verdict","reconsideration")},ensure_ascii=False,indent=2))
        elif args.command=="attach":
            if not args.report: raise ValueError("Supply the actual independent report")
            record=earlyreview.attach(project,args.report)
            print(json.dumps({"review":record["id"],"verdict":record["verdict"],"report":record["report"]["path"],
                              "author_notice_required":record["verdict"]!="GO"},ensure_ascii=False))
        elif args.command=="status":
            record=earlyreview.load(project,earlyreview.RECORD)
            print(json.dumps({key:record.get(key) for key in ("id","verdict","marginal_analysis_value","report")},ensure_ascii=False))
        else:
            problems=earlyreview.verify(project)
            print(json.dumps({"ok":not problems,"problems":problems},ensure_ascii=False))
            return 2 if problems else 0
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc: print("Early review pending: "+str(exc));return 2


if __name__=="__main__": raise SystemExit(main())
