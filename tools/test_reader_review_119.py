"""Synthetic independent-review contracts; no real paper or claim of a real audit."""
import json
from pathlib import Path
import tempfile
import unittest

from wfcore import registry, reviewrounds as rr
from wfcore.checks import Ctx
from wfcore.checks.artifacts import submission_audit_matches_freeze
from wfcore.packagefreeze import sync_evidence
from wfcore.readiness import atomic_json
from wfcore.reviewfindings import catalogue
from wfcore.state import State


class ReaderReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="medpaper-reader-119-")
        self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name)
        self.state=State(self.project).create("medpaper","1.19.0","S24_package_human_review")
        self.text("08_submission/bundle/paper.txt","Synthetic review fixture only")
        self.data("08_submission/bundle/manifest.json",{"items":[{"file":"08_submission/bundle/paper.txt","role":"manuscript"}]})

    def text(self,rel,value):
        path=self.project/rel; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(value,encoding="utf-8"); return path

    def data(self,rel,value):
        atomic_json(self.project/rel,value)

    def report(self,record,medical=True):
        headings=["Reader comprehension","Editorial screening and low-level errors","Guideline compliance"]
        if medical: headings.append("Medical presentation")
        prose="\n\n".join("## "+heading+"\n\n"+"Synthetic review: the table identifies the study population and counting unit, and the legend decodes the reported interval without backstage context." for heading in headings)
        meta={"reviewed_artifacts":record["reviewed_artifacts"],"findings":[],"finding_inventory_complete":True,
              "section_verdicts":{heading:"no_actionable_findings" for heading in headings}}
        return self.text("temp/review.md",prose+"\n```json\n"+json.dumps(meta)+"\n```\n")

    def test_current_package_review_requires_medical_reading(self):
        record=rr.start(self.project,"package")
        self.assertEqual(record["schema_version"],4)
        with self.assertRaisesRegex(ValueError,"Medical presentation"):
            rr.attach(self.project,"package",self.report(record,medical=False))
        attached=rr.attach(self.project,"package",self.report(record))
        self.assertIsNotNone(attached["report"])

    def test_legacy_round_is_not_silently_rewritten(self):
        self.state.data["pipeline_version"]="1.18.0"; self.state.save()
        record=rr.start(self.project,"package")
        self.assertEqual(record["schema_version"],3)
        rr.attach(self.project,"package",self.report(record,medical=False))

    def test_action_can_stay_in_actual_scientific_section(self):
        text="## Reader comprehension\nClear.\n## Medical presentation\nClear.\n## Scientific validity\n[finding:N1] The denominator differs from the stated eligible population."
        row={"id":"N1","section":"Scientific validity","text":"Denominator does not match the study population.","locator":"Table 1, n column","category":"numbers","affects_science":True}
        meta={"finding_inventory_complete":True,"findings":[row],"section_verdicts":{"Reader comprehension":"no_actionable_findings","Medical presentation":"no_actionable_findings","Scientific validity":"findings_listed"}}
        self.assertEqual(catalogue(text,meta,("Reader comprehension","Medical presentation")),[row])
        moved=text.replace("## Scientific validity\n[finding:N1]","[finding:N1]\n## Scientific validity\n")
        with self.assertRaisesRegex(ValueError,"declared prose section"):
            catalogue(moved,meta,("Reader comprehension","Medical presentation"))
        with self.assertRaisesRegex(ValueError,"absent"):
            catalogue(text.replace("## Scientific validity","## Something else"),meta,("Reader comprehension","Medical presentation"))

    def test_code_block_cannot_supply_review_prose_or_finding(self):
        record=rr.start(self.project,"package")
        path=self.report(record,medical=False)
        text=path.read_text(encoding="utf-8")
        text+="\n```text\n## Medical presentation\n"+"This is fenced test material, not reviewer findings. "*4+"\n```\n"
        path.write_text(text,encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Medical presentation"):
            rr.attach(self.project,"package",path)

    def test_final_audit_ids_alone_do_not_certify_medical_reading(self):
        freeze_id="A"*64
        self.data("08_submission/package_review_freeze.json",{"freeze_id":freeze_id})
        context=sync_evidence(self.project)["audit_context_id"]
        audit=self.text("08_submission/independent_submission_audit.md",f"# Verdict\nPASS\nFreeze ID: {freeze_id}\nAudit context ID: {context}\n")
        pipe=registry.load(); stage=pipe.stage("S25_submission_audit")
        ctx=Ctx(pipe,self.state,self.project,stage,{"check":"submission_audit_matches_freeze"})
        self.assertFalse(submission_audit_matches_freeze(ctx).ok)
        content=audit.read_text(encoding="utf-8")
        for heading in ("Reader comprehension","Medical presentation","Editorial screening and low-level errors"):
            content+=f"\n## {heading}\n\nThe synthetic manuscript defines its population and comparison; the table footnote and plotted interval agree with the stated clinical measure.\n"
        audit.write_text(content,encoding="utf-8")
        self.assertTrue(submission_audit_matches_freeze(ctx).ok)
        self.state.data.setdefault("decisions",{})["submission_package_independent_audit"]={"value":"PASS"}
        audit.write_text(content.replace("\nPASS\n","\nREVISE\n"),encoding="utf-8")
        self.assertFalse(submission_audit_matches_freeze(ctx).ok)
        audit.write_text(content.replace("\nPASS\n","\nPASS\nREVISE\n"),encoding="utf-8")
        self.assertFalse(submission_audit_matches_freeze(ctx).ok)


if __name__=="__main__": unittest.main()
