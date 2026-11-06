"""Synthetic clinical writing prompts and real source-preserving figure production."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from text.polish import lint_medical
from figures.r_audit import audit_svg
import test_r_figures as legacy

ROOT=Path(__file__).resolve().parents[1]


class MedicalAuthoringTests(unittest.TestCase):
    def test_interval_and_significance_prompts_are_advisory_and_source_neutral(self):
        text="# Results\n\nThe hazard ratio was 1.42 (Table 2).\n\nAdmission was significantly higher (P = 0.02).\n"
        rows=lint_medical("results.md",text)
        self.assertEqual({r["kind"] for r in rows},{"medical_interval_context","medical_significance_context"})
        self.assertTrue(all(r["severity"]=="advisory" for r in rows))
        self.assertEqual(lint_medical("results.md","HR 1.42 (95% CI, 1.10 to 1.84)."),[])
        self.assertEqual(lint_medical("results.md","There were 48 admissions. Median stay was 4 days (IQR, 2 to 7)."),[])

    def test_composed_sections_do_not_confuse_abstract_results_with_main_results(self):
        text="# Abstract\n\n## Results\n\nHR 1.42.\n\n# Methods\n\nHR 1.42 was the anticipated effect.\n\n# Results\n\nOR 1.60.\n\n# References\n\nHR 1.99 is the source title.\n"
        rows=lint_medical("full_manuscript.md",text)
        self.assertEqual(len(rows),2)
        self.assertNotIn("anticipated",str(rows));self.assertNotIn("source title",str(rows))
        self.assertEqual(lint_medical("methods.md","The hazard ratio was 1.42."),[])

    def test_no_automatic_tense_subject_or_qualitative_penalty(self):
        text="Patients were interviewed. Participants described fatigue. The analysis identifies two themes."
        self.assertEqual(lint_medical("results.md",text),[])

    def test_forest_drawn_ticks_and_direction_labels_do_not_overlap_axis_title(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from figures.recipes import forest_plot
        from figures.elements import tick_label_collisions
        for width in ("double","1.5"):
            fig,ax=forest_plot([{"label":"Primary population","estimate":.94,"ci":(.68,1.31)},
                                {"label":"Sensitivity analysis","estimate":1.06,"ci":(.76,1.52)}],width=width,height_mm=85)
            self.addCleanup(plt.close,fig)
            fig.canvas.draw();renderer=fig.canvas.get_renderer()
            self.assertEqual(tick_label_collisions(fig,renderer),[])
            self.assertGreaterEqual(len([t for t in ax.get_xticklabels() if t.get_visible() and t.get_text()]),2)
            self.assertTrue(all(not t.get_text() for t in ax.get_xticklabels(minor=True)))
            xlabel=ax.xaxis.label.get_window_extent(renderer)
            labels=[t for t in ax.texts if "Favours" in t.get_text()]
            for t in labels:
                box=t.get_window_extent(renderer)
                self.assertLess(box.y1,xlabel.y0-2)
                self.assertGreaterEqual(box.x0,0);self.assertLessEqual(box.x1,fig.bbox.width)
            boxes=[t.get_window_extent(renderer) for t in labels]
            self.assertFalse(boxes[0].overlaps(boxes[1]))
            preview=os.environ.get("MEDPAPER_TEST_PREVIEW_DIR")
            if preview and width=="double":
                target=Path(preview);target.mkdir(parents=True,exist_ok=True)
                fig.savefig(target/"LegacyForest.png",dpi=150)

    def test_real_r_clinical_recipes_and_managed_flow_provenance(self):
        if not shutil.which("Rscript"):self.skipTest("R unavailable; no rendering claim")
        case=legacy.RFigureTests(methodName="runTest");case.setUp();self.addCleanup(case.doCleanups)
        nodes={"id":["screened","excluded","included"],"label":["Adults assessed for eligibility","Excluded: eligibility criteria not met","Adults included in analysis"],
               "n":[920,120,800],"x":[.25,.77,.25],"y":[.8,.8,.25]}
        case.data("03_analysis/results/primary.json",{"nodes":nodes})
        case.entry.update(archetype="flow_diagram",title="Study population selection",content="Actual eligibility and inclusion counts")
        case.data("01_protocol/artifact_plan.json",{"main_figures":[case.entry],"main_tables":[]})
        case.script.write_text('''source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_style.R"))
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_recipes.R"))
r <- medpaper_result("03_analysis/results/primary.json")
nodes <- as.data.frame(lapply(r$nodes,unlist),stringsAsFactors=FALSE)
original <- nodes
edges <- data.frame(from=c("screened","screened"),to=c("excluded","included"))
p <- medpaper_selection_flow(nodes,edges)
stopifnot(identical(nodes,original))
bad <- nodes;bad$n[2] <- NA
stopifnot(inherits(try(medpaper_selection_flow(bad,edges),silent=TRUE),"try-error"))
bad <- nodes;bad$n[2] <- 1.5
stopifnot(inherits(try(medpaper_selection_flow(bad,edges),silent=TRUE),"try-error"))
bad <- rbind(edges,data.frame(from="included",to="screened"))
stopifnot(inherits(try(medpaper_selection_flow(nodes,bad),silent=TRUE),"try-error"))
medpaper_save(p,"05_figures/out/Figure1",width="double",height_mm=115)
''',encoding="utf-8")
        from figures.render_r import render
        from figures.qc import qc_figure,load_archetypes
        result=render(case.project,"Figure 1")
        self.keep_preview(case.project/"05_figures/out/Figure1.png","SelectionFlow.png")
        qc=qc_figure(case.entry,case.pipe.targets,load_archetypes(),case.project)
        self.assertTrue(qc["ok"],json.dumps(qc))
        art=json.loads((case.project/"05_figures/qc/Figure1.artist.json").read_text())
        self.assertTrue(art["elements"]["box_nodes"]["found"])
        self.assertTrue(art["elements"]["figure_statistics"]["found"])
        self.assertIn("n = 920",art["figure_text"])
        self.keep_preview(case.project/"05_figures/out/Figure1.png","SelectionFlow.png")
        script=case.text("clinical.R",'''source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_style.R"))
source(file.path(Sys.getenv("MEDPAPER_ROOT"),"tools/figures/r_recipes.R"))
d <- data.frame(exposure=c(1,2,3,4,5),estimate=c(.8,.9,1,1.2,1.5),lower=c(.6,.7,.8,.95,1.1),upper=c(1,1.1,1.2,1.45,1.9),group="Primary analysis")
original <- d
p <- medpaper_dose_response(d,"Serum marker (mg/dL)","Adjusted hazard ratio",null=1)
stopifnot(identical(d,original),nrow(ggplot2::ggplot_build(p)$data[[2]])==nrow(d))
medpaper_save(p,"DoseResponse",width="double",height_mm=90)
d$lower[1] <- NA
stopifnot(inherits(try(medpaper_dose_response(d,"Exposure","Effect"),silent=TRUE),"try-error"))
curves <- data.frame(threshold=rep(c(.05,.1,.2,.3),3),net_benefit=c(.08,.07,.05,.02,.06,.04,.01,-.03,0,0,0,0),group=rep(c("Clinical model","Treat all","Treat none"),each=4))
p <- medpaper_decision_curve(curves)
Sys.setenv(MEDPAPER_RENDER_STEM=file.path(dirname(Sys.getenv("MEDPAPER_RENDER_STEM")),"DecisionCurve"))
medpaper_save(p,"DecisionCurve",width="double",height_mm=90)
balance <- data.frame(variable=rep(c("Age","Baseline serum marker","Prior admission"),2),smd=c(-.25,.18,.22,-.04,.03,.05),group=rep(c("Unweighted","Weighted"),each=3))
original <- balance
p <- medpaper_balance(balance,threshold=.1)
stopifnot(identical(balance,original),nrow(ggplot2::ggplot_build(p)$data[[1]])==6)
Sys.setenv(MEDPAPER_RENDER_STEM=file.path(dirname(Sys.getenv("MEDPAPER_RENDER_STEM")),"Balance"))
medpaper_save(p,"Balance",width="double",height_mm=90)
stopifnot(length(medpaper_colours(6))==6)
stopifnot(inherits(try(medpaper_colours(7),silent=TRUE),"try-error"))
if(requireNamespace("ggsci",quietly=TRUE)) for(name in c("nejm","lancet","jama","jco")) stopifnot(length(medpaper_colours(3,name))==3)
''')
        env={**os.environ,"MEDPAPER_ROOT":str(ROOT),"MEDPAPER_RENDER_STEM":str(case.project/"DoseResponse"),"MEDPAPER_LABEL_POLICY":"{}"}
        run=subprocess.run(["Rscript","--vanilla",str(script)],env=env,capture_output=True,text=True,timeout=90)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        for name in ("DoseResponse","DecisionCurve","Balance"):
            self.assertTrue((case.project/f"{name}.pdf").is_file())
            audit=audit_svg(case.project/f"{name}.svg",json.loads((case.project/f"{name}.rmeta.json").read_text()))
            self.assertEqual(audit["text_clipped_at_edge"],[])
            self.keep_preview(case.project/f"{name}.png",name+".png")

    @staticmethod
    def keep_preview(path,name):
        preview=os.environ.get("MEDPAPER_TEST_PREVIEW_DIR")
        if preview:
            dest=Path(preview);dest.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest/name)


if __name__=="__main__":unittest.main(verbosity=2)
