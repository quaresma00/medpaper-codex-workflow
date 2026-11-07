"""Actual synthetic Word builds for author privacy and evidence-backed upload layout."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from docx import Document
from docx.oxml.ns import qn
from wfcore import submissionlayout as sl,journalcontext as jc,guides,guidelinerules,buildproof
from wfcore.readiness import atomic_json
from wfcore.state import State
from wfcore.submission import docx_sections
from tables.threeline import write_table
from test_source_aligned import DEFAULT_STYLE

ROOT=Path(__file__).resolve().parents[1]
PAPER='''# A controlled synthetic manuscript for submission layout tests

# Abstract
This synthetic specimen verifies document organization and makes no research claim.

Keywords: clinical study, synthetic specimen, document layout

# Introduction
The document is a controlled test fixture.

# Methods
The text and precomputed table values are synthetic test inputs.

# Results
The synthetic selection is shown in Figure 1 and the source tables describe the test population.

# Discussion
This specimen tests formatting without making a clinical inference.

# References
1. Controlled synthetic reference used only as a layout specimen.

# Figure legends
## Figure 1. Selection of the synthetic study population.
The boxes identify the eligibility and inclusion steps. Arrows indicate the direction of selection; counts are synthetic fixture values rather than clinical evidence.
'''
GUIDE='''Synthetic current author instructions for Original research.
Embed figure images in the main text after their first citation.
Place figure captions after the paragraph where the figure is first cited.
Place tables in the main text after their first citation.
Upload a separate title page containing the author details.
Name the supplementary methods document ESM1.docx.
All other requirements are unspecified in this controlled fixture.
'''


class SubmissionStructureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-submission-127-");self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)
        self.state=State(self.project).create("medpaper","1.27.0","S23_package")
        self.target={"journal":"Synthetic Journal","issn":"1234-5678","article_type":"Original research",
                     "guidelines_url":"https://example.org/guide","submission_layout":{}}
        self.data(jc.TARGET,self.target)
        self.style=self.data("08_submission/docx_style.json",{**DEFAULT_STYLE,"page_numbers":False})
        self.source=self.text("08_submission/integration/full_manuscript.md",PAPER)
        self.page=self.text("08_submission/integration/title_page.md","# Old draft title must not win\n\nStale Draft Author\n")
        self.authors={"authors":[{"name":"Synthetic Author","affiliations":["1"],"orcid":"0000-0000-0000-0001"}],
                      "affiliations":[{"id":"1","name":"Department of Medicine, Synthetic University"}],
                      "corresponding":{"name":"Synthetic Author","email":"author@example.org","phone":"+8613800123456","address":"Synthetic Road 42"}}
        self.data(sl.AUTHOR_FACTS,self.authors)
        table_dir=self.project/"04_tables/main";table_dir.mkdir(parents=True)
        for i in (1,2):
            with contextlib.redirect_stdout(io.StringIO()):
                write_table(table_dir/f"Table{i}.xlsx",sheet=f"Table{i}",title=f"Table {i}. Synthetic characteristics",
                            header=["Characteristic","Synthetic group"],rows=[["Age, years","42"],["Women, n","24"]],
                            footnotes=["All values are invented test inputs; no actual patient data are included."])
        from PIL import Image
        path=self.project/"05_figures/out/Figure1.png";path.parent.mkdir(parents=True)
        Image.new("RGB",(320,180),"white").save(path)
        self.plan={"main_figures":[{"id":"Figure 1","file":"05_figures/out/Figure1.png",
                    "legend_anchor":"The synthetic selection is shown in Figure 1 and the source tables describe the test population.",
                    "anchor":"The synthetic selection is shown in Figure 1 and the source tables describe the test population."}],
                   "main_tables":[{"id":f"Table {i}","file":f"04_tables/main/Table{i}.xlsx","sheet":f"Table{i}"} for i in (1,2)]}
        self.data(sl.PLAN,self.plan)
        self.data("08_submission/submission_requirements.json",{"article_type":"Original research","required_upload_roles":["manuscript"]})

    def text(self,rel,text):
        path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding="utf-8");return path
    def data(self,rel,value):atomic_json(self.project/rel,value);return self.project/rel

    def captured_override(self,**values):
        settings=dict(self.target["submission_layout"]);settings.update(values)
        quotes={"figures":"Embed figure images in the main text after their first citation.",
                "figure_legends":"Place figure captions after the paragraph where the figure is first cited.",
                "tables":"Place tables in the main text after their first citation.",
                "separate_title_page":"Upload a separate title page containing the author details.",
                "supplement_filenames":"Name the supplementary methods document ESM1.docx."}
        settings["evidence"]={key:{"status":"required","source_id":jc.digest(self.target["guidelines_url"])[:16],
                                   "quote":quotes[key],"locator":"Synthetic instruction"} for key in values}
        self.target["submission_layout"]=settings;self.data(jc.TARGET,self.target)
        context={"context_id":"controlled-test-context","identity":jc.identity(self.target),"sources":{},"assets":{}}
        self.data(jc.CONTEXT,context)
        with patch("wfcore.guides.download",return_value=(GUIDE.encode(),self.target["guidelines_url"],"text/plain")):
            source=guides.capture(self.project,self.target["guidelines_url"],mode="http")
        rows=[]
        for topic in sorted(guidelinerules.TOPICS):
            row={"id":topic,"topic":topic,"status":"unspecified","source_id":source["id"],
                 "quote":"Synthetic current author instructions for Original research.","locator":"Synthetic instructions",
                 "reason":"No other clause is assessed by this isolated controlled layout test fixture."}
            if topic=="layout":row.update(status="required",quote=next(iter(settings["evidence"].values()))["quote"],
                                          check={"type":"profile","field":"submission_layout","value":settings,"roles":["manuscript"]})
            rows.append(row)
        self.data(jc.REQUIREMENTS,{"article_type":"Original research","required_upload_roles":["manuscript"],"guide_rules":rows})
        self.text("08_submission/guidelines_extract.md",GUIDE)
        jc.seal(self.project)

    def build(self,kind="manuscript",name=None):
        output=self.project/"08_submission/bundle"/(name or (kind+".docx"))
        src=self.source if kind=="manuscript" else self.page
        proc=subprocess.run([sys.executable,str(ROOT/"tools/manuscript/build_docx.py"),"build","--kind",kind,
                             "--input",str(src),"--output",str(output),"--style-config",str(self.style)],
                            env={**os.environ,"MEDPAPER_PROJECT":str(self.project)},capture_output=True,text=True,timeout=60)
        return proc,output

    def successful(self,*args,**kwargs):
        proc,out=self.build(*args,**kwargs);self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr);return out

    def preview(self,path,name):
        preview=os.environ.get("MEDPAPER_TEST_PREVIEW_DIR")
        if preview:
            dest=Path(preview);dest.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest/name)

    def test_actual_default_main_authors_tables_and_separate_figures(self):
        out=self.successful();doc=Document(out)
        texts=[p.text for p in doc.paragraphs]
        abstract=texts.index("Abstract")
        for line in sl.admin_lines(self.project):self.assertEqual(texts[:abstract].count(line),1)
        self.assertIn("+8613800123456","\n".join(texts));self.assertNotIn("Stale Draft Author","\n".join(texts))
        self.assertEqual(len(doc.inline_shapes),0);self.assertEqual(len(doc.tables),2)
        self.assertEqual(sl.docx_problems(out,self.project,"manuscript"),[])
        _,sections,_=docx_sections(out)
        self.assertNotIn("Synthetic characteristics",sections["References"])
        self.assertIn("Synthetic characteristics",sections["Tables"])
        self.assertIn("boxes",sections["Figure legends"])
        body=list(doc.element.body);ref=next(p._p for p in doc.paragraphs if p.text=="References");leg=next(p._p for p in doc.paragraphs if p.text=="Figure legends")
        for table in doc.tables:self.assertTrue(body.index(ref)<body.index(table._tbl)<body.index(leg))
        # Every table starts a real new-page section; no paragraph pageBreakBefore.
        self.assertGreaterEqual(len(doc.sections),4)
        self.assertFalse(doc.element.xpath(".//w:pageBreakBefore"))
        receipt=buildproof.load(self.project)[out.relative_to(self.project).as_posix()]
        self.assertIn(str((self.project/sl.AUTHOR_FACTS).resolve()),receipt["sources"])
        self.preview(out,"NonblindDefault.docx")

    def test_nonblind_does_not_generate_an_unrequested_separate_title_page(self):
        proc,out=self.build("title_page")
        self.assertNotEqual(proc.returncode,0);self.assertFalse(out.exists())
        main=self.successful()
        manifest={"items":[{"role":"manuscript","file":main.relative_to(self.project).as_posix()},
                           {"role":"figure","id":"Figure 1","file":"05_figures/out/Figure1.png"}]}
        self.assertEqual(sl.manifest_problems(self.project,manifest),[])
        manifest["items"].append({"role":"title_page","file":"08_submission/bundle/title_page.docx"})
        self.assertTrue(sl.manifest_problems(self.project,manifest))

    def test_double_blind_keeps_actual_authors_only_on_title_page(self):
        self.target["blinded_main_manuscript"]=True;self.data(jc.TARGET,self.target)
        main=self.successful();page=self.successful("title_page")
        main_text="\n".join(p.text for p in Document(main).paragraphs);page_text="\n".join(p.text for p in Document(page).paragraphs)
        self.assertNotIn("Synthetic Author",main_text);self.assertNotIn("0000-0000-0000-0001",main_text)
        self.assertIn("Synthetic Author",page_text);self.assertIn("0000-0000-0000-0001",page_text)
        self.assertEqual(Document(main).paragraphs[0].text,Document(page).paragraphs[0].text)
        self.assertFalse(Document(main).core_properties.author)
        self.preview(main,"BlindMain.docx");self.preview(page,"BlindTitlePage.docx")

    def test_explicit_separate_title_page_and_main_use_same_author_source(self):
        self.captured_override(separate_title_page=True)
        main=self.successful();page=self.successful("title_page")
        for path in (main,page):
            text="\n".join(p.text for p in Document(path).paragraphs)
            for line in sl.admin_lines(self.project):self.assertIn(line,text)
        self.authors["authors"][0]["name"]="Updated Synthetic Author";self.authors["corresponding"]["name"]="Updated Synthetic Author"
        self.data(sl.AUTHOR_FACTS,self.authors)
        for path in (main,page):self.assertTrue(sl.docx_problems(path,self.project,"manuscript" if path==main else "title_page"))

    def test_inline_images_need_real_required_clause_and_preserve_caption_independence(self):
        self.target["submission_layout"]={"figures":"inline"};self.data(jc.TARGET,self.target)
        with self.assertRaises(ValueError):sl.policy(self.project)
        self.target["submission_layout"]={}
        self.captured_override(figures="inline")
        out=self.successful();doc=Document(out)
        self.assertEqual(len(doc.inline_shapes),1)
        self.assertIn("Figure legends",[p.text for p in doc.paragraphs])
        self.target["submission_layout"]["evidence"]["figures"]["status"]="allowed";self.data(jc.TARGET,self.target)
        with self.assertRaises(ValueError):sl.policy(self.project)

    def test_caption_inline_rule_does_not_embed_image_or_pollute_results_counts(self):
        self.captured_override(figure_legends="inline")
        out=self.successful();doc=Document(out)
        self.assertEqual(len(doc.inline_shapes),0)
        self.assertNotIn("Figure legends",[p.text for p in doc.paragraphs])
        _,sections,_=docx_sections(out)
        self.assertNotIn("boxes",sections["Results"]);self.assertIn("boxes",sections["Figure legends"])
        self.assertEqual(sl.caption_problems(doc,["Figure 1"]),[])
        self.preview(out,"InlineCaption.docx")

    def test_meaningful_supplement_names_and_real_explicit_override(self):
        name=sl.supplemental_name(1,"Supplementary Methods","docx")
        self.assertEqual(name,"Supplemental_File_1_Supplementary_Methods.docx")
        manifest={"items":[{"role":"supplementary","file":"08_submission/bundle/"+name}]}
        self.assertEqual(sl.manifest_problems(self.project,manifest),[])
        manifest["items"][0]["file"]="08_submission/bundle/ESM1.docx"
        self.assertTrue(sl.manifest_problems(self.project,manifest))
        self.captured_override(supplement_filenames={"supplementary":"ESM1.docx"})
        self.assertEqual(sl.manifest_problems(self.project,manifest),[])

    def test_stale_foreign_guide_cannot_authorize_layout_change(self):
        self.captured_override(figures="inline")
        context=jc.current(self.project);source=next(iter(context["sources"].values()))
        (self.project/source["text"]).write_text("This is a changed guide from a different journal",encoding="utf-8")
        with self.assertRaises(ValueError):sl.policy(self.project)

    def test_explicit_inline_tables_are_excluded_from_prose_and_reference_counts(self):
        anchor="The synthetic selection is shown in Figure 1 and the source tables describe the test population."
        for entry in self.plan["main_tables"]:entry.update(anchor=anchor,orientation="portrait")
        self.data(sl.PLAN,self.plan)
        self.captured_override(tables="inline")
        out=self.successful();doc=Document(out)
        _,sections,_=docx_sections(out)
        self.assertEqual(sections["Results"],anchor)
        self.assertIn("Synthetic characteristics",sections["Tables"])
        self.assertIn("Age, years",sections["Tables"])
        self.assertIn("All values are invented",sections["Tables"])
        self.assertNotIn("Synthetic characteristics",sections["References"])
        self.assertEqual(len(doc.tables),2)
        captions=[p.text for p in doc.paragraphs if p.text.startswith(("Table 1.","Table 2."))]
        self.assertEqual(captions,["Table 1. Synthetic characteristics","Table 2. Synthetic characteristics"])
        # Portrait inline tables flow with the citing text; page breaks separate
        # author front matter and final legends, never the inline tables themselves.
        self.assertEqual(len(doc.sections),1)
        self.assertFalse(doc.element.xpath(".//w:pPr/w:sectPr"))
        legend=next(p for p in doc.paragraphs if p.text=="Figure legends")
        self.assertTrue(legend._p.getprevious().xpath(".//w:br[@w:type='page']"))
        self.preview(out,"InlineTables.docx")

    def test_current_journal_heading_aliases_are_checked_in_actual_word(self):
        self.target["main_text_headings"]={"Abstract":"Summary","References":"Bibliography","Figure legends":"Figure captions"}
        self.data(jc.TARGET,self.target)
        out=self.successful();doc=Document(out)
        self.assertIn("Figure captions",[p.text for p in doc.paragraphs])
        self.assertEqual(sl.docx_problems(out,self.project,"manuscript"),[])
        _,sections,_=docx_sections(out,{v.casefold():k for k,v in self.target["main_text_headings"].items()})
        self.assertIn("synthetic",sections["Abstract"])
        self.assertNotIn("Synthetic characteristics",sections["References"])

    def test_inline_table_orientation_restores_the_surrounding_portrait_text(self):
        from docx.enum.section import WD_SECTION_START,WD_ORIENT
        anchor="The synthetic selection is shown in Figure 1 and the source tables describe the test population."
        for index,entry in enumerate(self.plan["main_tables"]):
            entry.update(anchor=anchor,orientation="landscape" if index==0 else "portrait")
        self.data(sl.PLAN,self.plan);self.captured_override(tables="inline")
        out=self.successful();doc=Document(out)
        self.assertTrue(any(section.orientation==WD_ORIENT.LANDSCAPE for section in doc.sections))
        self.assertEqual(doc.sections[-1].orientation,WD_ORIENT.PORTRAIT)
        self.assertTrue(all(section.start_type==WD_SECTION_START.CONTINUOUS for section in doc.sections))

    def test_double_blind_audit_checks_affiliations_beyond_author_names(self):
        from wfcore.journalspec import blind_problems
        self.target["blinded_main_manuscript"]=True;self.data(jc.TARGET,self.target)
        out=self.successful();doc=Document(out)
        doc.add_paragraph("Department of Medicine, Synthetic University");doc.save(out)
        problems=blind_problems(out,self.project,"manuscript")
        self.assertTrue(any("Synthetic University" in p for p in problems))
        self.assertEqual(blind_problems(out,self.project,"title_page"),[])


if __name__=="__main__":unittest.main(verbosity=2)
