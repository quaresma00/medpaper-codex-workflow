#!/usr/bin/env python3
"""Prepare a display-free Discussion context, bind its short outline, or check a draft."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wfcore import discussion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "outline", "check"))
    parser.add_argument("--project", type=Path, default=Path(os.environ.get("MEDPAPER_PROJECT", "project")))
    parser.add_argument("--discussion-path", default=discussion.DISCUSSION)
    parser.add_argument("--results-path", default=discussion.RESULTS)
    parser.add_argument("--presentation-only", action="store_true")
    args = parser.parse_args(); project = args.project.resolve()
    try:
        from wfcore.engineintegrity import verify_engine
        verify_engine(Path(__file__).resolve().parents[2])
        if args.command in {"prepare", "outline"}:
            from wfcore.dependencies import guard_build
            from wfcore.state import State
            from wfcore.revision import permits
            guard_build(project)
            state = State(project).load()
            if state.current != "S16_discussion" and not permits(project, "S16_discussion"):
                raise ValueError("Prepare Discussion only at S16 or its explicitly scoped revision")
            value = discussion.prepare(project) if args.command == "prepare" else discussion.bind_outline(project)
            print(json.dumps(value, ensure_ascii=False)); return 0
        errors, warnings = discussion.check(project, discussion_path=args.discussion_path,
                                             results_path=args.results_path, presentation_only=args.presentation_only)
        print(json.dumps({"ok": not errors, "errors": errors, "reading_prompts": warnings}, ensure_ascii=False, indent=2))
        return 2 if errors else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("discussion: " + str(exc), file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
