"""Synthetic mistaken-review correction without unrelated manuscript/data changes."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_early_benchmark_128 as fixture
from wfcore import earlyreview as er
from wfcore.packagefreeze import _sha256

ROOT=Path(__file__).resolve().parents[1]
REASON="The independent reviewer overlooked the existing time-origin definition; please reread that unchanged source and reconsider the opinion."


class ReviewReconsiderationTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.EarlyScientificReviewTests("runTest");self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.project=self.base.project

    def attached(self,verdict="REVISE"):
        record=er.start(self.project,"/root")
        er.attach(self.project,self.base.report(record,verdict))
        return er.load(self.project,er.RECORD)

    def test_unchanged_go_and_revise_keep_default_reuse(self):
        for verdict in ("GO","REVISE","NO_GO"):
            with self.subTest(verdict=verdict):
                if (self.project/er.RECORD).exists():
                    (self.project/er.RECORD).unlink()
                record=self.attached(verdict)
                before=(self.project/er.RECORD).read_bytes()
                self.assertEqual(er.start(self.project,"/root")["id"],record["id"])
                self.assertEqual((self.project/er.RECORD).read_bytes(),before)

    def test_same_input_reconsideration_needs_actual_new_independent_report(self):
        old=self.attached();old_report=self.project/old["report"]["path"];old_bytes=old_report.read_bytes()
        scientific=er.inputs(self.project)
        new=er.start(self.project,"/root",reconsider=True,why=REASON)
        self.assertEqual(new["id"],"E002");self.assertIsNone(new["report"])
        self.assertNotIn("verdict",new);self.assertEqual(new["changed_since_previous"],[])
        self.assertEqual(new["reviewed_artifacts"],scientific)
        self.assertEqual(new["reconsideration"]["previous_report"],old["report"])
        self.assertEqual(new["reconsideration"]["reason"],REASON)
        self.assertTrue(any("Independent scientific review is required" in error for error in er.verify(self.project)))
        self.assertEqual(er.inputs(self.project),scientific)
        self.assertEqual(old_report.read_bytes(),old_bytes)
        with self.assertRaisesRegex(ValueError,"actual independent"):
            er.attach(self.project,self.base.report(new,"GO",agent="/root"))
        self.assertIsNone(er.load(self.project,er.RECORD)["report"])
        er.attach(self.project,self.base.report(new,"GO"))
        self.assertEqual(er.verify(self.project),[])
        self.assertEqual(old_report.read_bytes(),old_bytes)

    def test_reason_is_required_and_does_not_grant_go(self):
        self.attached();before=(self.project/er.RECORD).read_bytes()
        for reason in (None,"review again"," "*60):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,"concrete --why"):
                er.start(self.project,"/root",reconsider=True,why=reason)
        self.assertEqual((self.project/er.RECORD).read_bytes(),before)
        self.assertTrue(any("REVISE" in error for error in er.verify(self.project)))

    def test_pending_review_cannot_be_abandoned_with_reconsider(self):
        er.start(self.project,"/root");before=(self.project/er.RECORD).read_bytes()
        with self.assertRaisesRegex(ValueError,"attached independent"):
            er.start(self.project,"/root",reconsider=True,why=REASON)
        self.assertEqual((self.project/er.RECORD).read_bytes(),before)

    def test_real_scientific_changes_use_ordinary_start(self):
        old=self.attached();source=self.project/"03_analysis/results/main.json"
        source.write_text(json.dumps({"fixture":"changed result input, not a new interpretation"}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Scientific inputs changed"):
            er.start(self.project,"/root",reconsider=True,why=REASON)
        new=er.start(self.project,"/root")
        self.assertEqual(new["id"],"E002");self.assertIn("03_analysis/results/main.json",new["changed_since_previous"])
        self.assertNotIn("reconsideration",new)

    def test_changed_old_report_and_existing_next_destination_are_preserved(self):
        old=self.attached();path=self.project/old["report"]["path"];original=path.read_bytes()
        path.write_bytes(original+b"\nUnattached report change.\n")
        with self.assertRaisesRegex(ValueError,"Prior independent report"):
            er.start(self.project,"/root",reconsider=True,why=REASON)
        path.write_bytes(original)
        next_path=self.base.text(".wf/review_inbox/E002.md","Another existing report must never be overwritten.")
        before=_sha256(next_path)
        with self.assertRaisesRegex(ValueError,"already exists"):
            er.start(self.project,"/root",reconsider=True,why=REASON)
        self.assertEqual(_sha256(next_path),before)
        self.assertEqual(er.load(self.project,er.RECORD)["id"],"E001")

    def test_corrected_opinion_does_not_allow_changing_the_preserved_prior_report(self):
        old=self.attached();old_path=self.project/old["report"]["path"]
        new=er.start(self.project,"/root",reconsider=True,why=REASON)
        er.attach(self.project,self.base.report(new,"GO"))
        self.assertEqual(er.verify(self.project),[])
        old_path.write_bytes(old_path.read_bytes()+b"\nChanged historical review.\n")
        self.assertTrue(any("prior independent report" in item for item in er.verify(self.project)))

    def test_cli_exposes_explicit_reconsideration_and_keeps_source_files(self):
        self.attached();before=er.inputs(self.project)
        result=subprocess.run([sys.executable,str(ROOT/"tools/early_review.py"),"start","--project",str(self.project),
            "--executor-id","/root","--reconsider","--why",REASON],capture_output=True,text=True,encoding="utf-8",timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)["id"],"E002")
        self.assertEqual(er.inputs(self.project),before)
        self.assertTrue(er.verify(self.project))


if __name__=="__main__":unittest.main(verbosity=2)
