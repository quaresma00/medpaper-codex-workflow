"""Synthetic display-free Discussion drafting and source-bound outline behavior."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wfcore import discussion, buildproof, dependencies, registry, revision
from wfcore.readiness import atomic_json
from wfcore.state import State

ROOT = Path(__file__).resolve().parents[1]
OUTLINE = """- Principal finding: The association warrants cautious interpretation in this clinical population.
- Comparison with prior work and reasons for differences: Compare the different eligibility and exposure assessment with the selected cohort.
- Possible mechanisms: The data cannot test the proposed biological explanation.
- Clinical implications: The finding supports further evaluation rather than a change in prescribing.
- Limitations and direction of bias: Residual confounding may persist, with an uncertain net direction.
- Conclusion: Describe an association without claiming that treatment prevents admission.
"""


class DiscussionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="medpaper-discussion-127-")
        self.addCleanup(self.tmp.cleanup); self.project = Path(self.tmp.name)
        self.state = State(self.project).create("medpaper", "1.27.0", "S16_discussion")
        atomic_json(self.project/"01_protocol/study_facts.json", {
            "main_finding": "Higher serum phosphate was associated with admission for heart failure (Table 2).",
            "clinical_relevance": "The association requires evaluation before it could guide care.",
            "cannot_claim": "The observational design does not establish benefit from phosphate lowering."})
        self.notes = """# Study notes
## Discussion points
The selected cohort used a different definition of chronic exposure (Figure S2).
| Variable | Number |
|---|---|
| Raw display row | 800 |
## Possible mechanisms
Phosphate may reflect nutritional status and illness severity; this study cannot test that explanation.
## Limitations
Residual confounding may remain, but its overall direction cannot be determined from these data.
"""
        self.text("03_analysis/notes.md", self.notes)
        self.text("06_refs/deepread/previous.md", """# previous
## Their key numbers
9999 prior-study numbers deliberately not handed to the writer.
## How this supports or contradicts our finding
The earlier cohort used a shorter exposure window and different eligibility criteria (Table S1).
""")
        atomic_json(self.project/"06_refs/deepread/deepread_index.json", {"selected": [{"citekey": "previous", "notes": "06_refs/deepread/previous.md"}]})
        self.results = ("The adjusted hazard ratio for heart-failure admission was 1.42 with a 95% confidence interval "
                        "from 1.10 to 1.83 in the eligible cohort during long-term follow-up.")
        self.text(discussion.RESULTS, "# Results\n\n" + self.results)
        self.draft = """# Discussion

Higher serum phosphate was associated with heart-failure admission.

The earlier cohort used a shorter exposure window [@previous]. This difference may alter which patients are classified as chronically exposed and could explain the contrast between studies.

