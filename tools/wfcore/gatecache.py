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
                                "08_submission/integration/claim_bindings.json", "00_input/author_info.json"),
    "manuscript_structure": ("01_protocol/artifact_plan.json", "07_manuscript/title.md",
                             "07_manuscript/full_manuscript.md", "08_submission/target_journal.json"),
    "docx_bundle_ready": ("08_submission/bundle/**/*", "08_submission/docx_style.json",
                          "08_submission/target_journal.json", "08_submission/submission_requirements.json",
                          "08_submission/integration/supplementary_methods.md", "01_protocol/artifact_plan.json",
                          "00_input/author_info.json"),
}
TTL_SECONDS = 120


def descriptor(stage, spec):
    """Stable check slot; the associated identity separately binds all current inputs."""
    return hashlib.sha256(json.dumps([stage.id, spec], sort_keys=True).encode()).hexdigest()


def _usable(row):
    from .checks import Result
    try:
        if not isinstance(row, dict) or not 0 <= time.time() - row.get("at", 0) < TTL_SECONDS:
            return None
        result = Result(**row["result"])
        return result if result.ok else None
    except (KeyError, TypeError, ValueError):
        return None


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
        if spec.get("check") not in INPUTS or spec.get("live", False):
            return None
        patterns = list(INPUTS[spec["check"]])
        # All path overrides are included, not only their default locations.
        patterns.extend(v for k, v in spec.items() if isinstance(v, str) and
                        (k == "path" or k.endswith("_path") or k in {"manifest", "style"}))
        if spec["check"]=="numbers_have_provenance":
            patterns.append("01_protocol/artifact_plan.json")
            for location in ("07_manuscript/claim_bindings.json","08_submission/integration/claim_bindings.json"):
                path=self.project/location
                if path.is_file():
                    patterns.extend(row["source_path"] for row in json.loads(path.read_text(encoding="utf-8")).get("claims",[]) if row.get("kind")=="unit_scale" and row.get("source_path"))
            allowlist = self.project / "03_analysis/results/number_allowlist.tsv"
            if allowlist.is_file():
                for line in allowlist.read_text(encoding="utf-8").splitlines():
                    columns = line.strip().split("\t")
                    if len(columns) == 4 and columns[1] == "constant" and len(columns[3].strip()) >= 20:
                        # Match the real gate's accepted project-local constant sources.
                        try:
                            rel, _ = _safe_path(self.project, columns[2])
                        except ValueError:
                            continue
                        patterns.append(rel)
        if spec["check"] == "docx_bundle_ready":
            manifest = self.project / "08_submission/bundle/manifest.json"
            if manifest.is_file():
                patterns.extend(row["file"] for row in json.loads(manifest.read_text(encoding="utf-8")).get("items", []))
        if spec["check"] == "executor_acceptance":
            for report in self.project.glob(".wf/executor_acceptance_*.json"):
                patterns.extend(json.loads(report.read_text(encoding="utf-8")).get("inputs", {}))
        # Ctx redirects these scientific defaults to the current journal's derived layer.
        # Keep the default path too, so removal of the override also invalidates the check.
        from .checks import Ctx
        context = Ctx(self.pipeline, self.state, self.project, stage, spec)
        patterns.extend(context.p(pattern).relative_to(self.project).as_posix()
                        for pattern in list(patterns) if context.p(pattern) != self.project / pattern)
        files = {}
        for pattern in sorted(set(patterns)):
            _safe_path(self.project, pattern)  # Reject traversal before globbing.
            found = [p for p in self.project.glob(pattern) if p.is_file() and not (
                p.name.startswith("~$") and p.suffix.lower() in {".xlsx",".docx",".pptx"})]
            files[pattern] = {p.relative_to(self.project).as_posix(): _sha256(p) for p in sorted(found)}
        payload = {"stage": stage.id, "spec": spec, "files": files, "engine": self.engine,
                   "targets": self.pipeline.targets, "config": self.state.config(),
                   "pipeline_version": self.state.data.get("pipeline_version"),
                   "engine_pin": self.state.data.get("engine_pin"),
                   "decisions": self.state.data.get("decisions", {})}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def get(self, identity):
        row = self.new.get(identity, self.old.get(identity, {})) if identity else {}
        result = _usable(row)
        if result is None:
            return None
        self.new[identity] = row  # Do not extend the freshness window on a cache hit.
        self.reused += 1
        return result

    def put(self, identity, result):
        if identity and result.ok:
            self.new[identity] = {"at": time.time(), "result": asdict(result)}

    def save(self):
        # A local check must not evict valid evidence for unrelated unchanged artifacts.
        # Identity is still recomputed before reuse; retain original timestamps, not TTLs.
        retained = {key: row for key, row in {**self.old, **self.new}.items() if _usable(row) is not None}
        atomic_json(self.path, retained)
