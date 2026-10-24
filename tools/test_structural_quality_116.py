"""Synthetic counterexamples for clinical labels, review closure and non-scientific numbering."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from wfcore import registry,reviewrounds as rr,presentationdelta as delta
from wfcore.readiness import atomic_json
from wfcore.state import State
from wfcore import clinicalpresentation as cp,displayrefs
from wfcore.proportions import validate

class StructuralQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="medpaper-structural-quality-"); self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name); self.pipe=registry.load()
        self.state=State(self.project).create("medpaper","1.16.0","S19_human_review")
        self.plan={"main_figures":[],"main_tables":[],"supp_figures":[],"supp_tables":[]}
        self.data("01_protocol/artifact_plan.json",self.plan)
        for rel in ("07_manuscript/full_manuscript.md","05_figures/legends.md","04_tables/table_captions.md"): self.text(rel,"Synthetic clinical presentation only.")
    def text(self,rel,value):
        path=self.project/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(value,encoding="utf-8"); return path
    def data(self,rel,value): atomic_json(self.project/rel,value)
    def dictionary(self):
        self.plan["display_dictionary"]=[{"key":"source_a.endpoint","internal":"Composite A","label":"Clinical endpoint","definition":"Actual source-specific endpoint components","scope":"source_a"}]
        self.data("01_protocol/artifact_plan.json",self.plan)
    def report(self,record,findings=None):
        findings=findings or []
        headings=("Reader comprehension","Medical presentation")
        prose="\n\n".join("## "+h+"\n\n"+"Synthetic reviewer explanation of the actual controlled test content, not an independent medical verdict. "*2+
                              " ".join("[finding:"+r["id"]+"] "+r["text"] for r in findings if r["section"]==h) for h in headings)
        meta={"reviewed_artifacts":record["reviewed_artifacts"],"finding_inventory_complete":True,"findings":findings,
              "section_verdicts":{h:"findings_listed" if any(r["section"]==h for r in findings) else "no_actionable_findings" for h in headings}}
        return self.text("temp/review.md",prose+"\n```json\n"+json.dumps(meta)+"\n```\n")
    def test_clinical_layer_changes_display_not_model_keys(self):
        self.dictionary(); self.assertEqual(cp.label("source_a.endpoint",self.project),"Clinical endpoint")
        self.assertEqual(cp.label("unrelated outcome",self.project),"unrelated outcome")
        self.assertEqual(self.plan["display_dictionary"][0]["internal"],"Composite A")
    def test_same_code_different_sources_needs_scope(self):
        self.dictionary(); self.plan["display_dictionary"].append({"key":"source_b.endpoint","internal":"Composite A","label":"Different clinical endpoint","definition":"Different actual source components","scope":"source_b"}); self.data("01_protocol/artifact_plan.json",self.plan)
        with self.assertRaises(ValueError): cp.label("Composite A",self.project)
        self.assertEqual(cp.label("Composite A",self.project,scope="source_b"),"Different clinical endpoint")
    def test_new_production_assumptions_are_early_but_not_journal_selection(self):
        self.assertTrue(cp.verify_plan(self.project))
        self.plan["presentation_profile"]={"figure_font_pt_min":8,"column_width_mm_single":90,"number_format":{"thousands":","},"basis":"Reversible project publication-size assumptions, not journal requirements."}
        self.data("01_protocol/artifact_plan.json",self.plan); self.assertEqual(cp.verify_plan(self.project),[])
        self.assertFalse((self.project/"08_submission/target_journal.json").exists())
    def test_journal_overrides_need_actual_source_and_dimensions(self):
        self.data("08_submission/integration/artifact_plan.json",self.plan)
        self.data("08_submission/target_journal.json",{"figure_requirements":{"figure_font_pt_min":9}})
        with self.assertRaises(ValueError): cp.profile(self.project,True)
        self.data("08_submission/target_journal.json",{"figure_requirements":{"figure_font_pt_min":9,"figure_font_pt_max":12,"column_width_mm_single":85},"figure_rule_source":"https://example.org/author-guide"})
        self.assertEqual(cp.profile(self.project,True)["column_width_mm_single"],85)
    def test_flowchart_has_no_invented_axis_requirement(self):
        import tomllib
        from figures.qc import _archetype_checks
        registry_file=Path(__file__).parents[1]/"reference/archetypes.toml"
        archive=tomllib.loads(registry_file.read_text(encoding="utf-8"))
        found={key:{"found":True,"evidence":"Observed controlled synthetic elements"} for key in ("box_nodes","figure_statistics")}
        found["axis_labels"]={"found":False,"evidence":"Axis-free flowchart"}
        flow=_archetype_checks("flow_diagram",found,archive)
        self.assertFalse(any(r["name"]=="element:axis_labels" for r in flow))
        self.assertFalse(any(not r["ok"] and r["severity"]=="fail" for r in flow))
        self.assertTrue(any(r["name"]=="element:axis_labels" for r in _archetype_checks("forest_plot",found,archive)))
    def test_numbered_upload_label_not_an_unregistered_measurement(self):
        from wfcore.checks.numbers import _scrub,NUM_RE
        tokens=NUM_RE.findall(_scrub("See Online Resource 2. There were 159 reports and 64.2% with the outcome."))
        self.assertEqual(tokens,["159","64.2"])
    def test_publication_alias_cannot_rename_a_scientific_value(self):
        target={"display_reference_aliases":{"Online Resource 2":"supplementary_methods"},"display_reference_rule_source":"official test guide"}
        self.data("08_submission/target_journal.json",target)
        self.assertEqual(delta.canonical("See Supplementary Methods.",self.project),delta.canonical("See Online Resource 2.",self.project))
        self.assertNotEqual(delta.canonical("Risk was 2.0",self.project),delta.canonical("Risk was 3.0",self.project))
        with self.assertRaises(ValueError): displayrefs.aliases({"display_reference_aliases":{"159 patients":"supplementary_methods"},"display_reference_rule_source":"test"})
    def test_heading_roles_support_journal_statement_order(self):
        from wfcore.journalspec import aliases
        self.assertEqual(aliases({"main_text_headings":{"Declarations and Statements":"Statements and Declarations"}})["Declarations and Statements"],"Statements and Declarations")
    def test_percentage_arithmetic_uses_real_fact_denominator(self):
        catalog={"female":{"values":{"women":102,"available":159},"context":{"percentage_basis":"Reports with known sex, same eligibility and period"}}}
        claim={"fact_ids":["female"],"proportions":[{"fact_id":"female","numerator_key":"women","denominator_key":"available","reported":"64.2%"}]}
        self.assertEqual(validate(claim,catalog,"Women accounted for 64.2%."),[])
        self.assertTrue(validate({**claim,"proportions":[{**claim["proportions"][0],"reported":"36.2%"}]},catalog,"Women accounted for 36.2%."))
    def test_same_sentence_percentage_bases_cannot_silently_differ(self):
        catalog={"a":{"values":{"n":102,"d":159},"context":{"percentage_basis":"Known sex records"}},"b":{"values":{"n":102,"d":282},"context":{"percentage_basis":"All eligible records"}}}
        claim={"fact_ids":["a","b"],"proportions":[{"fact_id":k,"numerator_key":"n","denominator_key":"d","reported":p} for k,p in (("a","64.2%"),("b","36.2%"))]}
        self.assertTrue(validate(claim,catalog,"64.2% versus 36.2%."))
        reason="The first percentage uses known-sex records; the second includes records with missing sex."
        claim["different_percentage_bases"]=reason
        self.assertEqual(validate(claim,catalog,"64.2% versus 36.2%. "+reason),[])
    def test_comprehension_finding_not_in_priority_list_still_needs_resolution(self):
        record=rr.start(self.project,"manuscript")
        finding={"id":"C1","section":"Reader comprehension","text":"The synthetic endpoint code needs its clinical definition.","locator":"Figure label","category":"objective","affects_science":False}
        rr.attach(self.project,"manuscript",self.report(record,[finding]))
        with self.assertRaises(ValueError): rr.close(self.project,"manuscript",[],[])
        self.text("07_manuscript/full_manuscript.md","The endpoint is now named in ordinary clinical language in this synthetic fixture.")
        rr.close(self.project,"manuscript",[["07_manuscript/full_manuscript.md","Clarified actual endpoint label"]],[],resolutions={"C1":{"status":"fixed","files":["07_manuscript/full_manuscript.md"],"reason":"Replaced the synthetic code with its explicit clinical label."}})
        self.assertEqual(rr.latest(self.project,"manuscript")["finding_resolutions"]["C1"]["status"],"fixed")
    def test_review_prose_marker_cannot_be_omitted_from_inventory(self):
        record=rr.start(self.project,"manuscript"); path=self.report(record)
        path.write_text(path.read_text()+"\n[finding:UNLISTED] This is an omitted actionable issue.\n",encoding="utf-8")
        with self.assertRaises(ValueError): rr.attach(self.project,"manuscript",path)
    def test_producer_only_fix_needs_current_scoped_proof(self):
        from wfcore.reviewfindings import close
        from wfcore.determinism import receipt
        rel="03_analysis/code/producer.py"
        path=self.text(rel,"# Synthetic producer correction; no real study data\n")
        record={"before":{},"started_at":"2026-10-24T01:00:00+00:00","findings":[{"id":"C1"}]}
        proof={"status":"complete","completed_at":"2026-10-23T01:00:00+00:00","validation":{"ok":True,"results":[{"fixture":True}]},"items":[{"changed_files":[receipt(path,rel)]}]}
        self.data(".wf/revisions/R001.json",proof)
        resolutions={"C1":{"status":"fixed","reason":"The actual source producer was corrected and validated.","files":[rel],"revision_round":"R001"}}
        with self.assertRaises(ValueError): close(record,{},[],[],resolutions,self.project)
        proof["completed_at"]="2026-10-24T02:00:00+00:00"; self.data(".wf/revisions/R001.json",proof)
        self.assertEqual(close(record,{},[],[],resolutions,self.project),resolutions)
        path.write_text("# Synthetic untracked drift\n",encoding="utf-8")
        with self.assertRaises(ValueError): close(record,{},[],[],resolutions,self.project)
    def test_downstream_material_is_not_an_analysis_input(self):
        from analysis.results import is_scientific_input
        self.assertTrue(is_scientific_input("02_data/processed/cohort.csv"))
        for rel in ("07_manuscript/methods.md","05_figures/legends.md","01_protocol/artifact_plan.json","01_protocol/display_review.json"):
            self.assertFalse(is_scientific_input(rel),rel)
    def test_later_review_defaults_to_delta_and_keeps_complete_context(self):
        record=rr.start(self.project,"manuscript"); rr.attach(self.project,"manuscript",self.report(record)); rr.close(self.project,"manuscript",[],[]); rr.decide(self.project,"manuscript","another_round","请再审阅修改部分")
        self.text("07_manuscript/full_manuscript.md","Changed synthetic sentence only.")
        later=rr.start(self.project,"manuscript")
        self.assertEqual(later["mode"],"delta"); self.assertIn("05_figures/legends.md",later["before"])
    def test_preview_does_not_mutate_approval_or_state(self):
        self.state.data["current"]="S24_package_human_review"; self.state.save()
        self.text("08_submission/integration/note.md","Synthetic journal note.")
        path=self.text("temp/plan.json",json.dumps({"feedback_verbatim":"Please format only this synthetic journal note.","interpretation":"Change only the intended presentation and preserve science.","items":[{"kind":"journal-format","change_type":"administrative","request":"Change the journal note display only.","affected_sources":["08_submission/integration/note.md"],"acceptance_criteria":["Scientific facts unchanged"]}]}))
        before=self.state.file.read_bytes()
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name("rework.py")),"preview","--project",str(self.project),"--plan",str(path)],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr); self.assertEqual(self.state.file.read_bytes(),before)
    def test_backend_review_history_is_not_posthoc_transparency(self):
        from wfcore.medicalstyle import diagnose
        self.assertTrue(any(r["kind"]=="revision_history" for r in diagnose("Added after review, after internal review.","paper.md")))
        self.assertFalse(any(r["kind"]=="revision_history" for r in diagnose("This was a post hoc analysis undertaken after the data were examined.","paper.md")))

if __name__=="__main__": unittest.main(verbosity=2)
