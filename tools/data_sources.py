"""Register only the exact data root the user authorized; never copies or changes raw data."""
import argparse,json
from pathlib import Path
from wfcore import datasources,paths
from wfcore.argtext import add


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["add","show","resolve"])
    parser.add_argument("--project",type=Path,default=paths.project_dir())
    parser.add_argument("--name"); parser.add_argument("--path",type=Path); parser.add_argument("--reference")
    add(parser,"--why")
    args=parser.parse_args()
    try:
        if args.command=="add":
            if not args.name or not args.path or not args.why: raise ValueError("add requires --name, --path and actual --why/--why-file")
            print(datasources.register(args.project,args.name,args.path,args.why))
        elif args.command=="resolve": print(datasources.resolve(args.project,args.reference))
        else: print(json.dumps(datasources.load(args.project),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("Data source refused: "+str(exc)); return 2


if __name__=="__main__": raise SystemExit(main())
