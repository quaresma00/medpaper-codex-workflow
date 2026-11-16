"""Synthetic verified-source projections; no research/citation evidence is fabricated."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

from pubmed import build_library, eutils as eu, reference_view as view, verify
from wfcore import refproof


class ReferenceViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="medpaper-reference-view-")
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.refs = self.project / "06_refs"
        self.refs.mkdir()
        self.rows = [dict(pmid="101", title="Synthetic clinical question one", abstract="The synthetic finding was uncertain.", doi="10.1000/one", pmcid="PMC101"),
                     dict(pmid="202", title="Synthetic clinical question two", abstract="A different synthetic comparison.", doi="10.1000/two", pmcid="")]
        self.library = {"entries": []}
        self.rebuild_library()
        self.renew_proof()
        self.output = "06_refs/views/analysis_sources.json"

    def raw(self):
        records = []
        for source in self.rows:
            r = {k: escape(v) for k, v in source.items()}
            records.append(f'''<PubmedArticle><MedlineCitation><PMID>{r["pmid"]}</PMID><Article>
<ArticleTitle>{r["title"]}</ArticleTitle><Abstract><AbstractText>{r["abstract"]}</AbstractText></Abstract>
<Journal><Title>Synthetic Medical Journal</Title><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue></Journal>
<AuthorList><Author><LastName>Fixture</LastName><ForeName>Alice</ForeName></Author></AuthorList>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">{r["doi"]}</ArticleId>
{('<ArticleId IdType="pmc">'+r["pmcid"]+'</ArticleId>') if r["pmcid"] else ''}
</ArticleIdList></PubmedData></PubmedArticle>''')
        return "<PubmedArticleSet>" + "".join(records) + "</PubmedArticleSet>"

    def rebuild_library(self):
        entries = []
        for record in eu.parse_pubmed_xml(self.raw()):
            entry = build_library._entry_from_record(record, set())
            entry["citekey"] = "article" + record["pmid"]
            entries.append(entry)
        self.library["entries"] = entries
        self.save_library()

    def save_library(self):
        (self.refs / "library.json").write_text(json.dumps(self.library), encoding="utf-8")

    def renew_proof(self):
        # Exercise the actual verifier and its EFetch cache path. Only transport
        # is synthetic; no authored verified=true receipt is accepted as a test shortcut.
        with patch.dict(os.environ, {"MEDPAPER_PROJECT": str(self.project)}):
            with patch.object(eu, "http_get", return_value=self.raw().encode()):
                with patch("sys.argv", ["verify.py"]), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(verify.main(), 0)
        self.assertTrue(refproof.validate_local_proof(self.project)[0])

    def export(self, **kwargs):
        return view.export_view(self.project, self.output, citekeys=["article101"], fields=["title", "abstract"], **kwargs)

    def observed(self, path):
        return path.read_bytes(), path.stat().st_mtime_ns

    def test_exact_selected_source_fields_and_mandatory_identity_are_exported(self):
        originals = {name: self.observed(self.refs / name) for name in ("library.json", "verified.json")}
        result = self.export()
        self.assertEqual(result["status"], "written")
        data = json.loads((self.project / self.output).read_text(encoding="utf-8"))
        self.assertEqual(len(data["records"]), 1)
        self.assertEqual(data["records"][0], {"citekey": "article101", "pmid": "101", "doi": "10.1000/one",
                                                   "pmcid": "PMC101", "title": self.rows[0]["title"], "abstract": self.rows[0]["abstract"]})
        self.assertNotIn("verified", data)
        self.assertNotIn("cache_file", data["records"][0])
        self.assertNotIn("retrieved_at", data["records"][0])
        for name, before in originals.items():
            self.assertEqual(self.observed(self.refs / name), before)

    def test_unused_verified_append_usage_and_fetch_changes_preserve_view_bytes_and_mtime(self):
        self.export()
        path = self.project / self.output
        before = self.observed(path)
        self.rows.append(dict(pmid="303", title="Unconsumed synthetic source", abstract="Unused source text.", doi="10.1000/three", pmcid=""))
        self.rebuild_library()
        self.library.update(updated_at="2030-01-01", queries=[{"query": "new discovery event"}])
        self.library["entries"][0].update(retrieved_at="2030-01-01", cache_file="06_refs/cache/discovery_only.xml",
                                           uncited_reason="Different usage note that is not a scientific producer input.")
        self.save_library()
        self.renew_proof()
        self.assertEqual(self.export()["status"], "unchanged")
        self.assertEqual(view.check_view(self.project, self.output)["status"], "valid")
        self.assertEqual(self.observed(path), before)

    def test_selection_order_fields_order_and_pmid_alias_do_not_rewrite(self):
        result = view.export_view(self.project, self.output, pmids=["202", "101"], fields=["title", "doi"])
        before = self.observed(self.project / self.output)
        again = view.export_view(self.project, self.output, citekeys=["article101", "article202"], fields=["doi", "title", "title"])
        self.assertEqual((result["status"], again["status"]), ("written", "unchanged"))
        self.assertEqual(self.observed(self.project / self.output), before)

    def test_selected_source_content_change_is_stale_until_scoped_reexport(self):
        self.export()
        old = self.observed(self.project / self.output)
        self.rows[0]["abstract"] = "The changed synthetic source does not support the previous wording."
        self.rebuild_library()
        self.renew_proof()
        with self.assertRaisesRegex(ValueError, "Selected reference identity/content"):
            view.check_view(self.project, self.output)
        self.assertEqual(self.observed(self.project / self.output), old)
        self.assertEqual(self.export()["status"], "written")
        self.assertNotEqual((self.project / self.output).read_bytes(), old[0])

    def test_changed_selected_article_identity_is_not_silently_accepted(self):
        self.export()
        self.rows[0].update(doi="10.1000/revised-source", pmcid="PMC999")
        self.rebuild_library()
        self.renew_proof()
        with self.assertRaisesRegex(ValueError, "Selected reference identity/content"):
            view.check_view(self.project, self.output)

    def test_missing_selected_reference_and_empty_identity_fail(self):
        self.export()
        self.rows.pop(0)
        self.rebuild_library()
        self.renew_proof()
        with self.assertRaisesRegex(ValueError, "absent from the managed library"):
            view.check_view(self.project, self.output)
        self.library["entries"][0]["pmid"] = ""
        self.save_library()
        with self.assertRaisesRegex(ValueError, "real numeric PMID"):
            view.project_view(self.project, citekeys=["article202"], fields=["title"])

    def test_unverified_boolean_or_tampered_xml_cannot_create_or_validate_view(self):
        self.export()
        path = self.project / self.output
        before = self.observed(path)
        proof = json.loads((self.refs / "verified.json").read_text())
        raw_path = self.project / proof["records"]["article101"]["evidence"]["cache_file"]
        raw_path.write_bytes(raw_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "genuine reference proof"):
            view.check_view(self.project, self.output)
        (self.refs / "verified.json").write_text('{"verified":true}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "genuine reference proof"):
            self.export()
        self.assertEqual(self.observed(path), before)

    def test_output_namespace_and_unrelated_files_are_protected(self):
        for rel in ("06_refs/library.json", "07_manuscript/full_manuscript.md", "../outside.json", str(self.project / "absolute.json")):
            with self.subTest(path=rel), self.assertRaises(ValueError):
                view.export_view(self.project, rel, citekeys=["article101"], fields=["title"])
        path = self.project / self.output
        path.parent.mkdir()
        path.write_text('{"author_work":"preserve"}', encoding="utf-8")
        before = self.observed(path)
        with self.assertRaisesRegex(ValueError, "unrelated JSON"):
            self.export(replace=True)
        self.assertEqual(self.observed(path), before)

    def test_changed_view_selection_requires_explicit_replace(self):
        self.export()
        with self.assertRaisesRegex(ValueError, "requires --replace"):
            view.export_view(self.project, self.output, citekeys=["article202"], fields=["title"])
        self.assertEqual(view.export_view(self.project, self.output, citekeys=["article202"], fields=["title"], replace=True)["status"], "written")

    def test_revision_guard_blocks_out_of_scope_changes_but_read_only_check_still_works(self):
        self.export()
        state = self.project / ".wf/state.json"
        state.parent.mkdir()
        state.write_text('{"active_revision_round":"R001"}', encoding="utf-8")
        revisions = state.parent / "revisions"
        revisions.mkdir()
        (revisions / "R001.json").write_text('{"schema_version":2,"status":"active","allowed_files":[]}', encoding="utf-8")
        self.assertEqual(view.check_view(self.project, self.output)["status"], "valid")
        self.rows[0]["title"] = "Updated synthetic clinical question"
        self.rebuild_library()
        self.renew_proof()
        with self.assertRaisesRegex(ValueError, "out-of-scope build"):
            self.export()

    def test_non_source_fields_and_unknown_pmid_are_not_exported(self):
        for fields in (["retrieved_at"], ["verified"], ["journal_abbrev"], []):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "Explicit fields"):
                view.project_view(self.project, citekeys=["article101"], fields=fields)
        with self.assertRaisesRegex(ValueError, "Selected PMID is absent"):
            view.project_view(self.project, pmids=["999"], fields=["title"])

    def test_cli_check_is_read_only_and_reports_bounded_summary(self):
        with patch("sys.argv", ["reference_view.py", "--project", str(self.project), "export", "--pmids", "101", "--fields", "title", "--output", self.output]):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(view.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["records"], 1)
        before = {p: self.observed(p) for p in (self.project / self.output, self.refs / "library.json", self.refs / "verified.json")}
        with patch("sys.argv", ["reference_view.py", "--project", str(self.project), "check", "--input", self.output]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(view.main(), 0)
        self.assertEqual({p: self.observed(p) for p in before}, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
