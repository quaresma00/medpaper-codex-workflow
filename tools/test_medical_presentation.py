"""Synthetic interface/negative controls only; never review the user's absent manuscript."""
import json
from pathlib import Path
import tempfile
import unittest
from wfcore import medicalstyle as m
from wfcore.readiness import atomic_json
from wfcore.packagefreeze import _sha256
from wfcore.state import State

class MedicalPresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="medpaper-medical-style-"); self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name); self.state=State(self.project).create("medpaper","1.15.0","S17_assemble")
        self.plan={"main_tables":[],"main_figures":[],"supp_tables":[],"supp_figures":[]}
        self.data("01_protocol/artifact_plan.json",self.plan)
        self.text("07_manuscript/full_manuscript.md","# Synthetic medical manuscript\n\nNo real findings are represented here.")
    def text(self,rel,value):
        path=self.project/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(value,encoding="utf-8"); return path
    def data(self,rel,value): atomic_json(self.project/rel,value)
    def report(self): return {"medical_style_version":1,"display_findings":{}}
    def test_ordinary_medical_statistical_terms_are_not_a_blacklist(self):
        text="Firth penalized logistic regression, exact confidence intervals, common support, deduplication, Missing, Python 3.13 and R 4.5.2. None of the null hypotheses were rejected."
        self.assertEqual(m.diagnose(text,"methods.md"),[])
    def test_generic_parser_count_is_not_a_patient_count(self):
        issues=m.diagnose("1,234 demographic lines read","FigureX.svg")
        self.assertEqual(issues[0]["kind"],"runtime_count")
        self.assertIn("counting unit",issues[0]["message"])
    def test_implementation_flag_does_not_rewrite_or_prespecify(self):
        text="A data-derived vocabulary frozen after processing used Unicode normalization."
        self.text("07_manuscript/full_manuscript.md",text)
        before=(self.project/"07_manuscript/full_manuscript.md").read_bytes()
        self.assertTrue(m.scan(self.project)); self.assertEqual((self.project/"07_manuscript/full_manuscript.md").read_bytes(),before)
        self.assertNotIn("predefined",m.visible(self.project/"07_manuscript/full_manuscript.md"))
    def test_actual_xlsx_all_sheets_and_mixed_footnotes(self):
        from openpyxl import Workbook
        path=self.project/"04_tables/t.xlsx"; path.parent.mkdir(parents=True)
        book=Workbook(); sheet=book.active; sheet.title="Main"
        sheet.append(["Median age (IQR)","50 (40-60)"]); sheet.append([None,"Collapse step"])
        sheet.append(["Values are numbers of reports (column percentage)."])
        book.create_sheet("Second").append(["Not fitted"]); book.save(path)
        text=m.visible(path); issues=m.diagnose(text,"04_tables/t.xlsx")
        self.assertIn("Second!1",text)
        self.assertTrue({"summary_footnote","processing_label","software_state"}.issubset({r["kind"] for r in issues}))
    def test_mixed_summary_exception_is_not_falsely_rejected(self):
        self.assertFalse(any(r["kind"]=="summary_footnote" for r in m.diagnose("Median (IQR). Values are numbers of reports unless otherwise indicated.","table.xlsx")))
    def test_no_automatic_collapse_of_missing_or_unbounded_states(self):
        text="Not fitted; Undefined; NA; unbounded confidence interval; observed zero."
        self.text("07_manuscript/full_manuscript.md",text); m.scan(self.project)
        self.assertEqual((self.project/"07_manuscript/full_manuscript.md").read_text(),text)
    def test_raster_text_is_not_inferred_from_a_filename(self):
        path=self.text("05_figures/Figure1.png","not actually an image; scan does not pretend to inspect raster contents")
        self.assertEqual(m.visible(path),"")
    def test_svg_reader_reads_visible_text_not_script_variables(self):
        path=self.text("05_figures/a.svg",'<svg xmlns="http://www.w3.org/2000/svg"><text>Clinical outcome</text><metadata>Composite A</metadata></svg>')
        self.assertEqual(m.visible(path),"Clinical outcome")
    def test_present_issue_cannot_be_marked_fixed_or_closed_as_preference(self):
        self.text("07_manuscript/full_manuscript.md","Composite A was reported.")
        issue=m.scan(self.project)[0]; report=self.report()
        report["style_resolutions"]={issue["id"]:{"action":"edited","reason":"Test statement intentionally unchanged for this negative control.","evidence_location":"Synthetic fixture Methods and panel label."}}
        self.assertTrue(m.verify(self.project,report))
        report["style_resolutions"][issue["id"]]["action"]="retained"
        self.assertEqual(m.verify(self.project,report),[])
    def test_changed_issue_invalidates_old_retained_reason(self):
        self.text("07_manuscript/full_manuscript.md","Composite A is a synthetic label.")
        issue=m.scan(self.project)[0]; report=self.report()
        report["style_resolutions"]={issue["id"]:{"action":"retained","reason":"A synthetic label retained solely to exercise the controlled interface.","evidence_location":"The synthetic fixture has no real clinical endpoint."}}
        self.text("07_manuscript/full_manuscript.md","Composite B is now a different synthetic label.")
        self.assertTrue(m.verify(self.project,report))
    def test_unrelated_line_shift_does_not_reopen_identical_risk(self):
        before=m.diagnose("Composite A is a synthetic label.","manuscript.md")[0]
        after=m.diagnose("A new heading.\n\nComposite A is a synthetic label.","manuscript.md")[0]
        self.assertEqual(before["id"],after["id"])
    def test_new_acceptance_requires_actual_medical_checks(self):
        self.plan["main_figures"]=[{"id":"Figure 1","file":"05_figures/a.svg"}]
        self.data("01_protocol/artifact_plan.json",self.plan)
        self.text("05_figures/a.svg",'<svg xmlns="http://www.w3.org/2000/svg"><text>Synthetic outcome</text></svg>')
        self.assertTrue(m.verify(self.project,self.report()))
        report=self.report(); report["display_findings"]={"Figure 1":{"medical_checks":{key:"Synthetic controlled observation specifically about "+key for key in m.FIELDS["figure"]}}}
        self.assertEqual(m.verify(self.project,report),[])
    def test_existing_completed_pinned_stage_does_not_retroactively_reopen(self):
        self.state.data["engine_pin"]="1.14.0"; self.state.data["stages"]["S17_assemble"]={"status":"done"}; self.state.save()
        self.assertEqual(m.verify(self.project,{}),[])
    def test_layout_requires_real_render_and_current_bytes(self):
        from PIL import Image
        from docx import Document
        self.data("08_submission/integration/artifact_plan.json",self.plan)
        self.text("08_submission/integration/full_manuscript.md","Synthetic final source.")
        upload=self.project/"08_submission/bundle/manuscript.docx"; upload.parent.mkdir(parents=True)
        doc=Document(); doc.add_paragraph("Synthetic medical fixture."); doc.save(upload)
        self.data("08_submission/bundle/manifest.json",{"items":[{"file":"08_submission/bundle/manuscript.docx","role":"manuscript"}]})
        render=self.project/"08_submission/evidence/page.png"; render.parent.mkdir(parents=True)
        Image.new("RGB",(40,40),"white").save(render)
        report=self.report(); self.assertTrue(m.verify(self.project,report,"journal",True))
        report["document_layout"]=[{"upload":"08_submission/bundle/manuscript.docx","source_sha256":_sha256(upload),"render":"08_submission/evidence/page.png","render_sha256":_sha256(render),"locator":"Synthetic first-page layout location only.","observation":"Controlled blank-page interface fixture, not a real manuscript visual review."}]
        self.assertEqual(m.verify(self.project,report,"journal",True),[])
        Image.new("RGB",(40,40),"black").save(render)
        self.assertTrue(m.verify(self.project,report,"journal",True))
    def test_fake_png_receipt_is_not_a_render(self):
        self.text("08_submission/evidence/fake.png","Not rendered image bytes")
        with self.assertRaises(OSError): m.layout_inputs(self.project,{"document_layout":[{"render":"08_submission/evidence/fake.png"}]})

if __name__=="__main__": unittest.main(verbosity=2)
