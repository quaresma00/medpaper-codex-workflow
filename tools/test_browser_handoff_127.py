"""Real source-file registration and truthful handoff state; no login/CAPTCHA automation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_journal_context_124 as fixture
from wfcore import guides,journalcontext as jc

ROOT=Path(__file__).resolve().parents[1]


class BrowserHandoffTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.JournalContextTests(methodName="runTest");self.base.setUp()
        self.addCleanup(self.base.doCleanups);self.project=self.base.project
        self.base.ready();self.url=jc.load(self.project,jc.TARGET)["guidelines_url"]

    def start(self,url=None,reason="captcha",tab="iab:synthetic-tab-1"):
        return guides.browser_handoff(self.project,url or self.url,reason,tab)

    def register(self,url=None):
        source=self.base.text("temp/browser-export.txt",fixture.TEXT)
        return guides.capture(self.project,url or self.url,file=source,
                              why="Genuine source-file registration path exercised by this synthetic fixture; no authentication asserted.",
                              retrieved_at=jc.now())

    def test_handoff_keeps_sources_but_blocks_old_seal(self):
        before=jc.current(self.project)["sources"]
        row=self.start()
        self.assertEqual(row["status"],"waiting_for_user")
        self.assertEqual(jc.current(self.project)["sources"],before)
        self.assertNotIn("seal",jc.current(self.project))
        with self.assertRaisesRegex(ValueError,"waiting for the user"):jc.seal(self.project)
        with self.assertRaisesRegex(ValueError,"waiting for the user"):jc.guard(self.project)

    def test_user_done_flag_is_not_an_acquisition_receipt(self):
        self.start()
        result=subprocess.run([sys.executable,str(ROOT/"tools/journal.py"),"--project",str(self.project),
                               "browser-handoff","--url",self.url,"--reason","captcha","--completed"],
                              capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,2)
        self.assertEqual(jc.current(self.project)["browser_handoff"]["status"],"waiting_for_user")

    def test_actual_registered_guide_resolves_pending_and_can_be_sealed(self):
        self.start();source=self.register();context=jc.current(self.project)
        self.assertEqual(source["mode"],"registered")
        self.assertEqual(context["browser_handoff"]["status"],"source_captured")
        self.assertEqual(context["browser_handoff"]["raw_sha256"],source["raw_sha256"])
        self.assertNotIn("seal",context)
        jc.seal(self.project);self.assertEqual(jc.problems(self.project),[])

    def test_challenge_export_remains_pending_and_does_not_overwrite_valid_source(self):
        self.start();before=jc.current(self.project)["sources"]
        challenge=self.base.text("temp/challenge.html","<html><body>Verify you are human CAPTCHA</body></html>")
        with self.assertRaisesRegex(ValueError,"challenge"):
            guides.capture(self.project,self.url,file=challenge,why="Actual challenge fixture is deliberately not a guide source",retrieved_at=jc.now())
        self.assertEqual(jc.current(self.project)["sources"],before)
        self.assertEqual(jc.current(self.project)["browser_handoff"]["status"],"waiting_for_user")

    def test_unrelated_page_does_not_complete_subsidiary_guide_handoff(self):
        self.start(self.url+"/figure-rules")
        self.register(self.url)
        self.assertEqual(jc.current(self.project)["browser_handoff"]["status"],"waiting_for_user")

    def test_resume_same_tab_and_no_clobbering_another_request(self):
        row=self.start();later=self.start(tab="")
        self.assertEqual(later["tab_ref"],row["tab_ref"])
        self.assertEqual(later["requested_at"],row["requested_at"])
        with self.assertRaisesRegex(ValueError,"current browser handoff"):
            self.start(self.url+"/other-guide")
        self.assertEqual(jc.current(self.project)["browser_handoff"]["url"],self.url)

    def test_another_journal_does_not_inherit_login_or_tab_state(self):
        self.start()
        target={**self.base.target,"journal":"Synthetic next journal","issn":"8765-4321","guidelines_url":"https://next.example.org/authors"}
        new=jc.begin(self.project,target)
        self.assertNotIn("browser_handoff",new)
        self.assertTrue((self.project/new["previous_archive"]/"journal_context.json").exists())

    def test_failed_headless_path_requests_native_browser_without_inventing_human_handoff(self):
        async def unavailable(_url):raise ValueError("Optional headless browser unavailable in this fixture")
        with patch("wfcore.guides.download",side_effect=OSError("403 in a synthetic response")),patch("wfcore.guides.browser_download",unavailable):
            with self.assertRaisesRegex(ValueError,"native browser"):
                guides.capture(self.project,self.url)
        self.assertNotIn("browser_handoff",jc.current(self.project))


if __name__=="__main__":unittest.main(verbosity=2)
