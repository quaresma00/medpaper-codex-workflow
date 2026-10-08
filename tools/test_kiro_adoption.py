"""Isolated behavioral tests for borrowed concepts, not executions of Kiro code."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from analysis.reproduce import canonical, replay, run, verify
from pubmed.identity import inspect, errors
from wfcore.readiness import atomic_json
from wfcore.checks.numbers import _walk
from wfcore.gatecache import Receipts
from wfcore import registry
from wfcore.state import State

ROOT = Path(__file__).resolve().parents[1]


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="medpaper-adoption-")
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.write("02_data/raw/a.csv", "value\n1.123456789012345\n2.0\n")
        for name in ("a", "b"):
            self.write(f"03_analysis/code/{name}.py", f'''
import csv, os
from pathlib import Path
from analysis.results import write_results, set_seed
set_seed(37)
p=Path(os.environ["MEDPAPER_PROJECT"])
values=[float(r["value"]) for r in csv.DictReader((p/"02_data/raw/a.csv").open())]
write_results("{name}.json", {{"n":len(values),"values":values,"clinical_timestamp":"2026-10-08T12:01:02Z"}}, seed=37,inputs=["02_data/raw/a.csv"])
''')

    def write(self, rel, text):
        out = self.project / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return out

    def execute(self):
        run(self.project, "03_analysis/code/a.py")
        run(self.project, "03_analysis/code/b.py")

    def test_actual_receipts_and_reuse_without_reexecution(self):
        self.execute()
        original = (self.project / "03_analysis/results/a.json").read_bytes()
        self.assertIn("missing/stale", verify(self.project)[0])
        self.assertEqual(len(replay(self.project)), 2)
        self.assertEqual(verify(self.project), [])
        with patch("analysis.reproduce.run", side_effect=AssertionError("Must not rerun unchanged producer")):
            self.assertEqual(replay(self.project), [])
        self.assertEqual(original, (self.project / "03_analysis/results/a.json").read_bytes())

    def test_targeted_change_and_unaffected_proof(self):
        self.execute(); replay(self.project)
        b = self.project / ".wf/reproduction/b.json"
        before = b.read_bytes()
        code = self.project / "03_analysis/code/a.py"
        code.write_text(code.read_text() + "\n# Focused producer correction\n")
        self.assertTrue(verify(self.project))
        run(self.project, "03_analysis/code/a.py")
        self.assertEqual(replay(self.project, ["03_analysis/results/a.json"]), ["03_analysis/code/a.py"])
        self.assertEqual(before, b.read_bytes())
        self.assertEqual(verify(self.project), [])

    def test_input_drift_and_forged_status_do_not_pass(self):
        self.execute(); replay(self.project)
        self.write("02_data/raw/a.csv", "value\n999\n")
        self.assertTrue(verify(self.project))
        atomic_json(self.project / ".wf/analysis_reproduction.json", {"verified":True,"status":"PASS"})
        self.assertTrue(verify(self.project))

    def test_retained_replay_tampering_rejected(self):
        self.execute(); replay(self.project)
        retained = self.project / ".wf/reproduction/a.json"
        value = json.loads(retained.read_text()); value["n"] = 99
        atomic_json(retained,value)
        self.assertTrue(verify(self.project))

    def test_new_project_cannot_use_legacy_receipt_bypass(self):
        self.execute()
        state=State(self.project).create("medpaper","1.9.0","S06_protocol_final")
        state.data["analysis_receipts_required"]=True; state.save()
        out=self.project/"03_analysis/results/a.json"
        value=json.loads(out.read_text()); del value["environment"]
        atomic_json(out,value)
        self.assertTrue(any("receipt missing" in error for error in verify(self.project)))

    def test_declared_input_change_has_narrow_producer_scope(self):
        from wfcore.dependencies import closure
        self.write("02_data/raw/b.csv","value\n4\n")
        code=self.project/"03_analysis/code/b.py"
        code.write_text(code.read_text().replace("raw/a.csv","raw/b.csv"))
        self.execute()
        affected=closure(self.project,["02_data/raw/a.csv"])
        self.assertIn("03_analysis/code/a.py",affected)
        self.assertNotIn("03_analysis/code/b.py",affected)
        self.assertNotIn("03_analysis/results/b.json",affected)

    def test_metadata_not_number_evidence_and_clinical_dates_not_erased(self):
        pool=set(); _walk({"estimate":1.2,"environment":{"seed":45678,"version":"4.5.2"}},pool)
        self.assertNotIn("45678",pool)
        self.assertNotIn("4.5",pool)
        value={"timestamp":"clinical-date","environment":{"written_at":"receipt-time","seed":37}}
        self.assertEqual(canonical(value),{"timestamp":"clinical-date","environment":{"seed":37}})

    def test_identity_article_metadata_not_bibliography(self):
        entry={"doi":"10.1234/real","pmid":"40000000","title":"Real article"}
        wrong=b'<article><front><article-meta><article-id pub-id-type="doi">10.9999/wrong</article-id></article-meta></front><back><ref-list>10.1234/real</ref-list></back></article>'
        self.assertEqual(inspect(entry,wrong,".xml")["status"],"mismatch")
        reference_only=b'<article><back><ref-list><article-id pub-id-type="doi">10.1234/real</article-id></ref-list></back></article>'
        self.assertEqual(inspect(entry,reference_only,".xml")["status"],"pending")
        html=b'<html><head><meta content="10.1234/real" name="citation_doi"></head></html>'
        self.assertEqual(inspect(entry,html,".html")["status"],"match")
        pdf=self.write("06_refs/fulltext/unknown.pdf","%PDF-1.4 reference DOI 10.1234/real")
        self.assertTrue(errors(entry,pdf,{"identity":{"status":"match"}}))

    def test_wrong_download_preserves_existing_article(self):
        from pubmed.fulltext import _save
        p=self.project/"06_refs/fulltext"; p.mkdir(parents=True)
        prior=self.write("06_refs/fulltext/key.xml","Approved full text")
        with patch("pubmed.fulltext.out_dir",return_value=p), self.assertRaises(ValueError):
            _save("key.xml",b'<article><front><article-meta><article-id pub-id-type="doi">10.1/wrong</article-id></article-meta></front></article>',{"doi":"10.1/right"})
        self.assertEqual(prior.read_text(),"Approved full text")

    def test_reference_rule_changes_invalidate_cached_engine(self):
        pipe=registry.load(); state=State(self.project).create("medpaper",pipe.meta["version"],"S08_methods")
        receipts=Receipts(self.project,pipe,state)
        self.assertIn("reference/methods-structure.md",receipts.engine)

    @unittest.skipUnless(shutil.which("Rscript"),"R missing: R checks NOT EXECUTED")
    def test_real_r_writer_precision_and_replay(self):
        self.write("03_analysis/code/rtest.R", '''
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/analysis/results.R"))
set.seed(37)
values <- read.csv(file.path(Sys.getenv("MEDPAPER_PROJECT"),"02_data/raw/a.csv"))$value
medpaper_write_results("rtest.json",list(n=length(values),values=values),seed=37,inputs="02_data/raw/a.csv")
''')
        run(self.project,"03_analysis/code/rtest.R")
        value=json.loads((self.project/"03_analysis/results/rtest.json").read_text())
        self.assertEqual(value["values"][0],1.123456789012345)
        self.assertEqual(value["environment"]["language"],"R")
        self.assertEqual(replay(self.project),["03_analysis/code/rtest.R"])
        self.assertEqual(verify(self.project),[])

    @unittest.skipUnless(shutil.which("Rscript"),"R missing: R recipes NOT EXECUTED")
    def test_real_r_recipes_and_missing_data_not_silently_removed(self):
        script=self.write("recipe_test.R",'''
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_style.R"))
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_recipes.R"))
d <- data.frame(label=c("Group A","Group B"),estimate=c(1.2,.8),lower=c(1,.6),upper=c(1.4,1))
stopifnot(nrow(ggplot2::ggplot_build(medpaper_forest(d))$data[[3]])==2)
d <- data.frame(fpr=c(0,.1,.4,1),tpr=c(0,.5,.8,1),group="Model")
stopifnot(nrow(ggplot2::ggplot_build(medpaper_roc(d))$data[[2]])==4)
c <- data.frame(predicted=c(.1,.4,.8),observed=c(.12,.38,.75),group="Model")
stopifnot(nrow(ggplot2::ggplot_build(medpaper_calibration(c))$data[[2]])==3)
d$fpr[2] <- NA_real_
stopifnot(inherits(try(medpaper_roc(d),silent=TRUE),"try-error"))
''')
        process=subprocess.run([shutil.which("Rscript"),"--vanilla",str(script)],env={**os.environ,"MEDPAPER_ROOT":str(ROOT)},capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)


if __name__ == "__main__":
    unittest.main()
