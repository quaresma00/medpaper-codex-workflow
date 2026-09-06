#!/usr/bin/env python3
"""Create, synchronize, or verify the full-acquisition evidence manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wfcore import dataproof  # noqa: E402
from wfcore.state import State  # noqa: E402


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _skeleton() -> dict:
    return {
        "schema_version": dataproof.SCHEMA_VERSION,
        "requested_scope": dataproof.FULL_SCOPE,
        "status": "incomplete",
        "protocol_population": "",
        "acquisition_method": "scripted",
        "pilot": {"used": False},
        "protocol_sampling": None,
        "sources": [{
            "id": "",
            "type": "api",
            "locator": "",
            "retrieved_at": "",
            "source_total_expected": 0,
            "records_requested": 0,
            "records_received": 0,
            "source_total_evidence": {
                "path": "02_data/raw/source_count.json",
                "kind": "json_pointer_integer",
                "pointer": "/total",
            },
            "received_count_evidence": [{
                "path": "02_data/raw/page_001.json",
                "kind": "json_pointer_length",
                "pointer": "/records",
            }],
            "complete": False,
            "truncation_applied": False,
            "pagination": {
                "applicable": True,
                "pages_expected": None,
                "pages_received": 0,
                "terminal_reached": False,
                "next_cursor_at_end": None,
            },
        }],
        "raw_files": [],
        "acquisition_files": [],
        "raw_bundle_sha256": "",
        "analysis_dataset": {
            "primary_source_id": "",
            "n_rows": 0,
            "excluded_after_acquisition": 0,
            "relationship": "one_record_per_analysis_row",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="manage the medpaper acquisition proof")
    parser.add_argument("command", choices=["init", "sync", "verify"])
    parser.add_argument("--project", type=Path, default=Path("project"))
    args = parser.parse_args()
    project = args.project.resolve()
    manifest_path = project / dataproof.MANIFEST_REL

    if args.command == "init":
        if manifest_path.exists():
            print(f"refusing to overwrite existing {manifest_path}", file=sys.stderr)
            return 2
        _write(manifest_path, _skeleton())
        print(f"created incomplete template -> {manifest_path}")
        print("fill protocol_population, sources, counts/evidence and analysis_dataset; then run sync")
        return 0

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cannot read {manifest_path}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(manifest, dict):
        print("acquisition manifest must be one JSON object", file=sys.stderr)
        return 2

    if args.command == "sync":
        raw = dataproof.inventory(project, "02_data/raw")
        code = dataproof.inventory(project, "02_data/acquisition")
        manifest["raw_files"] = raw
        manifest["acquisition_files"] = code
        manifest["raw_bundle_sha256"] = dataproof.bundle_sha256(raw)
        _write(manifest_path, manifest)
        print(f"synchronized {len(raw)} raw and {len(code)} acquisition file(s) -> {manifest_path}")
        print(f"copy this exact value to dataset_summary.json source_hash: {manifest['raw_bundle_sha256']}")
        return 0

    state = None
    state_path = project / ".wf/state.json"
    if state_path.exists():
        state = State(project, ".wf").load()
    outcome = dataproof.validate(project, state)
    if not outcome.ok:
        print("data acquisition proof failed:", file=sys.stderr)
        for problem in outcome.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    print(
        f"verified full acquisition: {outcome.sources} source(s), "
        f"{outcome.records_received} record(s), {outcome.raw_files} raw file(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
