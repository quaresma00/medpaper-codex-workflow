import unittest
from test_composed_methods_constants_1296 import ComposedMethodsConstants
from wfcore.checks.numbers import _prose_offenders
class JournalMethodsConstants(ComposedMethodsConstants):
 def check(self,text):return _prose_offenders(self.ctx,"08_submission/integration/full_manuscript.md",text,set(),set(),set())
 def test_numbered_subheading_keeps_exact_accepted_paragraph(self):
  self.assertEqual(self.check(self.block.replace("# Methods","# Methods\n\n## 2.1 Data sources")+"\n# Results\n\nNo values."),[])
 def test_new_or_changed_journal_constant_context_fails(self):
  self.assertTrue(self.check(self.block.replace("archives","records")))
 def test_paragraph_moved_to_results_cannot_borrow_methods(self):
  self.assertTrue(self.check("# Methods\n\nNo values.\n\n# Results\n\nHistorical source archives start in 2004."))
if __name__=="__main__":unittest.main()
