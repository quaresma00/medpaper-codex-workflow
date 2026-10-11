#!/usr/bin/env python3
"""Freeze or verify the analysis contract and clinical story before writing."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wfcore.readiness import freeze_writing, verify_writing, verify_displays, reader_inputs


def _preview(value):
    if isinstance(value,str):
        return value if len(value)<=300 else {"preview":value[:300],"characters":len(value)}
    if isinstance(value,list):
        return [_preview(x) for x in value] if len(value)<=8 else {"preview":[_preview(x) for x in value[:8]],"items":len(value)}
    if isinstance(value,dict):
        keys=list(value);shown={k:_preview(value[k]) for k in keys[:12]}
        if len(keys)>12:shown["_display_omitted_fields"]=len(keys)-12
        return shown
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "verify", "displays", "review-inputs", "facts"])
    parser.add_argument("--project", type=Path, default=Path("project"))
    parser.add_argument("--fact-id",action="append",default=[])
    parser.add_argument("--fields",nargs="+",help="specific fact fields to display")
    parser.add_argument("--limit",type=int,default=20)
    parser.add_argument("--offset",type=int,default=0)
    parser.add_argument("--full",action="store_true",help="print complete facts only when explicitly needed")
    parser.add_argument("--output",type=Path,help="full resolved catalog output (default project/temp/resolved_facts.json)")
    args = parser.parse_args()
    try:
        if args.command == "facts":
            from wfcore.claims import facts
            from wfcore.readiness import atomic_json
            catalog = facts(args.project)
            output = args.output or args.project/".wf/resolved_facts.json"
            atomic_json(output,catalog)
            if args.limit < 1 or args.offset < 0:
                raise ValueError("facts pagination needs a positive limit and nonnegative offset")
            selected = args.fact_id or list(catalog)
            if any(key not in catalog for key in selected):
                raise ValueError("Unknown fact id requested")
            shown = selected if args.full else selected[args.offset:args.offset+args.limit]
            data = {k:({field:catalog[k][field] for field in args.fields} if args.fields else catalog[k]) for k in shown}
            print(json.dumps({"total":len(catalog),"shown":len(data),"complete_file":str(output),
                              "display_only_preview":not args.full,"facts":data if args.full else {k:_preview(v) for k,v in data.items()}},indent=2,ensure_ascii=False))
            return 0
        if args.command == "review-inputs":
            print(json.dumps({"reviewed_artifacts": reader_inputs(args.project)}, indent=2, ensure_ascii=False))
            return 0
        if args.command == "freeze":
            freeze_writing(args.project)
        problems = (verify_displays(args.project) if args.command == "displays"
                    else verify_writing(args.project))
        print("\n".join(problems) if problems else "readiness: PASS")
        return 2 if problems else 0
    except (OSError, ValueError,KeyError) as exc:
        print(f"readiness: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
