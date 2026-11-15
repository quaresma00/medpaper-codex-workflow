"""Observed subtitle rejection and preserved clinical labels; synthetic figures only."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from figures import style
from figures.qc import qc_figure
import test_r_figures as r_fixtures


class FigureTextPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="medpaper-figure-text-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.addCleanup(plt.close, "all")

    def figure(self):
        fig, ax = plt.subplots(figsize=(3.6, 3))
        ax.plot([0, 1], [0, 1], label="Clinical group")
        ax.set_xlabel("Follow-up (months)")
        ax.set_ylabel("Cumulative incidence (%)")
        return fig, ax

    def r_case(self):
        if not shutil.which("Rscript"):
            self.skipTest("Rscript unavailable; real R subtitle checks not executed")
        case = r_fixtures.RFigureTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        return case

    def test_python_explicit_subtitle_fails_before_replacing_previous_outputs(self):
        fig, ax = self.figure()
        subtitle = fig.text(.5, .94, "Explanatory subtitle", gid="medpaper-subtitle")
        stem = self.folder / "Figure1"
        previous = {suffix: b"Existing author figure" for suffix in (".png", ".pdf")}
        for suffix, content in previous.items(): stem.with_suffix(suffix).write_bytes(content)
        with self.assertRaisesRegex(ValueError, "subtitles are not allowed"):
            style.save(fig, stem)
        for suffix, content in previous.items(): self.assertEqual(stem.with_suffix(suffix).read_bytes(), content)
        self.assertEqual(ax.get_xlabel(), "Follow-up (months)")
        self.assertEqual(subtitle.get_text(), "Explanatory subtitle")  # No silent deletion.

    def test_python_named_subtitle_is_observed_but_hidden_text_is_not(self):
        fig, _ = self.figure()
        fig._subtitle = fig.text(.5, .95, "Explanatory subtitle")
        self.assertEqual([r["text"] for r in style.figure_text_roles(fig) if r["role"] == "subtitle"], ["Explanatory subtitle"])
        fig._subtitle.set_visible(False)
        self.assertFalse(any(r["role"] == "subtitle" for r in style.figure_text_roles(fig)))

    def test_python_main_and_wrapped_panel_titles_are_not_guessed_to_be_subtitles(self):
        fig, ax = self.figure()
        fig.suptitle("Hepatobiliary events")
        ax.set_title("Cumulative incidence\nof hepatobiliary events")
        ax.text(.2, .4, "HR 1.25 (95% CI 1.02–1.53)")
        roles = style.figure_text_roles(fig)
        self.assertFalse(any(row["role"] == "subtitle" for row in roles))
        self.assertIn("HR 1.25 (95% CI 1.02–1.53)", [r["text"] for r in roles])
        self.assertIn("Follow-up (months)", [r["text"] for r in roles])

    def test_python_artist_metadata_and_qc_do_not_waive_a_recognized_subtitle(self):
        fig, _ = self.figure()
        fig.text(.5, .95, "Explanatory subtitle", gid="subtitle")
        stem = self.folder / "05_figures/out/Figure1"
        stem.parent.mkdir(parents=True)
        fig.savefig(stem.with_suffix(".png"), dpi=100)
        fig.savefig(stem.with_suffix(".pdf"))
        sidecar = Path(style.audit_figure(fig, stem))
        art = json.loads(sidecar.read_text(encoding="utf-8"))
        self.assertTrue(any(row["role"] == "subtitle" for row in art["text_roles"]))
        report = qc_figure({"id":"Figure 1","file":"05_figures/out/Figure1.png","pdf":"05_figures/out/Figure1.pdf","width":"single"}, {}, project=self.folder)
        check = next(row for row in report["checks"] if row["name"] == "no_figure_subtitle")
        self.assertFalse(check["ok"])
        self.assertEqual(check["severity"], "fail")
        self.assertFalse(report["ok"])

    def test_r_actual_plot_composition_and_named_grid_subtitles_preserve_previous_outputs(self):
        case = self.r_case()
        original = case.script.read_text(encoding="utf-8")
        call = 'medpaper_save(p, "05_figures/out/Figure1", width="double", height_mm=75)'
        variants = [
            'p <- p + labs(subtitle="Explanatory subtitle")\n' + call,
            'q <- medpaper_compose(list(p,p)) + patchwork::plot_annotation(subtitle="Overall explanation")\nmedpaper_save(q,"05_figures/out/Figure1",width="double",panels=list(p,p))',
            'q <- medpaper_compose(list(p+labs(subtitle="Nested explanation"),p))\nmedpaper_save(q,"05_figures/out/Figure1",width="double",panels=list(p,p))',
            'q <- grid::grobTree(grid::textGrob("Explanatory subtitle",name="subtitle"))\nmedpaper_save(q,"05_figures/out/Figure1",width="double",panels=list(p))',
        ]
        old_png = case.text(case.entry["file"], "Previous author PNG")
        old_pdf = case.text(case.entry["pdf"], "Previous author PDF")
        from figures.render_r import render
        for variant in variants:
            with self.subTest(variant=variant.splitlines()[0]):
                case.script.write_text(original.replace(call, variant), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "subtitles are not allowed"):
                    render(case.project, "Figure 1")
                self.assertEqual(old_png.read_text(), "Previous author PNG")
                self.assertEqual(old_pdf.read_text(), "Previous author PDF")

    def test_r_successful_render_retains_actual_clinical_and_statistical_text_roles(self):
        case = self.r_case()
        # Metadata must describe mapped display text, never the internal input
        # alias that the medical label policy replaced before drawing.
        case.script.write_text(case.script.read_text(encoding="utf-8").replace('x="Adjusted odds ratio (95% CI)"','x="adjusted_or_ci"'),encoding="utf-8")
        plan_path = case.project / "01_protocol/artifact_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["display_dictionary"] = [{"key":"clinical.adjusted_or_ci","internal":"adjusted_or_ci",
                                       "label":"Adjusted odds ratio (95% CI)","definition":"Adjusted effect measure with its source interval.","scope":"all"}]
        case.data("01_protocol/artifact_plan.json",plan)
        from figures.render_r import render
        render(case.project, "Figure 1")
        art = json.loads((case.project / "05_figures/qc/Figure1.artist.json").read_text(encoding="utf-8"))
        self.assertTrue(any(row["role"] == "x" and row["text"] == "Adjusted odds ratio (95% CI)" for row in art["text_roles"]))
        self.assertFalse(any(row["role"] == "subtitle" for row in art["text_roles"]))
        self.assertTrue(any("OR 1.34" in text for text in art["figure_text"]))
        self.assertTrue(any("OR 1.34" in text for panel in art["runtime"]["panels"] for text in panel["text_roles"]["layer_labels"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
