import unittest,tempfile
from pathlib import Path
from docx import Document
from wfcore.journalspec import apply_docx
from wfcore.submission import docx_sections
class FrontMatter(unittest.TestCase):
 def test_body_mapping_does_not_number_abstract_subheading(self):
  d=Document();d.add_paragraph('Methods',style='Heading 2');d.add_paragraph('Methods',style='Heading 1')
  apply_docx(d,{'main_text_headings':{'Methods':'2 Methods'}},'manuscript')
  self.assertEqual([p.text for p in d.paragraphs],['Methods','2 Methods'])
 def test_key_points_end_keywords(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'m.docx';d=Document();d.add_paragraph('Title',style='Heading 1')
   d.add_paragraph('Abstract',style='Heading 1');d.add_paragraph('Abstract text.')
   d.add_paragraph('Keywords: A, B');d.add_paragraph('Key Points',style='Heading 1')
   d.add_paragraph('Clinical finding with a comma, and another clause.')
   d.add_paragraph('Introduction',style='Heading 1');d.add_paragraph('Body.');d.save(p)
   _,s,_=docx_sections(p)
   self.assertNotIn('Clinical',s['Keywords']);self.assertIn('Clinical',s['Key Points'])
if __name__=='__main__':unittest.main()
