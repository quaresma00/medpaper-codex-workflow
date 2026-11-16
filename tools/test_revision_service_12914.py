"""Synthetic local revision orchestration and real process timing; no study approvals."""
import argparse
import contextlib
from datetime import datetime,timedelta,timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import rework
from wfcore import revision,revisionservice as service
from wfcore.execution import run_logged
from wfcore.state import State


class RevisionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-service-");self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)
        self.state=State(self.project).create("medpaper","1.29.14","S24_package_human_review")
        self.source=self.project/"08_submission/integration/cover_letter.md"
        self.source.parent.mkdir(parents=True);self.source.write_text("Author-supplied administrative wording.",encoding="utf-8")
        self.record={"schema_version":2,"round_id":"R001","status":"active","review_stage":self.state.current,
            "allowed_files":[self.source.relative_to(self.project).as_posix()],"validation_stages":["S23_package"],
            "items":[{"id":"I001","kind":"cover-letter-or-package-structure","status":"pending","affected_sources":[self.source.relative_to(self.project).as_posix()]}],
            "baseline":revision.snapshot(self.project)}

    def completion(self):
        return {"summary":"Completed the specific administrative correction and read back the actual affected source and resulting document.",
                "items":[{"id":"I001","summary":"Corrected only the author-supplied administrative wording and read it back.",
                          "validated_by":["Actual affected source and rendered changed page inspected by the executor."]}]}

    def test_unchanged_sources_are_checked_not_claimed_modified(self):
        mark=service.completion_marks(self.project,self.record,self.completion())[0]
        self.assertEqual(mark.changed_file,[]);self.assertEqual(mark.checked_file,self.record["allowed_files"])
        self.source.write_text("Corrected author-supplied administrative wording.",encoding="utf-8")
        mark=service.completion_marks(self.project,self.record,self.completion())[0]
        self.assertEqual(mark.changed_file,self.record["allowed_files"]);self.assertEqual(mark.checked_file,[])

    def test_every_pending_item_needs_actual_explicit_resolution(self):
        for change in ({"items":[]},{"items":[{"id":"I099"}]}, {"summary":"OK"}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                service.completion_marks(self.project,self.record,{**self.completion(),**change})
        payload=self.completion();payload["items"][0]["validated_by"]=[]
        with self.assertRaises(ValueError):service.completion_marks(self.project,self.record,payload)

    def test_extra_out_of_scope_file_does_not_gain_receipt(self):
        outside=self.project/"07_manuscript/full_manuscript.md";outside.parent.mkdir();outside.write_text("Unrelated science")
        payload=self.completion();payload["items"][0]["files"]=["07_manuscript/full_manuscript.md"]
        with self.assertRaisesRegex(ValueError,"outside authored output scope"):
            service.completion_marks(self.project,self.record,payload)

    def test_preflight_is_read_only_and_surfaces_scope_drift(self):
        before={p:p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        report=service.preflight(self.project,self.state,self.record)
        self.assertTrue(report["read_only"]);self.assertEqual(report["changed_count"],0)
        self.assertEqual(before,{p:p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        rogue=self.project/"unplanned.txt";rogue.write_text("Unexpected change")
        self.assertTrue(service.preflight(self.project,self.state,self.record)["blockers"])

    def args(self):
        p=self.project/"completion.json";p.write_text(json.dumps(self.completion()),encoding="utf-8")
        return argparse.Namespace(completion=p,meaning_review=None)

    def test_failed_check_stops_before_mark_and_close(self):
        with patch.object(rework,"_load_round",return_value=(self.project/"round.json",self.record)),\
             patch.object(service,"preflight",return_value={"blockers":[],"validation_current":False}),\
             patch.object(service,"validation_current",return_value=False),\
             patch.object(revision,"check_round",return_value=2),\
             patch.object(rework,"_cmd_mark") as mark,patch.object(rework,"_cmd_close") as close:
            self.assertEqual(rework._cmd_finish(self.args(),self.project,None,self.state),2)
        mark.assert_not_called();close.assert_not_called()

    def test_current_check_is_reused_and_success_calls_existing_mark_close(self):
        events=[]
        with patch.object(rework,"_load_round",return_value=(self.project/"round.json",self.record)),\
             patch.object(service,"preflight",return_value={"blockers":[],"validation_current":True}),\
             patch.object(service,"validation_current",return_value=True),\
             patch.object(revision,"check_round") as check,\
             patch.object(rework,"_cmd_mark",side_effect=lambda *a:events.append("mark") or 0),\
             patch.object(rework,"_cmd_close",side_effect=lambda *a:events.append("close") or 0),\
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rework._cmd_finish(self.args(),self.project,None,self.state),0)
        check.assert_not_called();self.assertEqual(events,["mark","close"])

    def test_reuse_needs_current_signature_and_unexpired_success(self):
        self.record["validation"]={"ok":True,"checked_at":datetime.now(timezone.utc).isoformat(),"input_signature":"current"}
        with patch.object(revision,"input_signature",return_value="current"):
            self.assertTrue(service.validation_current(self.project,self.record))
            self.record["validation"]["checked_at"]=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
            self.assertFalse(service.validation_current(self.project,self.record))
        self.record["validation"]["checked_at"]=datetime.now(timezone.utc).isoformat()
        with patch.object(revision,"input_signature",return_value="drifted"):
            self.assertFalse(service.validation_current(self.project,self.record))

    def test_real_success_and_failure_processes_record_elapsed_context_without_guessing_cost(self):
        self.state.data["active_revision_round"]="R001";self.state.save()
        original=self.source.read_bytes()
        for code in (0,3):
            result=run_logged([sys.executable,"-c",f"raise SystemExit({code})"],project=self.project,
                              cwd=self.project,operation="synthetic_validation")
            self.assertEqual(result.returncode,code)
        records=[json.loads(p.read_text()) for p in (self.project/".wf/processes").glob("*.json")]
        self.assertEqual({r["status"] for r in records},{"complete","failed"})
        for row in records:
            self.assertEqual(row["stage"],self.state.current);self.assertEqual(row["revision_round"],"R001")
            self.assertGreaterEqual(row["duration_seconds"],0);self.assertIsNone(row["resource_usage"])
            self.assertGreaterEqual(datetime.fromisoformat(row["finished_at"]),datetime.fromisoformat(row["started_at"]))
        self.assertEqual(self.source.read_bytes(),original)


if __name__=="__main__":unittest.main(verbosity=2)
