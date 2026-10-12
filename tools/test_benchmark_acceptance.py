"""Isolated behavior tests; synthetic papers are fixtures, never a real bibliography."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from wfcore import benchmark as b, registry, revision
from wfcore.readiness import atomic_json
from wfcore.packagefreeze import _sha256
from wfcore.state import State
from wfcore.checks import Ctx, get, load_all
from wfcore.journalrules import display_limits, compare


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="medpaper-benchmark-test-"); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name); self.pipe = registry.load(); load_all()
        self.state = State(self.project).create("medpaper", "1.11.0", "S07_artifacts")
        # Local reference verification itself is tested with raw XML in the full regression.
        self.proof = patch("wfcore.refproof.validate_local_proof", return_value=(True, [], 2)); self.proof.start(); self.addCleanup(self.proof.stop)
        self.doc = {"benchmark_version": 1, "adequacy_rationale": "Two synthetic design-matched articles inform this test project only.", "comparators": [],
                    "adaptation": {"structure": {k: "Concrete project-specific adaptation for " + k for k in ("methods", "discussion", "main_vs_supplement", "declarations")},
                                   "references": {"ranges": {k: [0, 10] for k in (*b.SECTIONS, "library", "main_total")}, "basis": "Observed close articles and the project's actual argument needs, not a universal quota.",
                                                  "roles": [{"id": "prior", "section": "introduction", "claim": "The prior study establishes the existing uncertainty in clinical prognosis.", "source_type": "closest primary study", "required": True, "citekeys": ["test1"], "passage": "Prior clinical uncertainty remains documented [@test1]."}]},
                                   "displays": {k: "Specific study rationale and documented applicability for " + k for k in ("inventory_rationale", "essential_questions", "omissions")}}}
        entries = []; records = []
        for i in (1, 2):
            key = f"test{i}"; pmid = str(90000000 + i)
            fragments = {"methods": f"Methods statement for synthetic paper {i} explains clinical cohort selection.",
                         "discussion": f"Discussion in synthetic paper {i} contrasts existing evidence and limitations.",
                         "display": f"Table 1 in synthetic paper {i} reports denominators and missingness."}
            text = '<article><front><article-meta><article-id pub-id-type="pmid">' + pmid + '</article-id></article-meta></front><body>' + ''.join("<p>" + t + "</p>" for t in fragments.values()) + '</body></article>'
            rel = f"06_refs/fulltext/{key}.xml"; self.text(rel, text)
            entries.append({"citekey": key, "pmid": pmid, "journal": "Synthetic Medical Journal", "abstract": "Synthetic fixture abstract"})
            records.append({"citekey": key, "pmid": pmid, "fulltext": rel, "access": "oa", "sha256": _sha256(self.project / rel)})
            self.doc["comparators"].append({"citekey": key, "fulltext": rel, "sha256": _sha256(self.project / rel),
                 "relevance": {k: "Study-specific comparison explanation for " + k for k in ("topic", "design", "analysis")},
                 "observations": {**{k: "Full-text clinical ordering observed and adapted for " + k for k in ("methods_outline", "discussion_structure", "reference_roles", "display_roles")},
                                  "main_figures": i, "main_tables": 1, "supp_figures": 0, "supp_tables": 0, "citations": {k: i for k in b.SECTIONS}},
                 "evidence": [{"kind": k, "locator": k + " paragraph", "quote": v} for k, v in fragments.items()]})
        self.data("06_refs/library.json", {"entries": entries}); self.data("06_refs/fulltext/retrieval_manifest.json", {"retrievals": records})
        self.text("06_refs/refs.bib", "Synthetic fixture bibliography only")
        contract = {k: "Specific figure contribution explaining " + k for k in ("population", "comparison", "measure", "denominator_and_units", "interpretation_limit", "question", "placement_reason", "nonredundancy", "misinterpretation_risk")}
        self.plan = {"main_figures": [{"id": "Figure 1", "file": "05_figures/out/Figure1.png", "reader_contract": contract}], "main_tables": [], "supp_figures": [], "supp_tables": []}
        self.data("01_protocol/artifact_plan.json", self.plan)
        for rel in ("05_figures/out/Figure1.png", "05_figures/legends.md", "04_tables/table_captions.md"):
            self.text(rel, "Internal test display fixture, not a clinical research result")
        self.text("07_manuscript/introduction.md", self.doc["adaptation"]["references"]["roles"][0]["passage"])
        self.text("07_manuscript/full_manuscript.md", "# Introduction\nPrior clinical uncertainty remains documented [@test1].")
        self.write_doc(); b.seal(self.project)

    def data(self, rel, value): atomic_json(self.project / rel, value)
    def text(self, rel, value):
        path = self.project / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value, encoding="utf-8")
    def write_doc(self, layer="science"):
        self.text(b.SCIENCE if layer == "science" else b.JOURNAL, "# Internal benchmark\n```json\n" + json.dumps(self.doc) + "\n```\n")
    def report(self):
        contract = self.plan["main_figures"][0]["reader_contract"]
        return {"reviewer": "Primary executor, honest synthetic reader simulation", "inputs": b.acceptance_inputs(self.project), "final_outputs": False,
                "findings": {k: {"verdict": "PASS", "observation": "Inspected actual current specimen and resolved the specific " + k} for k in b.DIMENSIONS},
                "unresolved": [], "range_deviations": {}, "display_findings": {"Figure 1": {"contract_hash": hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest(),
                                                                                     "reviewed_file": "05_figures/out/Figure1.png",
                                                                                     "observation": "The actual single panel explains the denominator without mixing clinical groups."}}}

    def test_full_text_and_locked_project_adaptation_pass(self):
        self.assertEqual(b.verify_benchmark(self.project), []); self.assertEqual(b.display_fit(self.project), [])

    def test_abstract_or_notes_cannot_replace_registered_fulltext(self):
        self.doc["comparators"][0]["fulltext"] = "06_refs/cache/abstract.md"; self.text("06_refs/cache/abstract.md", "Abstract only"); self.write_doc()
        self.assertTrue(b.verify_benchmark(self.project))

    def test_fabricated_excerpt_rejected(self):
        self.doc["comparators"][0]["evidence"][0]["quote"] = "A invented full-text passage that never occurs in the registered article."
        self.write_doc(); self.assertTrue(b.verify_benchmark(self.project))

    def test_wrong_article_identity_rejected_even_with_new_hash(self):
        row = self.doc["comparators"][0]; self.text(row["fulltext"], '<article><front><article-meta><article-id pub-id-type="pmid">123</article-id></article-meta></front></article>')
        row["sha256"] = _sha256(self.project / row["fulltext"])
        records = json.loads((self.project / "06_refs/fulltext/retrieval_manifest.json").read_text()); records["retrievals"][0]["sha256"] = row["sha256"]
        self.data("06_refs/fulltext/retrieval_manifest.json", records); self.write_doc()
        self.assertTrue(any("contradicts" in problem for problem in b.verify_benchmark(self.project)))

    def test_count_lowering_or_required_role_removal_changes_lock(self):
        self.doc["adaptation"]["references"]["ranges"]["introduction"] = [0, 1]; self.write_doc()
        self.assertTrue(any("plan changed" in p for p in b.verify_benchmark(self.project)))
        with self.assertRaises(ValueError): b.seal(self.project)

    def test_late_untracked_replan_rejected(self):
        self.state.data["current"] = "S17_assemble"; self.state.save()
        with self.assertRaises(ValueError): b.seal(self.project)

    def test_source_and_passage_mappings_can_complete_without_loosening_plan(self):
        self.doc["adaptation"]["references"]["roles"][0]["citekeys"] = ["test2"]
        self.write_doc(); self.assertEqual(b.verify_benchmark(self.project), [])

    def test_many_library_entries_do_not_replace_missing_argument(self):
        role = self.doc["adaptation"]["references"]["roles"][0]; role["citekeys"] = []; self.write_doc()
        self.assertTrue(b.coverage(self.project, library_only=True))

    def test_source_role_must_bind_an_actual_cited_passage(self):
        self.assertEqual(b.coverage(self.project), [])
        self.text("07_manuscript/introduction.md", "A long uncited claim does not support the original project argument.")
        self.assertTrue(b.coverage(self.project))

    def test_metrics_separate_library_main_and_supplement(self):
        self.text("07_manuscript/supplementary_methods.md", "An extended method [@test2].")
        metrics = b.citation_metrics(self.project)
        self.assertEqual((metrics["library"], metrics["main_total"], metrics["supplementary"]), (2, 1, 1))

    def test_copied_display_purpose_rejected(self):
        second = copy.deepcopy(self.plan["main_figures"][0]); second["id"] = "Figure 2"; self.plan["main_figures"].append(second)
        self.data("01_protocol/artifact_plan.json", self.plan); self.assertTrue(b.display_fit(self.project))

    def test_prototype_review_cannot_reuse_a_changed_question_contract(self):
        from wfcore.readiness import verify_displays
        preview = "01_protocol/prototypes/Figure1.png"; self.text(preview, "Synthetic prototype bytes only")
        entry = self.plan["main_figures"][0]
        row = {"id": "Figure 1", "preview": preview, "preview_sha256": _sha256(self.project / preview), "source_hashes": {},
               "question": entry["reader_contract"]["question"], "contract_hash": b.contract_hash(entry), "verdict": "PASS"}
        row.update({k: "Actual item-specific test observation for " + k for k in ("reader_explanation", "denominator_units_missingness", "encoding_overlap", "layout", "reviewer")})
        self.data("01_protocol/display_review.json", {"items": [row]}); self.assertEqual(verify_displays(self.project), [])
        entry["reader_contract"]["question"] = "A different clinical question requires inspection again, not a reused PASS."
        self.data("01_protocol/artifact_plan.json", self.plan); self.assertTrue(verify_displays(self.project))

    def test_missing_executor_record_is_failed_gate_not_engine_exception(self):
        result = get("executor_acceptance")(Ctx(self.pipe, self.state, self.project, self.pipe.stage("S17_assemble"), {}))
        self.assertFalse(result.ok); self.assertNotIn("check raised", result.detail)

    def test_acceptance_binds_real_files_and_specific_contract(self):
        self.data(b.acceptance_rel("science"), self.report()); self.assertEqual(b.verify_acceptance(self.project), [])
        self.text("05_figures/out/Figure1.png", "Changed rendered display")
        self.assertTrue(b.verify_acceptance(self.project))

    def test_range_deviation_needs_reason_not_padding(self):
        self.doc["adaptation"]["references"]["ranges"]["introduction"] = [2, 4]; self.write_doc()
        # This test defines its prewriting range; no range is reset after drafting.
        self.data(".wf/benchmark_science_lock.json", {"plan_hash": b.plan_hash(self.doc)})
        row = self.report(); self.data(b.acceptance_rel("science"), row); self.assertTrue(b.verify_acceptance(self.project))
        row["range_deviations"]["introduction"] = "One directly relevant source covers the narrow claim; extra references would duplicate its evidence."
        self.data(b.acceptance_rel("science"), row); self.assertEqual(b.verify_acceptance(self.project), [])

    def test_pass_label_without_findings_rejected(self):
        row = self.report(); row["findings"]["methods_logic"]["observation"] = "PASS"; self.data(b.acceptance_rel("science"), row)
        self.assertTrue(b.verify_acceptance(self.project))

    def test_acceptance_itself_cannot_bless_an_unbound_argument(self):
        self.text("07_manuscript/introduction.md", "A changed unsupported claim cannot pass just because files were hashed.")
        self.data(b.acceptance_rel("science"), self.report())
        self.assertTrue(b.verify_acceptance(self.project))

    def test_pre_and_final_journal_acceptance_have_separate_bindings(self):
        self.assertNotEqual(b.acceptance_rel("journal"), b.acceptance_rel("journal", True))

    def test_sourced_journal_display_cap_not_a_universal_inventory_limit(self):
        self.data("08_submission/submission_requirements.json", {"article_type": "Original article", "display_limits": {
            "main_display_items": {"status": "required", "value": 2, "source": "https://journal.example/original"},
            "main_figures": {"status": "recommended", "value": 1, "source": "https://journal.example/original"}}})
        rules = display_limits(self.project)
        self.assertEqual(compare({"main_display_items": 2, "main_figures": 2}, rules), [])
        self.assertTrue(compare({"main_display_items": 3}, rules))

    def test_failed_accept_capture_preserves_prior_receipt(self):
        self.state.data["current"] = "S17_assemble"; self.state.save()
        row = self.report(); destination = b.acceptance_rel("science"); self.data(destination, row)
        before = (self.project / destination).read_bytes(); row["unresolved"] = ["Unresolved clinical label ambiguity"]
        self.data(".wf/test_review.json", row)
        run = subprocess.run([sys.executable, str(Path(__file__).parent / "manuscript/benchmark.py"), "accept", "--project", str(self.project),
                              "--review", str(self.project / ".wf/test_review.json")], capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0); self.assertEqual((self.project / destination).read_bytes(), before)

    def test_pdf_comparator_text_is_read_from_actual_pdf(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter(); page = writer.add_blank_page(612, 792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject(); stream.set_data(b"BT /F1 12 Tf 72 720 Td (Synthetic full text methods specimen) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        path = self.project / "test-comparator.pdf"; writer.write(path)
        self.assertIn("Synthetic full text methods specimen", b.text_of(path))

    def test_journal_comparator_cache_does_not_change_frozen_library(self):
        before = (self.project / "06_refs/library.json").read_bytes()
        entries = json.loads(before)["entries"]; records = json.loads((self.project / "06_refs/fulltext/retrieval_manifest.json").read_text())["retrievals"]
        for row, entry, record in zip(self.doc["comparators"], entries, records):
            row["citekey"] = record["citekey"] = "benchmark" + entry["pmid"]
            cache = "06_refs/cache/benchmark_efetch_pubmed_" + entry["pmid"] + ".xml"
            self.text(cache, '<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>' + entry["pmid"] + '</PMID><Article><ArticleTitle>Test comparator</ArticleTitle><Journal><Title>Synthetic Medical Journal</Title></Journal></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
            record["metadata_cache"] = cache; record["metadata_sha256"] = _sha256(self.project / cache)
        self.data("06_refs/fulltext/retrieval_manifest.json", {"retrievals": records})
        self.data("08_submission/target_journal.json", {"journal": "Synthetic Medical Journal"})
        self.data("08_submission/submission_requirements.json", {"article_type": "Original article"})
        self.doc["target_hashes"] = {rel: _sha256(self.project / rel) for rel in ("08_submission/target_journal.json", "08_submission/submission_requirements.json")}
        self.write_doc("journal"); self.data(".wf/benchmark_journal_lock.json", {"plan_hash": b.plan_hash(self.doc)})
        self.assertEqual(b.verify_benchmark(self.project, "journal"), [])
        self.assertEqual((self.project / "06_refs/library.json").read_bytes(), before)
        self.text(records[0]["metadata_cache"], "Changed source payload")
        self.assertTrue(b.verify_benchmark(self.project, "journal"))

    def test_deprecated_legacy_quotas_do_not_control_library_or_inventory(self):
        self.pipe.targets.update(reflib_min=100, main_figures_max=0)
        self.data("06_refs/library.json", {"entries": [{"citekey": "test1", "pmid": "90000001", "abstract": "Test abstract"}]})
        result = get("refs_library")(Ctx(self.pipe, self.state, self.project, self.pipe.stage("S13_reflib"), {"require_verified": False}))
        self.assertTrue(result.ok, result.detail)
        self.assertTrue(all(b.RETIRED_TARGETS.isdisjoint(self.pipe.raw["targets"]) for _ in [0]))

    def test_hidden_acceptance_drift_invalidates_incremental_signature(self):
        before = revision.snapshot(self.project); self.data(b.acceptance_rel("science"), self.report())
        self.assertNotEqual(before, revision.snapshot(self.project))

    def test_actual_comparator_registration_does_not_edit_scientific_library(self):
        from pubmed import fulltext
        from pubmed import eutils
        before = (self.project / "06_refs/library.json").read_bytes()
        pmid = "90000001"; cache = "06_refs/cache/benchmark_efetch_pubmed_registration.xml"
        self.text(cache, "Synthetic network payload used only by a mocked unit transport")
        source = self.project / "source-article.xml"
        source.write_text((self.project / "06_refs/fulltext/test1.xml").read_text()[:-10] + '<!--' + 'fixture-padding' * 100 + '--></article>', encoding="utf-8")
        entry = {"pmid": pmid, "journal": "Synthetic Medical Journal", "title": "Synthetic comparator fixture", "cache_file": cache}
        with patch.object(eutils, "project_root", return_value=self.project), patch.object(eutils, "efetch", return_value=[entry]) as fetch:
            with patch.object(sys, "argv", ["fulltext.py", "register", "--pmid", pmid, "--file", str(source), "--access", "oa", "--source-url", "https://journal.example/test", "--no-stub"]):
                self.assertEqual(fulltext.main(), 0)
            fetch.assert_called_once_with([pmid], fresh=True, purpose="benchmark")
        self.assertEqual((self.project / "06_refs/library.json").read_bytes(), before)
        record = next(row for row in json.loads((self.project / "06_refs/fulltext/retrieval_manifest.json").read_text())["retrievals"] if row["citekey"] == "benchmark" + pmid)
        self.assertEqual(record["metadata_cache"], cache); self.assertEqual(record["metadata_sha256"].upper(), _sha256(self.project / cache))

    def test_incomplete_fulltext_fetch_returns_failure_before_dependent_capture(self):
        from pubmed import fulltext, eutils
        with patch.object(eutils, "project_root", return_value=self.project), patch.object(fulltext, "fetch_one", return_value={"access": "paywalled", "route": "unavailable", "fulltext": ""}):
            with patch.object(sys, "argv", ["fulltext.py", "fetch", "--citekey", "test1", "--no-stub"]):
                self.assertEqual(fulltext.main(), 2)

    def test_legacy_scientific_freeze_not_invalidated_by_new_backstage_coverage(self):
        from wfcore import scientificfreeze as sf
        rel = "07_manuscript/full_manuscript.md"; path = self.project / rel
        records = [{"path": rel, "sha256": sf._sha256(path), "bytes": path.stat().st_size}]
        evidence = self.project / b.SCIENCE
        current = records + [{"path": b.SCIENCE, "sha256": sf._sha256(evidence), "bytes": evidence.stat().st_size}]
        payload = {"schema_version": 3, "algorithm": "SHA-256", "review_package_id": "synthetic-test-package", "files": records,
                   "freeze_id": sf._freeze_id("synthetic-test-package", records)}
        self.data(sf.FREEZE_REL, payload)
        with patch.object(sf, "verify_review_package", return_value=(True, [], {"package_id": "synthetic-test-package"})), patch.object(sf, "collect_files", return_value=current):
            self.assertTrue(sf.verify(self.project)[0])
            payload["schema_version"] = 4; self.data(sf.FREEZE_REL, payload)
            self.assertFalse(sf.verify(self.project)[0])  # New freezes must cover the benchmark.
            payload["schema_version"] = 3; self.data(sf.FREEZE_REL, payload)
            current[0] = {**current[0], "sha256": "CHANGED-SCIENTIFIC-CONTENT"}
            self.assertFalse(sf.verify(self.project)[0])  # Legacy compatibility never waives science drift.


if __name__ == "__main__": unittest.main()
