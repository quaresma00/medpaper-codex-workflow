"""Synthetic source-bound scientific judgments; no real medical data or model fitting."""
import json
from pathlib import Path
import tempfile
import unittest

from wfcore.readiness import CONTRACT,FACTS,CONTRACT_KEYS,STORY_KEYS,atomic_json,freeze_writing,verify_writing
from wfcore.state import State


class ScientificDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-scientific-decisions-")
        self.addCleanup(self.tmp.cleanup); self.project=Path(self.tmp.name)
        self.state=State(self.project).create("medpaper","1.20.0","S06_protocol_final")
        self.data(CONTRACT,{key:"Synthetic documented analysis rule for testing." for key in CONTRACT_KEYS})
        self.data(FACTS,{**{key:"Synthetic evidence-limited clinical interpretation." for key in STORY_KEYS},"result_sources":["03_analysis/results/main.json"]})
        self.data("03_analysis/results/main.json",{"estimate":1.0,"ci_low":0.5,"ci_high":2.0})
        self.text("03_analysis/code/main.py","# Synthetic test producer\n")
        for rel in ("01_protocol/protocol_final.md","01_protocol/protocol_diff.md"):
            self.text(rel,"Synthetic test protocol")
        self.data("02_data/acquisition_manifest.json",{"scope":"Synthetic full input universe"})

    def text(self,rel,value):
        file=self.project/rel; file.parent.mkdir(parents=True,exist_ok=True); file.write_text(value,encoding="utf-8")
    def data(self,rel,value): atomic_json(self.project/rel,value)
    def assess(self):
        self.state.record_decision("analysis_converged","YES","Primary and validity questions resolved on this actual result version.")
        self.state.record_decision("go_nogo_2","GO","Interpretable estimate and uncertainty support the scoped scientific question.")

    def test_go_is_bound_before_freeze_not_backfilled_after_change(self):
        self.assess(); old=self.state.decision("go_nogo_2")["scientific_inputs"].copy()
        self.data("03_analysis/results/main.json",{"estimate":3.0,"ci_low":1.1,"ci_high":4.0})
        with self.assertRaisesRegex(ValueError,"older scientific evidence"):
            freeze_writing(self.project)
        self.assertEqual(self.state.decision("go_nogo_2")["scientific_inputs"],old)
        self.assertFalse((self.project/"01_protocol/writing_readiness.json").exists())
        self.assess(); frozen=freeze_writing(self.project)
        self.assertEqual(frozen["schema_version"],2)
        self.assertEqual(verify_writing(self.project),[])

    def test_convergence_and_publishability_each_need_current_evidence(self):
        self.assess(); self.text("03_analysis/code/helper.R","# Changed synthetic method helper")
        self.state.record_decision("go_nogo_2","GO","The revised scientific result has been assessed on its actual evidence.")
        with self.assertRaisesRegex(ValueError,"analysis_converged"):
            freeze_writing(self.project)

    def test_backstage_notes_and_production_files_do_not_reopen_analysis(self):
        self.assess(); freeze_writing(self.project)
        self.text("03_analysis/analysis_log.md","Added explanatory note, no changed scientific source.")
        self.text("05_figures/legends.md","Synthetic display wording changed after scientific freeze.")
        self.assertEqual(verify_writing(self.project),[])

    def test_retained_invalid_result_cannot_feed_active_numeric_pool(self):
        from wfcore.checks import Ctx
        from wfcore.checks.numbers import _pool
        self.assess(); freeze_writing(self.project)
        self.data(".wf/retired_analysis/invalid_version.json", {"estimate": 987654})
        _, values, sources = _pool(Ctx(None, self.state, self.project, None, {}))
        self.assertNotIn("987654", values)
        self.assertFalse(any("retired_analysis" in path for path in sources))
        self.assertEqual(verify_writing(self.project), [])

    def test_cli_failure_does_not_register_positive_decision_or_note(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from wfcore.cli import cmd_decide
        import contextlib
        import io
        (self.project/FACTS).unlink()
        args=SimpleNamespace(name="analysis_converged", value="YES", why="Assessed required analysis on the current scientific sources.")
        with patch("wfcore.cli._load", return_value=(None, self.state, self.project)), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cmd_decide(args), 2)
        current=State(self.project).load()
        self.assertIsNone(current.decision("analysis_converged"))
        self.assertFalse(current.data.get("handoff"))

    def test_stop_cannot_coexist_with_current_writing_permission(self):
        self.assess(); freeze_writing(self.project)
        self.state.record_decision("go_nogo_2","STOP","A newly recognized validity barrier prevents advancing this interpretation.")
        self.assertTrue(verify_writing(self.project))

    def test_missing_scientific_inputs_cannot_receive_positive_decision(self):
        (self.project/FACTS).unlink()
        with self.assertRaises(OSError): self.assess()
        self.assertIsNone(self.state.decision("analysis_converged"))

    def test_changed_interpretation_requires_fresh_judgment(self):
        self.assess(); freeze_writing(self.project)
        facts=json.loads((self.project/FACTS).read_text(encoding="utf-8"))
        facts["cannot_claim"]="Changed synthetic inference boundary."
        self.data(FACTS,facts)
        self.assertTrue(verify_writing(self.project))
        with self.assertRaises(ValueError): freeze_writing(self.project)

    def test_legacy_freeze_stays_legacy_without_invented_binding(self):
        self.state.data["pipeline_version"]="1.19.0"; self.state.save(); self.assess()
        payload=freeze_writing(self.project)
        self.assertEqual(payload["schema_version"],1)
        self.state.data["pipeline_version"]="1.20.0"; self.state.save()
        self.assertEqual(verify_writing(self.project),[])
        with self.assertRaises(ValueError): freeze_writing(self.project)


if __name__=="__main__": unittest.main(verbosity=2)
