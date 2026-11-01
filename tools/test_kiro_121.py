"""Synthetic review isolation, source-bound rebuilding and journal-rule regressions."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from docx import Document
from wfcore import buildproof, rebuild, reviewrounds as rr
from wfcore.journalrules import limits, compare, advisories
from wfcore.packagefreeze import _sha256
from wfcore.readiness import atomic_json
from wfcore.reviewguard import extract, snapshot, verify
from wfcore.state import State

ROOT=Path(__file__).resolve().parents[1]


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="medpaper-kiro-121-")
        self.addCleanup(self.temp.cleanup); self.project=Path(self.temp.name)
        self.state=State(self.project).create("medpaper","1.21.0","S24_package_human_review")

    def text(self,rel,value):
        p=self.project/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(value,encoding="utf-8"); return p
    def data(self,rel,value): atomic_json(self.project/rel,value)
    def package(self):
        self.text("08_submission/bundle/paper.txt","Synthetic medical reading material.")
        self.data("08_submission/bundle/manifest.json",{"items":[{"role":"manuscript","file":"08_submission/bundle/paper.txt"}]})
    def report(self,record,revalidation=False):
        headings=["Reader comprehension","Medical presentation","Editorial screening and low-level errors","Guideline compliance"]
        prose="\n\n".join("## "+h+"\n"+"Synthetic reader observation: population, comparison, effect measure and interpretation limits are stated and the legend explains the interval without internal implementation context." for h in headings)
        meta={"reviewed_artifacts":record["revalidation_request"]["inputs"] if revalidation else record["reviewed_artifacts"],
              "findings":[],"finding_inventory_complete":True,"section_verdicts":{h:"no_actionable_findings" for h in headings}}
        return self.text("temp/report.md",prose+"\n```json\n"+json.dumps(meta)+"\n```\n")

    def test_unselected_result_change_and_deletion_refuse_independent_report(self):
        self.package(); extra=self.text("03_analysis/results/secondary.json",'{"estimate":1}')
        rec=rr.start(self.project,"package"); report=self.report(rec)
        self.assertEqual(rec["schema_version"],5)
        extra.write_text('{"estimate":2}',encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"during independent"): rr.attach(self.project,"package",report)
        extra.unlink()
        with self.assertRaisesRegex(ValueError,"during independent"): rr.attach(self.project,"package",report)
        self.assertIsNone(rr.latest(self.project,"package")["report"])

    def test_legitimate_corrections_get_fresh_revalidation_request(self):
        self.package(); rec=rr.start(self.project,"package")
        rr.attach(self.project,"package",self.report(rec))
        self.text("08_submission/bundle/paper.txt","Synthetic corrected medical reading material.")
        with self.assertRaisesRegex(ValueError,"Prepare"): rr.attach(self.project,"package",self.report(rec),revalidation=True)
        rec=rr.prepare_revalidation(self.project,"package")
        rr.attach(self.project,"package",self.report(rec,True),revalidation=True)
        self.assertEqual(len(rr.latest(self.project,"package")["reports"]),2)

    def test_ingestion_preserves_actual_report_and_rejects_ambiguous_state(self):
        self.package(); rec=rr.start(self.project,"package"); body=self.report(rec).read_text(encoding="utf-8")
        src=self.text("temp/reply.md","Reviewer response\n<<<REPORT>>>"+body+"<<<END>>>\nDone")
        env={**os.environ,"MEDPAPER_PROJECT":str(self.project),"MEDPAPER_ROOT":str(ROOT)}
        run=subprocess.run([sys.executable,str(ROOT/"tools/review_round.py"),"ingest","--scope","package","--project",str(self.project),"--from-file",str(src)],capture_output=True,text=True,env=env)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        rec=rr.latest(self.project,"package")
        self.assertEqual((self.project/rec["report"]["path"]).read_text(encoding="utf-8"),body)
        for value in ('{"thread":"report"}','<<<REPORT>>>incomplete','<<<REPORT>>>a<<<END>>> <<<REPORT>>>b<<<END>>>'):
            with self.assertRaises(ValueError): extract(value)

    def test_guard_ignores_backstage_logs_and_does_not_read_raw_data(self):
        self.text("02_data/raw/test.csv","Synthetic private fixture")
        before=snapshot(self.project)
        self.text("temp/progress.txt","Synthetic progress")
        self.text(".wf/logs/review.log","Synthetic log")
        verify(self.project,before)
        self.assertFalse(any(p.startswith("02_data/") for p in before))

    def test_new_scientific_context_does_not_rewrite_old_round_inputs(self):
        for rel in ("07_manuscript/full_manuscript.md","05_figures/legends.md","04_tables/table_captions.md","01_protocol/protocol_v1.md"):
            self.text(rel,"Synthetic research context")
        self.data("01_protocol/artifact_plan.json",{})
        self.state.data.update(pipeline_version="1.20.0",current="S18_independent_review");self.state.save()
        old=rr.start(self.project,"manuscript")
        self.assertNotIn("01_protocol/protocol_v1.md",old["before"])
        self.state.data["pipeline_version"]="1.21.0";self.state.save()
        self.assertEqual(rr.inputs(self.project,"manuscript"),old["before"])
        new=rr.restart(self.project,"manuscript","Synthetic explicit restart to evaluate the current source version.")
        self.assertIn("01_protocol/protocol_v1.md",new["before"])

    def managed(self,name="letter",source=None):
        source=source or self.text(f"08_submission/integration/{name}.md",f"# {name}\nSynthetic medical document.")
        style=self.project/"08_submission/docx_style.json"
        if not style.is_file(): self.data("08_submission/docx_style.json",{})
        out=self.project/f"08_submission/bundle/{name}.docx";out.parent.mkdir(parents=True,exist_ok=True)
        doc=Document();doc.add_paragraph("Synthetic generated document.");doc.save(out)
        buildproof.record(self.project,out,[source,style],entrypoints=[source],tool="tools/manuscript/build_docx.py",
                          parameters={"kind":"cover_letter","style":str(style),"inputs":[str(source)]})
        return source,out
    def manifest(self,*outputs):
        self.data("08_submission/bundle/manifest.json",{"items":[{"role":"cover_letter","file":p.relative_to(self.project).as_posix()} for p in outputs]})

    def test_rebuild_uses_true_consumers_and_preserves_other_output(self):
        src,a=self.managed("a");_,b=self.managed("b");self.manifest(a,b)
        self.assertEqual(rebuild.plan(self.project),[])
        src.write_text("# Updated synthetic letter",encoding="utf-8")
        jobs=rebuild.plan(self.project)
        self.assertEqual([r["output"] for r in jobs],[a.relative_to(self.project).as_posix()])
        self.assertIn(str(src),jobs[0]["command"])
        unchanged=_sha256(b)
        from manuscript.build_docx import main
        with patch.dict(os.environ,{"MEDPAPER_PROJECT":str(self.project)}),patch("sys.argv",jobs[0]["command"][1:]),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(),0)
        self.assertEqual(rebuild.plan(self.project),[])
        self.assertEqual(_sha256(b),unchanged)

    def test_missing_generated_file_rebuilt_but_manual_edit_preserved(self):
        _,out=self.managed();self.manifest(out);original=out.read_bytes();out.unlink()
        self.assertEqual(len(rebuild.plan(self.project)),1)
        out.write_bytes(original+b"manual-edit")
        with self.assertRaisesRegex(ValueError,"preserve author edits"): rebuild.plan(self.project)

    def test_builder_failure_stops_before_audit_or_baseline_update(self):
        src,out=self.managed();self.manifest(out);src.write_text("Changed source")
        self.state.data["current"]="S23_package";self.state.save()
        calls=[]
        def fail(cmd,**kwargs):
            calls.append(cmd);return argparse.Namespace(returncode=2,stdout="Synthetic failure",stderr="")
        with self.assertRaisesRegex(ValueError,"stopped before downstream"):
            rebuild.run(self.project,execute=fail)
        self.assertEqual(len(calls),1)
        self.assertFalse((self.project/"08_submission/package_content_baseline.json").exists())

    def test_unresolved_meaning_stops_before_any_build_planning(self):
        with patch("wfcore.revision.active",return_value={"presentation_candidate":True}),patch("wfcore.revision.scope_problems",return_value=[]),patch("wfcore.presentationdelta.classify",return_value={"class":"needs_executor_meaning_review"}),patch("wfcore.rebuild.plan") as planned:
            with self.assertRaisesRegex(ValueError,"classification before"): rebuild.run(self.project)
        planned.assert_not_called()

    def test_upstream_rebuild_includes_actual_downstream_consumer(self):
        src,a=self.managed("a");_,b=self.managed("b",source=a);self.manifest(a,b)
        src.write_text("Changed source")
        self.assertEqual([r["output"] for r in rebuild.plan(self.project)],[a.relative_to(self.project).as_posix(),b.relative_to(self.project).as_posix()])

    def test_unknown_builder_and_external_arguments_fail_preflight(self):
        src,out=self.managed();self.manifest(out);src.write_text("Changed source")
        receipts=buildproof.load(self.project);rel=out.relative_to(self.project).as_posix()
        receipts[rel]["tool"]="unregistered-producer.py";self.data(buildproof.RECEIPTS,receipts)
        with self.assertRaisesRegex(ValueError,"supported recorded builder"): rebuild.plan(self.project)
        receipts[rel]["tool"]="tools/manuscript/build_docx.py";receipts[rel]["parameters"]["inputs"]=["../other-study/paper.md"]
        self.data(buildproof.RECEIPTS,receipts)
        with self.assertRaises(ValueError): rebuild.plan(self.project)

    def test_page_derived_limits_are_advisory_and_explicit_caps_stay_hard(self):
        row={"status":"required","value":100,"source":"Official guide states a page budget","basis":"page_derived","derivation":"Estimated from the guide's page budget, not an explicit word limit."}
        self.data("08_submission/submission_requirements.json",{"article_type":"Original Article","word_count":{"source":"Official author guide","limit":None},"limits":{"main":row}})
        _,rules=limits(self.project)
        self.assertEqual(compare({"main":101},rules),[]);self.assertTrue(advisories({"main":101},rules))
        row={**row,"basis":"explicit"};self.data("08_submission/submission_requirements.json",{"article_type":"Original Article","word_count":{"source":"Official guide"},"limits":{"main":row}})
        self.assertTrue(compare({"main":101},limits(self.project)[1]))
        row["estimated"]=True
        self.data("08_submission/submission_requirements.json",{"article_type":"Original Article","word_count":{"source":"Official guide"},"limits":{"main":row}})
        with self.assertRaises(ValueError): limits(self.project)

    def test_hidden_local_paths_removed_without_changing_medical_text(self):
        from manuscript.build_docx import normalize_docx,load_style
        from wfcore.journalspec import metadata_problems
        _,out=self.managed();doc=Document(out)
        doc.core_properties.comments=r"F:\private-study\patient-data.csv"
        doc.core_properties.author="Synthetic author";doc.save(out)
        self.assertTrue(metadata_problems(out))
        before=[p.text for p in doc.paragraphs]
        normalize_docx(out,load_style(self.project/"08_submission/docx_style.json"),"cover_letter")
        self.assertEqual(metadata_problems(out),[])
        self.assertEqual([p.text for p in Document(out).paragraphs],before)
        self.assertEqual(Document(out).core_properties.author,"Synthetic author")

    def test_nonupload_evidence_does_not_count_as_second_manuscript(self):
        from wfcore.submission import build_portal
        _,out=self.managed("paper")
        doc=Document();doc.add_paragraph("Synthetic medical study")
        doc.add_heading("Abstract",level=1);doc.add_paragraph("Synthetic abstract content.")
        doc.add_heading("Introduction",level=1);doc.add_paragraph("Synthetic clinical question.");doc.save(out)
        self.data("08_submission/bundle/manifest.json",{"items":[
            {"role":"manuscript","file":out.relative_to(self.project).as_posix()},
            {"role":"manuscript","file":"08_submission/bundle/preview.txt","upload":False}]})
        self.data("08_submission/submission_requirements.json",{"article_type":"Original Article","word_count":{"source":"Official guide, no word cap","include_sections":["Introduction"],"limit":None,"abstract_limit":None}})
        self.data("00_input/author_info.json",{key:"Synthetic supplied administrative fact" for key in
            ("authors","affiliations","corresponding","funding","conflicts","ethics_approval","data_availability")})
        portal=build_portal(self.project)
        self.assertEqual(len(portal["uploads"]),1)

    def test_manifest_docx_audit_ignores_nonupload_internal_text(self):
        from manuscript.build_docx import audit_manifest
        outputs=[self.managed(name)[1] for name in ("paper","title","letter")]
        items=[{"role":role,"file":out.relative_to(self.project).as_posix()} for role,out in
               zip(("manuscript","title_page","cover_letter"),outputs)]
        items.append({"role":"manuscript","file":"08_submission/bundle/internal-notes.md","upload":False})
        self.data("08_submission/bundle/manifest.json",{"items":items})
        args=argparse.Namespace(manifest=self.project/"08_submission/bundle/manifest.json",style_config=self.project/"08_submission/docx_style.json")
        with patch.dict(os.environ,{"MEDPAPER_PROJECT":str(self.project)}),patch("manuscript.build_docx.audit_docx",return_value=[]) as audit,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit_manifest(args),0)
        self.assertEqual(audit.call_count,3)


if __name__=="__main__": unittest.main(verbosity=2)
