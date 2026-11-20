"""Generic isolated fixtures for revision preflight and Windows junction pruning."""
from __future__ import annotations

from contextlib import redirect_stderr
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from wfcore import evidence, revision, revisionservice
from wfcore.state import State


class PreflightPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="medpaper-preflight-")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.project = self.root / "project"
        self.state = State(self.project).create("medpaper", "1.29.15", "S24_package_human_review")

    def put(self, rel, content="Synthetic fixture"):
        target = self.project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def record(self, **changes):
        return {
            "round_id": "R001", "review_stage": self.state.current,
            "status": "active", "schema_version": 2, "baseline": revision.snapshot(self.project),
            "items": [], "allowed_files": [], "validation_stages": [], **changes,
        }

    def test_prunes_already_excluded_trees_before_enumeration_and_keeps_sources(self):
        excluded = (
            "temp/staging", ".wf/revisions/history", "08_submission/releases/archive",
            "07_manuscript/review_packages/archive", "03_analysis/code/__pycache__",
            "08_submission/submission_packages/author-copy",
        )
        for prefix in excluded:
            for item in range(100):
                self.put(f"{prefix}/nested/{item}.md")
        raw = self.put("02_data/raw/source.csv")
        cache = self.put("06_refs/cache/actual.xml")
        fulltext = self.put("06_refs/fulltext/report.txt")
        retained = (
            ".wf/benchmark_science.json", ".wf/executor_acceptance_final.json",
            ".wf/discussion_outline.md", "03_analysis/code/model.py",
            "08_submission/journal_archives/first/bundle/manuscript.docx",
        )
        for rel in retained:
            self.put(rel)

        real_scandir = os.scandir
        visited = []

        def scandir(path):
            rel = Path(path).relative_to(self.project).as_posix()
            visited.append(rel)
            self.assertFalse(any(rel == prefix or rel.startswith(prefix + "/") for prefix in excluded))
            self.assertNotIn(rel, {"temp", ".wf/revisions", "08_submission/releases", "07_manuscript/review_packages"})
            return real_scandir(path)

        with patch.object(revision.os, "scandir", side_effect=scandir), \
             patch.object(revision, "_sha256", wraps=revision._sha256) as hashes:
            result = revision.snapshot(self.project)
        self.assertIn("02_data/raw", visited)
        for path in (raw, cache, fulltext):
            metadata = path.stat()
            self.assertEqual(result[path.relative_to(self.project).as_posix()],
                             f"stat:{metadata.st_size}:{metadata.st_mtime_ns}")
        self.assertEqual({str(call.args[0]) for call in hashes.call_args_list},
                         {str(self.project / rel) for rel in retained})

    def test_author_copy_is_tracked_separately_even_with_legacy_baseline(self):
        author_rel = "08_submission/submission_packages/author-copy/paper.docx"
        source = self.put("08_submission/integration/paper.md", "Current source")
        old = self.record()
        old["baseline"][author_rel] = "A historic author-copy fingerprint"
        self.put(author_rel, "Author edits the separate work copy")
        self.assertEqual(revision.scope_problems(self.project, old), [])
        source.write_text("Unplanned change to the actual managed source", encoding="utf-8")
        self.assertTrue(revision.scope_problems(self.project, old))

    def test_external_windows_junction_is_never_entered(self):
        if os.name != "nt":
            self.skipTest("Windows junction check")
        outside = self.root / "outside_dependencies"
        outside.mkdir()
        (outside / "outside.py").write_text("Synthetic external file", encoding="utf-8")
        junction = self.project / "linked_dependencies"
        made = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                              capture_output=True, timeout=10)
        self.assertEqual(made.returncode, 0, made.stderr)
        self.addCleanup(os.rmdir, junction)
        self.assertTrue(junction.is_junction())
        real_scandir = os.scandir

        def scandir(path):
            self.assertNotEqual(Path(path), junction)
            self.assertFalse(Path(path).resolve().is_relative_to(outside))
            return real_scandir(path)

        with patch.object(revision.os, "scandir", side_effect=scandir):
            result = revision.snapshot(self.project)
        self.assertNotIn("linked_dependencies/outside.py", result)
        old_rel = "linked_dependencies/outside.py"
        record = self.record(baseline={**result, old_rel: "legacy path fingerprint"})
        with patch.object(revision.os, "scandir", side_effect=scandir), redirect_stderr(io.StringIO()):
            report = revisionservice.preflight(self.project, self.state, record)
        self.assertEqual(report["linked_baseline_paths"], [old_rel])
        self.assertIn(f"unplanned change: {old_rel}", report["blockers"])

    def test_preflight_shares_project_snapshot_and_reference_renewal_proof(self):
        self.put("08_submission/integration/cover_letter.md")
        record = self.record(presentation_candidate=True)
        record["validation"] = {
            "ok": True, "checked_at": datetime.now(timezone.utc).isoformat(),
            "input_signature": revision.input_signature(self.project, record),
        }
        stderr = io.StringIO()
        with patch.object(revision, "snapshot", wraps=revision.snapshot) as snapshot, \
             patch.object(evidence, "reference_renewal_problems", wraps=evidence.reference_renewal_problems) as renewal, \
             redirect_stderr(stderr):
            report = revisionservice.preflight(self.project, self.state, record)
        self.assertEqual(snapshot.call_count, 1)
        self.assertEqual(renewal.call_count, 1)
        self.assertTrue(report["validation_current"])
        self.assertEqual(report["classification"]["class"], "presentation")
        self.assertIn("scanning project files", stderr.getvalue())
        self.assertIn("project files observed", stderr.getvalue())

    def test_cancellation_leaves_files_and_revision_state_read_only(self):
        source = self.put("03_analysis/code/model.py")
        stored_round = self.put(".wf/revisions/R001.json", '{"status":"active"}')
        record = self.record(presentation_candidate=True)
        before = [(path, path.read_bytes(), path.stat().st_mtime_ns)
                  for path in (source, self.state.file, stored_round)]
        stderr = io.StringIO()
        with patch.object(revision.os, "scandir", side_effect=KeyboardInterrupt), redirect_stderr(stderr):
            with self.assertRaises(KeyboardInterrupt):
                revisionservice.preflight(self.project, self.state, record)
        self.assertIn("scanning project files", stderr.getvalue())
        for path, content, mtime in before:
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_completion_marks_look_up_declared_sources_without_walking_tree(self):
        rel = "08_submission/integration/cover_letter.md"
        self.put(rel)
        record = self.record(allowed_files=[rel], items=[{"id": "I1", "affected_sources": [rel]}])
        submission = {"summary": "The intended revision was addressed and inspected in this isolated fixture.",
                      "items": [{"id": "I1", "summary": "The actual source was checked and its text matched.",
                                 "validated_by": ["Synthetic source inspection"]}]}
        with patch.object(revision, "snapshot", side_effect=AssertionError("completion scanned entire project")):
            marks = revisionservice.completion_marks(self.project, record, submission)
        self.assertEqual(marks[0].checked_file, [rel])


if __name__ == "__main__":
    unittest.main(verbosity=2)
