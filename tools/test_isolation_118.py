"""Synthetic runtime-retrospective controls: raw references, exact replay and scoped decisions."""
import importlib.util,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from wfcore import datasources as ds,dataproof,medicalstyle
from wfcore.readiness import atomic_json
from wfcore.packagefreeze import _sha256
from wfcore.state import State
from analysis.reproduce import run,replay,verify,PROOFS

ROOT=Path(__file__).resolve().parents[1]


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="medpaper-isolation-"); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.project=self.base/"study"; self.project.mkdir()
        self.state=State(self.project).create("medpaper","1.18.0","S05_analysis")
    def text(self,rel,value):
        path=self.project/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(value,encoding="utf-8"); return path
    def data(self,rel,value): atomic_json(self.project/rel,value)
    def source(self):
        raw=self.base/"authorized.csv"; raw.write_text("value\n1\n2\n",encoding="utf-8")
        ref=ds.register(self.project,"authorized",raw,"The synthetic author authorizes only this exact original data file")
        return raw,ref
    def producer(self,name="primary",input="data:authorized",fail=False):
        script=f"03_analysis/code/{name}.py"
        self.text(script,f'''import json
from pathlib import Path
from analysis.results import write_results
from analysis.datasources import open_data
with open_data({input!r},"r",encoding="utf-8") as handle:
    values=[int(line.strip()) for line in handle.read().splitlines()[1:]]
write_results({name+'.json'!r},{{"count":len(values),"total":sum(values)}},seed=37,inputs=[{input!r}])
'''+("raise RuntimeError('Synthetic genuine producer failure')\n" if fail else ""))
        return script
    def test_external_reference_reads_original_without_copy_or_alias(self):
        raw,ref=self.source(); before=_sha256(raw)
        with ds.open_readonly(self.project,ref,"r",encoding="utf-8") as h: self.assertEqual(h.read(),"value\n1\n2\n")
        self.assertEqual(_sha256(raw),before); self.assertFalse((self.project/"02_data/raw").exists())
        with self.assertRaises(ValueError): ds.open_readonly(self.project,ref,"w")
    def test_unauthorized_traversal_and_other_study_roots_are_refused(self):
        other=self.base/"other"; (other/".wf").mkdir(parents=True); (other/".wf/state.json").write_text("{}")
        with self.assertRaises(ValueError): ds.register(self.project,"other",other,"Synthetic unauthorized other-study root must be refused")
        raw=self.base/"data"; raw.mkdir(); (raw/"x.csv").write_text("x")
        ds.register(self.project,"local",raw,"Synthetic author authorizes this isolated raw directory only")
        for ref in ("data:local/../other/.wf/state.json","data:unregistered/x.csv"):
            with self.assertRaises(ValueError): ds.resolve(self.project,ref)
    def test_registry_does_not_silently_ignore_corruption(self):
        self.text(ds.REGISTRY,"not JSON")
        with self.assertRaises(ValueError): ds.load(self.project)
        self.text(ds.REGISTRY,"[]")
        with self.assertRaises(ValueError): ds.load(self.project)
    def test_raw_manifest_and_actual_counts_include_registered_data(self):
        raw,ref=self.source(); items=dataproof.inventory(self.project,"02_data/raw")
        self.assertEqual(items[0]["path"],ref)
        self.assertEqual(dataproof.evidence_count(self.project,{"path":ref,"kind":"delimited_rows"},{ref}),2)
        raw.write_text("value\n1\n9\n",encoding="utf-8"); problems=[]
        dataproof._same_inventory(items,dataproof.inventory(self.project,"02_data/raw"),"raw_files",problems)
        self.assertTrue(problems)
        from wfcore.checks import Ctx
        from wfcore.checks.fsx import file_count
        from wfcore import registry
        pipe=registry.load(); context=Ctx(pipe,self.state,self.project,pipe.stage("S04_data"),{"glob":"02_data/raw/**","min":1,"include_data_sources":True})
        self.assertTrue(file_count(context).ok)
    def test_full_acquisition_gate_accepts_registered_complete_data_and_rejects_drift(self):
        raw,ref=self.source(); self.data("02_data/raw/count.json",{"total":2})
        inventory=dataproof.inventory(self.project,"02_data/raw"); digest=dataproof.bundle_sha256(inventory)
        manifest={"schema_version":1,"requested_scope":dataproof.FULL_SCOPE,"status":"complete","protocol_population":"Every row in the explicitly authorized synthetic source table.","acquisition_method":"user_provided","pilot":{"used":False},"sources":[{"id":"all","type":"user_provided","locator":"Authorized synthetic data table","retrieved_at":"2026-10-29T00:00:00+00:00","source_total_expected":2,"records_requested":2,"records_received":2,"source_total_evidence":{"path":"02_data/raw/count.json","kind":"json_pointer_integer","pointer":"/total"},"received_count_evidence":[{"path":ref,"kind":"delimited_rows"}],"complete":True,"truncation_applied":False,"pagination":{"applicable":False}}],"raw_files":inventory,"acquisition_files":[],"raw_bundle_sha256":digest,"analysis_dataset":{"primary_source_id":"all","n_rows":2,"excluded_after_acquisition":0,"relationship":"one_record_per_analysis_row"}}
        self.data(dataproof.MANIFEST_REL,manifest)
        self.data(dataproof.SUMMARY_REL,{"n_rows":2,"source_hash":digest,"acquisition_scope":dataproof.FULL_SCOPE,"acquisition_status":"complete"})
        result=dataproof.validate(self.project,self.state); self.assertTrue(result.ok,result.problems)
        raw.write_text("value\n1\n2\n3\n",encoding="utf-8")
        self.assertFalse(dataproof.validate(self.project,self.state).ok)
    def test_python_replay_uses_no_raw_copy_reuses_proof_and_preserves_full_data(self):
        raw,ref=self.source(); script=self.producer(); run(self.project,script)
        actual=shutil.copy2
        def copy(source,destination,*a,**kw):
            self.assertNotEqual(Path(source).resolve(),raw.resolve())
            return actual(source,destination,*a,**kw)
        with patch("analysis.reproduce.shutil.copy2",side_effect=copy): self.assertEqual(replay(self.project),[script])
        self.assertEqual(verify(self.project),[]); self.assertEqual(replay(self.project),[])
        self.assertEqual(raw.read_text(),"value\n1\n2\n")
        self.assertEqual(list((self.project/".wf/replay_sandboxes").glob("run_*")),[])
        self.assertTrue(list((self.project/".wf/processes").glob("*.log")))
    def test_copy_budget_refuses_before_materializing_local_input(self):
        self.text("02_data/raw/input.csv","value\n1\n2\n")
        script=self.text("03_analysis/code/local.py",'''from pathlib import Path
from analysis.results import write_results
write_results("local.json",{"count":2},seed=37,inputs=["02_data/raw/input.csv"])
''')
        run(self.project,script.relative_to(self.project).as_posix())
        with patch("analysis.reproduce.shutil.copy2",side_effect=AssertionError("Budget must fail BEFORE copy")),self.assertRaisesRegex(ValueError,"copy budget"):
            replay(self.project,copy_limit_bytes=1)
    def test_new_producer_and_prose_changes_do_not_force_old_producer_replay(self):
        self.source(); first=self.producer(); run(self.project,first); replay(self.project)
        self.text("02_data/codebook.md","Documentation not consumed by either producer changed.")
        self.assertEqual(replay(self.project),[])
        second=self.producer("added"); run(self.project,second)
        self.assertEqual(replay(self.project),[second]); self.assertEqual(verify(self.project),[])
    def test_downstream_replay_receives_complete_proven_upstream_output(self):
        self.source(); first=self.producer(); run(self.project,first); replay(self.project)
        child="03_analysis/code/downstream.py"
        self.text(child,'''import json
from pathlib import Path
from analysis.results import write_results
r=json.loads(Path("03_analysis/results/primary.json").read_text())
write_results("downstream.json",{"total":r["total"]},seed=37,inputs=["03_analysis/results/primary.json"])
''')
        run(self.project,child); self.assertEqual(replay(self.project),[child]); self.assertEqual(verify(self.project),[])
    def test_changed_raw_data_invalidates_old_proof_without_repaired_boolean(self):
        raw,_=self.source(); script=self.producer(); run(self.project,script); replay(self.project)
        raw.write_text("value\n1\n3\n",encoding="utf-8")
        self.assertTrue(verify(self.project))
    def test_failed_later_producer_cannot_overwrite_previous_replay_proof(self):
        self.source(); first=self.producer(); run(self.project,first); replay(self.project)
        report=(self.project/PROOFS).read_bytes(); saved=json.loads(report)
        retained=self.project/saved["03_analysis/results/primary.json"]["replayed"]; prior=retained.read_bytes()
        with (self.project/first).open("a",encoding="utf-8") as stream: stream.write("# Real source revision in this synthetic fixture\n")
        run(self.project,first)
        bad="03_analysis/code/zzz_unstable.py"
        self.text(bad,'''from pathlib import Path
from analysis.results import write_results
n=2 if Path(".wf/state.json").exists() else 999
write_results("zzz_unstable.json",{"n":n},seed=37,inputs=["data:authorized"])
''')
        run(self.project,bad)
        with self.assertRaisesRegex(ValueError,"replay differs"): replay(self.project)
        self.assertEqual((self.project/PROOFS).read_bytes(),report); self.assertEqual(retained.read_bytes(),prior)
    def test_real_r_reference_writer_and_replay_use_same_original(self):
        if not shutil.which("Rscript"): self.skipTest("Rscript unavailable")
        self.source(); script="03_analysis/code/primary.R"
        self.text(script,'''source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/analysis/results.R"))
d <- read.csv(medpaper_data_path("data:authorized"))
medpaper_write_results("primary.json",list(count=nrow(d),total=sum(d$value)),seed=37,inputs=c("data:authorized"))
''')
        run(self.project,script); self.assertEqual(replay(self.project),[script]); self.assertEqual(verify(self.project),[])
    def test_replay_error_and_interrupt_clear_only_owned_sandbox(self):
        from wfcore.replayjobs import sandbox
        with self.assertRaises(KeyboardInterrupt):
            with sandbox(self.project) as folder:
                self.assertTrue(folder.is_relative_to(self.project)); raise KeyboardInterrupt()
        self.assertEqual(list((self.project/".wf/replay_sandboxes").glob("run_*")),[])
    def test_stale_cleanup_preserves_unknown_owner_and_live_child(self):
        from wfcore.replayjobs import cleanup,DIRECTORY
        root=self.project/DIRECTORY; unknown=root/"run_unknown"; unknown.mkdir(parents=True)
        owned=root/"run_owned"; owned.mkdir()
        atomic_json(owned/"owner.json",{"project":str(self.project),"directory":owned.name,"pid":777,"token":"synthetic"})
        self.data(".wf/processes/child.json",{"cwd":str(owned),"pid":888,"status":"running"})
        with patch("wfcore.replayjobs.alive",side_effect=lambda pid:pid==888): self.assertFalse(cleanup(self.project,True)[0]["removed"])
        with patch("wfcore.replayjobs.alive",return_value=False): self.assertTrue(cleanup(self.project,True)[0]["removed"])
        self.assertTrue(unknown.exists())
    def test_installed_engine_drift_fails_without_mutating_research(self):
        from wfcore.engineintegrity import verify_engine,BASELINE
        import hashlib
        root=self.base/"engine"; file=root/"tools/worker.py"; file.parent.mkdir(parents=True); file.write_bytes(b"original")
        atomic_json(root/BASELINE,{"schema_version":1,"files":{"tools/worker.py":hashlib.sha256(file.read_bytes()).hexdigest()}})
        self.assertIn("matches",verify_engine(root)); file.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError,"engine changed"): verify_engine(root)
        with self.assertRaises(ValueError): verify_engine(self.base/"missing",required=True)
        (root/BASELINE).write_text("[]")
        with self.assertRaises(ValueError): verify_engine(root)
    def test_grouping_is_one_bound_number_not_several_smaller_numbers(self):
        from wfcore.checks.numbers import _offenders,normalize_grouping
        for text in ("20,586,612 reports","20\u2009586\u2009612 reports","20\u202f586\u202f612 reports"):
            self.assertEqual(_offenders(text,{20586612},{"20586612"},set()),[])
            self.assertTrue(_offenders(text,{20,586,612},{"20","586","612"},set()))
        self.assertEqual(normalize_grouping("1, 2, 3"),"1, 2, 3")
    def test_table_identifier_columns_preserve_digits_but_counts_follow_journal(self):
        from tables.threeline import write_table
        from openpyxl import load_workbook
        self.data("08_submission/target_journal.json",{"number_format":{"thousands":","}})
        path=self.project/"04_tables/main/Table1.xlsx"
        with patch.dict(os.environ,{"MEDPAPER_PROJECT":str(self.project)}):
            write_table(path,"Table 1","Table 1. Synthetic report identifiers.",["Report ID","Reports"],[["00123456","123456"]],["Synthetic example only."],identifier_columns=["Report ID"])
        book=load_workbook(path); self.assertEqual(book.active["A3"].value,"00123456"); self.assertEqual(book.active["B3"].value,"123,456"); book.close()
    def test_supplement_and_figures_do_not_escape_medical_language_review(self):
        self.data("01_protocol/artifact_plan.json",{})
        self.text("07_manuscript/full_manuscript.md","Plain synthetic clinical prose.")
        self.text("07_manuscript/supplementary_methods.md","The unregistered protocol changed before internal review.")
        issues=medicalstyle.scan(self.project)
        self.assertTrue(any(r["path"].endswith("supplementary_methods.md") and r["kind"]=="internal_plan_history" for r in issues))
        self.assertEqual(medicalstyle.diagnose("This analysis was post hoc and exploratory.","methods.md"),[])
    def polish(self):
        spec=importlib.util.spec_from_file_location("polish_isolation_test",ROOT/"tools/text/polish.py"); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
    def test_lint_does_not_force_normal_nouns_or_approval_identifiers_to_change(self):
        module=self.polish()
        self.assertFalse(module.lint_spelling([("paper.md","We analyzed the data. Sensitivity analyses and clinical characteristics were reported.")]))
        self.assertTrue(module.lint_spelling([("paper.md","We analyzed the results and analysed the outcomes.")]))
        self.assertFalse(any(r["kind"]=="sentence_starts_with_numeral" for r in module.lint_style("paper.md","Approval No. 2026J999 was recorded.")))
    def test_duplicate_removal_is_narrow_and_does_not_exempt_new_science(self):
        from wfcore.presentationdelta import snapshot
        from wfcore.revision import snapshot as actual_snapshot
        import subprocess
        rel="07_manuscript/full_manuscript.md"; self.text(rel,"There were 12 reports. There were 12 reports.")
        before=actual_snapshot(self.project)
        record={"round_id":"R001","status":"active","baseline":before,"presentation_baseline":snapshot(self.project,before)}
        self.data(".wf/revisions/R001.json",record); self.state.data.update(current="S24_package_human_review",active_revision_round="R001"); self.state.save()
        state=(self.project/".wf/state.json").read_bytes(); receipt=(self.project/".wf/revisions/R001.json").read_bytes()
        self.text(rel,"There were 12 reports.")
        command=[sys.executable,str(ROOT/"tools/rework.py"),"classify","--project",str(self.project)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(result.returncode,0,result.stdout+result.stderr); self.assertTrue(json.loads(result.stdout)["read_only"])
        self.text(rel,"There were 13 reports. No increase was seen.")
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(result.returncode,2); self.assertEqual(json.loads(result.stdout)["class"],"scientific")
        self.assertEqual((self.project/".wf/state.json").read_bytes(),state); self.assertEqual((self.project/".wf/revisions/R001.json").read_bytes(),receipt)
    def test_optional_proposal_reuse_binds_original_author_words_and_unchanged_basis(self):
        from wfcore.reviewdecisions import reuse
        report=self.text(".wf/review_rounds/M001.review1.md","Actual independent report in this synthetic test only.")
        evidence=self.text("03_analysis/results/scientific.json",'{"n":12}')
        finding={"id":"F1","optional_method":True,"proposal_id":"second-reviewer","proposal_text":"Consider an optional second clinical reviewer of the same records.","proposal_basis":{"03_analysis/results/scientific.json":_sha256(evidence)}}
        original={"scope":"manuscript","id":"M001","closed_at":"2026-10-29","after":{"source":"hash"},"report":{"path":report.relative_to(self.project).as_posix(),"sha256":_sha256(report)},"findings":[finding],"kept":[["F1","Actual author declined this optional analysis."]],"author_decisions":{"F1":{"author_words":"I decline a second reviewer for this unchanged optional procedure.","rationale":"The explicit author chose the current design after considering this exact recommendation.","inputs":{"source":"hash"},"report_sha256":_sha256(report)}}}
        self.data(".wf/review_rounds/M001.json",original)
        current={"scope":"manuscript","id":"M002","after":{"new_source":"hash2"},"report":{"sha256":"current-report"}}
        request={"reuse_from":{"scope":"manuscript","round":"M001","finding":"F1"}}
        inherited=reuse(self.project,current,finding,request); self.assertEqual(inherited["author_words"],original["author_decisions"]["F1"]["author_words"])
        with self.assertRaises(ValueError): reuse(self.project,current,{**finding,"optional_method":False},request)
        evidence.write_text('{"n":13}')
        with self.assertRaises(ValueError): reuse(self.project,current,finding,request)


if __name__=="__main__": unittest.main(verbosity=2)
