"""Synthetic reference renewals preserve science; no network or real project access."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pubmed import build_library, eutils, verify
from wfcore import evidence, presentationdelta, refproof, registry, revision
from wfcore.packagefreeze import _sha256
from wfcore.readiness import atomic_json
from wfcore.state import State
import test_pubmed_id_scope_1291 as xml_fixture


class RenewableReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="medpaper-renewable-evidence-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.pipe = registry.load()
        self.state = State(self.project).create("medpaper", self.pipe.meta["version"], "S24_package_human_review")
        self.raw = "<PubmedArticleSet>" + xml_fixture.article() + "</PubmedArticleSet>"
        self.library = {"entries": []}
        build_library.add_records(self.library, eutils.parse_pubmed_xml(self.raw))
        self.entry = self.library["entries"][0]
        self.key = self.entry["citekey"]
        self.data("06_refs/library.json", self.library)
        self.text("06_refs/refs.bib", build_library.to_bibtex(self.library["entries"]))
        self.text("06_refs/refs.ris", build_library.to_ris(self.library["entries"]))
        self.verifier_cache = "06_refs/cache/verify_efetch_pubmed_baseline.xml"
        self.source = self.payload(self.verifier_cache)
        self.proof(self.source)
        self.letter = "08_submission/integration/cover_letter.md"
        self.text(self.letter, "# Letter\nDear Editor,\n\nWe submit the accompanying clinical study.")
        self.row = {"schema_version": 2, "round_id": "R001", "status": "active",
                    "review_stage": self.state.current, "presentation_candidate": True,
                    "allowed_files": [self.letter], "validation_stages": ["S23_package"],
                    "items": [{"id": "E01", "kind": "journal-format", "status": "pending"}],
                    "checks": [{"stage": "S23_package", "spec": {"check": "md_sections", "path": self.letter, "headings": ["Letter"]}},
                               {"stage": "S23_package", "spec": {"check": "reference_provenance", "live": True}}]}
        self.row["baseline"] = revision.snapshot(self.project)
        self.row["presentation_baseline"] = presentationdelta.snapshot(self.project, self.row["baseline"])
        self.round_path = self.project / ".wf/revisions/R001.json"
        self.data(".wf/revisions/R001.json", self.row)
        self.state.data["active_revision_round"] = "R001"
        self.state.save()

    def text(self, rel, value):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        return path

    def data(self, rel, value):
        atomic_json(self.project / rel, value)

    def payload(self, rel, raw=None):
        raw = self.raw if raw is None else raw
        path = self.text(rel, raw)
        source = eutils.parse_pubmed_xml(raw, cache_file=rel)[0]
        source.update(cache_sha256=refproof.file_sha256(path), fresh_fetch=True)
        return source

    def proof(self, source):
        result = verify.verify_entry(self.entry, source, False, self.project)
        self.assertTrue(result["verified"])
        self.data("06_refs/verified.json", {
            "schema": refproof.SCHEMA, "generator": {"tool": refproof.GENERATOR, "mode": "fresh_ncbi_pubmed_efetch"},
            "verified_at": result["at"], "library_sha256": refproof.file_sha256(self.project / "06_refs/library.json"),
            "n_entries": 1, "n_verified": 1, "records": {self.key: result}})

    def gate(self, suffix="new", raw=None):
        return self.payload(f"06_refs/cache/gate_efetch_pubmed_{suffix}.xml", raw)

    def classification(self):
        return presentationdelta.classify(self.project, self.row)

    def assert_scientific(self):
        result = self.classification()
        self.assertEqual(result["class"], "scientific", result)
        return " ".join(result["reasons"])

    def test_only_exact_reference_evidence_namespaces_are_renewable(self):
        self.assertTrue(evidence.reference_evidence("06_refs/verified.json"))
        self.assertTrue(evidence.reference_evidence("06_refs/cache/gate_efetch_pubmed_next.xml"))
        for rel in ("06_refs/library.json", "06_refs/refs.bib", "06_refs/fulltext/article.xml", "07_manuscript/cache/source.xml"):
            self.assertFalse(evidence.reference_evidence(rel))

    def test_same_primary_records_new_gate_events_are_presentation_not_scientific(self):
        for suffix in ("first", "second"):
            self.gate(suffix)
        self.assertEqual(self.classification()["class"], "presentation")
        self.assertEqual(revision.scope_problems(self.project, self.row), [])

    def test_same_source_verifier_receipt_can_renew_but_never_grants_new_library_trust(self):
        source = self.payload("06_refs/cache/verify_efetch_pubmed_renewal.xml")
        self.proof(source)
        self.assertEqual(self.classification()["class"], "presentation")
        proof = json.loads((self.project / "06_refs/verified.json").read_text())
        proof["library_sha256"] = "0" * 64
        self.data("06_refs/verified.json", proof)
        self.assertIn("invalid current provenance", self.assert_scientific())

    def test_new_unknown_pmid_or_changed_own_identity_metadata_and_abstract_are_blocked(self):
        replacements = [("<PMID>123</PMID>", "<PMID>456</PMID>"),
                        ("10.1000/main", "10.1000/other"), ("PMC100", "PMC777"),
                        ("Synthetic primary clinical article", "Synthetic primary clinical articles"),
                        ("Synthetic Clinical Journal", "Another Clinical Journal"),
                        ("<Year>2026</Year>", "<Year>2025</Year>"),
                        ("<LastName>Fixture</LastName>", "<LastName>Another</LastName>"),
                        ("Actual synthetic study findings", "No actual synthetic study findings"),
                        ("</Article>", "<PublicationTypeList><PublicationType>Retracted Publication</PublicationType></PublicationTypeList></Article>")]
        for old, new in replacements:
            with self.subTest(field=old):
                rel = "06_refs/cache/gate_efetch_pubmed_new.xml"
                self.payload(rel, self.raw.replace(old, new))
                self.assertIn("identity or consumed source", self.assert_scientific())
                (self.project / rel).unlink()

    def test_reference_list_changes_do_not_become_the_primary_papers_identity(self):
        self.gate(raw=self.raw.replace("PMC999", "PMC888").replace("10.1000/reference", "10.1000/another-cited-reference"))
        self.assertEqual(self.classification()["class"], "presentation")

    def test_empty_duplicate_or_malformed_payload_and_arbitrary_cache_are_blocked(self):
        for raw in ("<PubmedArticleSet/>", "<PubmedArticleSet>" + xml_fixture.article() * 2 + "</PubmedArticleSet>", "<invalid>"):
            with self.subTest(raw=raw[:40]):
                rel = "06_refs/cache/gate_efetch_pubmed_bad.xml"
                self.text(rel, raw)
                self.assert_scientific()
                (self.project / rel).unlink()
        self.text("06_refs/cache/unmanaged.json", '{"verified": true}')
        self.assertIn("not a new managed", self.assert_scientific())

    def test_mutation_or_deletion_of_existing_xml_is_never_an_added_retrieval_event(self):
        path = self.project / self.verifier_cache
        path.write_text(self.raw + "\n", encoding="utf-8")
        self.assert_scientific()
        path.unlink()
        self.assert_scientific()

    def test_library_export_fulltext_or_source_claim_changes_keep_their_scientific_owner(self):
        for rel in ("06_refs/library.json", "06_refs/refs.bib", "06_refs/fulltext/new.xml", "06_refs/source_claims.json"):
            with self.subTest(rel=rel):
                before = (self.project / rel).read_bytes() if (self.project / rel).exists() else None
                self.text(rel, "Changed scientific source")
                self.assert_scientific()
                if before is None: (self.project / rel).unlink()
                else: (self.project / rel).write_bytes(before)

    def test_boolean_only_verification_does_not_make_a_new_xml_event_safe(self):
        self.gate()
        self.data("06_refs/verified.json", {"verified": True})
        self.assertIn("invalid current provenance", self.assert_scientific())

    def test_wording_check_generates_actual_gate_fixture_then_round_closes_without_stage_rewind(self):
        import rework
        self.text(self.letter, "# Letter\nDear Editor.\n\nWe submit the accompanying clinical study.")
        def fetched(*args, **kwargs):
            self.assertTrue(kwargs["fresh"])
            return [self.gate("during_check")]
        with patch("pubmed.eutils.efetch", side_effect=fetched), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(revision.check_round(self.project, self.pipe, self.state, self.round_path, self.row), 0)
        self.assertEqual(self.row["validation"]["results"][-1]["check"], "reference_evidence_unchanged")
        self.row["items"][0].update(status="done", changed_files=[{"path": self.letter, "sha256": _sha256(self.project / self.letter)}])
        self.data(".wf/revisions/R001.json", self.row)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rework._cmd_close(argparse.Namespace(summary="Corrected only the salutation punctuation and verified its true unchanged scientific dependencies."), self.state), 0)
        closed = json.loads(self.round_path.read_text())
        self.assertEqual(closed["status"], "complete")
        self.assertEqual(self.state.current, "S24_package_human_review")
        self.assertNotIn("active_revision_round", self.state.data)

    def test_close_rejects_tampered_postcheck_event_without_closing_or_changing_library(self):
        import rework
        with patch("pubmed.eutils.efetch", side_effect=lambda *a, **kw: [self.gate("during_check")]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(revision.check_round(self.project, self.pipe, self.state, self.round_path, self.row), 0)
        library = (self.project / "06_refs/library.json").read_bytes()
        self.row["items"][0].update(status="done", checked_files=[{"path": self.letter, "sha256": _sha256(self.project / self.letter)}])
        self.data(".wf/revisions/R001.json", self.row)
        self.text("06_refs/cache/gate_efetch_pubmed_during_check.xml", self.raw.replace("PMC100", "PMC777"))
        with self.assertRaisesRegex(ValueError, "renewed evidence is invalid"):
            rework._cmd_close(argparse.Namespace(summary="This synthetic close must refuse altered source identity rather than accepting presentation status."), self.state)
        self.assertEqual(json.loads(self.round_path.read_text())["status"], "active")
        self.assertEqual((self.project / "06_refs/library.json").read_bytes(), library)

    def test_new_metadata_drift_created_by_validation_does_not_receive_a_presentation_pass(self):
        # The ordinary identity verifier deliberately has a fuzzy title comparison.
        # A source version delta must nevertheless be surfaced before presentation PASS.
        changed = self.raw.replace("Synthetic primary clinical article", "Synthetic primary clinical articles")
        with patch("pubmed.eutils.efetch", side_effect=lambda *a, **kw: [self.gate("during_check", changed)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(revision.check_round(self.project, self.pipe, self.state, self.round_path, self.row), 2)
        result = next(row for row in self.row["validation"]["results"] if row["check"] == "reference_evidence_unchanged")
        self.assertFalse(result["ok"])
        self.assertFalse(self.row["validation"]["ok"])
        self.assertEqual(self.state.current, "S24_package_human_review")


if __name__ == "__main__":
    unittest.main(verbosity=2)
