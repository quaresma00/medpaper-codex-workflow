"""Synthetic incremental-review checks; no research data or network access."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from wfcore import gates, registry, revision
from wfcore.checks import Result, get, load_all
from wfcore.gatecache import Receipts, TTL_SECONDS
from wfcore.readiness import atomic_json
from wfcore.state import State


class RevisionEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="medpaper-revision-119-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.pipe = registry.load()
        self.state = State(self.project).create("medpaper", self.pipe.meta["version"], "S24_package_human_review")
        load_all()
        self.stage = self.pipe.stage("S23_package")

    def text(self, rel, content):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def spec(self, rel):
        return {"check": "md_sections", "path": rel, "headings": ["Note"]}

    def cache(self):
        return Receipts(self.project, self.pipe, self.state)

    def test_local_check_keeps_unvisited_valid_receipts(self):
        specs = [self.spec("07_manuscript/first.md"), self.spec("07_manuscript/second.md")]
        for spec in specs:
            self.text(spec["path"], "# Note\nA separate checked source.")
        cache = self.cache()
        first = cache.identity(self.stage, specs[0])
        cache.put(first, Result(True, "md_sections")); cache.save()
        stamp = json.loads(cache.path.read_text())[first]["at"]
        second = self.cache()
        second.put(second.identity(self.stage, specs[1]), Result(True, "md_sections")); second.save()
        resumed = self.cache()
        self.assertIsNotNone(resumed.get(first))
        self.assertEqual(json.loads(cache.path.read_text())[first]["at"], stamp)

    def test_same_invocation_reuses_actual_result_and_prunes_expired_or_failed(self):
        self.text("07_manuscript/first.md", "# Note\nActual source.")
        cache = self.cache(); identity = cache.identity(self.stage, self.spec("07_manuscript/first.md"))
        cache.put(identity, Result(True, "md_sections"))
        self.assertIsNotNone(cache.get(identity)); self.assertEqual(cache.reused, 1)
        cache.old["expired"] = {"at": time.time() - TTL_SECONDS - 1, "result": {"ok": True, "check": "md_sections"}}
        cache.old["failed"] = {"at": time.time(), "result": {"ok": False, "check": "md_sections"}}
        cache.old["malformed"] = []
        cache.save(); retained = json.loads(cache.path.read_text())
        self.assertEqual(set(retained), {identity})

    def test_changed_source_configuration_rules_or_state_cannot_reuse(self):
        rel = "07_manuscript/first.md"; self.text(rel, "# Note\nActual source.")
        spec = self.spec(rel); cache = self.cache(); original = cache.identity(self.stage, spec)
        cache.put(original, Result(True, "md_sections")); cache.save()
        self.text(rel, "# Note\nChanged source.")
        self.assertIsNone(cache.get(cache.identity(self.stage, spec)))
        self.text(rel, "# Note\nActual source.")
        self.state.set_config("spelling", "british")
        self.assertIsNone(cache.get(cache.identity(self.stage, spec)))
        self.state.set_config("spelling", "american")
        cache.engine["synthetic-rule.py"] = "changed-rule-content"
        self.assertIsNone(cache.get(cache.identity(self.stage, spec)))
        cache = self.cache(); self.state.data["pipeline_version"] = "0.0.0"
        self.assertIsNone(cache.get(cache.identity(self.stage, spec)))

    def test_actual_journal_override_is_part_of_check_identity(self):
        self.text("01_protocol/artifact_plan.json", '{"main_figures": []}')
        target = self.text("08_submission/integration/artifact_plan.json", '{"main_figures": []}')
        cache = self.cache(); spec = {"check": "manuscript_structure"}
        before = cache.identity(self.stage, spec)
        target.write_text('{"main_figures": [{"id": "Figure 1"}]}', encoding="utf-8")
        self.assertNotEqual(before, cache.identity(self.stage, spec))
        target.unlink()
        self.assertNotEqual(before, cache.identity(self.stage, spec))

    def test_numeric_constant_source_and_author_identifiers_are_bound(self):
        source = self.text("01_protocol/constants.md", "Follow-up is 365 days by the documented design.")
        self.text("03_analysis/results/number_allowlist.tsv", "365\tconstant\t01_protocol/constants.md\tFollow-up duration is a recorded design constant.\n")
        cache = self.cache(); spec = {"check": "numbers_have_provenance", "path": "07_manuscript/methods.md"}
        before = cache.identity(self.stage, spec)
        source.write_text("The actual follow-up period is 180 days.", encoding="utf-8")
        self.assertNotEqual(before, cache.identity(self.stage, spec))
        before = cache.identity(self.stage, spec)
        self.text("00_input/author_info.json", '{"ethics_approval":"TEST-2026-01"}')
        self.assertNotEqual(before, cache.identity(self.stage, spec))

    def test_unknown_live_and_integrity_checks_have_no_cache_identity(self):
        cache = self.cache()
        for spec in ({"check": "reference_provenance", "live": True}, {"check": "data_acquisition_complete"},
                     {"check": "unknown"}, {"check": "md_sections", "live": True}):
            self.assertIsNone(cache.identity(self.stage, spec))

    def round(self, checks=None):
        source = "08_submission/integration/note.md"
        evidence = "08_submission/evidence/guide.md"
        self.text(source, "# Note\nUnchanged authored manuscript.")
        self.text(evidence, "# Note\nInitial source evidence.")
        specs = checks if checks is not None else [self.spec(source), self.spec(evidence)]
        row = {"schema_version": 2, "round_id": "R001", "status": "active",
               "review_stage": "S24_package_human_review", "allowed_files": [source],
               "baseline": revision.snapshot(self.project),
               "items": [{"kind": "journal-format", "affected_sources": [source], "change_type": "wording"}],
               "checks": [{"stage": self.stage.id, "spec": spec} for spec in specs]}
        path = self.project / ".wf/revisions/R001.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(revision.check_round(self.project, self.pipe, self.state, path, row), 0)
        return row, evidence

    def test_evidence_refresh_runs_only_changed_pure_consumer(self):
        row, evidence = self.round(); checked_at = row["validation"]["checked_at"]
        self.text(evidence, "# Note\nGenuinely renewed evidence with unchanged manuscript.")
        actual = get("md_sections"); reads = []
        def capture(ctx):
            reads.append(ctx.spec["path"])
            return actual(ctx)
        with patch("wfcore.checks.get", return_value=capture):
            revision.refresh_evidence(self.project, self.pipe, self.state, row)
        self.assertEqual(reads, [evidence])
        self.assertEqual(row["validation"]["checked_at"], checked_at)
        self.assertEqual(row["validation"]["renewable_evidence"][evidence], revision.snapshot(self.project)[evidence])
        self.assertEqual(self.state.current, "S24_package_human_review")

    def test_invalid_changed_pure_evidence_blocks_close(self):
        row, evidence = self.round()
        self.text(evidence, "# Wrong heading\nInvalid new evidence.")
        before = json.dumps(row["validation"], sort_keys=True)
        with self.assertRaisesRegex(ValueError, "renewed evidence is invalid"):
            revision.refresh_evidence(self.project, self.pipe, self.state, row)
        self.assertEqual(json.dumps(row["validation"], sort_keys=True), before)

    def test_live_refresh_runs_before_its_pure_consumer(self):
        source = "08_submission/integration/note.md"; evidence = "08_submission/evidence/guide.md"
        actual = get("md_sections"); order = []
        def lookup(name):
            if name == "reference_provenance":
                def renew(ctx):
                    order.append("live")
                    self.text(evidence, "# Note\nFresh authoritative evidence from test adapter.")
                    return Result(True, name)
                return renew
            def pure(ctx):
                order.append(ctx.spec["path"])
                return actual(ctx)
            return pure
        with patch("wfcore.checks.get", side_effect=lookup):
            row, evidence = self.round([self.spec(source), self.spec(evidence), {"check": "reference_provenance", "live": True}])
            # The initial validation rechecks only the pure consumer changed by the later live check.
            self.assertEqual(order, [source, evidence, "live", evidence])
            order.clear(); self.text(evidence, "# Note\nEvidence pending renewed source check.")
            revision.refresh_evidence(self.project, self.pipe, self.state, row)
        self.assertEqual(order[0], "live")
        self.assertNotIn(source, order)

    def test_legacy_round_without_check_identity_revalidates_evidence(self):
        row, evidence = self.round()
        row["validation"].pop("check_identities")
        self.text(evidence, "# Wrong heading\nChanged source must not be skipped for a legacy receipt.")
        with self.assertRaises(ValueError):
            revision.refresh_evidence(self.project, self.pipe, self.state, row)

    def test_scope_failure_stops_before_dependent_checks(self):
        row, _ = self.round()
        self.text("07_manuscript/unrelated.md", "An undeclared changed scientific source.")
        with patch("wfcore.checks.get") as lookup:
            results, _, _ = revision.validate(self.project,self.pipe,self.state,row)
        lookup.assert_not_called()
        self.assertEqual(len(results),1)
        self.assertTrue(results[0].blocking)


if __name__ == "__main__":
    unittest.main(verbosity=2)