The association may reflect underlying illness severity, but the observational design cannot distinguish that explanation from a biological effect. These findings therefore do not establish that phosphate lowering would prevent admission. Residual confounding may remain and its net direction is uncertain.
"""

    def text(self, rel, value):
        path = self.project/rel; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8"); return path

    def prepare(self):
        discussion.prepare(self.project)
        self.text(discussion.OUTLINE, OUTLINE)
        discussion.bind_outline(self.project)
        self.text(discussion.DISCUSSION, self.draft)

    def test_materials_are_real_plain_text_without_displays_or_internal_paths(self):
        discussion.prepare(self.project)
        packet = (self.project/discussion.MATERIALS).read_text(encoding="utf-8")
        self.assertIn("Higher serum phosphate", packet)
        self.assertIn("[@previous]", packet)
        self.assertNotIn("Table 2", packet); self.assertNotIn("Figure S2", packet)
        self.assertNotIn("Raw display row", packet); self.assertNotIn("800", packet)
        self.assertNotIn("9999", packet)
        self.assertEqual(discussion.material_problems(packet), [])
        sources = buildproof.load(self.project)[discussion.MATERIALS]["sources"]
        self.assertFalse(any(x in source for source in sources for x in ("04_tables", "05_figures")))
        self.assertIn(str((self.project/discussion.RESULTS).resolve()), sources)
        self.assertNotIn(self.results, packet)

    def test_missing_mechanism_note_is_not_filled_with_invented_science(self):
        discussion.prepare(self.project); before = (self.project/discussion.MATERIALS).read_bytes()
        self.text("03_analysis/notes.md", self.notes.replace("## Possible mechanisms\nPhosphate may reflect nutritional status and illness severity; this study cannot test that explanation.\n", ""))
        with self.assertRaisesRegex(ValueError, "Possible explanations"):
            discussion.prepare(self.project)
        self.assertEqual((self.project/discussion.MATERIALS).read_bytes(), before)

    def test_json_result_dump_is_not_a_plain_language_finding(self):
        path = self.project/"01_protocol/study_facts.json"
        facts = json.loads(path.read_text(encoding="utf-8"))
        facts["main_finding"] = {"estimate": 1.42, "analysis_id": "model_primary"}
        atomic_json(path, facts)
        with self.assertRaisesRegex(ValueError, "plain-language narrative"):
            discussion.prepare(self.project)
        self.assertFalse((self.project/discussion.MATERIALS).exists())

    def test_complete_short_outline_and_argument_pass_without_paper_subheadings(self):
        self.prepare()
        errors, warnings = discussion.check(self.project)
        self.assertEqual(errors, []); self.assertEqual(warnings, [])
        self.assertEqual(discussion.outline_problems(OUTLINE), [])
        self.assertNotIn("##", self.draft)

    def test_missing_outline_point_and_generic_na_do_not_count_as_complete(self):
        self.assertTrue(discussion.outline_problems(OUTLINE.replace("- Clinical implications: The finding supports further evaluation rather than a change in prescribing.\n", "")))
        self.assertTrue(discussion.outline_problems(OUTLINE.replace("The data cannot test the proposed biological explanation.", "N/A")))
        self.assertEqual(discussion.outline_problems(OUTLINE), [])

    def test_outline_cannot_reintroduce_result_displays_into_writer_context(self):
        self.assertTrue(discussion.outline_problems(OUTLINE + "\nSee Table 2 for exact results.\n"))
        self.assertTrue(discussion.outline_problems(OUTLINE + "\n| Group | Result |\n| Trial | 42 |\n"))
        self.assertTrue(discussion.outline_problems(OUTLINE + "\n```python\nprint('result')\n```\n"))

    def test_changed_material_sources_invalidate_only_relevant_writing_context(self):
        self.prepare()
        self.text("03_analysis/notes.md", self.notes + "\nAdditional supported limitation.\n")
        errors, _ = discussion.check(self.project)
        self.assertTrue(any(x["kind"] == "materials_stale" for x in errors))
        self.assertEqual(self.state.load().current, "S16_discussion")

    def test_changed_outline_is_not_silently_certified(self):
        self.prepare()
        self.text(discussion.OUTLINE, OUTLINE.replace("further evaluation", "external validation"))
        errors, _ = discussion.check(self.project)
        self.assertTrue(any(x["kind"] == "outline_stale" for x in errors))
        discussion.bind_outline(self.project)
        self.assertEqual(discussion.check(self.project)[0], [])

    def test_results_change_requires_readback_but_unchanged_summary_reuses_outline(self):
        self.prepare()
        original_outline = (self.project/discussion.OUTLINE).read_bytes()
        self.text(discussion.RESULTS, "# Results\n\n" + self.results + "\n\nAn additional source-supported result was clarified.")
        self.assertTrue(any(x["kind"] == "materials_stale" for x in discussion.check(self.project)[0]))
        discussion.prepare(self.project)
        self.assertEqual(discussion.check(self.project)[0], [])
        self.assertEqual((self.project/discussion.OUTLINE).read_bytes(), original_outline)

    def test_near_whole_results_sentence_is_blocked_but_short_principal_summary_is_allowed(self):
        errors, _ = discussion.diagnose("# Discussion\n\n" + self.results, "# Results\n\n" + self.results)
        self.assertTrue(any(x["kind"] == "results_repetition" for x in errors))
        almost = self.results.replace("adjusted hazard ratio", "estimated hazard ratio")
        self.assertTrue(discussion.diagnose(almost, self.results)[0])
        self.assertEqual(discussion.diagnose(self.draft, self.results)[0], [])

    def test_numerical_results_recap_is_not_excused_by_short_length(self):
        value = "Mean age was 62 years and follow-up was 3 years."
        self.assertTrue(discussion.diagnose(value, value)[0])
        self.assertEqual(discussion.diagnose("The association remained uncertain.", "The association remained uncertain.")[0], [])

    def test_reasonable_few_supplement_references_pass_and_walkthrough_is_blocked(self):
        reasonable = self.draft + "\nThe alternative outcome definition supports the same interpretation (Table S1).\n"
        self.assertEqual(discussion.diagnose(reasonable, self.results)[0], [])
        excessive = ("The first subgroup is shown in Table S1. The second subgroup is shown in Figure S2. "
                     "The third subgroup is shown in Table S3. These observations require further study.")
        self.assertTrue(any(x["kind"] == "supplement_display_walkthrough" for x in discussion.diagnose(excessive, self.results)[0]))

    def test_three_real_explanatory_supplement_references_are_prompts_not_a_quota_failure(self):
        text = ("Residual confounding may explain the difference in the restricted cohort (Table S1). "
                "The contrasting definition suggests measurement error rather than a biological effect (Figure S2). "
                "The clinical interpretation remains limited because surveillance differed across settings (Table S3). "
                "An observational association does not establish treatment benefit.")
        errors, warnings = discussion.diagnose(text, self.results)
        self.assertEqual(errors, []); self.assertTrue(warnings)

    def test_main_results_is_not_confused_with_abstract_results(self):
        combined = "# Title\n\n# Abstract\n\n## Results\n\n" + self.results + "\n\n# Results\n\nA different main result is described here.\n\n# Discussion\n\n" + self.results
        self.assertEqual(discussion.diagnose(combined, combined)[0], [])

    def test_current_journal_aliases_extract_real_separate_chapters(self):
        rel = "08_submission/integration/full_manuscript.md"
        atomic_json(self.project/"08_submission/target_journal.json", {"main_text_headings": {"Results": "Findings", "Discussion": "Interpretation"}})
        composed = "# Title\n\n# Abstract\n\n## Results\n\n" + self.results + "\n\n# Findings\n\nA different main result is described here.\n\n# Interpretation\n\n" + self.results
        self.text(rel, composed)
        self.assertEqual(discussion.check(self.project, discussion_path=rel, results_path=rel, presentation_only=True)[0], [])
        self.text(rel, composed.replace("A different main result is described here.", self.results))
        self.assertTrue(any(x["kind"] == "results_repetition" for x in discussion.check(self.project, discussion_path=rel, results_path=rel, presentation_only=True)[0]))

    def test_same_file_without_separate_chapters_cannot_compare_itself(self):
        rel = "08_submission/integration/full_manuscript.md"
        self.text(rel, "# Results and Discussion\n\n" + self.results)
        with self.assertRaisesRegex(ValueError, "Discussion"):
            discussion.check(self.project, discussion_path=rel, results_path=rel, presentation_only=True)

    def test_legacy_pin_is_preserved_until_explicit_adoption(self):
        self.state.data["engine_pin"] = "1.26.0"; self.state.save()
        self.assertEqual(discussion.check(self.project), ([], []))
        discussion.prepare(self.project)
        self.assertTrue(discussion.enabled(self.project))
        self.assertEqual(self.state.load().data["engine_pin"], "1.26.0")

    def test_actual_cli_order_prepare_outline_then_draft_and_check(self):
        cli = ROOT/"tools/manuscript/discussion.py"
        def run(command):
            return subprocess.run([sys.executable, str(cli), command, "--project", str(self.project)],
                                  cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        prepared = run("prepare"); self.assertEqual(prepared.returncode, 0, prepared.stdout+prepared.stderr)
        self.text(discussion.OUTLINE, OUTLINE)
        outlined = run("outline"); self.assertEqual(outlined.returncode, 0, outlined.stdout+outlined.stderr)
        self.text(discussion.DISCUSSION, self.draft)
        checked = run("check"); self.assertEqual(checked.returncode, 0, checked.stdout+checked.stderr)
        self.assertTrue(json.loads(checked.stdout)["ok"])

    def review_round(self, sources, *, change_type="wording", kind="discussion"):
        self.state.data["current"] = "S19_human_review"; self.state.save()
        return {"schema_version": 2, "review_stage": "S19_human_review", "baseline": revision.snapshot(self.project),
                "items": [{"kind": kind, "owning_stage": "S16_discussion", "change_type": change_type,
                           "affected_sources": sources}]}

    def test_stage_gates_registered_and_read_actual_composed_sections(self):
        from wfcore.checks import get, load_all, Ctx
        load_all(); pipe = registry.load()
        self.assertIsNotNone(get("discussion_ready"))
        for sid, path in (("S16_discussion", discussion.DISCUSSION), ("S17_assemble", "07_manuscript/full_manuscript.md"),
                          ("S22_polish", "08_submission/integration/full_manuscript.md")):
            gate = next(g for g in pipe.stage(sid).gate if g["check"] == "discussion_ready")
            self.assertEqual(gate["since"], "1.27.0")
            if sid != "S16_discussion":
                self.assertEqual(gate["path"], path); self.assertEqual(gate["results_path"], path)
                self.assertTrue(gate["presentation_only"])
        self.prepare()
        stage = pipe.stage("S16_discussion"); spec = next(g for g in stage.gate if g["check"] == "discussion_ready")
        self.assertTrue(get("discussion_ready")(Ctx(pipe, self.state, self.project, stage, spec)).ok)

    def test_packet_and_outline_dependencies_rebuild_writing_not_analysis(self):
        self.prepare()
        for source in (discussion.MATERIALS, discussion.OUTLINE):
            outputs = dependencies.closure(self.project, [source], change_type="wording")
            self.assertIn(discussion.DISCUSSION, outputs)
            self.assertIn("07_manuscript/full_manuscript.md", outputs)
            self.assertNotIn(discussion.RESULTS, outputs)
            self.assertFalse(any(p.startswith(("04_tables/", "05_figures/", "02_data/", "03_analysis/results/")) for p in outputs))

    def test_discussion_wording_allows_context_refresh_without_replaying_analysis(self):
        self.prepare(); pipe = registry.load()
        record = self.review_round([discussion.DISCUSSION])
        revision.plan_scope(self.project, pipe, record)
        self.assertIn(discussion.MATERIALS, record["allowed_files"])
        self.assertIn(discussion.OUTLINE, record["allowed_files"])
        self.assertNotIn("S06_protocol_final", record["validation_stages"])
        self.assertFalse(any(r["spec"]["check"] == "data_acquisition_complete" for r in record["checks"]))
        self.assertNotIn("03_analysis/notes.md", record["allowed_files"])
        before = revision.input_signature(self.project, record)
        self.text(discussion.OUTLINE, OUTLINE + "\nA changed writing outline.\n")
        self.assertNotEqual(before, revision.input_signature(self.project, record))
        self.assertEqual(self.state.load().current, "S19_human_review")

    def test_only_declared_narrative_notes_can_change_without_scientific_route(self):
        self.prepare(); pipe = registry.load()
        original = "# Study notes\n\nUnchanged analysis interpretation boundary.\n\n" + self.notes
        self.text("03_analysis/notes.md", original)
        record = self.review_round(["03_analysis/notes.md", discussion.DISCUSSION])
        revision.plan_scope(self.project, pipe, record)
        self.assertNotIn("S06_protocol_final", record["validation_stages"])
        self.assertFalse(any(r["spec"]["check"] == "data_acquisition_complete" for r in record["checks"]))
        changed = original.replace("its overall direction cannot be determined", "its overall direction remains uncertain")
        self.text("03_analysis/notes.md", changed)
        self.assertEqual(revision.scope_problems(self.project, record), [])
        self.text("03_analysis/notes.md", changed.replace("Unchanged analysis interpretation boundary.", "Changed analysis selection rule."))
        self.assertTrue(any("non-Discussion analysis notes" in p for p in revision.scope_problems(self.project, record)))
        # Replanning must preserve the original outside-section guard, not bless drift.
        guard = record["discussion_notes_guard"]
        revision.plan_scope(self.project, pipe, record)
        self.assertEqual(record["discussion_notes_guard"], guard)
        self.assertTrue(revision.scope_problems(self.project, record))

    def test_other_notes_and_scientific_results_keep_validity_checks(self):
        pipe = registry.load()
        for sources, kind, change in ((["03_analysis/notes.md"], "analysis", "scientific"),
                                      (["03_analysis/results/primary.json"], "discussion", "scientific")):
            record = self.review_round(sources, kind=kind, change_type=change)
            revision.plan_scope(self.project, pipe, record)
            self.assertIn("S06_protocol_final", record["validation_stages"])
            self.assertNotIn("discussion_notes_guard", record)
            self.assertTrue(any(r["spec"]["check"] == "data_acquisition_complete" for r in record["checks"]))

    def test_batch_parser_permits_only_explicit_discussion_wording_notes(self):
        from rework import _read_batch_plan
        pipe = registry.load()
        item = {"kind": "discussion", "change_type": "wording", "request": "Clarify the direction of residual confounding.",
                "affected_sources": ["03_analysis/notes.md", discussion.DISCUSSION],
                "acceptance_criteria": ["Keep the quantitative findings and analysis unchanged."]}
        plan = {"feedback_verbatim": "Please clarify the interpretation of residual confounding.",
                "interpretation": "Revise supported Discussion interpretation without changing the study population or any quantitative analysis.",
                "items": [item]}
        path = self.project/"temp/feedback.json"; atomic_json(path, plan)
        self.assertEqual(_read_batch_plan(path, ["discussion"], "S19_human_review", pipe)["items"][0]["change_type"], "wording")
        item["affected_sources"] = ["03_analysis/results/primary.json"]; atomic_json(path, plan)
        with self.assertRaisesRegex(ValueError, "scientific analysis sources"):
            _read_batch_plan(path, ["discussion"], "S19_human_review", pipe)
        item["kind"] = "methods-wording"; item["affected_sources"] = ["03_analysis/notes.md"]; atomic_json(path, plan)
        with self.assertRaisesRegex(ValueError, "scientific analysis sources"):
            _read_batch_plan(path, ["methods-wording"], "S19_human_review", pipe)


if __name__ == "__main__": unittest.main(verbosity=2)
