"""Synthetic retrieval routing and global credential lookup; never contacts real sources."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pubmed import eutils as eu, fulltext
import test_source_access_120 as fixture


class RetrievalCredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-retrieval-128-");self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)
        self.entry={"citekey":"fixture","doi":"10.1000/fixture","title":"Synthetic reference test","pmid":"123"}
        self.root=patch.object(eu,"project_root",return_value=self.project);self.root.start();self.addCleanup(self.root.stop)
    def local(self,suffix=".pdf"):
        p=self.project/("06_refs/fulltext/fixture"+suffix);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes((b"%PDF-1.7\n" if suffix==".pdf" else b"<article>")+b"synthetic fixture "*100)
        return {"access":"oa","route":"fixture-only","fulltext":p.relative_to(self.project).as_posix(),"source_url":"https://example.org/fixture"}

    def test_persisted_user_key_works_in_stale_desktop_environment(self):
        with patch.object(eu,"user_setting",side_effect=lambda n:"example-new-user-value" if n=="NCBI_API_KEY" else None),patch.dict(os.environ,{"NCBI_API_KEY":"example-stale-value"}):
            self.assertEqual(eu.api_key(),"example-new-user-value")

    def test_process_and_pubmed_alias_fallback_without_persistent_setting(self):
        with patch.object(eu,"user_setting",return_value=None),patch.dict(os.environ,{"PUBMED_API_KEY":"example-alias-value"},clear=True):
            self.assertEqual(eu.api_key(),"example-alias-value")

    def test_retry_error_does_not_expose_secret_in_url_or_error_text(self):
        from urllib.error import URLError
        key="example-sensitive-value"
        with patch.object(eu,"api_key",return_value=key),patch.object(eu,"_throttle"),patch("pubmed.eutils.time.sleep"),patch("pubmed.eutils.urllib.request.urlopen",side_effect=URLError("failed with "+key)):
            with self.assertRaises(RuntimeError) as caught:eu.http_get("https://example.org/test",{"api_key":key},retries=1)
        self.assertNotIn(key,str(caught.exception));self.assertIn("redacted",str(caught.exception))

    def test_link_only_does_not_stop_later_actual_full_text_route(self):
        link={"access":"link-only","route":"landing","fulltext":"https://example.org/link"}
        later=self.local()
        with patch.object(fulltext,"ROUTES",(lambda e:link,lambda e:later)):
            result=fulltext.fetch_one(self.entry)
        self.assertEqual(result["fulltext"],later["fulltext"])
        self.assertEqual([x["outcome"] for x in result["attempts"]],["link_only","downloaded"])

    def test_pdf_requirement_cannot_be_satisfied_by_xml(self):
        xml=self.local(".xml")
        with patch.object(fulltext,"ROUTES",(lambda e:xml,)):
            result=fulltext.fetch_one(self.entry,require_pdf=True)
        self.assertEqual(result["access"],"external-needed")
        self.assertTrue(result["require_pdf"])
        self.assertIn("user",result["next_action"])

    def test_all_failures_remain_unresolved_and_keep_actual_route_outcomes(self):
        def failed(entry):raise ValueError("synthetic upstream failure")
        with patch.object(fulltext,"ROUTES",(failed,lambda e:None)),contextlib.redirect_stdout(io.StringIO()):
            result=fulltext.fetch_one(self.entry)
        self.assertEqual(result["access"],"external-needed")
        self.assertEqual([x["outcome"] for x in result["attempts"]],["failed","unavailable"])
        self.assertIn("exact DOI/title/PDF",result["next_action"])

    def test_attempt_history_survives_real_registration(self):
        fulltext.record_retrieval(self.entry,{"access":"external-needed","attempts":[{"route":"fixture","outcome":"not_found"}]})
        result=self.local();result.update(access="external",authorization_note="Actual synthetic user-selected retrieval route, not an OA license claim")
        record=fulltext.record_retrieval(self.entry,result)
        self.assertEqual(record["access"],"external");self.assertEqual(len(record["attempts"]),1)
        self.assertIn("sha256",record)

    def test_external_copy_is_not_mislabeled_oa_and_still_requires_identity(self):
        base=fixture.SourceAccessTests(methodName="runTest");base.setUp();self.addCleanup(base.doCleanups)
        # Reuse a genuine synthetic article-body fixture, never an actual scholarly PDF.
        with patch.object(eu,"project_root",return_value=base.project):
            path=base.register()
            args=["fulltext.py","register","--citekey",base.key,"--file",str(path),"--access","external",
                  "--source-url","https://example.org/external-fixture","--route","synthetic-external"]
            with patch("sys.argv",args),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):fulltext.main()
            args += ["--authorization-note","Synthetic user-selected external route; no assertion of OA or institutional license"]
            with patch("sys.argv",args),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(fulltext.main(),0)
            record=json.loads((base.project/"06_refs/fulltext/retrieval_manifest.json").read_text())["retrievals"][0]
            self.assertEqual(record["access"],"external")
            self.assertEqual(base.proof()["verified"],True)
            path.write_text(path.read_text().replace("10.1000/fixture","10.1000/wrong"),encoding="utf-8")
            self.assertFalse(base.proof()["verified"])

    def test_existing_verified_readable_file_is_not_downloaded_again(self):
        base=fixture.SourceAccessTests(methodName="runTest");base.setUp();self.addCleanup(base.doCleanups)
        with patch.object(eu,"project_root",return_value=base.project):
            path=base.register();before=path.read_bytes()
            with patch.object(fulltext,"ROUTES",(lambda e:self.fail("existing source fetched again"),)):
                result=fulltext.fetch_one(base.entry)
            self.assertEqual(result["fulltext"],path.relative_to(base.project).as_posix())
            self.assertEqual(path.read_bytes(),before)


if __name__=="__main__":unittest.main(verbosity=2)
