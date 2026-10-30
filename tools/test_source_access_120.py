"""Synthetic-only regressions: real source fields cannot be replaced with invented text."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pubmed import build_library, fulltext, verify
from wfcore import refproof, registry
from wfcore.checks import Ctx
from wfcore.checks.refs import refs_library, citekeys_resolve
from wfcore.readiness import atomic_json
from wfcore.state import State


class SourceAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="medpaper-source-access-")
        self.addCleanup(self.tmp.cleanup)
        self.project=Path(self.tmp.name)
        self.pipe=registry.load()
        self.state=State(self.project).create("medpaper","1.20.0","S13_reflib")
        self.raw='''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID>
<Article><ArticleTitle>Synthetic reference test</ArticleTitle>
<Journal><Title>Synthetic Test Journal</Title><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
<AuthorList><Author><LastName>Fixture</LastName><ForeName>Alice</ForeName></Author></AuthorList>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/fixture</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></PubmedArticleSet>'''
        self.source=refproof.parse_pubmed_payload(self.raw)["123"]
        library={"entries":[]}
        self.assertEqual(build_library.add_records(library,[self.source]),(1,0,0))
        self.entry=library["entries"][0]
        self.key=self.entry["citekey"]
        atomic_json(self.project/"06_refs/library.json",library)
        self.cache="06_refs/cache/verify_efetch_pubmed_fixture.xml"
        self.text(self.cache,self.raw)
        self.source.update(cache_file=self.cache,cache_sha256=refproof.file_sha256(self.project/self.cache),fresh_fetch=True)
        self.text("06_refs/refs.bib",build_library.to_bibtex(library["entries"]))
        self.text("07_manuscript/proof.md",f"Synthetic supported claim [@{self.key}].")

    def text(self,rel,value):
        path=self.project/rel; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(value,encoding="utf-8"); return path

    def register(self,body=True):
        article='<article><front><article-meta><article-id pub-id-type="doi">10.1000/fixture</article-id><title-group><article-title>Synthetic reference test</article-title></title-group></article-meta></front>'
        article += ('<body><p>'+('Synthetic test content describing a mathematical method. '*35)+'</p></body>') if body else ('<!--'+'synthetic padding '*90+'-->')
        path=self.text("06_refs/fulltext/fixture.xml",article+'</article>')
        args=["fulltext.py","register","--citekey",self.key,"--file",str(path),"--access","oa","--source-url","https://example.org/synthetic-test","--replace-existing"]
        with patch("pubmed.eutils.project_root",return_value=self.project),patch("sys.argv",args),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fulltext.main(),0)
        record=json.loads((self.project/"06_refs/fulltext/retrieval_manifest.json").read_text())["retrievals"][0]
        return self.project/record["fulltext"]

    def proof(self):
        result=verify.verify_entry(self.entry,self.source,False,self.project)
        atomic_json(self.project/"06_refs/verified.json",{
            "schema":refproof.SCHEMA,"generator":{"tool":refproof.GENERATOR,"mode":"fresh_ncbi_pubmed_efetch"},
            "verified_at":result["at"],"library_sha256":refproof.file_sha256(self.project/"06_refs/library.json"),
            "n_entries":1,"n_verified":int(result["verified"]),"records":{self.key:result}})
        return result

    def ctx(self,**spec):
        return Ctx(self.pipe,self.state,self.project,self.pipe.stage("S13_reflib"),spec)

    def test_no_abstract_candidate_is_retained_but_not_citable_without_fulltext(self):
        self.assertEqual(self.entry["abstract"],"")
        self.assertFalse(self.proof()["verified"])
        self.assertFalse(citekeys_resolve(self.ctx(paths=["07_manuscript/proof.md"])).ok)

    def test_register_before_verification_breaks_no_abstract_circular_dependency(self):
        self.assertFalse((self.project/"06_refs/verified.json").exists())
        self.register()
        self.assertTrue(self.proof()["verified"])
        self.assertTrue(refproof.validate_local_proof(self.project)[0])
        self.assertTrue(refs_library(self.ctx(require_readable_source=True)).ok)
        self.assertTrue(citekeys_resolve(self.ctx(paths=["07_manuscript/proof.md"])).ok)
        self.assertEqual(json.loads((self.project/"06_refs/library.json").read_text())["entries"][0]["abstract"],"")

    def test_fulltext_drift_revokes_citation_permission(self):
        path=self.register(); self.assertTrue(self.proof()["verified"])
        path.write_text(path.read_text()+"<!--changed-->",encoding="utf-8")
        self.assertFalse(refproof.validate_local_proof(self.project)[0])
        self.assertFalse(citekeys_resolve(self.ctx(paths=["07_manuscript/proof.md"])).ok)

    def test_fabricated_abstract_cannot_replace_missing_source_text(self):
        self.entry["abstract"]="Invented evidence, synthetic test only."
        self.assertTrue(refproof.compare_entry_to_source(self.entry,self.source))
        self.assertFalse(verify.verify_entry(self.entry,self.source,False,self.project)["verified"])

    def test_existing_abstract_must_match_beyond_whitespace(self):
        source={**self.source,"abstract":"The estimate was not different.\nNo causal inference."}
        entry={**self.entry,"abstract":"The estimate was not different. No causal inference."}
        self.assertEqual(refproof.compare_entry_to_source(entry,source),[])
        self.assertTrue(verify.verify_entry(entry,source,False,self.project)["verified"])
        entry["abstract"]="The estimate was different. No causal inference."
        self.assertFalse(verify.verify_entry(entry,source,False,self.project)["verified"])

    def test_metadata_only_article_and_wrong_identity_are_rejected(self):
        self.register(body=False)
        self.assertIn("body",str(refproof.readable_source_errors(self.project,self.entry)))
        path=self.register()
        path.write_text(path.read_text().replace("10.1000/fixture","10.1000/wrong"),encoding="utf-8")
        manifest=json.loads((self.project/"06_refs/fulltext/retrieval_manifest.json").read_text())
        manifest["retrievals"][0]["sha256"]=refproof.file_sha256(path)
        atomic_json(self.project/"06_refs/fulltext/retrieval_manifest.json",manifest)
        self.assertIn("contradicts",str(refproof.readable_source_errors(self.project,self.entry)))

    def test_stub_duplicate_and_malformed_registration_fail_closed(self):
        for value in ([],[None],{},[{"citekey":self.key,"access":"paywall"}],
                      [{"citekey":self.key},{"citekey":self.key}]):
            with self.subTest(value=value):
                atomic_json(self.project/"06_refs/fulltext/retrieval_manifest.json",{"retrievals":value})
                self.assertTrue(refproof.readable_source_errors(self.project,self.entry))

    def test_retraction_and_unconfirmed_pdf_are_not_relaxed(self):
        self.register()
        flagged={**self.source,"flags":["RETRACTED_OR_RETRACTION"]}
        self.assertFalse(verify.verify_entry(self.entry,flagged,False,self.project)["verified"])
        manifest=json.loads((self.project/"06_refs/fulltext/retrieval_manifest.json").read_text())
        path=self.text("06_refs/fulltext/fixture.pdf","%PDF synthetic corrupt test "+"x"*1200)
        row=manifest["retrievals"][0]; row.update(fulltext="06_refs/fulltext/fixture.pdf",sha256=refproof.file_sha256(path))
        atomic_json(self.project/"06_refs/fulltext/retrieval_manifest.json",manifest)
        self.assertIn("identity unresolved",str(refproof.readable_source_errors(self.project,self.entry)))
        from pubmed.identity import norm
        row["identity_confirmation"]={"sha256":row["sha256"].upper(),"expected":{k:norm(k,self.entry.get(k)) for k in ("doi","pmid","pmcid","title")},"confirmed_by":"Synthetic fixture","note":"Synthetic claimed inspection must not make a corrupt PDF readable."}
        atomic_json(self.project/"06_refs/fulltext/retrieval_manifest.json",manifest)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertIn("cannot read",str(refproof.readable_source_errors(self.project,self.entry)))

    def test_legacy_abstract_rule_is_explicit_and_conflicting_policy_rejected(self):
        self.register(); self.proof()
        self.assertFalse(refs_library(self.ctx(require_abstract=True)).ok)
        self.assertFalse(refs_library(self.ctx(require_abstract=True,require_readable_source=True)).ok)

    def test_actual_pdf_confirmation_accepts_tool_generated_hash_case(self):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject
        path=self.project/"synthetic.pdf"
        writer=PdfWriter(); page=writer.add_blank_page(100,100)
        stream=DecodedStreamObject(); stream.set_data(b"0 0 m 10 10 l S")
        page[NameObject("/Contents")]=writer._add_object(stream)
        writer.add_metadata({"/Title":"Synthetic test PDF", "/Subject":"Synthetic fixture padding "*100})
        writer.write(path)
        register=["fulltext.py","register","--citekey",self.key,"--file",str(path),"--access","oa","--source-url","https://example.org/synthetic-test"]
        confirm=["fulltext.py","confirm","--citekey",self.key,"--confirmed-by","Synthetic fixture reader","--identity-note","Synthetic end-to-end confirmation of the exact registered fixture document."]
        with patch("pubmed.eutils.project_root",return_value=self.project),contextlib.redirect_stdout(io.StringIO()):
            with patch("sys.argv",register): self.assertEqual(fulltext.main(),0)
            self.assertTrue(refproof.readable_source_errors(self.project,self.entry))
            with patch("sys.argv",confirm): self.assertEqual(fulltext.main(),0)
        self.assertEqual(refproof.readable_source_errors(self.project,self.entry),[])
        self.assertTrue(self.proof()["verified"])


if __name__=="__main__": unittest.main(verbosity=2)
