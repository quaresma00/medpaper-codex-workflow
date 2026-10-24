"""Synthetic behavior tests; no real study approvals or source evidence are fabricated."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from wfcore import registry, studypolicy, reviewrounds as rr
from wfcore.checks import Ctx,get,load_all
from wfcore.readiness import atomic_json
from wfcore.packagefreeze import _sha256
from wfcore.state import State
from wfcore.qualitylimits import legend_limit
from wfcore.sourceclaims import mask

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="medpaper-policy-test-"); self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name); self.pipe=registry.load(); load_all()
        self.state=State(self.project).create("medpaper",self.pipe.meta["version"],"S19_human_review")
    def text(self,rel,text):
        p=self.project/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding="utf-8"); return p
    def data(self,rel,data): atomic_json(self.project/rel,data); return self.project/rel
    def ctx(self,name,stage="S03_protocol",**spec): return get(name)(Ctx(self.pipe,self.state,self.project,self.pipe.stage(stage),spec))
    def public_context(self):
        policy=self.text("02_data/policy.txt","Synthetic fixture policy: this anonymous public test source requires no additional review or consent. Redistribution is prohibited.")
        source={"name":"Synthetic public source","type":"public_database","identifiability":"anonymous","access":"official fixture repository","third_party":True,"redistribution":"prohibited",
                "ethics_applicability":"not_required_by_applicable_policy","consent_applicability":"not_required_by_applicable_policy","applicability_reason":"The documented test policy applies specifically to this anonymous secondary use.",
                "policy_evidence":[{"source":"https://example.org/policy","retrieved_at":"2026-10-24","file":"02_data/policy.txt","sha256":_sha256(policy),"excerpt":policy.read_text()}]}
        self.data("01_protocol/idea.json",{"design":"secondary database analysis","research_context":{"jurisdiction":"synthetic local policy","vulnerable_groups":False,"sources":[source]}})
        return source
    def test_order_is_tables_figures_results_then_reconcile(self):
        self.assertEqual([self.pipe.next_of(s).id for s in ("S08_methods","S10_tables","S11_figures","S09_results")],["S10_tables","S11_figures","S09_results","S12_reconcile"])
    def test_unknown_design_source_is_not_inferred(self):
        self.data("01_protocol/idea.json",{})
        self.assertGreaterEqual(len(studypolicy.assess(self.project)["unresolved"]),4)
    def test_upgrade_preserves_results_draft_and_finishes_only_missing_displays(self):
        state=State(self.project).create("medpaper","1.13.0","S09_results")
        path=self.text("07_manuscript/results.md","Existing author draft, preserve verbatim.")
        state.migrate_pipeline("1.14.0",[s.id for s in self.pipe.stages])
        self.assertEqual(state.current,"S10_tables")
        self.assertEqual(path.read_text(),"Existing author draft, preserve verbatim.")
    def test_public_policy_derives_restricted_availability_without_asking_author(self):
        self.public_context(); self.assertEqual(studypolicy.assess(self.project)["unresolved"],[])
        generated=studypolicy.declarations(self.project)
        self.assertIn("cannot be redistributed",generated["data_availability"])
        self.assertNotIn("reasonable request",generated["data_availability"])
    def test_mixed_clinical_data_not_exempted_by_public_source(self):
        source=self.public_context(); data=json.loads((self.project/"01_protocol/idea.json").read_text())
        data["research_context"]["sources"].append({**source,"name":"Clinical validation","type":"existing_records","identifiability":"coded"})
        self.data("01_protocol/idea.json",data)
        self.assertTrue(any("Clinical validation" in x for x in studypolicy.assess(self.project)["unresolved"]))
    def test_changed_policy_invalidates_assessment(self):
        self.public_context(); studypolicy.save(self.project)
        self.text("02_data/policy.txt","Changed policy")
        self.assertFalse(self.ctx("study_governance").ok)
    def test_statistical_plan_cannot_hide_primary_family(self):
        self.data("01_protocol/analysis_contract.json",{"statistical_reporting":{"primary_comparisons":True}})
        self.assertFalse(self.ctx("statistical_reporting_plan").ok)
        self.data("01_protocol/analysis_contract.json",{"statistical_reporting":{"primary_comparisons":2,"multiplicity":"Holm adjustment for the two primary comparisons.","effect_measures":"Report the odds ratio for each primary endpoint.","intervals":"Report two-sided 95% confidence intervals.","exploratory_labeling":"Secondary analyses are explicitly exploratory."}})
        self.assertTrue(self.ctx("statistical_reporting_plan").ok)
    def test_crosswalk_requires_actual_semantics(self):
        self.data("01_protocol/analysis_contract.json",{"variable_definitions":[{"source_field":"x"}]})
        self.assertFalse(self.ctx("variable_definitions").ok)
        base={"source_field":"source_column","definition":"Explicit source-codebook definition","unit":"person","coding":"source coding mapped without ambiguity","time_window":"baseline record","missing_rule":"Preserve source missing values","source_locator":"Synthetic codebook section 2"}
        self.data("01_protocol/analysis_contract.json",{"variable_definitions":[{**base,"role":"eligibility"},{**base,"role":"outcome"}]})
        self.assertTrue(self.ctx("variable_definitions").ok)
    def test_spotcheck_is_not_count_only(self):
        self.data("03_analysis/results/dataset_summary.json",{"source_record_check":{"eligible_records":100,"cases":[{}]*10}})
        self.assertFalse(self.ctx("source_record_spotcheck",stage="S05_analysis").ok)
        source=self.text("02_data/raw/test.csv","id,outcome\n1,0\n2,1\n3,0\n")
        derived=self.text("02_data/derived/test.csv",source.read_text())
        cases=[{"record_locator":f"synthetic row {i}","source_file":"02_data/raw/test.csv","source_sha256":_sha256(source),"derived_file":"02_data/derived/test.csv","derived_sha256":_sha256(derived),"comparisons":[{"variable":"outcome","source_value":v,"derived_value":v}]} for i,v in ((1,0),(2,1),(3,0))]
        check={"eligible_records":3,"selection_basis":"All three synthetic records, preserving zero and event states.","reviewer":"Controlled synthetic test","checked_at":"2026-10-24","cases":cases}
        self.data("03_analysis/results/dataset_summary.json",{"source_record_check":check})
        self.assertTrue(self.ctx("source_record_spotcheck",stage="S05_analysis").ok)
        self.text("02_data/derived/test.csv","changed")
        self.assertFalse(self.ctx("source_record_spotcheck",stage="S05_analysis").ok)
    def test_reference_count_is_advisory_but_unused_entries_need_reason(self):
        self.text("07_manuscript/full_manuscript.md","# Synthetic\n\nNo cited sources in this test.")
        self.assertFalse(self.ctx("manuscript_size_health",stage="S17_assemble").blocking)
        self.data("06_refs/library.json",{"entries":[{"citekey":"unused"}]})
        self.assertFalse(self.ctx("reference_usage",stage="S17_assemble").ok)
    def test_default_legend_cap_absent_official_cap_binds(self):
        self.assertIsNone(legend_limit(self.project))
        self.data("08_submission/submission_requirements.json",{"article_type":"original","figure_legend_words":{"status":"recommended","value":80,"source":"official test guide"}})
        self.assertIsNone(legend_limit(self.project))
        self.data("08_submission/submission_requirements.json",{"article_type":"original","figure_legend_words":{"status":"required","value":80,"source":"official test guide"}})
        self.assertEqual(legend_limit(self.project),80)
        self.text("05_figures/legends.md","# Figure legends\n\n## Figure 1\n"+"Necessary decoding information. "*90)
        self.assertFalse(self.ctx("legend_length_advice",stage="S07_artifacts").blocking)
        self.assertTrue(self.ctx("legend_length_advice",stage="S24_package_human_review").blocking)
    def test_prior_numeric_comparison_needs_its_own_source(self):
        _,problems=mask(self.project,"07_manuscript/discussion.md","A previous study reported risk 2.3 [@prior].")
        self.assertTrue(problems)
    def test_exact_cited_source_does_not_whitelist_other_values(self):
        full=self.text("06_refs/fulltext/prior.html","<html>In the synthetic source cohort the risk ratio was 2.3.</html>")
        passage="The prior synthetic cohort reported a risk ratio of 2.3 [@prior]."
        self.data("06_refs/library.json",{"entries":[{"citekey":"prior"}]})
        self.data("06_refs/fulltext/retrieval_manifest.json",{"retrievals":[{"citekey":"prior","fulltext":"06_refs/fulltext/prior.html","sha256":_sha256(full),"access":"oa"}]})
        self.data("07_manuscript/claim_bindings.json",{"claims":[],"source_claims":[{"path":"07_manuscript/discussion.md","text":passage,"citekey":"prior","fulltext":"06_refs/fulltext/prior.html","sha256":_sha256(full),"locator":"Synthetic source Results first paragraph","excerpt":"In the synthetic source cohort the risk ratio was 2.3.","support":"Same endpoint and comparison in this controlled test only."}]})
        with patch("wfcore.refproof.validate_local_proof",return_value=(True,[],{})),patch("pubmed.identity.errors",return_value=[]):
            self.assertEqual(mask(self.project,"07_manuscript/discussion.md",passage)[1],[])
            self.assertTrue(mask(self.project,"07_manuscript/discussion.md",passage+"\n\nAnother risk was 9.8 [@prior].")[1])
            self.text("06_refs/fulltext/prior.html","Tampered source")
            self.assertTrue(mask(self.project,"07_manuscript/discussion.md",passage)[1])
    def test_legacy_number_allowlist_is_closed(self):
        from wfcore.checks.numbers import _allowlist
        self.text("03_analysis/results/number_allowlist.tsv","9.8\tFor convenience invented value\n")
        ctx=Ctx(self.pipe,self.state,self.project,self.pipe.stage("S08_methods"),{})
        self.assertNotIn("9.8",_allowlist(ctx))
    def test_review_kept_science_requires_actual_author_adjudication(self):
        from test_review_rounds import ReviewRoundTests
        self.data("01_protocol/artifact_plan.json",{"main_figures":[],"main_tables":[]})
        for rel in ("07_manuscript/full_manuscript.md","05_figures/legends.md","04_tables/table_captions.md"): self.text(rel,"Synthetic content only.")
        record=rr.start(self.project,"manuscript")
        report=self.text("temp/review.md","# Synthetic reviewer\n\n## Reader comprehension\n\n"+"Synthetic substantive review content. "*5+"\n\n## Medical presentation\n\n"+"Synthetic substantive review content. "*5+"\n```json\n"+json.dumps({"reviewed_artifacts":record["reviewed_artifacts"],"findings":[{"id":"N1","category":"numbers","affects_science":True}]})+"\n```\n")
        rr.attach(self.project,"manuscript",report)
        with self.assertRaises(ValueError): rr.close(self.project,"manuscript",[],[["N1","Prefer the current number"]])
        rr.close(self.project,"manuscript",[],[],1)
        with self.assertRaises(ValueError): rr.decide(self.project,"manuscript","no_further_review","我确认这一版")

    def test_external_copy_is_optional_readonly_and_excludes_engine_facts(self):
        from wfcore.reviewexport import export
        self.data("01_protocol/artifact_plan.json",{"main_figures":[],"main_tables":[]})
        self.data("01_protocol/study_facts.json",{"internal_fact":"not for an external reader"})
        for rel in ("07_manuscript/full_manuscript.md","05_figures/legends.md","04_tables/table_captions.md"): self.text(rel,"Synthetic only.")
        self.assertFalse((self.project/".wf/external_review").exists())
        folder=export(self.project,"manuscript","请制作一份供第三方审阅的只读版本")
        self.assertTrue((folder/"变更说明.md").is_file())
        self.assertFalse((folder/"01_protocol/study_facts.json").exists())
        import stat
        self.assertFalse((folder/"07_manuscript/full_manuscript.md").stat().st_mode & stat.S_IWUSR)
        for file in folder.rglob("*"):
            if file.is_file(): file.chmod(file.stat().st_mode | stat.S_IWUSR)

if __name__=="__main__": unittest.main(verbosity=2)
