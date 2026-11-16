"""Exact contextual reading must not become a statistical-integrity exemption."""
import copy
import unittest
from text.polish import apply_style_exceptions,style_exception_key
from wfcore.checks.polish import _canonical_section_counts

REASON='Verbatim uppercase brand-name matching literal in the supplementary operating definitions, not an undefined narrative abbreviation.'
class ContextualPolishTests(unittest.TestCase):
 def row(self,kind='abbrev_undefined',file='(body)',detail="'EXAMPLEBRAND' is used in the body but never defined there"):
  return {'file':file,'kind':kind,'detail':detail,'severity':'blocking'}
 def test_exact_diagnostic_can_remain_as_explained_advisory(self):
  row=self.row();original=copy.deepcopy(row);out=apply_style_exceptions([row],{style_exception_key(row):REASON})[0]
  self.assertEqual(out['severity'],'advisory');self.assertEqual(out['contextual_exception'],REASON)
  self.assertEqual(out['original_severity'],'blocking');self.assertEqual(row,original)
 def test_no_exception_remains_blocking(self):
  self.assertEqual(apply_style_exceptions([self.row()],{})[0]['severity'],'blocking')
 def test_kind_only_is_not_a_blanket_exception(self):
  self.assertEqual(apply_style_exceptions([self.row()],{'abbrev_undefined':REASON})[0]['severity'],'blocking')
 def test_different_token_does_not_reuse_exception(self):
  row=self.row();other=self.row(detail="'OTHER' is used in the body but never defined there")
  self.assertEqual(apply_style_exceptions([other],{style_exception_key(row):REASON})[0]['severity'],'blocking')
 def test_different_file_does_not_reuse_exception(self):
  row=self.row();other={**row,'file':'abstract.md'}
  self.assertEqual(apply_style_exceptions([other],{style_exception_key(row):REASON})[0]['severity'],'blocking')
 def test_short_reason_is_not_adjudication(self):
  row=self.row();self.assertEqual(apply_style_exceptions([row],{style_exception_key(row):'ignore'})[0]['severity'],'blocking')
 def test_numeric_and_statistical_findings_cannot_be_excepted(self):
  for kind in ['p_zero','range_dash','pvalue_style','data_agreement','lost_citation']:
   row=self.row(kind=kind);self.assertEqual(apply_style_exceptions([row],{style_exception_key(row):REASON})[0]['severity'],'blocking')
 def test_exact_affiliation_identifier_can_be_contextual(self):
  row=self.row(kind='sentence_starts_with_numeral',file='title_page.md',detail='An actual affiliation list begins with 1.')
  self.assertEqual(apply_style_exceptions([row],{style_exception_key(row):'This is the supplied affiliation identifier, not the start of a narrative sentence.'})[0]['severity'],'advisory')
 def test_separate_conclusion_is_counted_as_main_text(self):
  counts=_canonical_section_counts('# Title of the study\n# Abstract\nA report.\n# Introduction\nOne question.\n# Discussion\nClinical interpretation.\n# Conclusion\nA cautious conclusion.\n# References\n')
  self.assertEqual(counts['conclusion'],3);self.assertEqual(counts['discussion'],2)
if __name__=='__main__':unittest.main()
