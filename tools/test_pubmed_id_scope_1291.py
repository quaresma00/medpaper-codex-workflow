"""Synthetic PubMed XML keeps article identifiers separate from cited identifiers."""
import copy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pubmed import eutils,verify
from wfcore import refproof


def article(pmc="PMC100",doi="10.1000/main",refs=True,elocation="",nested=False,pmid="123"):
    ids=(f'<ArticleId IdType="pmc">{pmc}</ArticleId>' if pmc else '')
    ids+=(f'<ArticleId IdType="doi">{doi}</ArticleId>' if doi else '')
    reference='''<Reference><Citation>Unrelated synthetic cited article</Citation><ArticleIdList>
<ArticleId IdType="pubmed">999</ArticleId><ArticleId IdType="pmc">PMC999</ArticleId>
<ArticleId IdType="doi">10.1000/reference</ArticleId></ArticleIdList></Reference>'''
    back=("<ReferenceList>"+("<ReferenceList>" if nested else "")+reference+
          ("</ReferenceList>" if nested else "")+"</ReferenceList>") if refs else ''
    return f'''<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>
<ArticleTitle>Synthetic primary clinical article</ArticleTitle><Abstract><AbstractText>Actual synthetic study findings, with no patient data.</AbstractText></Abstract>
<Journal><Title>Synthetic Clinical Journal</Title><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue></Journal>
<AuthorList><Author><LastName>Fixture</LastName><ForeName>Alice</ForeName><Initials>A</Initials></Author></AuthorList>
{('<ELocationID EIdType="doi">'+elocation+'</ELocationID>') if elocation else ''}
</Article></MedlineCitation><PubmedData><ArticleIdList>{ids}</ArticleIdList>{back}</PubmedData></PubmedArticle>'''


class IdentifierScopeTests(unittest.TestCase):
    def parsed(self,**kwargs):
        raw='<PubmedArticleSet>'+article(**kwargs)+'</PubmedArticleSet>'
        client=eutils.parse_pubmed_xml(raw)[0];source=refproof.parse_pubmed_payload(raw)[str(kwargs.get('pmid','123'))]
        return raw,client,source

    def test_actual_article_identifiers_survive_following_reference_list(self):
        _,client,source=self.parsed()
        for row in (client,source):
            self.assertEqual(row['pmcid'],'PMC100');self.assertEqual(row['doi'],'10.1000/main');self.assertEqual(row['pmid'],'123')

    def test_article_without_pmcid_stays_empty_despite_cited_pmcid(self):
        _,client,source=self.parsed(pmc='')
        self.assertEqual(client['pmcid'],'');self.assertEqual(source['pmcid'],'')

    def test_missing_main_identifiers_never_fall_back_to_reference_identifiers(self):
        _,client,source=self.parsed(pmc='',doi='')
        for row in (client,source):self.assertEqual((row['doi'],row['pmcid']),('',''))

    def test_nested_reference_lists_do_not_change_article_identity(self):
        _,client,source=self.parsed(nested=True)
        self.assertEqual(client['pmcid'],'PMC100');self.assertEqual(source['pmcid'],'PMC100')

    def test_reference_order_does_not_change_either_parser(self):
        raw,client,source=self.parsed()
        changed=raw.replace('PMC999','PMC888').replace('10.1000/reference','10.1000/different-reference')
        self.assertEqual(eutils.parse_pubmed_xml(changed)[0]['pmcid'],client['pmcid'])
        self.assertEqual(refproof.parse_pubmed_payload(changed)['123']['doi'],source['doi'])

    def test_elocation_doi_is_taken_only_from_main_article(self):
        _,client,source=self.parsed(doi='',elocation='10.1000/main-elocation')
        for row in (client,source):self.assertEqual(row['doi'],'10.1000/main-elocation')
        raw,_,_=self.parsed(doi='',pmc='')
        raw=raw.replace('<Citation>','<ELocationID EIdType="doi">10.1000/not-main</ELocationID><Citation>')
        self.assertEqual(eutils.parse_pubmed_xml(raw)[0]['doi'],'')
        self.assertEqual(refproof.parse_pubmed_payload(raw)['123']['doi'],'')

    def test_batch_records_do_not_borrow_another_articles_identifiers(self):
        raw='<PubmedArticleSet>'+article()+article(pmc='PMC200',doi='10.1000/second',pmid='456')+'</PubmedArticleSet>'
        clients=eutils.parse_pubmed_xml(raw);sources=refproof.parse_pubmed_payload(raw)
        self.assertEqual([x['pmcid'] for x in clients],['PMC100','PMC200'])
        self.assertEqual([sources[k]['pmcid'] for k in ('123','456')],['PMC100','PMC200'])

    def book_xml(self,where):
        own='<ArticleIdList><ArticleId IdType="doi">10.1000/book-entry</ArticleId><ArticleId IdType="pmc">PMC300</ArticleId></ArticleIdList>'
        reference='<ReferenceList><Reference><ArticleIdList><ArticleId IdType="doi">10.1000/cited-book</ArticleId><ArticleId IdType="pmc">PMC999</ArticleId></ArticleIdList></Reference></ReferenceList>'
        return ('<PubmedArticleSet><PubmedBookArticle><BookDocument><PMID>789</PMID>'+
                (own if where=='BookDocument' else '<ArticleIdList/>')+
                '<Book><BookTitle>Synthetic clinical book</BookTitle></Book>'+reference+
                '</BookDocument><PubmedBookData>'+(own if where=='PubmedBookData' else '<ArticleIdList/>')+
                '</PubmedBookData></PubmedBookArticle></PubmedArticleSet>')

    def test_book_primary_identifiers_are_retained_from_either_own_location(self):
        for where in ('BookDocument','PubmedBookData'):
            with self.subTest(where=where):
                raw=self.book_xml(where)
                # Exercise identifier extraction only; this fix does not extend
                # the verifier's other book-specific bibliographic fields.
                book=ET.fromstring(raw).find('PubmedBookArticle')
                for row in (eutils.parse_pubmed_xml(raw)[0],refproof._source_record(book)):
                    self.assertEqual((row['doi'],row['pmcid']),('10.1000/book-entry','PMC300'))

    def test_book_without_own_identifiers_does_not_borrow_cited_book_ids(self):
        raw=self.book_xml('absent')
        book=ET.fromstring(raw).find('PubmedBookArticle')
        for row in (eutils.parse_pubmed_xml(raw)[0],refproof._source_record(book)):
            self.assertEqual((row['doi'],row['pmcid']),('',''))

    def test_correct_library_passes_but_reference_pmcid_and_real_mismatch_fail(self):
        _,client,source=self.parsed()
        self.assertEqual(refproof.compare_entry_to_source(client,source),[])
        with tempfile.TemporaryDirectory(prefix='medpaper-pmc-scope-') as folder:
            # verify_entry can compare real metadata without claiming a receipt
            # because this isolated fixture has no fresh-network evidence.
            source['cache_file']='';client['citekey']='fixture'
            self.assertTrue(verify.verify_entry(client,source,False,Path(folder))['verified'])
            for wrong in ('PMC999','PMC777'):
                broken=copy.deepcopy(client);broken['pmcid']=wrong
                self.assertIn('PMCID differs from PubMed payload',refproof.compare_entry_to_source(broken,source))
                self.assertFalse(verify.verify_entry(broken,source,False,Path(folder))['verified'])


if __name__=='__main__':unittest.main(verbosity=2)
