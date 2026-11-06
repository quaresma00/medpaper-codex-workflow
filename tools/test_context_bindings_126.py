"""Current-result attribution: same numbers/outcome do not establish the same finding."""
import json
from pathlib import Path
import tempfile
import unittest

from wfcore import claims
from wfcore.readiness import atomic_json
from wfcore.state import State


class ContextBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="medpaper-context-126-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        self.state = State(self.project).create("medpaper", "1.26.0", "S09_results")
        self.rel = "07_manuscript/results.md"
        self.context = dict(outcome="heart-failure admission", population="adults",
                            comparison="exposed versus unexposed", model="adjusted model",
                            timepoint="long-term follow-up", unit="hazard ratio", denominator="eligible adults")
        self.quote = ("Among adults, the adjusted model for exposed versus unexposed showed "
                      "heart-failure admission over long-term follow-up "
                      "(hazard ratio 1.42; 95% CI, 1.10 to 1.83).")
        values = dict(estimate=1.42, ci_low=1.10, ci_high=1.83)
        self.export = {"primary": {"context": self.context, "values": values}}
        self.catalog = {"primary": dict(source="03_analysis/results/primary.json", pointer="/primary", context=self.context)}
        # These real alternative result contexts make the mismatches source-observable,
        # instead of pretending a word blacklist comprehends every medical population.
        self.alternatives = dict(population="children", comparison="exposed versus active treatment",
                                 model="unadjusted model", timepoint="short-term follow-up")
        for field, value in self.alternatives.items():
            context = {**self.context, field: value}
            self.export[field] = {"context": context, "values": values}
            self.catalog[field] = dict(source="03_analysis/results/primary.json", pointer="/"+field, context=context)
        self.save_sources()

    def save_sources(self):
        atomic_json(self.project/"03_analysis/results/primary.json", self.export)
        atomic_json(self.project/"01_protocol/study_facts.json", {"numeric_facts": self.catalog})

    def row(self, quote=None, *, evidence=True):
        quote = quote or self.quote
        row = {"path": self.rel, "text": quote, "fact_ids": ["primary"]}
        if evidence:
            fact = claims.facts(self.project)["primary"]
            row["context_evidence"] = {"primary": {"fact_fingerprint": fact["fingerprint"],
                "claim_fingerprint": claims.fingerprint(quote),
                "observations": {field: self.context[field] for field in claims.PROSE_CONTEXT_KEYS}}}
        return row

    def validate(self, row, body=None):
        atomic_json(self.project/"07_manuscript/claim_bindings.json", {"schema_version": 1, "claims": [row]})
        return claims.validate_prose(self.project, self.rel, body or row["text"])

    def test_legacy_reproduction_and_current_missing_readback(self):
        self.state.data["engine_pin"] = "1.25.0"; self.state.save()
        self.assertEqual(self.validate(self.row(evidence=False)), [])
        for field, wrong in self.alternatives.items():
            quote = self.quote.replace(self.context[field], wrong)
            self.assertEqual(self.validate(self.row(quote, evidence=False)), [], field)
        self.state.data["engine_pin"] = "1.26.0"; self.state.save()
        self.assertIn("context_evidence", str(self.validate(self.row(evidence=False))))
        self.assertEqual(self.state.load().current, "S09_results")

    def test_correct_source_bound_literal_context_passes(self):
        self.assertEqual(self.validate(self.row()), [])

    def test_only_population_comparison_model_or_time_change_is_rejected(self):
        for field, wrong in self.alternatives.items():
            with self.subTest(field=field):
                quote = self.quote.replace(self.context[field], wrong)
                row = self.row(quote)
                row["context_evidence"]["primary"]["observations"][field] = wrong
                self.assertTrue(self.validate(row), field)

    def test_known_context_conflict_cannot_be_closed_with_pass_or_generic_readback(self):
        quote = self.quote.replace("adjusted model", "unadjusted model")
        row = self.row(quote)
        row["context_evidence"]["primary"]["observations"]["model"] = {
            "mode": "read_back", "reviewer": "executor", "scope": "claim", "quote": quote,
            "interpretation": "This is declared to be the adjusted primary model despite its displayed words.",
            "reason": "This synthetic attempted override has no scientific basis and must not make an exported conflicting context acceptable."}
        self.assertIn("another exported context", str(self.validate(row)))
        row = self.row()
        row["context_evidence"]["primary"]["observations"]["model"] = {"judgement": "pass"}
        self.assertTrue(self.validate(row))

    def test_adjusted_is_not_a_substring_match_for_unadjusted(self):
        self.assertFalse(claims._phrase("adjusted model", "unadjusted model"))
        self.assertTrue(claims._phrase("adjusted model", "the adjusted model,"))

    def test_actual_same_section_context_can_be_inherited_without_repeating_it(self):
        row = self.row()
        quote = "Heart-failure admission was estimated with a hazard ratio of 1.42 (95% CI, 1.10 to 1.83)."
        intro = "Adults were compared as exposed versus unexposed using the adjusted model over long-term follow-up."
        row["text"] = quote
        proof = row["context_evidence"]["primary"]
        proof["claim_fingerprint"] = claims.fingerprint(quote)
        proof["observations"] = {field: {"mode": "literal", "scope": "section", "quote": intro}
                                 for field in claims.PROSE_CONTEXT_KEYS}
        self.assertEqual(self.validate(row, intro+"\n\n"+quote), [])
        self.assertTrue(self.validate(row, quote+"\n\n"+intro))

    def test_repeated_sentence_cannot_share_a_binding_across_subgroups(self):
        quote = "Heart-failure admission had a hazard ratio of 1.42 (95% CI, 1.10 to 1.83)."
        anchor = "Adults, exposed versus unexposed, adjusted model, long-term follow-up."
        body = "# Results\n\n## Discovery\n\n"+anchor+"\n\n"+quote+"\n\n## Validation\n\nChildren were evaluated separately.\n\n"+quote
        row = self.row(quote)
        proof = row["context_evidence"]["primary"]
        proof["observations"] = {field: {"mode": "literal", "scope": "section", "quote": anchor}
                                 for field in claims.PROSE_CONTEXT_KEYS}
        self.assertIn("ambiguous", str(self.validate(row, body)))
        row["section"] = ["Results", "Discovery"]
        self.assertIn("lacks a source-bound claim", str(self.validate(row, body)))
        second = json.loads(json.dumps(row)); second["section"] = ["Results", "Validation"]
        atomic_json(self.project/"07_manuscript/claim_bindings.json", {"schema_version": 1, "claims": [row, second]})
        self.assertTrue(claims.validate_prose(self.project, self.rel, body))

    def test_identical_sentences_require_individual_occurrences(self):
        quote = self.quote
        row = self.row(); body = "# Results\n\n"+quote+"\n\n"+quote
        self.assertIn("ambiguous", str(self.validate(row, body)))
        row["section"] = ["Results"]; row["occurrence"] = 1
        second = json.loads(json.dumps(row)); second["occurrence"] = 2
        atomic_json(self.project/"07_manuscript/claim_bindings.json", {"schema_version": 1, "claims": [row, second]})
        self.assertEqual(claims.validate_prose(self.project, self.rel, body), [])

    def test_assembly_keeps_identical_abstract_and_results_as_two_located_claims(self):
        results = self.row(); abstract = self.row(); abstract["path"] = "07_manuscript/abstract.md"
        atomic_json(self.project/"07_manuscript/claim_bindings.json", {"schema_version": 1, "claims": [results, abstract]})
        body = "# Abstract\n\n"+self.quote+"\n\n# Results\n\n"+self.quote
        payload = claims.assembled_bindings(self.project, body)
        derived = [row for row in payload["claims"] if row["path"] == "07_manuscript/full_manuscript.md"]
        self.assertEqual(len(derived), 2)
        self.assertEqual({tuple(row["section"]) for row in derived}, {("Abstract",), ("Results",)})
        atomic_json(self.project/"07_manuscript/claim_bindings.json", payload)
        self.assertEqual(claims.validate_prose(self.project, "07_manuscript/full_manuscript.md", body), [])

    def test_assembly_parent_chapter_locator_keeps_real_nested_context(self):
        results = self.row(); abstract = self.row(); abstract["path"] = "07_manuscript/abstract.md"
        atomic_json(self.project/"07_manuscript/claim_bindings.json", {"schema_version": 1, "claims": [results, abstract]})
        body = "# Abstract\n\n## Results\n\n"+self.quote+"\n\n# Results\n\n## Primary analysis\n\n"+self.quote
        payload = claims.assembled_bindings(self.project, body)
        atomic_json(self.project/"07_manuscript/claim_bindings.json", payload)
        self.assertEqual(claims.validate_prose(self.project, "07_manuscript/full_manuscript.md", body), [])

    def test_abstract_anchor_cannot_certify_main_results_context(self):
        self.rel = "07_manuscript/full_manuscript.md"
        row = self.row()
        quote = "Heart-failure admission had a hazard ratio of 1.42 (95% CI, 1.10 to 1.83)."
        anchor = "Adults exposed versus unexposed, adjusted model, long-term follow-up."
        row["text"] = quote
        proof = row["context_evidence"]["primary"]
        proof["claim_fingerprint"] = claims.fingerprint(quote)
        proof["observations"] = {field: {"mode": "literal", "scope": "section", "quote": anchor}
                                 for field in claims.PROSE_CONTEXT_KEYS}
        body = "# Abstract\n\n"+anchor+"\n\n# Results\n\n"+quote
        self.assertTrue(self.validate(row, body))

    def test_changed_claim_or_finding_invalidates_only_its_readback(self):
        row = self.row()
        row["text"] = self.quote.replace("Among", "In")
        self.assertIn("fingerprint", str(self.validate(row)))
        row = self.row()
        self.export["primary"]["values"]["extra"] = 9.5
        self.save_sources()
        self.assertIn("fingerprint", str(self.validate(row)))
        self.assertEqual(self.state.load().current, "S09_results")

    def test_unrelated_fact_or_export_whitespace_does_not_expire_a_valid_readback(self):
        row = self.row()
        self.export["population"]["values"] = {"estimate": 5.8}
        self.save_sources()
        source = self.project/"03_analysis/results/primary.json"
        source.write_text(json.dumps(self.export, indent=5), encoding="utf-8")
        self.assertEqual(self.validate(row), [])

    def test_nonliteral_context_requires_real_scoped_executor_observation(self):
        row = self.row()
        proof = row["context_evidence"]["primary"]
        proof["observations"]["model"] = {"mode": "pending", "reason": "Cannot resolve this model yet"}
        self.assertIn("pending", str(self.validate(row)))
        proof["observations"]["model"] = {"mode": "read_back", "reviewer": "executor", "scope": "claim",
            "quote": "the adjusted model", "interpretation": "The reported contrast comes from the adjusted primary analysis.",
            "reason": "The result object identifies the adjusted model and this sentence explicitly reports that same estimate rather than an unadjusted comparison."}
        self.assertEqual(self.validate(row), [])

    def test_legitimate_model_shorthand_uses_readback_without_full_model_in_prose(self):
        context = {**self.context, "model": "Cox model adjusted for age, sex and cirrhosis"}
        self.context = context; self.export["primary"]["context"] = context; self.catalog["primary"]["context"] = context
        self.save_sources()
        row = self.row()
        row["context_evidence"]["primary"]["observations"]["model"] = {
            "mode": "read_back", "reviewer": "executor", "scope": "claim", "quote": "the adjusted model",
            "interpretation": "The concise adjusted-model phrase denotes the specified primary Cox analysis.",
            "reason": "The executed finding specifies age, sex and cirrhosis adjustment; the shorter sentence reports that estimate and does not assert a different covariate set."}
        self.assertEqual(self.validate(row), [])

    def test_explained_source_na_does_not_force_a_followup_sentence(self):
        context = {**self.context, "timepoint": "Not applicable: this controlled finding describes a cross-sectional measurement."}
        self.context = context; self.export["primary"]["context"] = context; self.catalog["primary"]["context"] = context
        self.save_sources()
        quote = self.quote.replace(" over long-term follow-up", "")
        row = self.row(quote)
        del row["context_evidence"]["primary"]["observations"]["timepoint"]
        self.assertEqual(self.validate(row), [])

    def test_old_project_can_opt_into_new_readback_without_state_rewrite(self):
        self.state.data["engine_pin"] = "1.25.0"; self.state.save()
        row = self.row(); self.assertEqual(self.validate(row), [])
        row["context_evidence"]["primary"]["fact_fingerprint"] = "stale"
        self.assertTrue(self.validate(row))
        self.assertEqual(self.state.load().data["engine_pin"], "1.25.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
