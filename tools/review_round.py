#!/usr/bin/env python3
"""Manage S18/S19 manuscript and S24 package subagent review rounds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wfcore import paths
from wfcore import reviewrounds as rounds
from wfcore.state import State


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "prepare-revalidation", "ingest", "attach", "close", "decide", "status", "reader-copies", "restart", "export"])
    parser.add_argument("--project", type=Path)
    parser.add_argument("--scope", choices=list(rounds.SCOPES), required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--delta",action="store_true",default=None)
    mode.add_argument("--full",action="store_true",help="explicit full reread; later rounds otherwise use actual delta")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--from-file", type=Path, help="actual saved reviewer Markdown reply; never a host state dump")
    parser.add_argument("--revalidation", action="store_true", help="attach actual post-scientific-fix independent revalidation; retains original report")
    parser.add_argument("--change", nargs=2, action="append", default=[])
    parser.add_argument("--kept", nargs=2, action="append", default=[])
    parser.add_argument("--unresolved", type=int, default=0)
    parser.add_argument("--answer", choices=["another_round", "no_further_review"])
    from wfcore.argtext import add
    add(parser,"--words")
    add(parser,"--why")
    parser.add_argument("--author-decisions",type=Path)
    parser.add_argument("--resolutions",type=Path,help="complete finding-ID disposition map for the existing review report")
    args = parser.parse_args()
    project = (args.project or paths.project_dir()).resolve()
    try:
        state = State(project).load()
        allowed = {"S18_independent_review", "S19_human_review"} if args.scope == "manuscript" else {"S24_package_human_review"}
        if args.command not in {"status", "reader-copies"} and state.current not in allowed:
            raise ValueError("review control must run at its own review checkpoint")
        if args.scope == "manuscript" and args.command in {"close", "decide"} and state.current != "S19_human_review":
            raise ValueError("S18 only obtains the independent report; corrections/closure/user decision belong to S19")
        if args.command == "start":
            record = rounds.start(project, args.scope, delta=False if args.full else args.delta)
            copies = {}  # independent reviewers read originals; extra reading copies are opt-in
            record["reader_copies"] = copies
            rounds.save(project, record)
            print(json.dumps({"round": record["id"], "mode": record["mode"], "reader_copies": copies,
                              "report_destination":record.get("report_destination"),
                              "reviewed_artifacts": record["reviewed_artifacts"],
                              "deleted_since_previous": record["deleted_since_previous"]}, ensure_ascii=False, indent=2))
        elif args.command == "restart":
            record = rounds.restart(project, args.scope, args.why or "")
            record["reader_copies"] = {}
            rounds.save(project, record)
            print(json.dumps({"round": record["id"], "reviewed_artifacts": record["reviewed_artifacts"]}, indent=2))
        elif args.command == "prepare-revalidation":
            record = rounds.prepare_revalidation(project, args.scope)
            print(json.dumps({"round": record["id"], "reviewed_artifacts": record["revalidation_request"]["inputs"],
                              "report_destination": record["report_destination"]}, ensure_ascii=False, indent=2))
        elif args.command in {"attach", "ingest"}:
            if args.command == "ingest":
                if not args.from_file:
                    raise ValueError("--from-file must name the actual saved reviewer reply")
                from wfcore.reviewguard import extract
                from wfcore.packagefreeze import _safe_path
                record = rounds.latest(project, args.scope)
                if not record or record.get("closed_at"):
                    raise ValueError("An open review round is required")
                body = extract(args.from_file.read_text(encoding="utf-8"))
                args.report = _safe_path(project, record["report_destination"])[1]
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(body, encoding="utf-8")
            if not args.report:
                raise ValueError("--report must name the actual independent review")
            record = rounds.attach(project, args.scope, args.report, revalidation=args.revalidation)
        elif args.command == "close":
            decisions=json.loads(args.author_decisions.read_text(encoding="utf-8")) if args.author_decisions else None
            resolutions=json.loads(args.resolutions.read_text(encoding="utf-8")) if args.resolutions else None
            record = rounds.close(project, args.scope, args.change, args.kept, args.unresolved,decisions,resolutions)
        elif args.command == "decide":
            if not args.answer or not args.words:
                raise ValueError("--answer and --words are required")
            record = rounds.decide(project, args.scope, args.answer, args.words)
        elif args.command == "reader-copies":
            if not args.why or len(args.why.strip())<8: raise ValueError("Extra reader copies require the actual explicit request in --why; they are not default deliverables")
            print(json.dumps(rounds.reader_copies(project, rounds.inputs(project, args.scope),
                                                  f".wf/review_copies/{args.scope}"), ensure_ascii=False, indent=2))
            return 0
        elif args.command == "export":
            if not args.words or len(args.words.strip())<8: raise ValueError("Preserve the user's explicit request for an external reviewer copy in --words")
            from wfcore.reviewexport import export
            print(export(project,args.scope,args.words)); return 0
        else:
            record = rounds.latest(project, args.scope)
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0
        print(f"review round {record['id']}: {args.command}; no review ZIP generated")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"review round refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
