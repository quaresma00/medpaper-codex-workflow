"""Exact same-checkpoint evidence reuse; real synthetic source/proof, no network."""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_source_access_120 as fixture
from wfcore import liverefs, registry
from wfcore.checks import Ctx
from wfcore.checks.refs import reference_provenance
from wfcore.gatecache import Receipts
from wfcore.packagefreeze import _sha256
from wfcore.readiness import atomic_json


class ExecutionEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.SourceAccessTests("runTest");self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.project=self.base.project;self.state=self.base.state;self.pipe=registry.load()
        with contextlib.redirect_stdout(io.StringIO()):self.base.register()
        self.assertTrue(self.base.proof()["verified"])
        self.gate_rel="06_refs/cache/gate_efetch_pubmed_fixture.xml"
        (self.project/self.gate_rel).write_text(self.base.raw,encoding="utf-8")
        self.live={**self.base.source,"cache_file":self.gate_rel}

    def check(self,stage="S13_reflib"):
        return reference_provenance(Ctx(self.pipe,self.state,self.project,self.pipe.stage(stage),{"live":True}))

    def test_check_then_advance_reuses_same_real_s13_checkpoint_only(self):
        with patch("pubmed.eutils.efetch",return_value=[self.live]) as fetch:
            self.assertTrue(self.check().ok)
            stamp=json.loads((self.project/liverefs.REL).read_text())["at"]
            self.assertTrue(self.check().ok)
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(json.loads((self.project/liverefs.REL).read_text())["at"],stamp)
            self.assertTrue(self.check("S25_submission_audit").ok)
            self.assertEqual(fetch.call_count,2)
            self.assertTrue(self.check("S25_submission_audit").ok)
            self.assertEqual(fetch.call_count,2)

    def test_expired_or_future_checkpoint_is_not_extended(self):
        with patch("pubmed.eutils.efetch",return_value=[self.live]) as fetch:
            for delta in (timedelta(seconds=-121),timedelta(seconds=10)):
                self.assertTrue(self.check().ok)
                path=self.project/liverefs.REL;data=json.loads(path.read_text())
                data["at"]=(datetime.now(timezone.utc)+delta).isoformat();atomic_json(path,data)
                before=fetch.call_count
                self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,before+1)

    def test_generic_24_hour_cache_cannot_seed_first_critical_checkpoint(self):
        liverefs.store_sources(self.project,[self.live])
        with patch("pubmed.eutils.efetch",side_effect=OSError("synthetic offline")) as fetch:
            self.assertFalse(self.check().ok);self.assertEqual(fetch.call_count,1)

    def test_changed_xml_and_changed_verification_cannot_reuse_checkpoint(self):
        with patch("pubmed.eutils.efetch",return_value=[self.live]) as fetch:
            self.assertTrue(self.check().ok)
            gate=self.project/self.gate_rel;gate.write_text(self.base.raw+"\n",encoding="utf-8")
            self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,2)
            proof=self.project/"06_refs/verified.json";proof.write_bytes(proof.read_bytes()+b"\n")
            self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,3)

    def test_new_journal_revision_or_engine_pin_is_a_different_checkpoint(self):
        with patch("pubmed.eutils.efetch",return_value=[self.live]) as fetch:
            self.assertTrue(self.check().ok)
            atomic_json(self.project/"08_submission/journal_context.json",{"context_id":"actual-next-context"})
            self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,2)
            self.state.data["active_revision_round"]="R-next";self.state.save()
            self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,3)
            self.state.data["engine_pin"]="1.29.0";self.state.save()
            self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,4)

    def test_failed_live_response_never_creates_critical_pass(self):
        with patch("pubmed.eutils.efetch",return_value=[]) as fetch:
            self.assertFalse(self.check().ok);self.assertFalse(self.check().ok)
            self.assertEqual(fetch.call_count,2)
        self.assertFalse((self.project/liverefs.REL).exists())

    def test_changed_library_bytes_and_valid_renewed_proof_start_new_checkpoint(self):
        with patch("pubmed.eutils.efetch",return_value=[self.live]) as fetch:
            self.assertTrue(self.check().ok)
            library=self.project/"06_refs/library.json";library.write_bytes(library.read_bytes()+b"\n")
            # Regenerate the actual verifier fixture after the library bytes change;
            # never hand-edit a receipt using a different digest convention.
            self.assertTrue(self.base.proof()["verified"])
            self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,2)

    def test_current_rule_identity_change_requires_another_fresh_check(self):
        from wfcore import refproof
        actual=refproof.file_sha256
        with patch("pubmed.eutils.efetch",return_value=[self.live]) as fetch:
            self.assertTrue(self.check().ok)
            def changed(path):return "synthetic-new-rule-identity" if str(path).endswith("liverefs.py") else actual(path)
            with patch("wfcore.refproof.file_sha256",side_effect=changed):
                self.assertTrue(self.check().ok);self.assertEqual(fetch.call_count,2)

    def test_stricter_freshness_and_malformed_cache_do_not_grant_reuse(self):
        with patch("pubmed.eutils.efetch",return_value=[self.live]) as fetch:
            self.assertTrue(self.check().ok)
            path=self.project/liverefs.REL;data=json.loads(path.read_text())
            data["at"]=(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat();atomic_json(path,data)
            self.assertIsNone(liverefs.checkpoint_sources(self.project,[self.base.entry],"S13_reflib",max_hours=1/3600))
            for malformed in (None,[],{"checkpoint":"invented"}):
                atomic_json(path,malformed)
                before=fetch.call_count;self.assertTrue(self.check().ok)
                self.assertEqual(fetch.call_count,before+1)

    def test_local_forgery_still_fails_before_reusing_real_live_receipt(self):
        with patch("pubmed.eutils.efetch",return_value=[self.live]):self.assertTrue(self.check().ok)
        library=self.project/"06_refs/library.json";data=json.loads(library.read_text())
        data["entries"][0]["doi"]="10.9999/synthetic-forgery";atomic_json(library,data)
        with patch("pubmed.eutils.efetch",side_effect=AssertionError("local proof should fail first")):
            self.assertFalse(self.check().ok)

    def test_same_identity_hashes_overlapping_files_once_without_stat_only_reuse(self):
        source=self.project/"03_analysis/results/source.json";source.parent.mkdir(parents=True,exist_ok=True)
        source.write_text('{"value":100}',encoding="utf-8")
        (source.parent/"number_allowlist.tsv").write_text("365\tconstant\t03_analysis/results/source.json\tSynthetic registered design constant for this controlled test.\n",encoding="utf-8")
        receipt=Receipts(self.project,self.pipe,self.state)
        stage=self.pipe.stage("S09_results");spec={"check":"numbers_have_provenance","path":"07_manuscript/results.md"}
        seen=[]
        def tracked(path):
            if path==source:seen.append(path)
            return _sha256(path)
        with patch("wfcore.gatecache._sha256",side_effect=tracked):
            before=receipt.identity(stage,spec);self.assertEqual(len(seen),1)
            stat=source.stat();source.write_text('{"value":101}',encoding="utf-8")
            os.utime(source,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            after=receipt.identity(stage,spec);self.assertEqual(len(seen),2)
        self.assertNotEqual(before,after)


if __name__=="__main__":unittest.main(verbosity=2)
