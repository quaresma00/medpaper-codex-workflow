"""Isolated environment, installation and source-bound uncensored-KM controls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from analysis import reproduce
from wfcore.state import State
from wfcore.readiness import atomic_json
from figures.render_r import render
from figures.qc import qc_figure, load_archetypes
import test_r_figures as figures_fixture

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("bootstrap_runtime_126",ROOT/"bootstrap.py")
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)


class RuntimeKMTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-runtime-126-");self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)/"study with space";self.project.mkdir()

    def text(self,rel,value):
        path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path

    def r_path(self):
        path=shutil.which("Rscript")
        if not path:
            local=Path(r"D:/soft/R-4.5.2/bin/Rscript.exe")
            path=str(local) if local.is_file() else None
        if not path:self.skipTest("R unavailable; no actual R runtime/render claim")
        return path

    def test_bootstrap_rejects_incompatible_fallback_and_existing_venv(self):
        with patch.object(bootstrap,"VENV",self.project/".venv"),patch.object(bootstrap.sys,"version_info",(3,11)),patch.object(bootstrap,"run") as call:
            self.assertFalse(bootstrap.create_venv(None));call.assert_not_called()
            self.assertTrue(bootstrap.create_venv("test-uv"))
            self.assertEqual(call.call_args.args[0][1:4],["venv","--python","3.13"])
        venv=self.project/".venv"; exe=venv/("Scripts/python.exe" if os.name=="nt" else "bin/python")
        exe.parent.mkdir(parents=True);exe.write_text("test-only probe path")
        with patch.object(bootstrap,"VENV",venv),patch.object(bootstrap.subprocess,"run",return_value=subprocess.CompletedProcess([],0,"[3,11]","")):
            self.assertFalse(bootstrap.create_venv("test-uv"))
        with patch.object(bootstrap,"VENV",venv),patch.object(bootstrap.subprocess,"run",return_value=subprocess.CompletedProcess([],0,"[3,13]","")):
            self.assertTrue(bootstrap.create_venv(None))

    def test_actual_r_activates_private_environment_before_real_producer_and_replay(self):
        rscript=self.r_path()
        self.text("renv/activate.R",'Sys.setenv(MEDPAPER_PRIVATE_TEST="active")\n')
        lock=self.text("renv.lock",'{"fixture":"controlled private startup, no package installation"}\n')
        self.text("02_data/raw/values.csv","value\n1\n2\n3\n")
        self.text("03_analysis/code/primary.R",'''if (!identical(Sys.getenv("MEDPAPER_PRIVATE_TEST"),"active")) stop("private environment was not activated")
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/analysis/results.R"))
d <- read.csv(file.path(Sys.getenv("MEDPAPER_PROJECT"),"02_data/raw/values.csv"))
medpaper_write_results("primary.json",list(count=nrow(d),total=sum(d$value)),seed=37,inputs=c("02_data/raw/values.csv"))
''')
        with patch("analysis.reproduce.shutil.which",return_value=rscript):
            reproduce.run(self.project,"03_analysis/code/primary.R",timeout=30)
            result=json.loads((self.project/"03_analysis/results/primary.json").read_text())
            self.assertEqual(result["count"],3);self.assertEqual(result["total"],6)
            self.assertTrue(result["environment"]["renv"]["active"])
            self.assertEqual(result["environment"]["script"],"03_analysis/code/primary.R")
            self.assertEqual(reproduce.replay(self.project,timeout=30),["03_analysis/code/primary.R"])
            self.assertEqual(reproduce.verify(self.project),[])
            self.assertEqual(reproduce.replay(self.project,timeout=30),[])
            lock.write_text('{"fixture":"changed approved environment lock"}\n',encoding="utf-8")
            self.assertTrue(any("environment" in e for e in reproduce.verify(self.project)))
        self.assertEqual(list((self.project/"temp").glob("analysis-r-env-*")),[])

    def test_activation_failure_stops_before_producer_and_preserves_prior_result(self):
        self.text("renv/activate.R",'stop("controlled activation failure")\n')
        self.text("03_analysis/code/primary.R",'writeLines("must never run",file.path(Sys.getenv("MEDPAPER_PROJECT"),"unexpected.txt"))\n')
        output=self.text("03_analysis/results/primary.json",'{"prior":"preserved synthetic result"}\n')
        with patch("analysis.reproduce.shutil.which",return_value=self.r_path()):
            with self.assertRaisesRegex(ValueError,"Producer failed"):
                reproduce.run(self.project,"03_analysis/code/primary.R",timeout=30)
        self.assertFalse((self.project/"unexpected.txt").exists())
        self.assertIn("preserved",output.read_text())
        self.assertEqual(list((self.project/"temp").glob("analysis-r-env-*")),[])

    def test_lockfile_without_activation_is_not_a_global_library_fallback(self):
        self.text("renv.lock","{}")
        with self.assertRaisesRegex(ValueError,"activate"):
            reproduce.renv_context(self.project)

    def test_real_r_figure_uses_same_project_environment_and_preserves_outputs_on_failure(self):
        case=figures_fixture.RFigureTests(methodName="runTest");case.setUp();self.addCleanup(case.doCleanups)
        activation=case.text("renv/activate.R",'Sys.setenv(MEDPAPER_FIGURE_PRIVATE_TEST="active")\n')
        lock=case.text("renv.lock",'{"fixture":"controlled private figure startup"}\n')
        case.script.write_text('if(!identical(Sys.getenv("MEDPAPER_FIGURE_PRIVATE_TEST"),"active")) stop("private figure environment not activated")\n'+case.script.read_text(encoding="utf-8"),encoding="utf-8")
        with patch("figures.render_r.shutil.which",return_value=self.r_path()):
            render(case.project,"Figure 1")
            art=json.loads((case.project/"05_figures/qc/Figure1.artist.json").read_text())
            self.assertEqual(art["renv"],reproduce.renv_context(case.project))
            self.assertEqual(art["script"],case.entry["script"])
            self.assertTrue(qc_figure(case.entry,case.pipe.targets,load_archetypes(),case.project)["ok"])
            png=(case.project/case.entry["file"]).read_bytes();pdf=(case.project/case.entry["pdf"]).read_bytes()
            lock.write_text('{"fixture":"changed current figure lock"}\n',encoding="utf-8")
            self.assertFalse(qc_figure(case.entry,case.pipe.targets,load_archetypes(),case.project)["ok"])
            activation.write_text('stop("controlled figure activation failure")\n',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"R render failed"):
                render(case.project,"Figure 1")
        self.assertEqual((case.project/case.entry["file"]).read_bytes(),png)
        self.assertEqual((case.project/case.entry["pdf"]).read_bytes(),pdf)
        self.assertEqual(list((case.project/"temp").glob("r-figure-*")),[])

    def test_actual_r_uncensored_km_requires_specific_current_source_not_a_boolean(self):
        case=figures_fixture.RFigureTests(methodName="runTest");case.setUp();self.addCleanup(case.doCleanups)
        result={"curve":{"time":[0,1,2,3,4,5,6],"survival":[1,5/6,4/6,3/6,2/6,1/6,0]},
                "risk":{"time":[0,2,4,6],"n":[6,5,3,1]},
                "censoring":{"counting_unit":"participants","observations":6,"events":6,"censored":0},
                "float_counts":{"counting_unit":"participants","observations":6.0,"events":6.0,"censored":0.0},
                "has_censoring":{"counting_unit":"participants","observations":6,"events":5,"censored":1}}
        case.data("03_analysis/results/primary.json",result)
        case.entry.update(archetype="km_survival",title="Event-free survival",content="Synthetic full observed-event curve")
        case.data("01_protocol/artifact_plan.json",{"main_figures":[case.entry],"main_tables":[]})
        case.script.write_text('''source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_style.R"))
library(ggplot2)
r <- medpaper_result("03_analysis/results/primary.json")
curve <- data.frame(time=unlist(r$curve$time),survival=unlist(r$curve$survival),group="Group A")
risk <- data.frame(time=unlist(r$risk$time),n=unlist(r$risk$n),group="Group A")
p <- ggplot(curve,aes(x=time,y=survival,colour=group)) + geom_step(linewidth=.4) +
  annotate("text",x=4.5,y=.85,label=paste("n =",r$censoring$observations),size=3) +
  labs(x="Time (months)",y="Event-free survival") + medpaper_theme()
tab <- ggplot(risk,aes(x=time,y=group,label=n)) + geom_text(size=3) +
  labs(x="Time (months)",y="Number at risk") + medpaper_theme()
combined <- patchwork::wrap_plots(p,tab,ncol=1,heights=c(4,1))
medpaper_save(combined,"05_figures/out/Figure1",width="double",height_mm=115,panels=list(p,tab))
''',encoding="utf-8")
        with patch("figures.render_r.shutil.which",return_value=self.r_path()):render(case.project,"Figure 1")
        before=qc_figure(case.entry,case.pipe.targets,load_archetypes(),case.project)
        failures=[x["name"] for x in before["checks"] if not x["ok"] and x["severity"]=="fail"]
        self.assertEqual(failures,["element:censoring_marks"],json.dumps(before))
        case.entry["censoring_not_applicable"]={"file":"03_analysis/results/primary.json","pointer":"/censoring"}
        after=qc_figure(case.entry,case.pipe.targets,load_archetypes(),case.project)
        self.assertTrue(after["ok"],json.dumps(after))
        self.assertTrue(next(c for c in after["checks"] if c["name"]=="element:censoring_marks")["not_applicable"])
        floats=copy.deepcopy(case.entry);floats["censoring_not_applicable"]["pointer"]="/float_counts"
        self.assertTrue(qc_figure(floats,case.pipe.targets,load_archetypes(),case.project)["ok"])
        for ref in (True,{"file":"03_analysis/results/primary.json","pointer":"/has_censoring"},
                    {"file":"03_analysis/results/other.json","pointer":"/censoring"}):
            bad=copy.deepcopy(case.entry);bad["censoring_not_applicable"]=ref
            self.assertFalse(qc_figure(bad,case.pipe.targets,load_archetypes(),case.project)["ok"])
        preview=os.environ.get("MEDPAPER_TEST_PREVIEW_DIR")
        if preview:
            target=Path(preview);target.mkdir(parents=True,exist_ok=True)
            for suffix in ("png","pdf"):
                shutil.copy2(case.project/f"05_figures/out/Figure1.{suffix}",target/f"UncensoredKM.{suffix}")


if __name__=="__main__":unittest.main(verbosity=2)
