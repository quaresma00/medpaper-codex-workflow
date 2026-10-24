"""Short-lived reuse of pure checks with explicit content-hashed dependencies.

Unknown, live-source, acquisition, approval and freeze checks always execute.
This is an execution optimization, not a trust boundary against a hostile local user.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict

from . import paths
from .packagefreeze import _sha256, _safe_path
from .readiness import atomic_json

INPUTS = {
    "medical_benchmark": ("01_protocol/artifact_benchmark.md", "01_protocol/artifact_plan.json",
                          "08_submission/integration/journal_benchmark.md", "08_submission/integration/artifact_plan.json",
                          "08_submission/target_journal.json", "08_submission/submission_requirements.json",
                          ".wf/benchmark_*_lock.json", "06_refs/library.json", "06_refs/verified.json",
                          "06_refs/fulltext/*", "06_refs/cache/*.xml"),
    "literature_coverage": ("01_protocol/artifact_benchmark.md", "06_refs/library.json", "07_manuscript/*.md"),
    "executor_acceptance": (".wf/executor_acceptance_*.json", ".wf/benchmark_*_lock.json",
                            "01_protocol/artifact_benchmark.md", "01_protocol/artifact_plan.json",
                            "01_protocol/study_facts.json", "07_manuscript/*.md", "07_manuscript/claim_bindings.json",
                            "04_tables/**/*.xlsx", "04_tables/table_captions.md", "05_figures/out/*", "05_figures/legends.md",
                            "06_refs/library.json", "06_refs/refs.bib", "06_refs/fulltext/*",
                            "08_submission/target_journal.json", "08_submission/submission_requirements.json",
                            "08_submission/integration/**/*", "08_submission/bundle/**/*"),
    "md_sections": (), "md_wordcount": (), "no_ai_boilerplate": (),
    "supplementary_methods_clean": ("07_manuscript/supplementary_methods.md",),
    "numbers_have_provenance": ("06_refs/library.json", "06_refs/verified.json", "06_refs/fulltext/*", "06_refs/cache/*.xml", "01_protocol/protocol*.md", "03_analysis/results/*", "04_tables/**/*.xlsx",
                                "01_protocol/study_facts.json", "07_manuscript/claim_bindings.json",
                                "08_submission/integration/claim_bindings.json"),
    "manuscript_structure": ("01_protocol/artifact_plan.json", "07_manuscript/title.md",
                             "07_manuscript/full_manuscript.md"),
    "docx_bundle_ready": ("08_submission/bundle/**/*", "08_submission/docx_style.json",
                          "08_submission/target_journal.json", "08_submission/submission_requirements.json",
                          "08_submission/integration/supplementary_methods.md", "01_protocol/artifact_plan.json"),
}
TTL_SECONDS = 120


class Receipts:
    def __init__(self, project, pipeline, state):
        self.project, self.pipeline, self.state = project, pipeline, state
        self.path = state.dir / "check_receipts.json"
        try:
            self.old = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.old, dict):
                self.old = {}
        except (OSError, ValueError):
            self.old = {}
        self.new = {}
        self.reused = 0
        # Once per invocation; changes to any implementation invalidate old receipts.
        self.engine = {p.relative_to(paths.repo_root()).as_posix(): _sha256(p)
                       for folder in ("tools", "pipeline", "reference")
                       for p in (paths.repo_root() / folder).rglob("*")
                       if p.is_file() and p.suffix.lower() in {".py", ".r", ".toml", ".md"}}

    def identity(self, stage, spec):
        if spec.get("check") not in INPUTS:
            return None
        patterns = list(INPUTS[spec["check"]])
        # All path overrides are included, not only their default locations.
        patterns.extend(v for k, v in spec.items() if isinstance(v, str) and
                        (k == "path" or k.endswith("_path") or k in {"manifest", "style"}))
        if spec["check"] == "docx_bundle_ready":
            manifest = self.project / "08_submission/bundle/manifest.json"
            if manifest.is_file():
                patterns.extend(row["file"] for row in json.loads(manifest.read_text(encoding="utf-8")).get("items", []))
        if spec["check"] == "executor_acceptance":
            for report in self.project.glob(".wf/executor_acceptance_*.json"):
                patterns.extend(json.loads(report.read_text(encoding="utf-8")).get("inputs", {}))
        files = {}
        for pattern in patterns:
            _safe_path(self.project, pattern)  # Reject traversal before globbing.
            found = [p for p in self.project.glob(pattern) if p.is_file()]
            files[pattern] = {p.relative_to(self.project).as_posix(): _sha256(p) for p in sorted(found)}
        payload = {"stage": stage.id, "spec": spec, "files": files, "engine": self.engine,
                   "targets": self.pipeline.targets, "config": self.state.config(),
                   "decisions": self.state.data.get("decisions", {})}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def get(self, identity):
        from .checks import Result
        row = self.old.get(identity, {}) if identity else {}
        try:
            if not 0 <= time.time() - row.get("at", 0) < TTL_SECONDS:
                return None
            result = Result(**row["result"])
            if not result.ok:
                return None
        except (KeyError, TypeError, ValueError):
            return None
        self.new[identity] = row  # Do not extend the freshness window on a cache hit.
        self.reused += 1
        return result

    def put(self, identity, result):
        if identity and result.ok:
            self.new[identity] = {"at": time.time(), "result": asdict(result)}

    def save(self):
        atomic_json(self.path, self.new)
