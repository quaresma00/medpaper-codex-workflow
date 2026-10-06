"""Real R renderer smoke tests and synthetic negative controls; no real study files."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wfcore import registry, dependencies
from wfcore.state import State
from wfcore.readiness import atomic_json
from wfcore.checks import Ctx
from wfcore.checks.artifacts import artifact_plan_sane, figures_qc_pass
from figures.render_r import render
from figures.r_audit import audit_svg
from figures.qc import qc_figure, load_archetypes

ROOT = Path(__file__).resolve().parents[1]


class RFigureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="medpaper-r-figures-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        self.pipe = registry.load()
        self.state = State(self.project).create("medpaper", self.pipe.meta["version"], "S11_figures")
        self.entry = {"id": "Figure 1", "title": "Exposure and mortality", "content": "Adjusted odds ratios",
                      "source_results": ["03_analysis/results/primary.json"], "renderer": "R",
                      "script": "05_figures/out/Figure1.R", "file": "05_figures/out/Figure1.png",
                      "pdf": "05_figures/out/Figure1.pdf", "width": "double", "archetype": "forest_plot"}
        self.data("01_protocol/artifact_plan.json", {"main_figures": [self.entry], "main_tables": []})
        self.data("03_analysis/results/primary.json", {"groups": ["Group A", "Group B", "Group C"],
                  "estimate": [1.34, .87, 1.12], "lower": [1.10, .66, .93], "upper": [1.63, 1.15, 1.35]})
        self.script = self.text(self.entry["script"], '''
source(file.path(Sys.getenv("MEDPAPER_ROOT"), "tools/figures/r_style.R"))
library(ggplot2)
r <- medpaper_result("03_analysis/results/primary.json")
d <- data.frame(group=unlist(r$groups), estimate=unlist(r$estimate), low=unlist(r$lower), high=unlist(r$upper))
p <- ggplot(d, aes(x=estimate, y=group)) +
  geom_vline(xintercept=1, linetype="dashed", linewidth=.25) +
  geom_errorbar(aes(xmin=low, xmax=high), orientation="y", width=.14, linewidth=.3) +
  geom_point(size=2) +
  geom_text(aes(x=2.4, label=sprintf("OR %.2f (%.2f to %.2f)", estimate, low, high)), size=3) +
  scale_x_log10(limits=c(.5, 3.8), breaks=c(.5,1,2,3)) +
  labs(x="Adjusted odds ratio (95% CI)", y="Patient group") + medpaper_theme()
medpaper_save(p, "05_figures/out/Figure1", width="double", height_mm=75)
''')

    def text(self, rel, content):
        path = self.project / rel; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def data(self, rel, value):
        atomic_json(self.project / rel, value)

    def context(self, name):
        return Ctx(self.pipe, self.state, self.project, self.pipe.stage("S11_figures"), {"check": name})

    def require_r(self):
        if not shutil.which("Rscript"):
            self.skipTest("Rscript absent: real R smoke NOT EXECUTED")

    def test_real_r_forest_and_shared_qc(self):
        self.require_r()
        result = render(self.project, "Figure 1")
        self.assertEqual(result["engine"], "R")
        self.assertTrue((self.project / self.entry["pdf"]).stat().st_size > 1000)
        art = json.loads((self.project / "05_figures/qc/Figure1.artist.json").read_text())
        for key in ("axis_labels", "error_bars", "null_line", "figure_statistics"):
            self.assertTrue(art["elements"][key]["found"], key)
        self.assertGreaterEqual(art["min_font_pt"], 6)
        qc = qc_figure(self.entry, self.pipe.targets, load_archetypes(), self.project)
        self.assertTrue(qc["ok"], json.dumps(qc["checks"]))
        self.assertFalse(qc["visual_reviewed"])
        self.data("05_figures/qc/qc_report.json", {"figures": [qc]})
        self.assertFalse(figures_qc_pass(self.context("figures_qc_pass")).ok)
        # Synthetic bookkeeping test only; this is not a claim of real visual review.
        qc["visual_reviewed"] = True
        self.data("05_figures/qc/qc_report.json", {"figures": [qc]})
        self.assertTrue(figures_qc_pass(self.context("figures_qc_pass")).ok)
        self.data("03_analysis/results/primary.json", {"changed": True})
        self.assertFalse(figures_qc_pass(self.context("figures_qc_pass")).ok)

    def test_failed_r_script_preserves_previous_outputs(self):
        self.require_r()
        self.text(self.entry["file"], "Previous user PNG")
        self.text(self.entry["pdf"], "Previous user PDF")
        self.script.write_text('stop("Deliberate synthetic failure")', encoding="utf-8")
        with self.assertRaises(ValueError):
            render(self.project, "Figure 1")
        self.assertEqual((self.project / self.entry["file"]).read_text(), "Previous user PNG")
        self.assertEqual((self.project / self.entry["pdf"]).read_text(), "Previous user PDF")

    def test_real_r_patchwork_composite(self):
        self.require_r()
        self.entry.update({"archetype": "other", "archetype_rationale": "Composite box-and-interval plot with different medical measures."})
        self.data("01_protocol/artifact_plan.json", {"main_figures": [self.entry]})
        self.script.write_text('''
source(file.path(Sys.getenv("MEDPAPER_ROOT"), "tools/figures/r_style.R"))
library(ggplot2); library(patchwork)
r <- medpaper_result("03_analysis/results/primary.json")
d <- data.frame(group=unlist(r$groups), estimate=unlist(r$estimate), low=unlist(r$lower), high=unlist(r$upper))
a <- ggplot(d, aes(x=group, y=estimate)) + geom_col(fill=medpaper_palette[1], width=.6) +
  geom_errorbar(aes(ymin=low, ymax=high), width=.15, linewidth=.3) +
  labs(x="Patient group", y="Odds ratio") + medpaper_theme()
b <- ggplot(d, aes(x=group, y=estimate)) + geom_point(size=2, colour=medpaper_palette[2]) +
  geom_linerange(aes(ymin=low, ymax=high), linewidth=.3) +
  labs(x="Patient group", y="Odds ratio") + medpaper_theme()
p <- wrap_plots(a, b, ncol=2)
medpaper_save(p, "05_figures/out/Figure1", width="double", height_mm=75, panels=list(a,b))
''', encoding="utf-8")
        render(self.project, "Figure 1")
        art = json.loads((self.project / "05_figures/qc/Figure1.artist.json").read_text())
        self.assertEqual(art["n_axes"], 2)
        self.assertTrue(art["elements"]["axis_labels"]["found"])
        self.assertTrue(art["elements"]["bar_artist"]["found"])
        self.assertTrue(qc_figure(self.entry, self.pipe.targets, load_archetypes(), self.project)["ok"])

    def test_warning_about_removed_observations_fails(self):
        self.require_r()
        self.text(self.entry["file"], "Keep this previous PNG")
        content = self.script.read_text(encoding="utf-8").replace(
            'source(file.path(Sys.getenv("MEDPAPER_ROOT"), "tools/figures/r_style.R"))',
            'warning("Dropped observations: synthetic negative control")')
        self.script.write_text(content, encoding="utf-8")
        with self.assertRaises(ValueError):
            render(self.project, "Figure 1")
        self.assertEqual((self.project / self.entry["file"]).read_text(), "Keep this previous PNG")

    def test_r_dependency_keeps_other_figure_and_includes_measurements(self):
        other = {**self.entry, "id": "Figure 2", "script": "05_figures/out/Figure2.R",
                 "file": "05_figures/out/Figure2.png", "pdf": "05_figures/out/Figure2.pdf"}
        self.data("01_protocol/artifact_plan.json", {"main_figures": [self.entry, other]})
        impacted = dependencies.closure(self.project, [self.entry["script"]], change_type="layout")
        self.assertIn("05_figures/qc/Figure1.render.svg", impacted)
        self.assertIn("05_figures/qc/Figure1.rmeta.json", impacted)
        self.assertNotIn(other["file"], impacted)

    def test_r_plan_and_python_exception_rationale(self):
        self.assertTrue(artifact_plan_sane(self.context("artifact_plan_sane")).ok)
        invalid = {**self.entry, "renderer": "Python"}
        self.data("01_protocol/artifact_plan.json", {"main_figures": [invalid]})
        self.assertFalse(artifact_plan_sane(self.context("artifact_plan_sane")).ok)
        invalid.update({"script": "05_figures/out/Figure1.py", "renderer_reason": "Preserve an already approved Matplotlib figure and its user edits."})
        self.data("01_protocol/artifact_plan.json", {"main_figures": [invalid]})
        self.assertTrue(artifact_plan_sane(self.context("artifact_plan_sane")).ok)

    def test_no_early_publication_outputs(self):
        self.state.data["current"] = "S05_analysis"; self.state.save()
        with self.assertRaises(ValueError):
            render(self.project, "Figure 1")

    def test_scoped_r_build_cannot_write_unrelated_outputs(self):
        self.state.data["current"] = "S19_human_review"
        self.state.data["active_revision_round"] = "R001"; self.state.save()
        self.data(".wf/revisions/R001.json", {"schema_version": 2, "round_id": "R001", "status": "active",
                  "validation_stages": ["S11_figures"], "allowed_files": [self.entry["file"]]})
        with self.assertRaises(ValueError):
            render(self.project, "Figure 1")

    def test_unknown_rscript_is_not_a_python_fallback(self):
        with patch("figures.render_r.shutil.which", return_value=None), self.assertRaises(ValueError):
            render(self.project, "Figure 1")

    def test_svg_negative_controls_and_limits(self):
        svg = self.text("temp/test.svg", '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <text x="-5" y="10" textLength="30" style="font-size: 4px;">clipped</text>
        <text x="10" y="50" textLength="40" style="font-size: 8px;">overlap A</text>
        <text x="12" y="50" textLength="40" style="font-size: 8px;">overlap B</text></svg>''')
        art = audit_svg(svg, {"panels": []})
        self.assertEqual(art["min_font_pt"], 4)
        self.assertTrue(art["text_clipped_at_edge"])
        self.assertTrue(art["r_text_box_collisions"])
        self.assertFalse(art["elements"]["axis_labels"]["found"])
        self.assertTrue(art["measurement_limits"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
