"""Real three-line-workbook percentage checks using synthetic analysis facts only."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from tables.threeline import write_table
from wfcore import claims,registry
from wfcore.checks import Ctx,load_all
from wfcore.checks.numbers import numbers_have_provenance
from wfcore.readiness import atomic_json
from wfcore.state import State


class TableProportionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-proportion-126-");self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name);self.rel="04_tables/main/Table1.xlsx"
        self.state=State(self.project).create("medpaper","1.26.0","S10_tables")
        self.pipe=registry.load();load_all()
        self.context={"outcome":"Women","population":"Eligible reports","comparison":"Descriptive summary",
                      "model":"Observed count","timepoint":"Study period","unit":"Reports (%)",
                      "denominator":"Reports with known sex","percentage_basis":"Eligible reports with known sex in the actual study period"}
        self.values={"women":102,"available":159,"all_reports":282,"percentage":64.2}

    def build(self,value="64.2%",header="Women",proportions=None):
        path=self.project/self.rel;path.parent.mkdir(parents=True,exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            write_table(path,sheet="Table1",title="Table 1. Report characteristics",header=["Characteristic",header],
                        rows=[[self.context["outcome"],value]],footnotes=["Percentages use the stated source basis; absent values are not zero."])
        atomic_json(self.project/"03_analysis/results/primary.json",{"reported":{"context":self.context,"values":self.values}})
        atomic_json(self.project/"01_protocol/study_facts.json",{"numeric_facts":{"sex":{"source":"03_analysis/results/primary.json","pointer":"/reported","context":self.context}}})
        row={"path":self.rel,"sheet":"Table1","cell":"B3","text":str(value),"fact_ids":["sex"],"label_cells":["A3"]}
        if proportions is not None:row["proportions"]=proportions
        atomic_json(self.project/"07_manuscript/claim_bindings.json",{"schema_version":1,"claims":[row]})
        return path

    def ratio(self,denominator="available",reported="64.2"):
        return [{"fact_id":"sex","numerator_key":"women","denominator_key":denominator,"reported":reported}]

    def test_current_missing_percentage_evidence_is_rejected_in_production_gate(self):
        path=self.build()
        errors=claims.validate_tables(self.project,[path]);self.assertTrue(errors)
        result=numbers_have_provenance(Ctx(self.pipe,self.state,self.project,self.pipe.stage("S10_tables"),{"source":"tables"}))
        self.assertFalse(result.ok)

    def test_correct_proportion_is_accepted(self):
        self.assertEqual(claims.validate_tables(self.project,[self.build(proportions=self.ratio())]),[])

    def test_wrong_denominator_cannot_be_hidden_by_a_matching_display_value(self):
        errors=claims.validate_tables(self.project,[self.build(proportions=self.ratio("all_reports"))])
        self.assertTrue(any("denominator" in e for e in errors),errors)

    def test_count_percentage_header_requires_source_even_without_percent_in_cell(self):
        self.assertTrue(claims.validate_tables(self.project,[self.build("102 (64.2)","Reports, n (%)")]))
        self.assertEqual(claims.validate_tables(self.project,[self.build("102 (64.2)","Reports, n (%)",self.ratio())]),[])

    def test_interval_confidence_level_is_not_a_patient_proportion(self):
        self.values={"estimate":1.34,"low":1.10,"high":1.63}
        self.assertEqual(claims.validate_tables(self.project,[self.build("1.34 (95% CI, 1.10 to 1.63)","Effect")]),[])

    def test_non_numeric_na_and_counts_do_not_need_fabricated_denominators(self):
        self.assertEqual(claims.validate_tables(self.project,[self.build("N/A","Reports, n (%)")]),[])
        self.assertEqual(claims.validate_tables(self.project,[self.build("102","Number")]),[])

    def test_explicit_continuous_percentage_has_source_type_and_no_count_ratio(self):
        self.context.update(outcome="Ejection fraction",percentage_kind="measurement",unit="Ejection fraction (%)",
                            denominator="Not a patient proportion: continuous measurement",
                            percentage_basis="Mean observed ejection fraction on its physical percentage scale")
        self.values={"mean":55}
        self.assertEqual(claims.validate_tables(self.project,[self.build("55%","Mean value")]),[])

    def test_non_proportion_exemption_needs_actual_source_basis_and_unit(self):
        self.context.update(percentage_kind="measurement",unit="Reports",percentage_basis="")
        self.values={"mean":55}
        self.assertTrue(claims.validate_tables(self.project,[self.build("55%","Mean value")]))

    def test_legacy_completed_work_is_not_silently_rewritten(self):
        self.state.data.update(engine_pin="1.25.0",pipeline_version="1.25.0");self.state.save()
        path=self.build();before=path.read_bytes()
        self.assertEqual(claims.validate_tables(self.project,[path]),[])
        self.assertEqual(path.read_bytes(),before)
        self.assertTrue(claims.validate_tables(self.project,[self.build(proportions=self.ratio("all_reports"))]))

    def test_small_and_scientific_notation_percentages_keep_the_actual_denominator(self):
        self.values={"women":1,"available":200,"percentage":.5}
        for text,reported in ((".5%",".5"),("5e-1%","5e-1")):
            with self.subTest(text=text):
                self.assertEqual(claims.validate_tables(self.project,[self.build(text,proportions=self.ratio(reported=reported))]),[])
                self.assertTrue(claims.validate_tables(self.project,[self.build(text)]))


if __name__=="__main__":unittest.main(verbosity=2)
