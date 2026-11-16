"""Actual section editing, source drift and honest medical reading observations."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wfcore import buildproof,sectionwriting as sw
from wfcore.readiness import atomic_json
from wfcore.state import State

ROOT=Path(__file__).resolve().parents[1]
TEXT="""# Methods

We conducted a retrospective observational cohort study of adults receiving haemodialysis.
The eligible population included 120 adults. We did not infer a treatment benefit from
the association with heart-failure admission (hazard ratio, 1.34; 95% CI, 1.02 to 1.76;
P = 0.03; Table 2). The exposure definition followed the published method [@cohort].
"""


class SectionWritingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-section-128-");self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)
        self.state=State(self.project).create("medpaper","1.28.0","S08_methods")
        self.path=self.text("07_manuscript/methods.md",TEXT)
        self.source=self.text("01_protocol/protocol_final.md","Actual synthetic definition: retrospective adult haemodialysis cohort; no treatment-effect claim.")
        self.review={"quote":"We conducted a retrospective observational cohort study of adults receiving haemodialysis.",
                     "clinical_reading":"The text tells a medical reader that adults receiving haemodialysis formed a retrospective cohort and identifies the admission outcome.",
                     "fact_readback":"I compared the population, exposure and admission outcome with the synthetic protocol; values, uncertainty and the absence of a treatment-benefit claim remain unchanged."}

    def text(self,rel,text):
        path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding="utf-8");return path
    def begin(self):return sw.begin(self.project,"methods",[self.source.relative_to(self.project).as_posix()])
    def accept(self):return sw.accept(self.project,"methods",self.review)

    def test_actual_section_pass_records_current_medical_reading_without_extra_files(self):
        self.begin();self.path.write_text(TEXT.replace("The eligible population included","The study included"),encoding="utf-8")
        self.accept()
        self.assertEqual(sw.problems(self.project,["methods"]),[])
        row=buildproof.load(self.project)["07_manuscript/methods.md"]
        self.assertEqual(row["parameters"]["review"]["quote"],self.review["quote"])
        self.assertEqual(row["sha256"],row["content_sha256"])
        self.assertFalse(list(self.project.rglob("*polish*")))

    def test_missing_or_unfinished_reading_blocks_the_section(self):
        self.assertTrue(sw.problems(self.project,["methods"]))
        self.begin();self.assertTrue(sw.problems(self.project,["methods"]))
        self.assertEqual(sw.problems(self.project,["supplementary_methods"],["supplementary_methods"]),[])

    def test_changed_section_or_actual_reading_source_invalidates_only_that_section(self):
        self.begin();self.accept();self.path.write_text(TEXT+"\nA new paragraph.\n",encoding="utf-8")
        self.assertTrue(sw.problems(self.project,["methods"]))
        self.path.write_text(TEXT,encoding="utf-8");self.assertEqual(sw.problems(self.project,["methods"]),[])
        self.source.write_text("The scientific source has genuinely changed.",encoding="utf-8")
        self.assertTrue(sw.problems(self.project,["methods"]))

    def test_unrelated_file_does_not_expire_an_unchanged_medical_section(self):
        self.begin();self.accept();self.text("05_figures/unrelated_notes.md","An unrelated build note.")
        self.assertEqual(sw.problems(self.project,["methods"]),[])

    def test_reading_source_change_during_edit_cannot_be_accepted(self):
        self.begin();self.source.write_text("A genuinely different scientific protocol.",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"factual reading source changed"):self.accept()

    def test_actual_scientific_revision_can_reset_an_abandoned_wording_baseline(self):
        self.begin();self.path.write_text(TEXT.replace("120","121"),encoding="utf-8")
        revision={"items":[{"change_type":"scientific","affected_sources":["07_manuscript/methods.md"]}]}
        atomic_json(self.project/".wf/revisions/R001.json",revision)
        self.state.data["active_revision_round"]="R001";self.state.save()
        sw.begin(self.project,"methods",["01_protocol/protocol_final.md"],scientific_reset=True)
        self.accept();self.assertEqual(sw.problems(self.project,["methods"]),[])

    def test_medical_term_may_be_retained_with_its_specific_actual_context(self):
        from wfcore.medicalstyle import diagnose
        value=TEXT+"\nUnicode normalization was applied to harmonize the source diagnostic terminology.\n"
        self.path.write_text(value,encoding="utf-8");self.begin()
        findings=diagnose(value,"07_manuscript/methods.md")
        reason="This terminology describes the actual source-code harmonization needed for the exposure definition; its detailed implementation is in supplementary Methods."
        sw.accept(self.project,"methods",{**self.review,"resolutions":{item["id"]:reason for item in findings}})
        self.assertEqual(sw.problems(self.project,["methods"]),[])

    def test_numeric_citation_and_p_operator_changes_cannot_pass_as_wording(self):
        for old,new in (("1.34","1.43"),("[@cohort]","[@different]"),("P = 0.03","P < 0.03"),("Table 2","Table 3")):
            self.path.write_text(TEXT,encoding="utf-8");self.begin()
            self.path.write_text(TEXT.replace(old,new),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"protected content"):self.accept()
            self.path.write_text(TEXT,encoding="utf-8");self.accept()

    def test_polarity_and_design_changes_are_not_silently_medicalized(self):
        for old,new in (("did not infer","did infer"),("retrospective","prospective"),("observational","randomized")):
            self.path.write_text(TEXT,encoding="utf-8");self.begin()
            self.path.write_text(TEXT.replace(old,new),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"protected content"):self.accept()
            self.path.write_text(TEXT,encoding="utf-8");self.accept()

    def test_real_negative_wording_can_change_without_erasing_the_negative_result(self):
        first=TEXT.replace("We did not infer a treatment benefit","There was no inference of a treatment benefit")
        self.assertEqual(sw.facts(TEXT),sw.facts(first))

    def test_bare_pass_and_fabricated_passage_are_not_medical_reading(self):
        self.begin()
        with self.assertRaises(ValueError):sw.accept(self.project,"methods",True)
        bad={**self.review,"quote":"This sentence never appears in the actual paper."}
        with self.assertRaisesRegex(ValueError,"real current section passage"):sw.accept(self.project,"methods",bad)
        with self.assertRaises(ValueError):sw.accept(self.project,"methods",{**self.review,"clinical_reading":"passed"})

    def test_actual_engineering_risk_requires_fix_or_specific_medical_reason(self):
        self.path.write_text(TEXT+"\nThe processing contract uses source_sha256.\n",encoding="utf-8")
        self.begin()
        with self.assertRaisesRegex(ValueError,"actual medical-language findings"):self.accept()
        self.path.write_text(TEXT,encoding="utf-8");self.accept()

    def test_begin_is_idempotent_and_cannot_rebaseline_an_unfinished_edit(self):
        self.begin();old=buildproof.load(self.project)["07_manuscript/methods.md"]["parameters"]["original_sha256"]
        self.path.write_text(TEXT.replace("120","121"),encoding="utf-8");result=self.begin()
        self.assertTrue(result["preserved_baseline"])
        self.assertEqual(buildproof.load(self.project)["07_manuscript/methods.md"]["parameters"]["original_sha256"],old)
        with self.assertRaisesRegex(ValueError,"protected content"):self.accept()
        with self.assertRaisesRegex(ValueError,"scientific revision"):
            sw.begin(self.project,"methods",["01_protocol/protocol_final.md"],scientific_reset=True)

    def test_old_completed_pin_is_not_backfilled_and_full_manuscript_is_not_a_section(self):
        self.state.data["engine_pin"]="1.27.0";self.state.save()
        self.assertEqual(sw.problems(self.project,["methods"]),[])
        with self.assertRaisesRegex(ValueError,"one scientific section"):sw.section_path("07_manuscript/full_manuscript.md")
        self.begin();self.assertTrue(sw.problems(self.project,["methods"]))

    def test_old_project_one_section_adoption_does_not_reopen_other_completed_sections(self):
        self.state.data["engine_pin"]="1.27.0";self.state.save()
        self.begin();self.accept()
        self.assertEqual(sw.problems(self.project,list(sw.SECTIONS),["supplementary_methods"]),[])
        self.path.write_text(TEXT+"\nChanged interpretation.\n",encoding="utf-8")
        errors=sw.problems(self.project,list(sw.SECTIONS),["supplementary_methods"])
        self.assertEqual(len(errors),1);self.assertIn("methods.md",errors[0])

    def test_abstract_edit_cannot_begin_before_actual_early_scientific_go(self):
        self.text("07_manuscript/abstract.md","# Abstract\n\nThe retrospective cohort does not establish treatment benefit.")
        with patch("wfcore.earlyreview.verify",return_value=["Independent review is REVISE"]):
            with self.assertRaisesRegex(ValueError,"Independent review is REVISE"):
                sw.begin(self.project,"abstract",["01_protocol/protocol_final.md"])
        self.assertNotIn("07_manuscript/abstract.md",buildproof.load(self.project))
        with patch("wfcore.earlyreview.verify",return_value=[]):
            self.assertEqual(sw.begin(self.project,"abstract",["01_protocol/protocol_final.md"])["status"],"editing")

    def test_cli_runs_at_actual_owner_and_refuses_a_different_stage(self):
        def run(*args):return subprocess.run([sys.executable,str(ROOT/"tools/manuscript/section_writing.py"),*args,
              "--section","methods","--project",str(self.project)],capture_output=True,text=True,encoding="utf-8",timeout=30)
        began=run("begin","--source","01_protocol/protocol_final.md");self.assertEqual(began.returncode,0,began.stderr)
        review=self.project/"temp/review.json";atomic_json(review,self.review)
        accepted=run("accept","--review-file",str(review));self.assertEqual(accepted.returncode,0,accepted.stderr)
        self.state.data["current"]="S09_results";self.state.save()
        bad=run("begin","--source","01_protocol/protocol_final.md");self.assertNotEqual(bad.returncode,0)
        self.assertIn("active section stage",bad.stderr)


    def test_assembly_renews_actual_section_readback_and_preserves_freeze_boundary(self):
        self.begin();self.accept()
        self.state.data["current"]="S17_assemble";self.state.save()
        command=[sys.executable,str(ROOT/"tools/manuscript/section_writing.py"),"begin","--source","01_protocol/protocol_final.md","--section","methods","--project",str(self.project)]
        renewed=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",timeout=30)
        self.assertEqual(renewed.returncode,0,renewed.stderr)
        self.accept()
        self.text("07_manuscript/scientific_master_freeze.json","{}")
        frozen=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",timeout=30)
        self.assertNotEqual(frozen.returncode,0)
        self.assertIn("active section stage",frozen.stderr)

    def test_report_only_preserves_library_bytes_and_mtime(self):
        from pubmed import build_library
        library=self.text("06_refs/library.json",json.dumps({"entries":[],"updated_at":"2026-01-01T00:00:00Z"}))
        before=(library.read_bytes(),library.stat().st_mtime_ns)
        with patch.object(sys,"argv",["build_library.py","--report"]),patch.object(build_library.eu,"project_root",return_value=self.project),patch.object(build_library.eu,"refs_dir",return_value=library.parent):
            self.assertEqual(build_library.main(),0)
        self.assertEqual(before,(library.read_bytes(),library.stat().st_mtime_ns))


if __name__=="__main__":unittest.main(verbosity=2)
