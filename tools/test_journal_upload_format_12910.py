import unittest
from docx import Document
from wfcore.journalspec import apply_docx
from manuscript.build_docx import _canon_figure_id,_legend_problems
from wfcore.checks.manuscript import _canon_figure_id as check_id

class JournalCaptions(unittest.TestCase):
 def test_fig_alias_has_same_identity(self):
  self.assertEqual(_canon_figure_id('Fig. 1'),_canon_figure_id('Figure 1'))
  self.assertEqual(check_id('Fig. S1'),check_id('Figure S1'))
 def make(self,label='Figure 1. Clinical description'):
  d=Document();d.add_paragraph('Figure legends',style='Heading 1')
  d.add_paragraph(label,style='Heading 2')
  d.add_paragraph('Points identify reporting odds and bars show the uncertainty of estimates.')
  return d
 def test_explicit_caption_presentation(self):
  d=self.make();apply_docx(d,{'figure_caption_label':'Fig.'},'manuscript')
  self.assertEqual(d.paragraphs[1].text,'Fig. 1 Clinical description')
  self.assertTrue(all(r.bold for r in d.paragraphs[1].runs))
 def test_default_keeps_canonical_source_label(self):
  d=self.make();apply_docx(d,{},'manuscript')
  self.assertEqual(d.paragraphs[1].text,'Figure 1. Clinical description')
 def test_body_figure_reference_is_unchanged(self):
  d=Document();d.add_paragraph('Figure 1. Clinical description')
  apply_docx(d,{'figure_caption_label':'Fig.'},'manuscript')
  self.assertEqual(d.paragraphs[0].text,'Figure 1. Clinical description')
 def test_wrong_caption_number_remains_distinct(self):
  self.assertNotEqual(_canon_figure_id('Fig. 2'),_canon_figure_id('Figure 1'))

if __name__=='__main__':unittest.main()
