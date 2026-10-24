"""Inspect/seal benchmark plans and bind completed executor findings to current files."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wfcore import benchmark
from wfcore.readiness import atomic_json
from wfcore.paths import project_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "seal", "metrics", "accept", "style"])
    parser.add_argument("--project", type=Path)
    parser.add_argument("--layer", choices=["science", "journal"], default="science")
    parser.add_argument("--review", type=Path, help="Executor-authored findings, not automatically generated PASS")
    parser.add_argument("--final", action="store_true", help="Bind actual final journal uploads, not only integration prose")
    parser.add_argument("--limit",type=int,default=12,help="style diagnostics to show; full reading remains mandatory")
    parser.add_argument("--offset",type=int,default=0)
    args = parser.parse_args(); project = (args.project or project_dir()).resolve()
    try:
        if args.command=="style":
            from wfcore.medicalstyle import scan
            if args.limit<1 or args.offset<0: raise ValueError("Use positive limit and nonnegative offset")
            issues=scan(project,args.layer,args.final)
            selected=issues[args.offset:args.offset+args.limit]
            print(json.dumps({"total":len(issues),"shown":len(selected),"offset":args.offset,"issues":selected,
                              "meaning":"Risk prompts, not a blacklist or semantic/visual PASS; inspect actual figures."},ensure_ascii=False))
        elif args.command == "seal": benchmark.seal(project, args.layer); print("Benchmark plan sealed before writing/production")
        elif args.command == "metrics": print(json.dumps(benchmark.citation_metrics(project)))
        elif args.command == "verify":
            problems = benchmark.verify_benchmark(project, args.layer)
            if problems: raise ValueError("; ".join(problems[:8]))
            print("Source-bound comparator evidence/plan current; counts remain advisory")
        else:
            from wfcore.revision import guard_outputs, permits
            from wfcore.state import State
            owner = "S17_assemble" if args.layer == "science" else "S23_package" if args.final else "S22_polish"
            state = State(project).load()
            if state.current != owner and not permits(project, owner): raise ValueError(f"Acceptance belongs to {owner}")
            if not args.review: raise ValueError("Supply actual executor review findings with --review")
            if args.final and args.layer != "journal": raise ValueError("--final is journal upload acceptance only")
            row = json.loads(args.review.read_text(encoding="utf-8"))
            row.update(inputs=benchmark.acceptance_inputs(project, args.layer, final=args.final,report=row), final_outputs=args.final)
            destination = project / benchmark.acceptance_rel(args.layer, args.final); guard_outputs(project, [destination])
            # Validate in memory; failure cannot overwrite a prior acceptance receipt.
            defects = benchmark.verify_acceptance(project, args.layer, final=args.final, report=row)
            if defects: raise ValueError("; ".join(defects[:8]))
            atomic_json(destination, row)
            print("Executor findings bound; independent/user review and visual QA remain separate")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("FAIL: " + str(exc)); return 2


if __name__ == "__main__": raise SystemExit(main())
