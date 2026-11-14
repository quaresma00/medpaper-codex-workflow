"""Synthetic official portal conflicts and contextual upload-directory regressions."""
import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import stat
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_journal_context_124 as fixture
from wfcore import journalcontext as jc,guides,guidelinerules as rules,journalportal as portal
from wfcore.readiness import atomic_json,load

PORTAL="""Synthetic Journal A Original research submission portal instructions.
The live upload form requires the cover letter in 11 point type, unlike the public guide.
Only the required cover-letter upload is assessed in this controlled synthetic specimen.
No real portal login or manuscript submission has been performed.
"""


class JournalPortalTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.JournalContextTests(methodName="runTest");self.base.setUp()
        self.addCleanup(self.base.doCleanups);self.project=self.base.project;self.base.ready()

    def write(self,rel,text):return self.base.text(rel,text)

    def portal(self):
        target=load(self.project,jc.TARGET);target["submission_url"]="https://portal.example.org/submit"
        atomic_json(self.project/jc.TARGET,target)
        file=self.write("temp/visible-portal.txt",PORTAL)
        return guides.capture(self.project,target["submission_url"],file=file,source_kind="portal",
                              retrieved_at=jc.now(),why="Actual visible-text export from the controlled official submission portal fixture")

    def conflict(self):
        source=self.portal();req=load(self.project,jc.REQUIREMENTS)
        req["guide_rules"].append({"id":"portal.layout","topic":"layout","status":"required","source_id":source["id"],
            "quote":"The live upload form requires the cover letter in 11 point type, unlike the public guide.",
            "locator":"Current upload form, cover-letter instructions",
            "check":{"type":"style","field":"body_font_pt","value":11,"roles":["cover_letter"]}})
        atomic_json(self.project/jc.REQUIREMENTS,req)
        style=load(self.project,"08_submission/docx_style.json");style["body_font_pt"]=11
        atomic_json(self.project/"08_submission/docx_style.json",style)
        return source

    def test_real_portal_and_public_guide_are_distinct_sources(self):
        source=self.portal();context=jc.current(self.project)
        self.assertEqual(source["source_kind"],"portal");self.assertEqual(source["mode"],"registered")
        self.assertEqual(len(context["sources"]),2)
        with self.assertRaisesRegex(ValueError,"visible-text"):
            guides.capture(self.project,source["url"],source_kind="portal")
        html=self.write("temp/portal.html","<html>hidden input cookie</html>")
        with self.assertRaisesRegex(ValueError,"visible-text"):
            guides.capture(self.project,source["url"],source_kind="portal",file=html)

    def test_conflicting_guide_is_not_silently_ignored(self):
        self.conflict()
        with self.assertRaisesRegex(ValueError,"configuration"):
            jc.seal(self.project)
        result=portal.resolve(self.project,"layout","portal.layout",
            "The current Original research upload form makes 11 point mandatory for this exact role; its live restriction governs this submission attempt.")
        self.assertEqual(result["portal_rule"],"portal.layout")
        jc.seal(self.project);self.assertEqual(jc.problems(self.project),[])
        # Measurement does not impose both mutually exclusive font sizes.
        with patch("wfcore.guidelinerules._uploads",return_value=([],{})):
            rows=rules.measure(self.project,{})
        self.assertIn("superseded",next(r for r in rows if r["rule_id"]=="layout")["checks"])

    def test_foreign_or_optional_portal_cannot_override_required_guide(self):
        self.conflict();req=load(self.project,jc.REQUIREMENTS)
        new=req["guide_rules"][-1];new["status"]="allowed";atomic_json(self.project/jc.REQUIREMENTS,req)
        with self.assertRaisesRegex(ValueError,"current required"):
            portal.resolve(self.project,"layout","portal.layout","This is a sufficiently long reason but an allowed choice is not a compulsory portal restriction.")
        new["status"]="required";new["check"]["roles"]=["manuscript"];atomic_json(self.project/jc.REQUIREMENTS,req)
        with self.assertRaisesRegex(ValueError,"same field/roles"):
            portal.resolve(self.project,"layout","portal.layout","A different file role does not justify replacing the actual cover-letter requirement in this attempt.")

    def test_stale_or_foreign_portal_source_blocks_resealing(self):
        source=self.conflict()
        portal.resolve(self.project,"layout","portal.layout",
            "The current Original research upload form makes 11 point mandatory for this exact role and this current submission attempt.")
        context=jc.current(self.project)
        context["sources"][source["id"]]["fetched_at"]=(datetime.now(timezone.utc)-timedelta(days=91)).isoformat()
        atomic_json(self.project/jc.CONTEXT,context)
        with self.assertRaisesRegex(ValueError,"stale"):
            jc.seal(self.project)
        context["sources"][source["id"]]["fetched_at"]=jc.now()
        context["sources"][source["id"]]["context_id"]="foreign-attempt"
        atomic_json(self.project/jc.CONTEXT,context)
        with self.assertRaisesRegex(ValueError,"another journal"):
            jc.seal(self.project)

    def test_compatible_looser_portal_ceiling_does_not_relax_the_guide(self):
        source=self.portal();context=jc.current(self.project)
        guide=next(s for s in context["sources"].values() if s.get("source_kind")=="guide")
        rows=[{"id":"guide.abstract","source_id":guide["id"],"topic":"abstract","status":"required",
               "superseded_by":"portal.abstract","conflict_reason":"Both ceilings are compatible; a longer allowance does not force use of additional words.",
               "check":{"type":"limit","field":"abstract","value":250}},
              {"id":"portal.abstract","source_id":source["id"],"topic":"abstract","status":"required",
               "resolves":"guide.abstract","check":{"type":"limit","field":"abstract","value":300}}]
        self.assertTrue(any("stricter" in p for p in portal.supersession_problems(self.project,context,rows)))
    def test_portal_rule_checks_actual_word_not_only_the_configuration(self):
        output=self.base.build_letter();self.conflict()
        portal.resolve(self.project,"layout","portal.layout",
            "The current live upload form imposes 11 point for this exact cover-letter role, so the previous public guide rule is replaced in this attempt.")
        jc.seal(self.project)
        self.assertEqual(next(r for r in rules.measure(self.project,{}) if r["rule_id"]=="portal.layout")["status"],"FAIL")
        proc=subprocess.run([sys.executable,str(fixture.ROOT/"tools/manuscript/build_docx.py"),"build","--kind","cover_letter",
            "--input",str(self.project/"08_submission/cover_letter.md"),"--output",str(output),
            "--style-config",str(self.project/"08_submission/docx_style.json")],
            env={**os.environ,"MEDPAPER_PROJECT":str(self.project)},capture_output=True,text=True,timeout=60)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertEqual(next(r for r in rules.measure(self.project,{}) if r["rule_id"]=="portal.layout")["status"],"PASS")

    def test_portal_capture_does_not_discharge_a_guide_browser_handoff(self):
        url=load(self.project,jc.TARGET)["guidelines_url"]
        guides.browser_handoff(self.project,url,"captcha")
        file=self.write("temp/portal-visible.txt",PORTAL)
        guides.capture(self.project,url,file=file,source_kind="portal",retrieved_at=jc.now(),
                       why="Controlled actual visible browser export at a shared publisher URL for portal-only requirements")
        self.assertEqual(jc.current(self.project)["browser_handoff"]["status"],"waiting_for_user")

    def test_portal_login_handoff_clears_only_on_real_portal_capture(self):
        target=load(self.project,jc.TARGET);target["submission_url"]="https://portal.example.org/submit"
        atomic_json(self.project/jc.TARGET,target)
        guides.browser_handoff(self.project,target["submission_url"],"login",source_kind="portal")
        self.portal()
        self.assertEqual(jc.current(self.project)["browser_handoff"]["status"],"source_captured")

    def test_session_bearing_url_is_not_saved(self):
        with self.assertRaisesRegex(ValueError,"session-bearing"):
            guides.browser_handoff(self.project,load(self.project,jc.TARGET)["guidelines_url"]+"?session=synthetic-not-a-secret","login")
        with self.assertRaisesRegex(ValueError,"session-bearing"):
            jc.allowed_url(self.project,load(self.project,jc.TARGET)["guidelines_url"]+"#access_token=synthetic-placeholder")

    def test_observed_html_links_are_available_for_complete_guide_reading(self):
        url=load(self.project,jc.TARGET)["guidelines_url"]
        raw=(f'<html><body><p>{fixture.TEXT}</p><a href="/artwork">Artwork instructions</a>'
             '<a href="/supplements#format">Supplementary-file rules</a><script><a href="/hidden">hidden</a></script></body></html>').encode()
        with patch("wfcore.guides.download",return_value=(raw,url,"text/html")):
            source=guides.capture(self.project,url,mode="http")
        self.assertIn("https://a.example.org/artwork",source["discovered_links"])
        self.assertIn("https://a.example.org/supplements",source["discovered_links"])
        self.assertNotIn("https://a.example.org/hidden",source["discovered_links"])

    def uploads(self):
        self.write("08_submission/bundle/manuscript.docx","Synthetic controlled upload bytes, not an actual document")
        self.write("08_submission/bundle/Figure1.tif","Synthetic controlled image bytes")
        self.write("08_submission/bundle/internal-preview.txt","Do not upload this unused preview")
        atomic_json(self.project/"08_submission/bundle/manifest.json",{"items":[
            {"role":"manuscript","file":"08_submission/bundle/manuscript.docx"},
            {"role":"figure","file":"08_submission/bundle/Figure1.tif"},
            {"role":"preview","file":"08_submission/bundle/internal-preview.txt","upload":False}]})

    def test_named_delivery_contains_exact_uploads_with_journal_and_local_date(self):
        self.uploads();row=portal.deliver(self.project);directory=self.project/row["directory"]
        self.assertRegex(directory.name,r"Synthetic_Journal_A_\d{4}-\d{2}-\d{2}")
        self.assertEqual({p.name for p in directory.iterdir()},{"manuscript.docx","Figure1.tif"})
        self.assertEqual(row["preparation_timezone"],"Asia/Shanghai")
        self.assertNotIn("submitted_at",row)
        self.assertTrue(all(not p.stat().st_mode&stat.S_IWUSR for p in directory.iterdir()))
        self.assertEqual(portal.deliver(self.project)["directory"],row["directory"])

    def test_bundle_change_creates_collision_safe_new_directory_preserving_old(self):
        self.uploads();old=portal.deliver(self.project);old_path=self.project/old["directory"]/"manuscript.docx"
        original=old_path.read_bytes();self.write("08_submission/bundle/manuscript.docx","New controlled upload")
        new=portal.deliver(self.project)
        self.assertNotEqual(old["directory"],new["directory"]);self.assertTrue(new["directory"].endswith("_02"))
        self.assertEqual(old_path.read_bytes(),original)

    def test_author_edit_of_named_copy_is_detected_and_never_overwritten(self):
        self.uploads();row=portal.deliver(self.project);path=self.project/row["directory"]/"manuscript.docx"
        path.chmod(path.stat().st_mode|stat.S_IWUSR);path.write_bytes(b"Author modification must survive")
        self.assertEqual(portal.delivery_status(self.project)["status"],"changed_or_missing")
        with self.assertRaisesRegex(ValueError,"reconcile"):
            portal.deliver(self.project)
        self.assertEqual(path.read_bytes(),b"Author modification must survive")

    def test_switch_does_not_inherit_portal_exception_or_overwrite_old_named_directory(self):
        self.uploads();row=portal.deliver(self.project);old=self.project/row["directory"]
        self.portal();new=self.base.begin({**self.base.target,"journal":"Synthetic Journal B","issn":"8765-4321",
                                          "guidelines_url":"https://b.example.org/authors"})
        self.assertNotIn("delivery",new);self.assertEqual(new["sources"],{});self.assertTrue(old.is_dir())
        with self.assertRaisesRegex(ValueError,"official"):
            jc.allowed_url(self.project,"https://portal.example.org/submit")


if __name__=="__main__":unittest.main(verbosity=2)
