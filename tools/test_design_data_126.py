"""Design-adapted existing contracts and independently recounted complex data joins."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wfcore import dataproof
from wfcore.readiness import atomic_json, contract_problems, specific_contract_required
from wfcore.state import State

ROOT = Path(__file__).resolve().parents[1]


def design_contract(design="retrospective cohort"):
    """Explicit synthetic fixture, not a default scientific plan."""
    yes = lambda text: {"applicable": True, "definition": text}
    no = lambda text: {"applicable": False, "reason": text}
    return {
        "population_and_period": {"design": design, "population": "Adults in the synthetic test cohort", "period": "All available synthetic study dates",
                                  "time_origin": yes("First qualifying clinical visit"), "follow_up": yes("From first visit until admission, death or study end")},
        "eligibility": "Synthetic adult eligibility, fixed before reportable analysis.",
        "unit_and_denominators": {"analysis_unit": "patients", "key_fields": ["patient_id"], "denominator_basis": "Unique eligible patients, not joined medication rows"},
        "outcomes": "First hospital admission during the stated follow-up.",
        "models_and_sensitivity": {"primary_analysis": "Estimate adjusted association with first admission", "target_question_or_quantity": "Adjusted hazard ratio for baseline exposure versus reference",
                                   "confounding": yes("Prespecified clinical variables, not univariable p-value selection"),
                                   "sensitivity": no("No additional sensitivity analysis changes the identified study question in this synthetic fixture")},
        "missing_duplicates_outliers": {"missing_data": yes("Keep missing values explicit and use the specified complete-case analysis"),
                                        "duplicates": yes("Resolve repeated patient records using the dated source rule"),
                                        "outliers": no("No numerical exclusion threshold is used; recorded values are retained in this synthetic test")},
        "validation_and_adjudication": "Only the documented source outcome definitions were used.",
        "exploratory_vs_confirmatory": "Primary question fixed; additional findings are exploratory.",
        "evidence_boundaries": "Association does not establish a causal clinical benefit.",
    }


class DesignDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="medpaper-design-data-126-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)

    def text(self, rel, text):
        path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding="utf-8");return path

    def csvs(self):
        self.text("02_data/raw/patients.csv", "patient_id,age\np1,40\np2,50\np3,60\np4,70\n")
        self.text("02_data/raw/medications.csv", "patient_id,medication_id\np1,m1\np1,m2\np2,m3\np9,m9\n")
        self.text("02_data/processed/joined.csv", "patient_id,medication_id\np1,m1\np1,m2\np2,m3\n")
        return {"relationship": "complex_join", "planned_analysis_unit": "patients", "n_rows": 3,
                "join_steps": [{"id":"eligible_medication_join", "operation":"join", "relationship":"one_to_many",
                                "explanation":"Inner join of actual patient and medication records; unmatched units are retained in the audit, not called clinical exclusions.",
                                "inputs":[{"path":"02_data/raw/patients.csv","unit":"patients","unit_key":["patient_id"],"join_key":["patient_id"]},
                                          {"path":"02_data/raw/medications.csv","unit":"medication records","unit_key":["medication_id"],"join_key":["patient_id"],"output_key":["medication_id"]}],
                                "output":{"path":"02_data/processed/joined.csv","unit":"patients","unit_key":["patient_id"]}}]}

    def test_cohort_contract_has_explicit_unit_time_and_inference(self):
        self.assertEqual(contract_problems(self.project, design_contract(), strict=True), [])
        broken=design_contract();broken["population_and_period"]["time_origin"]="N/A"
        self.assertTrue(any("time_origin" in x for x in contract_problems(self.project,broken,strict=True)))
        broken=design_contract();del broken["unit_and_denominators"]["key_fields"]
        self.assertTrue(any("key_fields" in x for x in contract_problems(self.project,broken,strict=True)))

    def test_cross_sectional_and_qualitative_can_explain_na_without_inventing_models(self):
        for design in ("cross-sectional description", "qualitative interview study"):
            contract=design_contract(design)
            for key in ("time_origin","follow_up"):
                contract["population_and_period"][key]={"applicable":False,"reason":"Single observation/interview per participant; no longitudinal risk period is estimated"}
            contract["models_and_sensitivity"].update(primary_analysis="Summarize observed source characteristics or interview themes",
                                                       target_question_or_quantity="Describe the observed population or participants' experiences",
                                                       confounding={"applicable":False,"reason":"No comparative association or causal model is estimated for this descriptive question"})
            self.assertEqual(contract_problems(self.project,contract,strict=True),[])
            contract["models_and_sensitivity"]["confounding"]["reason"]="N/A"
            self.assertTrue(contract_problems(self.project,contract,strict=True))

    def test_legacy_pin_is_not_upgraded_by_engine_refresh(self):
        state=State(self.project).create("medpaper","1.26.0","S06_protocol_final")
        state.data["engine_pin"]="1.25.0";state.save()
        self.assertFalse(specific_contract_required(self.project))
        self.assertEqual(contract_problems(self.project,{"population_and_period":"Previously approved text"}),[])
        state.data["engine_pin"]="1.26.0";state.save()
        self.assertTrue(specific_contract_required(self.project))
        self.assertTrue(contract_problems(self.project,{"population_and_period":"Generic text"}))

    def test_join_recounts_duplicates_unmatched_units_and_final_rows(self):
        analysis=self.csvs();observed=dataproof.observe_join_steps(self.project,analysis)
        self.assertEqual(observed[0]["inputs"][0]["rows"],4)
        self.assertEqual(observed[0]["inputs"][0]["input_units_not_in_output"],2)
        self.assertEqual(observed[0]["inputs"][1]["rows"],4)
        self.assertEqual(observed[0]["inputs"][1]["unique_join_keys"],3)
        self.assertEqual(observed[0]["inputs"][1]["input_units_not_in_output"],1)
        self.assertEqual(observed[0]["output"]["rows"],3)
        self.assertEqual(observed[0]["output"]["unique_units"],2)
        analysis["join_steps"][0]["observed"]=observed[0]
        self.assertEqual(dataproof.join_step_problems(self.project,analysis,required=True),[])
        analysis["join_steps"][0]["observed"]["output"]["unique_units"]=3
        self.assertTrue(dataproof.join_step_problems(self.project,analysis,required=True))

    def test_duplicate_join_keys_cannot_be_declared_many_to_one(self):
        analysis=self.csvs();analysis["join_steps"][0]["relationship"]="many_to_one"
        with self.assertRaisesRegex(ValueError,"duplicate keys"):
            dataproof.observe_join_steps(self.project,analysis)

    def test_row_unit_change_needs_reason_and_contract_reconciliation(self):
        analysis=self.csvs();analysis["join_steps"][0]["output"].update(unit="patient-medication records",unit_key=["patient_id","medication_id"])
        with self.assertRaisesRegex(ValueError,"units differ"):
            dataproof.observe_join_steps(self.project,analysis)
        analysis["unit_change_reason"]="Each patient contributes separate medication records, and denominators are reported by unique patients separately."
        self.assertEqual(dataproof.observe_join_steps(self.project,analysis)[0]["output"]["unique_units"],3)
        atomic_json(self.project/"01_protocol/analysis_contract.json",design_contract())
        analysis["planned_analysis_unit"]="medication records"
        with self.assertRaisesRegex(ValueError,"analysis contract"):
            dataproof.observe_join_steps(self.project,analysis)

    def test_simple_relationship_does_not_require_complex_record(self):
        self.assertEqual(dataproof.join_step_problems(self.project,{"relationship":"one_record_per_analysis_row"},required=False),[])
        self.assertEqual(dataproof.join_step_problems(self.project,{"relationship":"complex_join"},required=False),[])
        self.assertTrue(dataproof.join_step_problems(self.project,{"relationship":"complex_join"},required=True))

    def test_changed_source_or_output_invalidates_observed_counts(self):
        analysis=self.csvs();analysis["join_steps"][0]["observed"]=dataproof.observe_join_steps(self.project,analysis)[0]
        self.text("02_data/raw/medications.csv","patient_id,medication_id\np1,m1\np1,m2\np2,m3\np9,m8\n")
        self.assertTrue(dataproof.join_step_problems(self.project,analysis,required=True))

    def test_each_existing_file_is_counted_once_for_all_unit_and_join_keys(self):
        analysis=self.csvs();reads=[];actual=Path.open
        def observe(path,*args,**kwargs):
            mode=args[0] if args else kwargs.get("mode","r")
            if Path(path).suffix==".csv" and "b" not in mode:reads.append(Path(path).name)
            return actual(path,*args,**kwargs)
        with patch.object(Path,"open",observe):dataproof.observe_join_steps(self.project,analysis)
        self.assertEqual(sorted(reads),["joined.csv","medications.csv","patients.csv"])

    def test_external_join_drift_changes_revision_identity_without_reading_source(self):
        from wfcore import datasources, revision
        outside=tempfile.TemporaryDirectory(prefix="medpaper-join-authorized-126-");self.addCleanup(outside.cleanup)
        source=Path(outside.name)/"patients.csv";source.write_text("patient_id\np1\n",encoding="utf-8")
        unused=Path(outside.name)/"unused.csv";unused.write_text("id\nx\n",encoding="utf-8")
        ref=datasources.register(self.project,"cohort",source,"Author authorizes this synthetic test source only")
        datasources.register(self.project,"unused",unused,"Separate authorized source not used in the current join")
        atomic_json(self.project/dataproof.MANIFEST_REL,{"analysis_dataset":{"relationship":"complex_join","join_steps":[{"inputs":[{"path":ref}],"output":{"path":"02_data/processed/joined.csv"}}]}})
        State(self.project).create("medpaper","1.26.0","S24_package_human_review")
        spec={"allowed_files":[],"checks":[],"validation_stages":[]}
        actual=Path.open
        def prohibit_source_read(path,*args,**kwargs):
            if Path(path).resolve()==source.resolve():raise AssertionError("A pure revision identity must stat, not read the full external source")
            return actual(path,*args,**kwargs)
        with patch("wfcore.paths.repo_root",return_value=self.project/"empty-engine"),patch.object(Path,"open",prohibit_source_read),patch("wfcore.dataproof.observe_join_steps",side_effect=AssertionError("No recount for a presentation identity")):
            first=revision.input_signature(self.project,spec)
            unused.write_text("id\ny\n",encoding="utf-8")
            self.assertEqual(first,revision.input_signature(self.project,spec))
            stat=source.stat();os.utime(source,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000_000))
            self.assertNotEqual(first,revision.input_signature(self.project,spec))
        source.unlink()
        with self.assertRaisesRegex(ValueError,"unavailable"):
            revision.input_signature(self.project,spec)

    def test_cli_generates_actual_count_evidence_and_failed_audit_preserves_manifest(self):
        analysis=self.csvs();manifest={"analysis_dataset":analysis}
        path=self.project/dataproof.MANIFEST_REL;atomic_json(path,manifest)
        run=lambda:subprocess.run([sys.executable,str(ROOT/"tools/data_manifest.py"),"audit-joins","--project",str(self.project)],capture_output=True,text=True,timeout=30)
        result=run();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(path.read_text(encoding="utf-8"));self.assertEqual(dataproof.join_step_problems(self.project,value["analysis_dataset"],required=True),[])
        self.text("02_data/processed/joined.csv","patient_id,medication_id\np1,m1\n")
        before=path.read_bytes();result=run();self.assertEqual(result.returncode,2,result.stdout+result.stderr);self.assertEqual(before,path.read_bytes())

    def test_actual_acquisition_gate_rejects_note_only_new_complex_join(self):
        analysis=self.csvs()
        analysis.update(primary_source_id="patients",excluded_after_acquisition=0,
                        explanation="The actual patient and medication inputs are inner-joined; this note alone cannot prove counts.")
        inventory=dataproof.inventory(self.project,"02_data/raw");digest=dataproof.bundle_sha256(inventory)
        sources=[]
        for sid in ("patients","medications"):
            evidence={"path":f"02_data/raw/{sid}.csv","kind":"delimited_rows"}
            sources.append({"id":sid,"type":"user_provided","locator":f"Authorized synthetic {sid} table","retrieved_at":"2026-11-06T00:00:00+00:00",
                            "source_total_expected":4,"records_requested":4,"records_received":4,"source_total_evidence":evidence,
                            "received_count_evidence":[evidence],"complete":True,"truncation_applied":False,"pagination":{"applicable":False}})
        manifest={"schema_version":1,"requested_scope":dataproof.FULL_SCOPE,"status":"complete",
                  "protocol_population":"All records in the two explicitly authorized synthetic source tables.","acquisition_method":"user_provided",
                  "pilot":{"used":False},"sources":sources,"raw_files":inventory,"acquisition_files":[],"raw_bundle_sha256":digest,"analysis_dataset":analysis}
        atomic_json(self.project/dataproof.MANIFEST_REL,manifest)
        atomic_json(self.project/dataproof.SUMMARY_REL,{"n_rows":3,"source_hash":digest,"acquisition_scope":dataproof.FULL_SCOPE,"acquisition_status":"complete"})
        state=State(self.project).create("medpaper","1.26.0","S04_data")
        self.assertFalse(dataproof.validate(self.project,state).ok)
        analysis["join_steps"][0]["observed"]=dataproof.observe_join_steps(self.project,analysis)[0]
        atomic_json(self.project/dataproof.MANIFEST_REL,manifest)
        result=dataproof.validate(self.project,state);self.assertTrue(result.ok,result.problems)
        del analysis["join_steps"]
        atomic_json(self.project/dataproof.MANIFEST_REL,manifest)
        self.assertFalse(dataproof.validate(self.project,state).ok)
        state.data["engine_pin"]="1.25.0";state.save()
        result=dataproof.validate(self.project,state);self.assertTrue(result.ok,result.problems)


if __name__ == "__main__":unittest.main(verbosity=2)
