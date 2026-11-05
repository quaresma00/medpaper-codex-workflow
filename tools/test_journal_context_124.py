"""Synthetic transfer/guide/output regressions; no real study or submission changes."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from wfcore import journalcontext as jc, guides, guidelinerules as gr, registry, journalworkspace, buildproof
from wfcore.readiness import atomic_json, load
from wfcore.state import State
from wfcore.checks import Ctx,load_all,get
import test_kiro_v190 as legacy
from test_source_aligned import DEFAULT_STYLE

ROOT=Path(__file__).resolve().parents[1]
TEXT="""Synthetic Journal author instructions for Original research.
Layout: Use Times New Roman 12 point. Double spacing is optional in this synthetic fixture.
Submission files must include a cover letter. Main text must not exceed 4000 words.
All authors must approve the actual cover letter and its statements.
Other topics: article type, length, abstract, keywords, references, figures, tables,
supplements, statements, uploads, layout, blinding, cover letter are assessed in this synthetic fixture.
"""


class JournalContextTests(unittest.TestCase):
    def setUp(self):
        self.base=legacy.NewMigrationTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.project=self.base.project;self.base.freeze()
        self.state=State(self.project).load();self.state.data.update(pipeline_version="1.24.0",engine_pin="1.23.0",current="S20_journal")
        self.state.data["stages"]["S20_journal"]={"status":"active"};self.state.save()
        self.target={"journal":"Synthetic Journal A","issn":"1234-5678","article_type":"Original research",
                     "submission_stage":"initial","guidelines_url":"https://a.example.org/authors"}
        self.begin()
    def text(self,rel,value):
        path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
    def data(self,rel,value): atomic_json(self.project/rel,value);return self.project/rel
    def begin(self,target=None): return jc.begin(self.project,target or self.target)
    def capture(self,text=TEXT,url=None):
        url=url or jc.current(self.project)["identity"]["journal"]
        if not url.startswith("https:"):url=load(self.project,jc.TARGET)["guidelines_url"]
        with patch("wfcore.guides.download",return_value=(text.encode(),url,"text/plain")):
            return guides.capture(self.project,url,mode="http")
    def ready(self,manual=False):
        source=self.capture();rows=[]
        for topic in sorted(gr.TOPICS):
            row={"id":topic,"topic":topic,"status":"unspecified","source_id":source["id"],"locator":"Synthetic guide",
                 "quote":"Synthetic Journal author instructions for Original research.",
                 "reason":"This controlled fixture declares no further actual journal constraint for this topic."}
            if topic=="layout":row.update(status="required",quote="Use Times New Roman 12 point.",
                                          check={"type":"style","field":"body_font_pt","value":12,"roles":["cover_letter"]})
            if topic=="uploads":row.update(status="required",quote="Submission files must include a cover letter.",
                                           check={"type":"uploads","value":["cover_letter"]})
            if manual and topic=="statements":row.update(status="required",quote="All authors must approve the actual cover letter and its statements.",
                                                        check={"type":"manual","roles":["cover_letter"]})
            rows.append(row)
        self.data(jc.REQUIREMENTS,{"article_type":"Original research","required_upload_roles":["cover_letter"],"guide_rules":rows})
        self.data("08_submission/docx_style.json",{**DEFAULT_STYLE,"page_numbers":False})
        self.text("08_submission/guidelines_extract.md",TEXT)
        return jc.seal(self.project)
    def build_letter(self):
        self.ready()
        src=self.text("08_submission/cover_letter.md","# Dear Editor\n\nThis is a controlled synthetic submission letter. No actual author approval or clinical result is asserted.\n")
        output=self.project/"08_submission/bundle/cover_letter.docx"
        result=subprocess.run([sys.executable,str(ROOT/"tools/manuscript/build_docx.py"),"build","--kind","cover_letter",
            "--input",str(src),"--output",str(output),"--style-config",str(self.project/"08_submission/docx_style.json")],
            env={**os.environ,"MEDPAPER_PROJECT":str(self.project)},capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.data("08_submission/bundle/manifest.json",{"items":[{"role":"cover_letter","file":output.relative_to(self.project).as_posix(),
            "source_files":[src.relative_to(self.project).as_posix()],"required_by":"Synthetic guide: Submission files"}]})
        return output
    def test_begin_switch_archives_guides_configs_bundle_and_preserves_science(self):
        self.ready();before={r:(self.project/r).read_bytes() for r in ("07_manuscript/full_manuscript.md","07_manuscript/scientific_master_freeze.json")}
        self.text("08_submission/cover_letter.md","Task-owned old journal letter")
        self.text("08_submission/bundle/old.docx","Synthetic old upload")
        self.text("08_submission/my_unrelated_notes.md","User notes preserved")
        target={**self.target,"journal":"Synthetic Journal B","issn":"8765-4321","guidelines_url":"https://b.example.org/authors"}
        new=self.begin(target);archive=self.project/new["previous_archive"]
        for name in ("docx_style.json","submission_requirements.json","guidelines_extract.md","cache","bundle","cover_letter.md"):
            self.assertTrue((archive/name).exists());self.assertFalse((self.project/"08_submission"/name).exists())
        self.assertTrue((self.project/"08_submission/my_unrelated_notes.md").is_file())
        for rel,value in before.items():self.assertEqual((self.project/rel).read_bytes(),value)
        self.assertTrue(jc.problems(self.project));self.assertEqual(State(self.project).load().current,"S20_journal")
    def test_same_context_resume_does_not_erase_edits(self):
        self.ready();edited=self.text("08_submission/integration/author_edit.md","Author's retained edit")
        old=jc.current(self.project);new=self.begin();self.assertEqual(old,new);self.assertTrue(edited.is_file())
    def test_same_journal_article_type_or_submission_stage_starts_new_attempt(self):
        initial=jc.current(self.project)["context_id"]
        changed=self.begin({**self.target,"article_type":"Short report"})
        self.assertNotEqual(initial,changed["context_id"])
        revision=self.begin({**self.target,"article_type":"Short report","submission_stage":"revision"})
        self.assertNotEqual(changed["context_id"],revision["context_id"])
    def test_deleted_or_restored_old_context_cannot_disable_guard(self):
        self.ready();old=load(self.project,jc.CONTEXT);(self.project/jc.CONTEXT).unlink()
        self.assertTrue(jc.enabled(self.project));self.assertTrue(jc.problems(self.project))
        self.begin({**self.target,"journal":"Synthetic B","issn":"8765-4321"})
        self.data(jc.CONTEXT,old)
        self.assertTrue(jc.problems(self.project))
    def test_old_rules_and_untraceable_quote_cannot_be_sealed(self):
        self.ready();req=load(self.project,jc.REQUIREMENTS);req["journal_context_id"]="old-attempt";self.data(jc.REQUIREMENTS,req)
        with self.assertRaisesRegex(ValueError,"another journal"):jc.seal(self.project)
        req.pop("journal_context_id");req["guide_rules"][0]["quote"]="This invented rule never appeared in the downloaded source";self.data(jc.REQUIREMENTS,req)
        with self.assertRaisesRegex(ValueError,"real passage"):jc.seal(self.project)
    def test_config_drift_and_missing_topic_block_before_build(self):
        self.ready();style=load(self.project,"08_submission/docx_style.json");style["body_font_pt"]=11;self.data("08_submission/docx_style.json",style)
        with self.assertRaises(ValueError):jc.guard(self.project)
        with self.assertRaisesRegex(ValueError,"configuration"):jc.seal(self.project)
        style["body_font_pt"]=12;self.data("08_submission/docx_style.json",style)
        req=load(self.project,jc.REQUIREMENTS);req["guide_rules"].pop();self.data(jc.REQUIREMENTS,req)
        with self.assertRaisesRegex(ValueError,"unassessed"):jc.seal(self.project)
    def test_complete_original_text_and_registration_basis_preserved(self):
        raw=b'\xef\xbb\xbf'+TEXT.encode();src=self.project/"download.txt";src.write_bytes(raw)
        source=guides.capture(self.project,self.target["guidelines_url"],file=src,why="Synthetic official-download registration, not an HTTP fetch",retrieved_at=jc.now())
        self.assertEqual((self.project/source["raw"]).read_bytes(),raw);self.assertEqual(src.read_bytes(),raw)
        self.assertEqual(source["mode"],"registered")
        with self.assertRaisesRegex(ValueError,"retrieved-at"):
            guides.capture(self.project,self.target["guidelines_url"],file=src,why="Synthetic real-source registration")
    def test_html_retains_table_details_even_when_reader_filter_omits_them(self):
        html=f'<html><body><h1>Author instructions</h1><p>{TEXT}</p><table><tr><td>Special upload</td><td>300 dpi TIFF only</td></tr></table><script>bad()</script></body></html>'.encode()
        suffix,text,reader=guides.extract(html,".html")
        self.assertIn("300 dpi TIFF only",text);self.assertNotIn("bad()",text)
    def test_challenge_success_response_requires_real_browser_fallback(self):
        async def browser(url):return (TEXT.encode(),url,"text/plain")
        with patch("wfcore.guides.download",return_value=(b'<html>Just a moment. Verify you are human.</html>',self.target["guidelines_url"],"text/html")),patch("wfcore.guides.browser_download",side_effect=browser):
            source=guides.capture(self.project,self.target["guidelines_url"])
        self.assertEqual(source["mode"],"browser")
    def test_blocked_fetch_never_fabricates_a_source_or_hides_failure(self):
        with patch("wfcore.guides.download",side_effect=OSError("403 denied")):
            with self.assertRaises(ValueError):guides.capture(self.project,self.target["guidelines_url"],mode="http")
        self.assertEqual(jc.current(self.project)["sources"],{})
    def test_unapproved_redirect_and_previous_journal_host_rejected(self):
        with patch("wfcore.guides.download",return_value=(TEXT.encode(),"https://elsewhere.example.org/authors","text/plain")):
            with self.assertRaisesRegex(ValueError,"official"):guides.capture(self.project,self.target["guidelines_url"],mode="http")
    def test_refresh_same_rules_does_not_invalidate_build_but_real_change_does(self):
        self.ready();first=jc.build_identity(self.project)
        self.capture(TEXT+"\nNew navigation footer.\n");self.assertTrue(jc.problems(self.project))
        jc.seal(self.project);self.assertEqual(first,jc.build_identity(self.project))
        style=load(self.project,"08_submission/docx_style.json");style["line_spacing"]=1.5;self.data("08_submission/docx_style.json",style)
        jc.seal(self.project);self.assertNotEqual(first,jc.build_identity(self.project))
    def test_live_docx_font_defect_is_measured_not_merely_configuration(self):
        output=self.build_letter();rows=gr.measure(self.project,{})
        self.assertTrue(all(r["status"]=="PASS" for r in rows),rows)
        from docx import Document
        from docx.shared import Pt
        doc=Document(output);doc.paragraphs[-1].runs[0].font.size=Pt(10);doc.save(output)
        rows=gr.measure(self.project,{})
        self.assertEqual(next(r for r in rows if r["rule_id"]=="layout")["status"],"FAIL")
    def test_build_receipt_binds_attempt_and_reuses_metadata_only_refresh(self):
        output=self.build_letter();rel=output.relative_to(self.project).as_posix();receipt=buildproof.load(self.project)[rel]
        self.assertEqual(receipt["journal_context_id"],jc.current(self.project)["context_id"])
        target=load(self.project,jc.TARGET);target["guidelines_fetched_at"]="2026-11-06";self.data(jc.TARGET,target)
        self.assertTrue(buildproof.inputs_current(receipt))
        self.begin({**self.target,"journal":"Synthetic B","issn":"8765-4321"})
        self.assertNotIn(rel,buildproof.load(self.project));self.assertFalse(output.exists())
    def test_manual_review_requires_actual_upload_and_render_then_drift_invalidates(self):
        output=self.build_letter();self.ready(manual=True)
        rows=gr.measure(self.project,{})
        self.assertEqual(next(r for r in rows if r["rule_id"]=="statements")["status"],"FAIL")
        from PIL import Image
        render=self.project/"08_submission/evidence/preview.png";render.parent.mkdir(parents=True,exist_ok=True);Image.new("RGB",(100,100),"white").save(render)
        rel=output.relative_to(self.project).as_posix()
        review=gr.record_review(self.project,"statements",[rel],render.relative_to(self.project).as_posix(),"Synthetic review of the actual controlled document confirms statement placement; this is not real author approval.")
        self.assertEqual(next(r for r in gr.measure(self.project,{"statements":review}) if r["rule_id"]=="statements")["status"],"PASS")
        render.write_bytes(b"changed");self.assertEqual(next(r for r in gr.measure(self.project,{"statements":review}) if r["rule_id"]=="statements")["status"],"FAIL")
    def test_legacy_completed_attempt_is_not_retroactively_rebuilt(self):
        (self.project/jc.CONTEXT).unlink();state=State(self.project).load();state.data.pop("journal_context_required",None);state.data["stages"]["S20_journal"]["status"]="done";state.save()
        load_all();ctx=Ctx(registry.load(),state,self.project,registry.load().stage("S24_package_human_review"),{"final":True})
        self.assertTrue(get("journal_requirements_current")(ctx).ok)
    def test_current_missing_context_cannot_be_forced(self):
        from wfcore import cli
        from dataclasses import replace
        import argparse
        state=State(self.project).load();pipe=registry.load();stage=replace(pipe.stage("S20_journal"),gate=[{"check":"journal_requirements_current","since":"1.24.0"}])
        with patch("wfcore.cli._load",return_value=(replace(pipe,stages=[stage]),state,self.project)),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.cmd_advance(argparse.Namespace(force=True,note="Synthetic bypass attempt")),2)
    def test_failed_switch_restores_old_attempt(self):
        self.ready();before=(self.project/jc.TARGET).read_bytes();before_context=(self.project/jc.CONTEXT).read_bytes()
        original=jc.atomic_json
        def failing(path,value):
            if path==self.project/jc.CONTEXT:raise OSError("Synthetic disk failure")
            return original(path,value)
        with patch("wfcore.journalcontext.atomic_json",side_effect=failing):
            with self.assertRaises(OSError):self.begin({**self.target,"journal":"Synthetic B","issn":"8765-4321"})
        self.assertEqual((self.project/jc.TARGET).read_bytes(),before);self.assertEqual((self.project/jc.CONTEXT).read_bytes(),before_context)
        self.assertEqual(jc.problems(self.project),[])
    def test_csl_resolves_real_parent_and_rejects_cycles_without_defaults(self):
        ns='xmlns="http://purl.org/net/xbiblio/csl"'
        child=f'<style {ns}><info><link rel="independent-parent" href="http://www.zotero.org/styles/parent"/></info></style>'.encode()
        parent=f'<style {ns}><citation><layout/></citation><bibliography><layout/></bibliography></style>'.encode()
        def response(url):return (parent if url.endswith('/parent.csl') else child,url,'application/xml')
        with patch("wfcore.guides.download",side_effect=response):asset=guides.fetch_csl(self.project,"child")
        self.assertTrue(asset["file"].endswith("/parent.csl"));self.assertEqual((self.project/asset["file"]).read_bytes(),parent)
        with patch("wfcore.guides.download",side_effect=lambda url:(child,url,'application/xml')):
            with self.assertRaisesRegex(ValueError,"cycle"):guides.fetch_csl(self.project,"child")
    def test_csl_rule_does_not_accept_word_built_without_that_style(self):
        output=self.build_letter();ctx=jc.current(self.project)
        csl=self.text("08_submission/cache/csl/synthetic.csl","Synthetic binding fixture, not a deployable CSL")
        ctx['assets']['csl:synthetic']={"file":csl.relative_to(self.project).as_posix(),"sha256":jc._sha256(csl)};self.data(jc.CONTEXT,ctx)
        req=load(self.project,jc.REQUIREMENTS);row=next(r for r in req['guide_rules'] if r['topic']=='references')
        row.update(status='required',check={"type":"csl","path":csl.relative_to(self.project).as_posix(),"roles":["cover_letter"]})
        self.data(jc.REQUIREMENTS,req);jc.seal(self.project)
        result=next(r for r in gr.measure(self.project,{}) if r['rule_id']=='references')
        self.assertEqual(result['status'],'FAIL')
    def test_empty_pdf_is_not_treated_as_successful_guide(self):
        from pypdf import PdfWriter
        stream=io.BytesIO();doc=PdfWriter();doc.add_blank_page(612,792);doc.write(stream)
        with self.assertRaisesRegex(ValueError,"no usable text"):guides.extract(stream.getvalue(),'.pdf')
    def test_new_package_round_keeps_historical_review_ids(self):
        self.build_letter()
        self.data('.wf/review_rounds/P007.json',{"id":"P007","scope":"package","synthetic_history":True})
        from wfcore import reviewrounds
        record=reviewrounds.start(self.project,'package')
        self.assertEqual(record['id'],'P008');self.assertTrue(load(self.project,'.wf/review_rounds/P007.json')['synthetic_history'])
        self.assertIn(jc.CONTEXT,record['before'])
    def test_guideline_switch_is_valid_scoped_work_without_science_replay(self):
        self.build_letter();from wfcore import revision
        state=State(self.project).load();state.data['current']='S24_package_human_review'
        row={"schema_version":2,"round_id":"R001","status":"active","review_stage":"S24_package_human_review",
             "baseline":revision.snapshot(self.project),"items":[{"kind":"journal-switch","owning_stage":"S20_journal",
             "change_type":"administrative","affected_sources":[jc.TARGET]}]}
        revision.plan_scope(self.project,registry.load(),row)
        self.data('.wf/revisions/R001.json',row);state.data['active_revision_round']='R001';state.save()
        self.begin({**self.target,"journal":"Synthetic B","issn":"8765-4321"})
        self.assertEqual(revision.scope_problems(self.project,row),[])
        self.assertNotIn('S05_analysis',row['validation_stages']);self.assertNotIn('S04_data',row['validation_stages'])
    def test_direct_legacy_replace_cannot_carry_old_guidelines_to_new_journal(self):
        self.ready();journalworkspace.initialise(self.project)
        target=load(self.project,jc.TARGET);target['journal']='Synthetic B';target['issn']='8765-4321';self.data(jc.TARGET,target)
        with self.assertRaises(ValueError):journalworkspace.initialise(self.project,replace=True)
    def test_real_official_template_is_used_recorded_and_missing_template_fails(self):
        self.ready()
        from docx import Document
        template=self.project/'downloaded_template.docx';doc=Document()
        doc.sections[0].header.paragraphs[0].text='SYNTHETIC TEMPLATE - controlled test only'
        doc.save(template)
        asset=guides.register_template(self.project,template,self.target['guidelines_url']+'/template.docx',
            'Synthetic official-template fixture; no actual publisher template is claimed',jc.now())
        req=load(self.project,jc.REQUIREMENTS)
        req['guide_rules'].append({"id":"layout.template","topic":"layout","status":"required","source_id":self.capture()['id'],
            "quote":"Synthetic Journal author instructions for Original research.","locator":"Synthetic template fixture",
            "check":{"type":"template","path":asset['file'],"roles":["cover_letter"]}})
        self.data(jc.REQUIREMENTS,req);jc.seal(self.project)
        source=self.text('08_submission/cover_letter.md','# Dear Editor\n\nThis is a synthetic letter testing journal Word template inheritance. It makes no scientific or authorship claim.\n')
        output=self.project/'08_submission/bundle/letter.docx';ref=self.project/asset['file']
        command=[sys.executable,str(ROOT/'tools/manuscript/build_docx.py'),'build','--kind','cover_letter','--input',str(source),'--output',str(output),
                 '--style-config',str(self.project/'08_submission/docx_style.json'),'--reference-doc',str(ref)]
        proc=subprocess.run(command,env={**os.environ,'MEDPAPER_PROJECT':str(self.project)},capture_output=True,text=True,timeout=60)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertIn('SYNTHETIC TEMPLATE',Document(output).sections[0].header.paragraphs[0].text)
        self.data('08_submission/bundle/manifest.json',{"items":[{"role":"cover_letter","file":output.relative_to(self.project).as_posix(),
            "source_files":[source.relative_to(self.project).as_posix()],"required_by":"Synthetic template rule"}]})
        self.assertEqual(next(r for r in gr.measure(self.project,{}) if r['rule_id']=='layout.template')['status'],'PASS')
        from wfcore.rebuild import command as recreate
        receipt=buildproof.load(self.project)[output.relative_to(self.project).as_posix()]
        self.assertIn('--reference-doc',recreate(self.project,output.relative_to(self.project).as_posix(),receipt))
        target=os.environ.get('MEDPAPER_TEST_PREVIEW_DIR')
        if target:
            import shutil
            dest=Path(target);dest.mkdir(parents=True,exist_ok=True);shutil.copy2(output,dest/'template-letter.docx')
        before=output.read_bytes();ref.unlink()
        failed=subprocess.run(command,env={**os.environ,'MEDPAPER_PROJECT':str(self.project)},capture_output=True,text=True,timeout=60)
        self.assertNotEqual(failed.returncode,0);self.assertEqual(output.read_bytes(),before)
    def test_final_measurements_bind_rule_reviews_and_source_drift(self):
        self.build_letter();from wfcore import submissionqc
        with patch('wfcore.submission.verify_portal',return_value=[]):
            measured=submissionqc.write(self.project)
        self.assertTrue(measured['ok'],measured['rows']);self.assertEqual(submissionqc.verify(self.project),[])
        context=jc.current(self.project);source=next(iter(context['sources'].values()))
        (self.project/source['text']).write_text('Changed real-source fixture text',encoding='utf-8')
        self.assertTrue(submissionqc.verify(self.project))


if __name__=="__main__":unittest.main(verbosity=2)
