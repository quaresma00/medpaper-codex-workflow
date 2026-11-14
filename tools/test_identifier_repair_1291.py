"""Synthetic-only managed repair of identifiers poisoned by cited-paper metadata."""
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

from pubmed import build_library as builder, eutils as eu
from wfcore import refproof


def article(pmid="123", **changes):
    row = {"title": "Synthetic clinical reference", "journal": "Synthetic Medical Journal",
           "year": "2026", "author": "Fixture", "abstract": "Actual synthetic source findings.",
           "doi": "10.1000/main" + pmid, "pmcid": "PMC" + pmid,
           "publication_type": "Journal Article"}
    row.update(changes)
    row = {k: escape(str(v)) for k, v in row.items()}
    identifiers = ((f'<ArticleId IdType="doi">{row["doi"]}</ArticleId>' if row["doi"] else "") +
                   (f'<ArticleId IdType="pmc">{row["pmcid"]}</ArticleId>' if row["pmcid"] else ""))
    return f'''<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>
<ArticleTitle>{row["title"]}</ArticleTitle><Abstract><AbstractText>{row["abstract"]}</AbstractText></Abstract>
<Journal><Title>{row["journal"]}</Title><ISOAbbreviation>Synth Med J</ISOAbbreviation>
<JournalIssue><Volume>3</Volume><Issue>2</Issue><PubDate><Year>{row["year"]}</Year></PubDate></JournalIssue></Journal>
<Pagination><MedlinePgn>10-15</MedlinePgn></Pagination>
<AuthorList><Author><LastName>{row["author"]}</LastName><ForeName>Alice</ForeName><Initials>A</Initials></Author></AuthorList>
<PublicationTypeList><PublicationType>{row["publication_type"]}</PublicationType></PublicationTypeList>
</Article></MedlineCitation><PubmedData><ArticleIdList>{identifiers}</ArticleIdList>
<ReferenceList><Reference><Citation>Unrelated cited paper</Citation><ArticleIdList>
<ArticleId IdType="doi">10.1000/poison</ArticleId><ArticleId IdType="pmc">PMC999</ArticleId>
</ArticleIdList></Reference></ReferenceList></PubmedData></PubmedArticle>'''


class IdentifierRepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="medpaper-identifier-repair-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(eu, "project_root", return_value=self.project).start()
        self.refs = eu.refs_dir()
        self.library = {"entries": [], "queries": [{"query": "original coverage", "hits": 2}]}
        builder.add_records(self.library, eu.parse_pubmed_xml(self.xml(["123", "456"])))
        self.library["entries"][0].update(citekey="original123", doi="10.1000/poison", pmcid="PMC999",
                                           uncited_reason="Kept as authentic background evidence, not cited yet.",
                                           user_note={"keep": "author decision"})
        self.library["entries"][1]["citekey"] = "unrelated456"
        self.write("library.json", json.dumps(self.library, ensure_ascii=False))
        self.write("refs.bib", builder.to_bibtex(self.library["entries"]))
        self.write("refs.ris", builder.to_ris(self.library["entries"]))
        self.write("verified.json", '{"verified": true, "old_receipt": "must be invalidated"}')
        self.write("usage.json", '{"uncited_reasons":{"original123":"Preserve the author rationale."}}')

    @staticmethod
    def xml(ids, changes=None):
        changes = changes or {}
        return "<PubmedArticleSet>" + "".join(article(p, **changes.get(p, {})) for p in ids) + "</PubmedArticleSet>"

    def write(self, name, text):
        path = self.refs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def outputs(self):
        return {name: (self.refs / name).read_bytes() if (self.refs / name).exists() else None
                for name in ("library.json", "refs.bib", "refs.ris", "verified.json", "usage.json")}

    def fresh(self, ids=("123",), changes=None):
        raw = self.xml(ids, changes)
        cache = self.write("cache/identifier_refresh_fixture.xml", raw)
        records = eu.parse_pubmed_xml(raw, cache_file="06_refs/cache/identifier_refresh_fixture.xml")
        for rec in records:
            rec.update(fresh_fetch=True, cache_sha256=refproof.file_sha256(cache))
        return records

    def refresh(self, records=None, ids=("123",)):
        with patch.object(eu, "efetch", return_value=records if records is not None else self.fresh()) as fetched:
            result = builder.refresh_identifiers(self.library, list(ids))
            fetched.assert_called_once_with(list(ids), fresh=True, purpose="identifier_refresh")
            return result

    def revision(self, *, kind="references", allowed=None, status="active"):
        folder = self.project / ".wf/revisions"
        folder.mkdir(parents=True, exist_ok=True)
        (folder.parent / "state.json").write_text('{"active_revision_round":"R001"}', encoding="utf-8")
        payload = {"schema_version": 2, "status": status, "validation_stages": ["S13_reflib"],
                   "items": [{"kind": kind, "owning_stage": "S13_reflib"}],
                   "allowed_files": allowed if allowed is not None else
                   ["06_refs/" + name for name in ("library.json", "refs.bib", "refs.ris", "verified.json")]}
        (folder / "R001.json").write_text(json.dumps(payload), encoding="utf-8")

    def freeze(self):
        frozen = self.project / "07_manuscript/scientific_master_freeze.json"
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_text('{"frozen_scientific_version":"must not be rewritten"}', encoding="utf-8")
        return frozen

    def test_cli_fresh_fetch_preserves_keys_notes_and_unrelated_entries_and_reexports(self):
        before = copy.deepcopy(self.library)
        usage = (self.refs / "usage.json").read_bytes()
        with patch.object(eu, "http_get", return_value=self.xml(["123"]).encode("utf-8")) as http:
            with patch("sys.argv", ["build_library.py", "--refresh-identifiers", "123"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(builder.main(), 0)
        self.assertEqual(http.call_count, 1)
        self.assertEqual(http.call_args.args[1]["id"], "123")
        library = builder.load_library()
        repaired = library["entries"][0]
        self.assertEqual(repaired["doi"], "10.1000/main123")
        self.assertEqual(repaired["pmcid"], "PMC123")
        self.assertTrue(repaired["cache_file"].startswith("06_refs/cache/identifier_refresh_efetch_pubmed_"))
        self.assertTrue((self.project / repaired["cache_file"]).is_file())
        for field, value in before["entries"][0].items():
            if field not in {"doi", "pmcid", "cache_file", "retrieved_at"}:
                self.assertEqual(repaired[field], value, field)
        self.assertEqual(library["entries"][1], before["entries"][1])
        self.assertEqual(library["queries"], before["queries"])
        self.assertEqual((self.refs / "usage.json").read_bytes(), usage)
        self.assertIn("doi = {10.1000/main123}", (self.refs / "refs.bib").read_text())
        self.assertIn("DO  - 10.1000/main123", (self.refs / "refs.ris").read_text())
        self.assertNotIn("10.1000/poison", (self.refs / "refs.bib").read_text())
        self.assertFalse((self.refs / "verified.json").exists())
        self.assertFalse(refproof.validate_local_proof(self.project)[0])

    def test_missing_own_identifiers_clear_contamination_instead_of_borrowing_reference_ids(self):
        self.refresh(self.fresh(changes={"123": {"doi": "", "pmcid": ""}}))
        row = builder.load_library()["entries"][0]
        self.assertEqual((row["doi"], row["pmcid"]), ("", ""))
        self.assertNotIn("10.1000/poison", (self.refs / "refs.ris").read_text())

    def test_refresh_does_not_mutate_callers_library(self):
        before = copy.deepcopy(self.library)
        self.refresh()
        self.assertEqual(self.library, before)

    def test_non_identifier_metadata_or_retraction_changes_abort_before_any_output_write(self):
        before = self.outputs()
        changes = [{"title": "A different clinical question"}, {"journal": "Another Clinical Journal"},
                   {"year": "2025"}, {"author": "SomeoneElse"}, {"abstract": "No actual synthetic source findings."},
                   {"publication_type": "Retracted Publication"}, {"publication_type": "Clinical Trial"}]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.refresh(self.fresh(changes={"123": change}))
                self.assertEqual(self.outputs(), before)

    def test_title_difference_below_verifiers_fuzzy_threshold_still_is_not_identifier_only(self):
        records = self.fresh(changes={"123": {"title": "Synthetic clinical references"}})
        self.assertGreaterEqual(refproof.ratio(self.library["entries"][0]["title"], records[0]["title"]),
                                refproof.TITLE_THRESHOLD)
        before = self.outputs()
        with self.assertRaisesRegex(ValueError, "title changed"):
            self.refresh(records)
        self.assertEqual(self.outputs(), before)

    def test_wrong_or_missing_or_duplicate_returned_pmids_abort(self):
        before = self.outputs()
        for records in (self.fresh(ids=["789"]), [], self.fresh() * 2):
            with self.subTest(pmids=[r["pmid"] for r in records]):
                with self.assertRaises(ValueError):
                    self.refresh(records)
                self.assertEqual(self.outputs(), before)

    def test_unknown_requested_pmid_is_rejected_before_network(self):
        before = self.outputs()
        with patch.object(eu, "efetch") as fetched:
            with self.assertRaisesRegex(ValueError, "existing library entry"):
                builder.refresh_identifiers(self.library, ["789"])
        fetched.assert_not_called()
        self.assertEqual(self.outputs(), before)

    def test_batch_failure_keeps_first_valid_entry_and_every_output_unchanged(self):
        before = self.outputs()
        records = self.fresh(["123", "456"], {"456": {"abstract": "Changed source science."}})
        with self.assertRaisesRegex(ValueError, "abstract"):
            self.refresh(records, ids=["123", "456"])
        self.assertEqual(self.outputs(), before)

    def test_network_failure_preserves_library_exports_and_existing_proof(self):
        before = self.outputs()
        with patch.object(eu, "efetch", side_effect=RuntimeError("Synthetic request failure")):
            with self.assertRaisesRegex(RuntimeError, "Synthetic request failure"):
                builder.refresh_identifiers(self.library, ["123"])
        self.assertEqual(self.outputs(), before)

    def test_nonfresh_or_changed_cached_payload_is_rejected(self):
        before = self.outputs()
        records = self.fresh()
        records[0]["fresh_fetch"] = False
        with self.assertRaisesRegex(ValueError, "fresh preserved"):
            self.refresh(records)
        records = self.fresh()
        (self.project / records[0]["cache_file"]).write_text("<changed/>", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fresh preserved"):
            self.refresh(records)
        self.assertEqual(self.outputs(), before)

    def test_fetched_metadata_must_match_preserved_xml(self):
        before = self.outputs()
        records = self.fresh()
        records[0]["pmcid"] = "PMC777"
        with self.assertRaisesRegex(ValueError, "preserved PubMed XML"):
            self.refresh(records)
        self.assertEqual(self.outputs(), before)

    def test_export_commit_failure_rolls_back_and_preserves_existing_proof(self):
        before = self.outputs()
        replace = os.replace
        attempts = 0

        def fail_second(src, dst):
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                raise OSError("Synthetic export failure")
            return replace(src, dst)

        records = self.fresh()
        with patch.object(builder.os, "replace", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "Synthetic export failure"):
                self.refresh(records)
        self.assertEqual(self.outputs(), before)
        self.assertFalse(list(self.refs.glob(".identifier_refresh_*")))

    def test_revision_guard_covers_every_actual_export_and_proof_invalidation(self):
        before = self.outputs()
        self.revision(allowed=["06_refs/library.json", "06_refs/refs.bib", "06_refs/refs.ris"])
        with patch.object(eu, "efetch") as fetched:
            with self.assertRaisesRegex(ValueError, "out-of-scope.*verified.json"):
                builder.refresh_identifiers(self.library, ["123"])
        fetched.assert_not_called()
        self.assertEqual(self.outputs(), before)

    def test_frozen_master_requires_active_scoped_references_revision(self):
        frozen = self.freeze()
        old = frozen.read_bytes()
        before = self.outputs()
        with patch.object(eu, "efetch") as fetched:
            with self.assertRaisesRegex(ValueError, "Scientific master is frozen"):
                builder.refresh_identifiers(self.library, ["123"])
            self.revision(kind="methods")
            with self.assertRaisesRegex(ValueError, "Scientific master is frozen"):
                builder.refresh_identifiers(self.library, ["123"])
        fetched.assert_not_called()
        self.assertEqual(self.outputs(), before)
        self.assertEqual(frozen.read_bytes(), old)

    def test_scoped_reference_repair_never_overwrites_scientific_freeze(self):
        frozen = self.freeze()
        old = frozen.read_bytes()
        self.revision()
        self.assertEqual(self.refresh(), 1)
        self.assertEqual(frozen.read_bytes(), old)
        self.assertFalse((self.refs / "verified.json").exists())

    def test_edit_during_network_request_is_preserved_instead_of_silently_overwritten(self):
        before = self.outputs()
        records = self.fresh()
        author_edit = dict(self.library, author_note="Changed while request was running")

        def edited(*args, **kwargs):
            self.write("library.json", json.dumps(author_edit))
            return records

        with patch.object(eu, "efetch", side_effect=edited):
            with self.assertRaisesRegex(ValueError, "outputs changed during refresh"):
                builder.refresh_identifiers(self.library, ["123"])
        self.assertEqual(builder.load_library(), author_edit)
        for name, value in before.items():
            if name != "library.json":
                self.assertEqual(self.outputs()[name], value)

    def test_normal_duplicate_acquisition_still_keeps_existing_identifiers_and_keys(self):
        before = copy.deepcopy(self.library)
        self.assertEqual(builder.add_records(self.library, self.fresh()), (0, 0, 1))
        self.assertEqual(self.library, before)

    def test_cli_refuses_mixing_repair_with_add_or_export(self):
        before = self.outputs()
        for option in (["--add-ids", "456"], ["--export"]):
            with self.subTest(option=option):
                with patch.object(eu, "efetch") as fetched:
                    with patch("sys.argv", ["build_library.py", "--refresh-identifiers", "123", *option]):
                        with contextlib.redirect_stderr(io.StringIO()):
                            with self.assertRaises(SystemExit) as raised:
                                builder.main()
                self.assertEqual(raised.exception.code, 2)
                fetched.assert_not_called()
                self.assertEqual(self.outputs(), before)


if __name__ == "__main__":
    unittest.main()
