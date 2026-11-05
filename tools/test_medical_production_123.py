"""Synthetic language/version counterexamples and a real R forest export."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from text.polish import lint_ai, lint_structure, lint_style
from wfcore import registry
from wfcore.checks import Ctx
from wfcore.checks.polish import ai_tells_clean, style_consistent
from wfcore.readiness import atomic_json
from wfcore.state import State

ROOT=Path(__file__).resolve().parents[1]


class MedicalProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-production-123-")
        self.addCleanup(self.tmp.cleanup); self.project=Path(self.tmp.name)
        self.pipe=registry.load(); self.state=State(self.project).create("medpaper","1.23.0","S22_polish")
        self.rel="08_submission/integration/full_manuscript.md"
        self.text(self.rel,"# Discussion\n\nHealthcare utilization was the outcome.\n")
    def text(self,rel,value):
        path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
    def ctx(self): return Ctx(self.pipe,self.state,self.project,self.pipe.stage("S22_polish"),{})
    def lint(self):
        result=subprocess.run([sys.executable,str(ROOT/"tools/text/polish.py"),"lint","--json"],
                              env={**os.environ,"MEDPAPER_PROJECT":str(self.project),"PYTHONIOENCODING":"utf-8"},
                              text=True,encoding="utf-8",capture_output=True,timeout=30)
        self.assertIn(result.returncode,(0,2),result.stdout+result.stderr)
        return result,json.loads(result.stdout)
    def test_legitimate_utilization_and_leverage_are_not_inflated_verbs(self):
        text="Healthcare utilization and drug utilisation were measured. High-leverage observations and regression leverage diagnostics were examined."
        self.assertEqual(lint_ai("methods.md",text,{}),[])
    def test_generic_verbs_remain_advice_without_rewriting_science(self):
        text="# Discussion\n\nWe utilized the database and leveraged the registry.\n"
        path=self.text(self.rel,text); result,report=self.lint()
        self.assertEqual(result.returncode,0);self.assertEqual(len(report["ai_tells"]),2)
        self.assertTrue(all(x["severity"]=="advisory" for x in report["ai_tells"]))
        self.assertTrue(ai_tells_clean(self.ctx()).ok);self.assertEqual(path.read_text(encoding="utf-8"),text)
    def test_density_and_justified_uncertainty_do_not_force_stronger_claims(self):
        risks=lint_structure("discussion.md","Moreover, this may potentially reflect confounding — the direction is unknown. Furthermore, precision is limited.")
        self.assertTrue(risks);self.assertTrue(all(x["severity"]=="advisory" for x in risks))
    def test_causal_keyword_does_not_turn_a_negation_into_an_error(self):
        risks=lint_style("discussion.md","A causal relationship has not been proven.")
        self.assertTrue(any(x["kind"]=="causal_overclaim" for x in risks))
        self.assertTrue(all(x["severity"]=="advisory" for x in risks))
    def test_actual_unit_notation_defects_still_block(self):
        self.text(self.rel,"# Discussion\n\nThe recorded dose was 5mg.\n")
        result,report=self.lint();self.assertEqual(result.returncode,2)
        self.assertTrue(any(x["kind"]=="unit_spacing" for x in report["style"]))
        self.assertFalse(style_consistent(self.ctx()).ok)
    def test_clean_report_cannot_certify_changed_manuscript(self):
        self.lint();self.assertTrue(ai_tells_clean(self.ctx()).ok)
        self.text(self.rel,"# Discussion\n\nThe recorded dose was 5mg.\n")
        self.assertIn("stale",ai_tells_clean(self.ctx()).detail)
        self.lint();self.assertFalse(style_consistent(self.ctx()).ok)
    def test_added_supplement_and_exception_changes_need_only_fresh_lint(self):
        self.lint();self.text("08_submission/integration/supplementary_methods.md","# Supplementary Methods\n\nRecords were linked using the described procedure.\n")
        self.assertFalse(ai_tells_clean(self.ctx()).ok)
        self.lint();self.assertTrue(ai_tells_clean(self.ctx()).ok)
        self.text("08_submission/integration/polish_allowlist.tsv","utilize (consider 'use')\tSynthetic context\n")
        self.assertFalse(ai_tells_clean(self.ctx()).ok)
        self.lint();self.assertTrue(ai_tells_clean(self.ctx()).ok)
    def test_changed_linter_identity_and_same_basename_substitution_fail(self):
        self.lint();path=self.project/"08_submission/integration/polish_report.json";report=json.loads(path.read_text())
        report["linter_sha256"]="0"*64;atomic_json(path,report)
        self.assertFalse(ai_tells_clean(self.ctx()).ok)
        self.lint();report=json.loads(path.read_text());digest=report["input_hashes"].pop(self.rel)
        report["input_hashes"]["elsewhere/full_manuscript.md"]=digest;atomic_json(path,report)
        self.assertFalse(ai_tells_clean(self.ctx()).ok)
    def test_completed_legacy_report_remains_historical(self):
        atomic_json(self.project/"08_submission/integration/polish_report.json",{"ai_tells":[],"structure":[]})
        self.assertFalse(ai_tells_clean(self.ctx()).ok)
        self.state.data["engine_pin"]="1.22.0";self.state.data["stages"]["S22_polish"]["status"]="done"
        self.assertTrue(ai_tells_clean(self.ctx()).ok)
    def test_real_forest_has_aligned_source_numbers_and_no_refitting(self):
        if not shutil.which("Rscript"): self.skipTest("R unavailable; no real rendering claim")
        script=self.text("forest.R",'''source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_style.R"))
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_recipes.R"))
d <- data.frame(label=c("Primary population","Restricted population","Alternative definition"),
                estimate=c(1.42,1.18,.95),lower=c(1.1,.8,.6),upper=c(1.83,1.74,1.5))
original <- d
stopifnot(inherits(try(medpaper_forest_table(d),silent=TRUE),"try-error"))
p <- medpaper_forest_table(d,measure="Adjusted odds ratio",null=1,log_scale=TRUE)
stopifnot(identical(d,original))
b <- ggplot2::ggplot_build(p)
stopifnot(identical(b$data[[4]]$label,c("1.42 (1.10 to 1.83)","1.18 (0.80 to 1.74)","0.95 (0.60 to 1.50)")))
medpaper_save(p,"Forest",width="double",height_mm=105)
linear <- data.frame(label="Coefficient",estimate=-.0002,lower=-.0004,upper=-.0001)
q <- medpaper_forest_table(linear,measure="Mean difference",null=0,log_scale=FALSE,interval_label="90% CI")
stopifnot(grepl("-0.0002",ggplot2::ggplot_build(q)$data[[4]]$label,fixed=TRUE))
''')
        env={**os.environ,"MEDPAPER_ROOT":str(ROOT),"MEDPAPER_RENDER_STEM":str(self.project/"Forest"),"MEDPAPER_LABEL_POLICY":"{}"}
        result=subprocess.run(["Rscript","--vanilla",str(script)],env=env,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue((self.project/"Forest.png").is_file());self.assertTrue((self.project/"Forest.pdf").is_file())
        svg=(self.project/"Forest.svg").read_text(encoding="utf-8")
        self.assertIn("1.42 (1.10 to 1.83)",svg);self.assertIn("Primary population",svg)
        target=os.environ.get("MEDPAPER_TEST_PREVIEW_DIR")
        if target:
            dest=Path(target);dest.mkdir(parents=True,exist_ok=True)
            for suffix in (".png",".pdf",".svg"):
                shutil.copy2(self.project/("Forest"+suffix),dest/("Forest"+suffix))


if __name__=="__main__": unittest.main(verbosity=2)
