"""Synthetic counterexamples for medical display adequacy, hierarchy and panel layout."""
import copy
import argparse
import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
from wfcore.displayquality import story_problems, flat_labels, panel_problems, production_problems
from wfcore.readiness import atomic_json
from wfcore.packagefreeze import _sha256
from wfcore import registry
from wfcore.state import State
from tables.threeline import write_table

ROOT=Path(__file__).resolve().parents[1]


class MedicalDisplaysTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-medical-displays-")
        self.addCleanup(self.tmp.cleanup); self.project=Path(self.tmp.name)
        self.plan={"main_figures":[{"id":"Figure 1","archetype":"flow_diagram"},
                                   {"id":"Figure 2","archetype":"forest_plot"}],
                   "main_tables":[{"id":"Table 1"}],"supp_tables":[{"id":"Table S1"}]}
        roles=[]
        for role,ids in (("selection",["Figure 1"]),("population",["Table 1"]),("primary_results",["Figure 2"]),("comparisons_or_robustness",["Figure 2","Table S1"])):
            row={"role":role,"applicable":True,"display_ids":ids,
                 "scientific_reason":"Synthetic clinical role supported by the actual study question and complete source results.",
                 "comparator_evidence":[{"citekey":"synthetic","locator":"Figure 1, page 2","adopt_or_depart":"Synthetic selection/counting convention is adapted to the study-specific population."}]}
            if role=="selection": row.update(process="multi_stage",steps=["Source reports","Eligible unique reports"],counting_unit_and_branches="Synthetic source rows become unique reports; exposed subsets are nested and not exclusion losses.")
            if role=="population": row["summaries"]={"categorical":"Counts and report percentages with explicit eligible-report denominators.","continuous":"Median and quartiles among observed ages, with available and missing counts."}
            roles.append(row)
        self.benchmark={"comparators":[{"citekey":"synthetic","observations":{"main_figures":6}}],"adaptation":{"displays":{"role_mapping":roles}}}
    def text(self,rel,value):
        p=self.project/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding="utf-8");return p
    def role(self,key): return next(r for r in self.benchmark["adaptation"]["displays"]["role_mapping"] if r["role"]==key)

    def test_lower_quantity_is_valid_when_necessary_roles_are_actually_covered(self):
        self.assertEqual(story_problems(self.plan,self.benchmark),[])
    def test_original_one_forest_and_supplement_count_table_cannot_replace_flow(self):
        self.plan["main_figures"]=[{"id":"Figure 1","archetype":"forest_plot"}]
        self.role("selection")["display_ids"]=["Table S1"]
        self.role("primary_results")["display_ids"]=["Figure 1"]
        self.role("comparisons_or_robustness")["display_ids"]=["Figure 1"]
        errors=story_problems(self.plan,self.benchmark)
        self.assertTrue(any("flow diagram" in p for p in errors))
    def test_flow_must_be_first_and_not_stand_in_for_results(self):
        self.plan["main_figures"][0]["archetype"]="forest_plot"
        self.plan["main_figures"][1]["archetype"]="flow_diagram"
        self.role("selection")["display_ids"]=["Figure 2"]
        self.assertTrue(any("Figure 1" in p for p in story_problems(self.plan,self.benchmark)))
        self.role("primary_results")["display_ids"]=["Figure 2"]
        self.assertTrue(any("clinical result" in p for p in story_problems(self.plan,self.benchmark)))
    def test_no_selection_and_unavailable_additional_analysis_are_honest_exceptions(self):
        self.role("selection").update(applicable=False,display_ids=[],process="none",steps=[],scientific_reason="Synthetic single-case descriptive account without study selection or competing analytic populations.")
        self.role("comparisons_or_robustness").update(applicable=False,display_ids=[],scientific_reason="Synthetic descriptive-only question has no supportable inferential sensitivity analysis.")
        self.assertEqual(story_problems(self.plan,self.benchmark),[])
    def test_existing_selection_cannot_be_declared_inapplicable_to_save_space(self):
        self.role("selection").update(applicable=False,display_ids=[])
        self.assertTrue(any("actual absence" in p for p in story_problems(self.plan,self.benchmark)))
    def test_population_summary_and_real_comparator_locator_are_required(self):
        self.role("population")["summaries"]={}
        self.role("primary_results")["comparator_evidence"][0]["locator"]=""
        problems=story_problems(self.plan,self.benchmark)
        self.assertTrue(any("continuous summaries" in p for p in problems));self.assertTrue(any("comparator page" in p for p in problems))
    def test_flat_export_prefixes_detected_without_banning_medical_terms(self):
        self.assertTrue(flat_labels(["Indication distribution: Unknown","Indication distribution: PBC","Indication distribution: Other"]))
        self.assertEqual(flat_labels(["Sex","Female","Male","Unknown","Drug-induced liver injury","Not estimable"]),[])
    def test_section_headers_indent_without_altering_counts_or_three_line_rules(self):
        output=self.project/"table.xlsx"
        with contextlib.redirect_stdout(io.StringIO()):
            write_table(output,"Table 1","Table 1. Synthetic report characteristics.",["Characteristic","Reports, n (%)"],
                        [["Sex",None],["Female","12 (60.0)"],["Male","6 (30.0)"],["Unknown","2 (10.0)"]],
                        ["Synthetic counts; percentages use 20 reports, not exposed patients."],group_rows=[0],indent_rows=[1,2,3])
        book=load_workbook(output);ws=book.active
        self.assertTrue(ws["A3"].font.bold);self.assertEqual(ws["A4"].alignment.indent,1)
        self.assertEqual(ws["B4"].value,"12 (60.0)");self.assertEqual(ws["B6"].value,"2 (10.0)")
        self.assertTrue(ws["A7"].alignment.wrap_text)
        self.assertGreater(ws.row_dimensions[7].height,15)
        self.assertEqual(ws["A7"].value,"Synthetic counts; percentages use 20 reports, not exposed patients.")
        self.assertIsNone(ws["A4"].border.top.style);self.assertEqual(ws["A6"].border.bottom.style,"thin");book.close()
    def test_group_heading_cannot_hide_a_statistical_observation(self):
        with self.assertRaisesRegex(ValueError,"must not contain observations"):
            write_table(self.project/"bad.xlsx","Table 1","Table 1. Test.",["Feature","n"],[["Sex",20]],["Synthetic test."],group_rows=[0])

    def svg(self,body):
        return self.text("figure.svg",'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">'+body+'</svg>')
    def test_title_letters_are_not_panel_tags_and_bottom_tags_fail(self):
        entry={"panels":["A","B"],"panel_layout":{"columns":1}}
        svg=self.svg('<text x="10" y="10">A Clinical endpoint</text><text x="10" y="210">B Laboratory findings</text>')
        self.assertTrue(panel_problems(svg,entry))
        svg=self.svg('<text x="390" y="190">A</text><text x="390" y="390">B</text>')
        self.assertTrue(any("upper-left" in p for p in panel_problems(svg,entry)))
    def test_independent_tags_at_each_top_left_pass(self):
        entry={"panels":["A","B"],"panel_layout":{"columns":1}}
        svg=self.svg('<text x="10" y="15">A</text><text x="10" y="215">B</text><text x="100" y="30">Clinical endpoint</text>')
        self.assertEqual(panel_problems(svg,entry),[])
    def test_prototype_pass_does_not_release_production(self):
        atomic_json(self.project/"01_protocol/artifact_plan.json",{"main_tables":[{"id":"Table 1","file":"table.xlsx","sheet":"Table 1"}]})
        atomic_json(self.project/"01_protocol/display_review.json",{"items":[{"id":"Table 1","verdict":"PASS"}]})
        self.assertTrue(production_problems(self.project,"table"))
    def test_actual_facets_cannot_evade_tags_by_omitting_declared_panels(self):
        from PIL import Image
        pic=self.project/"figure.png";Image.new("RGB",(500,500),"white").save(pic)
        entry={"id":"Figure 1","renderer":"R","file":"figure.png"}
        atomic_json(self.project/"01_protocol/artifact_plan.json",{"main_figures":[entry]})
        atomic_json(self.project/"05_figures/qc/figure.artist.json",{"n_axes":3})
        row={"reviewed_file":"figure.png","sha256":_sha256(pic),"rendered_preview":"figure.png","rendered_sha256":_sha256(pic),
             "reader_explanation":"Synthetic fixture only: three actual facets require explicit independent labels for readers.",
             "layout_and_style":"Synthetic negative control: no production or scientific visual acceptance is being claimed.","verdict":"PASS"}
        atomic_json(self.project/"01_protocol/display_review.json",{"final_reviews":{"Figure 1":row}})
        self.assertTrue(any("multiple panels" in p for p in production_problems(self.project,"figure")))
    def test_invalid_svg_has_no_fabricated_position_pass(self):
        entry={"panels":["A","B"],"panel_layout":{"columns":1}}
        svg=self.text("invalid.svg",'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 0 0"/>')
        with self.assertRaises(ValueError):panel_problems(svg,entry)
    def test_actual_table_render_and_file_identity_bound_and_drift_revokes(self):
        from PIL import Image,ImageDraw
        table=self.project/"table.xlsx"
        with contextlib.redirect_stdout(io.StringIO()):
            write_table(table,"Table 1","Table 1. Synthetic population.",["Feature","n"],[["Women",12]],["Synthetic report counts."])
        preview=self.project/"preview.png";im=Image.new("RGB",(800,400),"white");ImageDraw.Draw(im).text((20,20),"Synthetic table preview",fill="black");im.save(preview)
        atomic_json(self.project/"01_protocol/artifact_plan.json",{"main_tables":[{"id":"Table 1","file":"table.xlsx","sheet":"Table 1"}]})
        row={"reviewed_file":"table.xlsx","sha256":_sha256(table),"rendered_preview":"preview.png","rendered_sha256":_sha256(preview),
             "reader_explanation":"Synthetic clinical check identifies the eligible report unit and available-case denominator explicitly.",
             "layout_and_style":"Synthetic rendered layout has readable section labels and a separated concise note; no clinical QA is claimed for real data.","verdict":"PASS"}
        atomic_json(self.project/"01_protocol/display_review.json",{"final_reviews":{"Table 1":row}})
        self.assertEqual(production_problems(self.project,"table"),[])
        preview.write_bytes(b"changed synthetic preview")
        self.assertTrue(production_problems(self.project,"table"))
    def test_new_gates_preserve_completed_legacy_stages(self):
        from wfcore.gates import run_stage
        pipe=registry.load();state=State(self.project).create("medpaper","1.21.0","S12_reconcile")
        for sid in ("S07_artifacts","S10_tables","S11_figures","S09_results"):
            state.data["stages"][sid]={"status":"done"};state.save()
            stage=replace(pipe.stage(sid),gate=[g for g in pipe.stage(sid).gate if g["check"].startswith("medical_display_")])
            completed=run_stage(pipe,state,self.project,stage)
            self.assertTrue(completed);self.assertTrue(all(r.ok for r in completed))
            state.data["stages"][sid]={"status":"active"};state.save()
            self.assertTrue(any(r.blocking for r in run_stage(pipe,state,self.project,stage)))
    def test_force_cannot_release_missing_actual_display_review(self):
        from wfcore import cli
        pipe=registry.load();state=State(self.project).create("medpaper","1.22.0","S11_figures")
        stage=replace(pipe.stage("S11_figures"),gate=[{"check":"medical_display_production","kind":"figure","since":"1.22.0"}])
        scoped=replace(pipe,stages=[stage])
        with patch("wfcore.cli._load",return_value=(scoped,state,self.project)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.cmd_advance(argparse.Namespace(force=True,note="synthetic attempted bypass")),2)
        self.assertEqual(state.current,"S11_figures");self.assertFalse(state.is_done("S11_figures"))
    def test_real_r_composition_emits_separate_measured_tags(self):
        if not shutil.which("Rscript"): self.skipTest("R unavailable; no real R claim")
        stem=self.project/"Figure1"
        script=self.text("compose.R",'''source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_style.R"))
library(ggplot2)
d <- data.frame(group=c("Exposed","Reference"),estimate=c(1.2,1.0))
a <- ggplot(d,aes(group,estimate))+geom_point()+labs(title="Clinical endpoint",x="Study group",y="Estimate")+medpaper_theme()
b <- ggplot(d,aes(group,estimate))+geom_point()+labs(title="Laboratory endpoint",x="Study group",y="Estimate")+medpaper_theme()
panels <- list(a,b)
p <- medpaper_compose(panels,ncol=1)
medpaper_save(p,"Figure1",width="double",height_mm=160,panels=panels)
''')
        env={**os.environ,"MEDPAPER_ROOT":str(ROOT),"MEDPAPER_RENDER_STEM":str(stem),"MEDPAPER_LABEL_POLICY":"{}"}
        result=subprocess.run(["Rscript","--vanilla",str(script)],env=env,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(panel_problems(stem.with_suffix(".svg"),{"panels":["A","B"],"panel_layout":{"columns":1}}),[])


if __name__=="__main__": unittest.main(verbosity=2)
