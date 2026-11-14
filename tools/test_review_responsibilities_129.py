"""Synthetic author checkpoints remain distinct from actual independent final review."""
import json
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import test_review_rounds as fixture
from wfcore import reviewrounds as rr
from wfcore.packagefreeze import _sha256
from wfcore.state import State


class ReviewResponsibilityTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.ReviewRoundTests("runTest");self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.project=self.base.project;self.state=self.base.state
        self.state.data.update(engine_pin="1.29.0",pipeline_version="1.29.0");self.state.save()
        self.base.package()
        for target,value in (("wfcore.packagecontent.verify_baseline",(True,[],1)),
                             ("wfcore.submissionqc.verify",[]),("wfcore.benchmark.verify_acceptance",[]),
                             ("wfcore.journalcontext.guard",None)):
            mocked=patch(target,return_value=value);mocked.start();self.addCleanup(mocked.stop)

    def test_default_package_checkpoint_is_honest_author_review(self):
        record=rr.start(self.project,"package")
        self.assertEqual(record["review_kind"],"author_package");self.assertIsNone(record["report"])
        rr.close(self.project,"package",[],[])
        rr.decide(self.project,"package","no_further_review","我确认这一版")
        self.assertEqual(rr.approved(self.project,"package")["id"],record["id"])
        text=(self.project/"08_submission/package_human_review.md").read_text(encoding="utf-8")
        self.assertNotIn("Independent report:",text);self.assertIn("S25",text)
        self.assertFalse((self.project/"08_submission/independent_submission_audit.md").exists())

    def test_real_cli_reports_author_mode_and_rejects_a_misplaced_independent_flag(self):
        tool=Path(__file__).resolve().parent/"review_round.py"
        result=subprocess.run([sys.executable,str(tool),"start","--scope","package","--project",str(self.project)],capture_output=True,text=True,encoding="utf-8",timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('"review_kind": "author_package"',result.stdout)
        wrong=subprocess.run([sys.executable,str(tool),"close","--scope","package","--independent","--project",str(self.project)],capture_output=True,text=True,encoding="utf-8",timeout=30)
        self.assertNotEqual(wrong.returncode,0);self.assertIn("start-only",wrong.stderr)

    def test_unresolved_defects_and_waived_findings_cannot_close_author_checkpoint(self):
        rr.start(self.project,"package")
        for kept,unresolved in (([],1),([("F1","executor preference")],0)):
            with self.assertRaises(ValueError):rr.close(self.project,"package",[],kept,unresolved)

    def test_author_confirmation_freezes_real_files_but_never_passes_independent_final_audit(self):
        from wfcore import registry
        from wfcore.packagefreeze import write_freeze,verify_freeze
        from wfcore.checks import Ctx
        from wfcore.checks.artifacts import submission_audit_matches_freeze
        rr.start(self.project,"package");rr.close(self.project,"package",[],[])
        rr.decide(self.project,"package","no_further_review","我确认这一版")
        rr.approved(self.project,"package");write_freeze(self.project)
        self.assertTrue(verify_freeze(self.project)[0])
        pipe=registry.load();ctx=Ctx(pipe,State(self.project).load(),self.project,pipe.stage("S25_submission_audit"),{})
        self.assertFalse(submission_audit_matches_freeze(ctx).ok)

    def test_existing_content_visual_and_measurement_checks_remain_required(self):
        rr.start(self.project,"package")
        for target,result in (("wfcore.packagecontent.verify_baseline",(False,["visible text drift"],1)),
                              ("wfcore.submissionqc.verify",["Word measurements stale"]),
                              ("wfcore.benchmark.verify_acceptance",["Actual medical/visual reading missing"])):
            with self.subTest(target=target),patch(target,return_value=result):
                with self.assertRaisesRegex(ValueError,"QA remains incomplete"):rr.close(self.project,"package",[],[])
        self.assertIsNone(rr.latest(self.project,"package")["closed_at"])

    def test_actual_source_revision_must_finish_before_author_close(self):
        rr.start(self.project,"package");state=State(self.project).load()
        state.data["active_revision_round"]="R001";state.save()
        with self.assertRaisesRegex(ValueError,"scoped source"):rr.close(self.project,"package",[],[])

    def test_author_answer_and_current_files_are_bound_before_approval(self):
        rr.start(self.project,"package");rr.close(self.project,"package",[],[])
        with self.assertRaises(ValueError):rr.decide(self.project,"package","no_further_review","继续")
        rr.decide(self.project,"package","no_further_review","我确认这一版")
        self.base.text("08_submission/bundle/test.txt","Actual synthetic author edit")
        with self.assertRaisesRegex(ValueError,"drifted"):rr.approved(self.project,"package")

    def test_changed_files_need_explicit_scoped_correction_explanation(self):
        rr.start(self.project,"package");self.base.text("08_submission/bundle/test.txt","Changed synthetic source")
        with self.assertRaisesRegex(ValueError,"Record each changed"):rr.close(self.project,"package",[],[])
        rr.close(self.project,"package",[("08_submission/bundle/test.txt","Corrected the actual source and rebuilt this upload")],[])

    def test_author_checkpoint_cannot_accept_or_claim_an_independent_report(self):
        rr.start(self.project,"package")
        with self.assertRaisesRegex(ValueError,"author package checkpoint"):
            rr.attach(self.project,"package",self.base.text("temp/report.md","Synthetic non-independent text"))

    def test_explicit_independent_pre_review_and_old_pins_keep_real_report_requirement(self):
        rr.start(self.project,"package",author_only=False)
        with self.assertRaisesRegex(ValueError,"actual independent report"):rr.close(self.project,"package",[],[])
        # Separate legacy fixture, so no pending review is overwritten or migrated.
        legacy=fixture.ReviewRoundTests("runTest");legacy.setUp();self.addCleanup(legacy.doCleanups);legacy.package()
        record=rr.start(legacy.project,"package")
        self.assertNotIn("review_kind",record)
        with self.assertRaises(ValueError):rr.close(legacy.project,"package",[],[])

    def test_manuscript_review_receives_the_actual_current_early_report(self):
        self.state.data["current"]="S18_independent_review";self.state.save()
        report=self.base.text(".wf/review_inbox/E001.md","Synthetic early scientific opinion; this is unit-test content only")
        self.base.data(".wf/early_review.json",{"report":{"path":report.relative_to(self.project).as_posix()}})
        prose=self.project/"07_manuscript/full_manuscript.md"
        with patch("wfcore.reviewrounds.reader_inputs",return_value={"07_manuscript/full_manuscript.md":_sha256(prose)}),patch("wfcore.earlyreview.verify",return_value=[]):
            record=rr.start(self.project,"manuscript")
            self.assertTrue(record["early_science_context"])
            self.assertEqual(record["reviewed_artifacts"][".wf/review_inbox/E001.md"],_sha256(report))
            report.write_text("Changed synthetic scientific opinion",encoding="utf-8")
            self.assertTrue(rr.changed(record["reviewed_artifacts"],rr.inputs(self.project,"manuscript")))

    def test_manuscript_context_cannot_reuse_a_failed_early_science_review(self):
        self.state.data["current"]="S18_independent_review";self.state.save()
        with patch("wfcore.reviewrounds.reader_inputs",return_value={}),patch("wfcore.earlyreview.verify",return_value=["Scientific review is NO_GO"]):
            with self.assertRaisesRegex(ValueError,"NO_GO"):rr.start(self.project,"manuscript")


if __name__=="__main__":unittest.main(verbosity=2)
