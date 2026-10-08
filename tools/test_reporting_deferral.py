"""Behavioral regressions: no blanket study registration or early reporting forms."""
import json
from pathlib import Path
import tempfile
import unittest

from wfcore import gates, registry
from wfcore.checks import Ctx, get, load_all
from wfcore.state import State


class ReportingDeferralTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="medpaper-reporting-policy-")
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.pipe = registry.load()
        self.state = State(self.project).create("medpaper", self.pipe.meta["version"], "S01_intake")
        load_all()

    def write(self, rel, text):
        p = self.project / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def spec(self, stage, path):
        return next(s for s in self.pipe.stage(stage).gate if s.get("check") == "md_sections" and s.get("path") == path)

    def protocol(self, stage, path, omit=(), extra=""):
        headings = [h for h in self.spec(stage,path)["headings"] if h not in omit]
        return self.write(path,"# Local analysis plan\n\n" + "\n\n".join("## "+h+"\n\nSynthetic retrospective-cohort test content." for h in headings) + extra)

    def test_intake_without_guideline_or_registration_fields_passes_all_gates(self):
        idea={"title_working":"Retrospective database analysis", "design":"secondary analysis",
              "population":{"who":"existing eligible records"},"exposure":{"name":"measured exposure"},
              "comparator":{"name":"reference group"},"outcomes":{"primary":[{"name":"outcome"}]},
              "claimed_novelty":"Test fixture scientific question",
              "data_source_candidates":[{"name":"Existing institutional retrospective cohort","access":"institutional"}],
              "open_questions":[]}
        self.write("01_protocol/idea.json",json.dumps(idea))
        self.write("03_analysis/notes.md","# Notes\n\nSynthetic study notes.\n")
        results=gates.run_stage(self.pipe,self.state,self.project,self.pipe.stage("S01_intake"))
        self.assertFalse(any(r.blocking for r in results),[(r.check,r.detail) for r in results])
        self.assertNotIn("reporting_guideline_candidate",idea)
        spec=next(s for s in self.pipe.stage("S01_intake").gate if s["check"]=="json_keys")
        for broken in ({**idea,"data_source_candidates":[]},{k:v for k,v in idea.items() if k!="open_questions"},
                       {**idea,"open_questions":None}):
            self.write("01_protocol/idea.json",json.dumps(broken))
            result=get("json_keys")(Ctx(self.pipe,self.state,self.project,self.pipe.stage("S01_intake"),spec))
            self.assertFalse(result.ok,result.detail)

    def test_protocol_without_reporting_heading_or_registration_file_passes_all_gates(self):
        self.protocol("S03_protocol","01_protocol/protocol_v1.md")
        spec=self.spec("S03_protocol","02_data/acquisition_plan.md")
        self.write(spec["path"],"\n\n".join("## "+h+"\n\nComplete fixture acquisition instructions." for h in spec["headings"]))
        results=gates.run_stage(self.pipe,self.state,self.project,self.pipe.stage("S03_protocol"))
        self.assertFalse(any(r.blocking for r in results),[(r.check,r.detail) for r in results])
        self.assertEqual({p.name for p in (self.project/"01_protocol").iterdir()},{"protocol_v1.md"})

    def test_final_protocol_without_reporting_heading_passes_section_gate(self):
        stage="S06_protocol_final"; rel="01_protocol/protocol_final.md"
        self.protocol(stage,rel)
        result=get("md_sections")(Ctx(self.pipe,self.state,self.project,self.pipe.stage(stage),self.spec(stage,rel)))
        self.assertTrue(result.ok,result.detail)

    def test_methods_and_ethics_requirements_are_not_weakened(self):
        for stage,rel in (("S03_protocol","01_protocol/protocol_v1.md"),("S06_protocol_final","01_protocol/protocol_final.md")):
            for heading in ("Ethics","Statistical analysis plan","Population and eligibility"):
                with self.subTest(stage=stage,heading=heading):
                    self.protocol(stage,rel,omit=(heading,))
                    result=get("md_sections")(Ctx(self.pipe,self.state,self.project,self.pipe.stage(stage),self.spec(stage,rel)))
                    self.assertFalse(result.ok)
                    self.assertIn(heading.casefold(),result.detail.casefold())

    def test_legacy_extra_heading_does_not_force_source_rewrite(self):
        stage="S03_protocol";rel="01_protocol/protocol_v1.md"
        p=self.protocol(stage,rel,extra="\n\n## Reporting guideline\n\nHistorical user-written note.\n")
        original=p.read_bytes()
        result=get("md_sections")(Ctx(self.pipe,self.state,self.project,self.pipe.stage(stage),self.spec(stage,rel)))
        self.assertTrue(result.ok,result.detail)
        self.assertEqual(p.read_bytes(),original)


if __name__ == "__main__":
    unittest.main()
