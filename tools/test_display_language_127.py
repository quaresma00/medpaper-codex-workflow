"""Actual display text, scoped vocabulary and current medical read-back; synthetic only."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from wfcore import medicalstyle as m
from wfcore.packagefreeze import _sha256
from wfcore.readiness import atomic_json
from wfcore.state import State
from tables.threeline import write_table
import test_r_figures as r_fixture


class DisplayLanguageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-display-language-");self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)
        self.state=State(self.project).create("medpaper","1.27.0","S17_assemble")
        self.plan={"main_tables":[],"main_figures":[],"supp_tables":[],"supp_figures":[]}
        self.data("01_protocol/artifact_plan.json",self.plan)
        self.text("07_manuscript/full_manuscript.md","# Synthetic medical paper\n\nNo clinical study is represented by this fixture.")

    def data(self,rel,value):atomic_json(self.project/rel,value)
    def text(self,rel,value):
        p=self.project/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding="utf-8");return p
    def table(self,label="Heart-failure admission",footnote="Values are numbers of eligible reports; percentages use known outcome status."):
        p=self.project/"04_tables/main/Table1.xlsx";p.parent.mkdir(parents=True,exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            write_table(p,"Characteristics","Table 1. Clinical characteristics.",["Characteristic","Reports, n (%)"],[[label,"12 (60.0)"]],[footnote])
        self.plan["main_tables"]=[{"id":"Table 1","file":p.relative_to(self.project).as_posix(),"sheet":"Characteristics"}]
        self.data("01_protocol/artifact_plan.json",self.plan)
        return p

    def test_actual_title_header_body_and_footnote_cells_are_located(self):
        path=self.table("n_cases",footnote="Unknown source is stored as unknown_source in this synthetic fixture.")
        self.plan["display_dictionary"]=[{"key":"source_a.case_count","internal":"n_cases","label":"Reports with the outcome",
                                          "definition":"Actual reports meeting the clinical outcome definition","scope":"source_a"}]
        self.data("01_protocol/artifact_plan.json",self.plan)
        before=path.read_bytes()
        issues=m.scan(self.project)
        self.assertTrue(any(i["kind"]=="display_dictionary_label" and i["locator"]=="Characteristics!A3" for i in issues))
        self.assertTrue(any(i["kind"]=="display_code_label" and i["locator"]=="Characteristics!A4" for i in issues))
        self.assertEqual(path.read_bytes(),before)

    def test_supplementary_displays_get_the_same_reader_checks(self):
        self.table("source_A")
        self.plan["supp_tables"]=self.plan.pop("main_tables");self.plan["main_tables"]=[]
        self.plan["supp_tables"][0]["id"]="Table S1"
        self.data("01_protocol/artifact_plan.json",self.plan)
        self.assertTrue(any(i["kind"]=="display_code_label" for i in m.scan(self.project)))

    def test_legitimate_statistical_labels_and_clinical_unknown_are_not_banned(self):
        for label in ("log(OR)","False discovery rate (FDR)","Healthcare utilisation","Unknown","BRCA1","IL-6","Not estimable"):
            with self.subTest(label=label):
                self.assertEqual(m.diagnose_display(label,"table.xlsx","Main!A3",[]),[])

    def test_source_specific_dictionary_never_guesses_a_single_clinical_definition(self):
        rows=[{"key":"a.endpoint","internal":"Outcome A","label":"Heart failure","definition":"Source a clinical outcome","scope":"a"},
              {"key":"b.endpoint","internal":"Outcome A","label":"Hepatic decompensation","definition":"Source b clinical outcome","scope":"b"}]
        issues=m.diagnose_display("Outcome A","figure.svg","SVG text 1",rows)
        self.assertEqual(len(issues),1);self.assertIn("Heart failure",issues[0]["message"]);self.assertIn("Hepatic decompensation",issues[0]["message"])

    def test_only_relevant_dictionary_changes_expire_the_wording_resolution(self):
        row={"key":"a.endpoint","internal":"Outcome A","label":"Heart failure","definition":"Actual source outcome definition","scope":"a"}
        before=m.diagnose_display("Outcome A","figure.svg","SVG text 1",[row])[0]["id"]
        unrelated={"key":"b.other","internal":"Other code","label":"Other clinical outcome","definition":"Another source outcome","scope":"b"}
        self.assertEqual(m.diagnose_display("Outcome A","figure.svg","SVG text 1",[row,unrelated])[0]["id"],before)
        changed={**row,"definition":"A materially changed actual source outcome definition"}
        self.assertNotEqual(m.diagnose_display("Outcome A","figure.svg","SVG text 1",[changed])[0]["id"],before)

    def report(self):
        checks={key:"Synthetic actual observation about "+key+" for this clinical table." for key in m.FIELDS["table"]}
        return {"medical_style_version":1,"display_findings":{"Table 1":{"medical_checks":checks,
                "visible_wording":{"quote":"Heart-failure admission","locator":"Characteristics!A3",
                                  "clinical_reading":"The row names the clinical admission outcome, while the second column counts eligible reports with known status."}}}}

    def test_short_visible_quote_has_to_match_its_current_actual_location(self):
        self.table();report=self.report();self.assertEqual(m.verify(self.project,report),[])
        report["display_findings"]["Table 1"]["visible_wording"]["locator"]="Characteristics!A2"
        self.assertTrue(any("quote/location" in e for e in m.verify(self.project,report)))
        report=self.report();report["display_findings"]["Table 1"]["visible_wording"]["quote"]="unobserved synthetic endpoint"
        self.assertTrue(any("quote/location" in e for e in m.verify(self.project,report)))

    def test_one_quote_does_not_replace_actual_statistic_and_denominator_reading(self):
        self.table();report=self.report()
        del report["display_findings"]["Table 1"]["medical_checks"]["denominators_and_summaries"]
        self.assertTrue(any("denominators_and_summaries" in e for e in m.verify(self.project,report)))

    def test_missing_wording_observation_is_not_backfilled_for_legacy_completed_work(self):
        self.table();report=self.report();del report["display_findings"]["Table 1"]["visible_wording"]
        self.assertTrue(any("visible wording" in e for e in m.verify(self.project,report)))
        self.state.data.update(engine_pin="1.26.0",pipeline_version="1.26.0");self.state.save()
        self.assertEqual(m.verify(self.project,report),[])

    def test_unbound_neighbouring_svg_is_never_taken_as_raster_text(self):
        from PIL import Image
        image=self.project/"figure.png";Image.new("RGB",(80,80),"white").save(image)
        self.text("figure.svg",'<svg xmlns="http://www.w3.org/2000/svg"><text>n_cases</text></svg>')
        entry={"id":"Figure 1","file":"figure.png"}
        self.plan["main_figures"]=[entry];self.data("01_protocol/artifact_plan.json",self.plan)
        self.assertEqual(m.display_surfaces(self.project,entry),("figure.png",[]))
        self.assertEqual(m.scan(self.project),[])

    def test_svg_definitions_and_hidden_nodes_do_not_become_visible_label_evidence(self):
        p=self.text("actual.svg",'<svg xmlns="http://www.w3.org/2000/svg"><defs><text>n_cases</text></defs><g style="display:none"><text>source_A</text></g><text style="fill-opacity:0.00">n_cases</text><text>Adjusted <tspan visibility="hidden">source_A</tspan>odds ratio</text></svg>')
        self.assertEqual(m.visible(p),"Adjusted odds ratio")

    def test_final_word_table_cells_are_checked_without_treating_methods_code_as_table_text(self):
        from docx import Document
        p=self.project/"08_submission/bundle/manuscript.docx";p.parent.mkdir(parents=True)
        document=Document();document.add_paragraph("A genuine software variable p_value is described in Methods.")
        table=document.add_table(rows=1,cols=1);table.cell(0,0).text="source_A"
        document.save(p)
        self.data("08_submission/integration/artifact_plan.json",self.plan)
        self.data("08_submission/bundle/manifest.json",{"items":[{"role":"manuscript","file":"08_submission/bundle/manuscript.docx"}]})
        issues=m.scan(self.project,"journal",True)
        found=[i for i in issues if i["kind"]=="display_code_label"]
        self.assertEqual(len(found),1);self.assertEqual(found[0]["locator"],"Word table 1, row 1, cell 1")

    def test_real_r_png_uses_only_current_bound_svg_and_preserves_sources(self):
        if not shutil.which("Rscript"):self.skipTest("R unavailable; no real render claim")
        case=r_fixture.RFigureTests(methodName="runTest");case.setUp();self.addCleanup(case.doCleanups)
        case.state.data.update(engine_pin="1.27.0",pipeline_version="1.27.0");case.state.save()
        original=(case.project/"03_analysis/results/primary.json").read_bytes()
        case.script.write_text(case.script.read_text().replace('y="Patient group"','y="source_A"'),encoding="utf-8")
        from figures.render_r import render
        render(case.project,"Figure 1")
        issues=m.scan(case.project)
        self.assertTrue(any(i["kind"]=="display_code_label" and i["path"].endswith(".render.svg") for i in issues))
        inputs=m.display_language_inputs(case.project)
        self.assertIn("05_figures/qc/Figure1.render.svg",inputs)
        self.assertIn("03_analysis/results/primary.json",inputs)
        self.assertIn(case.entry["script"],inputs)
        svg=case.project/"05_figures/qc/Figure1.render.svg";before=svg.read_bytes()
        svg.write_bytes(before+b"\n")
        with self.assertRaisesRegex(ValueError,"changed"):m.scan(case.project)
        svg.write_bytes(before)
        case.script.write_text(case.script.read_text().replace('y="source_A"','y="Eligible clinical group"'),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"script changed"):m.scan(case.project)
        render(case.project,"Figure 1")
        self.assertFalse(any(i["kind"]=="display_code_label" for i in m.scan(case.project)))
        self.assertEqual((case.project/"03_analysis/results/primary.json").read_bytes(),original)
        preview=os.environ.get("MEDPAPER_TEST_PREVIEW_DIR")
        if preview:
            dest=Path(preview);dest.mkdir(parents=True,exist_ok=True)
            shutil.copy2(case.project/case.entry["file"],dest/"ClinicalLabels.png")

    def test_real_r_recipe_maps_only_display_labels_not_groups_or_numerical_statistics(self):
        if not shutil.which("Rscript"):self.skipTest("R unavailable; no real render claim")
        case=r_fixture.RFigureTests(methodName="runTest");case.setUp();self.addCleanup(case.doCleanups)
        plan=json.loads((case.project/"01_protocol/artifact_plan.json").read_text())
        plan["display_dictionary"]=[{"key":f"clinical.group_{index}","internal":raw,"label":label,
            "definition":"Synthetic display-only group label for a controlled recipe test","scope":"all"}
            for index,(raw,label) in enumerate((("Group A","Primary clinical population"),("Group B","Restricted clinical population"),("Group C","Alternative clinical definition")),1)]
        plan["display_dictionary"].append({"key":"numeric.group_code","internal":"1.34","label":"Never replace an effect estimate",
                                           "definition":"Synthetic numeric category code not used as a group in this figure","scope":"all"})
        case.data("01_protocol/artifact_plan.json",plan)
        case.script.write_text('''source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_style.R"))
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_recipes.R"))
r <- medpaper_result("03_analysis/results/primary.json")
d <- data.frame(label=unlist(r$groups),estimate=unlist(r$estimate),lower=unlist(r$lower),upper=unlist(r$upper))
original <- d
p <- medpaper_forest_table(d,measure="Adjusted odds ratio",null=1,log_scale=TRUE)
stopifnot(identical(d,original),identical(levels(p$data$label),rev(original$label)))
actual <- ggplot2::ggplot_build(p)
stopifnot(identical(actual$data[[4]]$label,c("1.34 (1.10 to 1.63)","0.87 (0.66 to 1.15)","1.12 (0.93 to 1.35)")))
medpaper_save(p,"05_figures/out/Figure1",width="double",height_mm=100)
''',encoding="utf-8")
        from figures.render_r import render
        render(case.project,"Figure 1")
        svg=(case.project/"05_figures/qc/Figure1.render.svg").read_text(encoding="utf-8")
        for expected in ("Primary clinical population","Restricted clinical population","Alternative clinical definition","1.34 (1.10 to 1.63)"):
            self.assertIn(expected,svg)
        self.assertNotIn("Group A",svg);self.assertNotIn("Never replace an effect estimate",svg)
        preview=os.environ.get("MEDPAPER_TEST_PREVIEW_DIR")
        if preview:
            dest=Path(preview);dest.mkdir(parents=True,exist_ok=True)
            shutil.copy2(case.project/case.entry["file"],dest/"DictionaryLabels.png")


if __name__=="__main__":unittest.main(verbosity=2)
