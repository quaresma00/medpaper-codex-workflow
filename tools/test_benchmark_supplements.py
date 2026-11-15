"""Synthetic source-linked appendix fixtures; never study/review evidence."""
import copy
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from wfcore import benchmark as b
from wfcore.packagefreeze import _sha256


class SourceLinkedSupplements(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.rel = '06_refs/fulltext/supplements/testkey/publisher_appendix.docx'
        file = self.project / self.rel; file.parent.mkdir(parents=True)
        with ZipFile(file, 'w') as z:
            z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Supplementary Figure 1. Synthetic interval display</w:t></w:r></w:p><w:p><w:r><w:t>Supplementary Table 9. Synthetic subgroup counts</w:t></w:r></w:p></w:body></w:document>')
        self.xml = '06_refs/fulltext/testkey.xml'
        (self.project / self.xml).write_text('<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><article-id pub-id-type="pmid">90000001</article-id><article-id pub-id-type="pmcid">PMC9000001</article-id><article-id pub-id-type="doi">10.0000/test</article-id></article-meta></front><back><supplementary-material><media xlink:href="publisher_appendix.docx"/></supplementary-material></back></article>')
        self.entry = dict(pmid='90000001', pmcid='PMC9000001', doi='10.0000/test')
        self.row = dict(citekey='testkey', supplementary_sources=[dict(file=self.rel, sha256=_sha256(file), article_xml=self.xml, article_xml_sha256=_sha256(self.project/self.xml), source_url='https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9000001/supplementaryFiles')])

    def texts(self): return b._supplementary_texts(self.project, self.row, self.entry)

    def test_actual_linked_appendix_caption_supports_s_notation(self):
        texts = self.texts()
        self.assertTrue(b._display_present('Figure 1 is the main flow.', texts, dict(id='Figure S1', kind='supp_figure')))
        self.assertTrue(b._display_present('', texts, dict(id='Table S9', kind='supp_table')))

    def test_missing_caption_and_main_inventory_cannot_borrow_appendix(self):
        texts = self.texts()
        self.assertFalse(b._display_present('', texts, dict(id='Table S99', kind='supp_table')))
        self.assertFalse(b._display_present('', texts, dict(id='Table 9', kind='main_table')))

    def test_changed_supplement_or_metadata_bytes_are_rejected(self):
        for field in ['sha256', 'article_xml_sha256']:
            with self.subTest(field=field):
                row = copy.deepcopy(self.row); row['supplementary_sources'][0][field] = 'bad'
                with self.assertRaises(ValueError): b._supplementary_texts(self.project, row, self.entry)

    def test_different_article_identity_is_rejected(self):
        for field in ['pmid', 'pmcid', 'doi']:
            with self.subTest(field=field):
                entry = {**self.entry, field:'other'}
                with self.assertRaises(ValueError): b._supplementary_texts(self.project, self.row, entry)

    def test_unlinked_filename_wrong_source_and_other_directory_are_rejected(self):
        for field, value in [('source_url', 'https://example.org/foreign'), ('file', '06_refs/fulltext/foreign.docx')]:
            with self.subTest(field=field):
                row=copy.deepcopy(self.row); row['supplementary_sources'][0][field]=value
                with self.assertRaises(ValueError): b._supplementary_texts(self.project,row,self.entry)
        xml=self.project/self.xml;xml.write_text(xml.read_text().replace('publisher_appendix.docx','another_file.docx'))
        self.row['supplementary_sources'][0]['article_xml_sha256']=_sha256(xml)
        with self.assertRaises(ValueError): self.texts()

    def test_main_literal_caption_and_legacy_missing_source_list_work(self):
        self.assertEqual(b._supplementary_texts(self.project,dict(citekey='legacy'),self.entry),[])
        self.assertTrue(b._display_present('table 2. actual main results', [], dict(id='Table 2',kind='main_table')))


if __name__ == '__main__': unittest.main(verbosity=2)
