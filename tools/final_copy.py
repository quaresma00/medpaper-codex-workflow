#!/usr/bin/env python3
"""Prepare, record, check and finish an explicitly requested author final-copy handoff."""
import argparse
import copy
from pathlib import Path
from wfcore import paths, registry, finalcopy, gates
from wfcore.state import State


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "record", "check", "finish"])
    parser.add_argument("--project", type=Path); parser.add_argument("--edit", action="append", default=[])
    parser.add_argument("--words", default="")
    args = parser.parse_args(); project = (args.project or paths.project_dir()).resolve()
    try:
        state = State(project).load()
        if state.current != "S25_submission_audit" or state.data.get("active_revision_round"): raise ValueError("finish source revisions and reach S25 first")
        if args.command == "prepare": print(f"prepared {finalcopy.prepare(project)} uploads; existing author edits preserved")
        elif args.command == "record": finalcopy.record(project, args.edit, args.words); print("actual author authorization/manual edits recorded")
        elif args.command == "check":
            problems = finalcopy.check(project)
            print("\n".join(problems) if problems else "author-copy deterministic content/format checks: PASS; inspect actual rendered final pages")
            return 2 if problems else 0
        else:
            problems = finalcopy.verified(project)
            if problems: raise ValueError("; ".join(problems))
            original_state = copy.deepcopy(state.data)
            try:
                state.record_decision("submission_package_independent_audit", "PASS_AUTHOR_FINAL_COPY", "Author-controlled final-copy handoff after original independent PASS; no claim that a reviewer saw the edited copy")
                pipeline = registry.load(); results = gates.run_stage(pipeline, state, project, pipeline.stage(state.current))
                if any(result.blocking for result in results): raise ValueError("; ".join(result.detail for result in results if result.blocking))
            except Exception:
                state.data = original_state
                state.save()
                raise
            state.data["terminal_mode"] = "AUTHOR_FINAL_COPY_HANDOFF_NOT_SUBMITTED"
            state.complete(state.current, None)
            print("AUTHOR_FINAL_COPY handoff complete. Original freeze/audit preserved. This is not journal submission or a new independent verdict.")
        return 0
    except (OSError, ValueError, KeyError) as exc: print(f"author copy refused: {exc}"); return 2


if __name__ == "__main__": raise SystemExit(main())
