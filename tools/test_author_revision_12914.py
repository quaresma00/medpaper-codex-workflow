"""Synthetic author-Word inspection and guarded layout import, no research project."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.enum.section import WD_ORIENT

from wfcore import authorrevision as a, buildproof
from wfcore.packagefreeze import _sha256
from wfcore.state import State


class AuthorRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="medpaper-author-word-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.managed = self.project / "08_submission/bundle/manuscript.docx"
        self.managed.parent.mkdir(parents=True)
        self.author = self.project / "author-renamed.docx"
        self.source = self.project / "08_submission/integration/full_manuscript.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("Synthetic source, no actual patients. Outcome rate 12%. [1]", encoding="utf-8")
        doc = Document(); doc.add_paragraph("Synthetic cohort results. The event rate was 12% [1].")
        doc.add_paragraph("The observed association was not causal.")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Population"; table.cell(0, 1).text = "Reports, n"
        table.cell(1, 0).text = "Eligible reports"; table.cell(1, 1).text = "12"
        doc.save(self.managed); shutil.copy2(self.managed, self.author)
        self.state = State(self.project).create("medpaper", "1.23.0", "S24_package_human_review")
        (self.project / "08_submission/bundle/manifest.json").write_text(json.dumps({"items": [
            {"file": self.rel, "role": "manuscript", "source": self.source.relative_to(self.project).as_posix()}]}), encoding="utf-8")
        buildproof.record(self.project, self.managed, [self.source], entrypoints=[self.source], tool="tools/manuscript/build_docx.py")

    @property
    def rel(self): return self.managed.relative_to(self.project).as_posix()

    def batch(self, *, allowed=None, status="active"):
        self.state.data["active_revision_round"] = "R001"; self.state.save()
        folder = self.project / ".wf/revisions"; folder.mkdir(exist_ok=True)
        (folder / "R001.json").write_text(json.dumps({"round_id": "R001", "schema_version": 2,
            "review_stage": "S24_package_human_review", "status": status,
            "allowed_files": [self.rel] if allowed is None else allowed}), encoding="utf-8")

    def landscape(self):
        doc = Document(self.author)
        section = doc.sections[0]; section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width
        doc.save(self.author)

    def adopt(self, report=None):
        report = report or a.compare(self.managed, self.author)
        return a.adopt_layout(self.project, self.managed, self.author,
                             managed_sha256=report["managed_sha256"], author_sha256=report["author_sha256"])

    def edit_xml(self, part, transform):
        with ZipFile(self.author) as z: parts = [(n, z.read(n)) for n in z.namelist()]
        with ZipFile(self.author, "w", ZIP_DEFLATED) as z:
            for name, content in parts: z.writestr(name, transform(content) if name == part else content)

    def test_inspect_is_read_only_handles_renamed_author_and_shows_section_layout(self):
        self.landscape()
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.managed, self.author, self.source)}
        report = a.compare(self.managed, self.author)
        self.assertEqual(report["classification"], "LAYOUT_CANDIDATE")
        self.assertTrue(report["section_properties"])
        self.assertFalse(report["numbers_changed"])
        for p, (content, stamp) in before.items():
            self.assertEqual(p.read_bytes(), content); self.assertEqual(p.stat().st_mtime_ns, stamp)

    def test_number_citation_and_negation_changes_require_real_source_reconciliation(self):
        doc = Document(self.author)
        doc.paragraphs[0].text = "Synthetic cohort results. The event rate was 21% [2]."
        doc.paragraphs[1].text = "The observed association was causal."
        doc.save(self.author)
        report = a.compare(self.managed, self.author)
        self.assertEqual(report["classification"], "SOURCE_RECONCILIATION_REQUIRED")
        self.assertTrue(report["numbers_changed"])
        self.assertTrue(report["citations_or_identifiers_changed"])
        self.assertTrue(report["clinical_qualifiers_changed"])
        self.assertIn("21%", report["shown_changes"][0]["after"])
        self.batch(); before = self.managed.read_bytes()
        with self.assertRaisesRegex(ValueError, "reconcile"):
            self.adopt(report)
        self.assertEqual(self.managed.read_bytes(), before)

    def test_same_words_in_different_order_are_not_automatic_layout(self):
        doc = Document(self.author)
        x, y = doc.paragraphs[:2]; left, right = x.text, y.text
        x.text, y.text = right, left; doc.save(self.author)
        report = a.compare(self.managed, self.author)
        self.assertEqual(report["classification"], "SOURCE_RECONCILIATION_REQUIRED")
        self.assertFalse(report["numbers_changed"])

    def test_table_cell_change_is_located_and_never_treated_as_formatting(self):
        doc = Document(self.author); doc.tables[0].cell(1, 1).text = "17"; doc.save(self.author)
        report = a.compare(self.managed, self.author, max_changes=20)
        self.assertIn("tables", report["changed_categories"])
        self.assertEqual(report["table_changes"][0]["row"], 2)
        self.assertEqual(report["table_changes"][0]["cell"], 2)
        self.assertIn("17", report["table_changes"][0]["after"])

    def test_hidden_deletion_or_changed_relationships_are_not_layout_exemptions(self):
        def deleted(blob):
            root = ET.fromstring(blob); p = root.find(".//" + a.W + "p")
            change = ET.SubElement(p, a.W + "del"); ET.SubElement(change, a.W + "delText").text = "Clinical qualifier"
            return ET.tostring(root)
        self.edit_xml("word/document.xml", deleted)
        self.assertEqual(a.compare(self.managed, self.author)["classification"], "SOURCE_RECONCILIATION_REQUIRED")
        shutil.copy2(self.managed, self.author)
        self.edit_xml("word/_rels/document.xml.rels", lambda blob: blob.replace(b"styles.xml", b"different-styles.xml"))
        report = a.compare(self.managed, self.author)
        self.assertIn("other_content", report["changed_categories"])

    def test_layout_import_preserves_author_bytes_and_records_real_import_not_review(self):
        self.batch(); self.landscape(); incoming = self.author.read_bytes()
        before_source = self.source.read_bytes(); original_author = self.author.read_bytes()
        marker = self.project / "08_submission/package_content_baseline.json"; marker.write_text("unmodified marker")
        result = self.adopt()
        self.assertEqual(self.managed.read_bytes(), incoming)
        self.assertEqual(self.author.read_bytes(), original_author)
        self.assertEqual(self.source.read_bytes(), before_source)
        self.assertEqual(marker.read_text(), "unmodified marker")
        self.assertEqual(result["status"], "IMPORTED_PENDING_ACTUAL_QA")
        snapshot = self.project / result["author_source"]
        self.assertEqual(snapshot.read_bytes(), incoming)
        receipt = buildproof.load(self.project)[self.rel]
        self.assertEqual(receipt["tool"], "tools/manuscript/author_revision.py")
        self.assertEqual(receipt["parameters"]["operation"], "author-layout-import")
        self.assertTrue(buildproof.inputs_current(receipt))
        self.author.unlink()  # Moving/renaming the author's working file does not lose preserved provenance.
        self.assertTrue(buildproof.inputs_current(receipt))

    def test_no_open_or_unsealed_or_out_of_scope_round_cannot_write(self):
        self.landscape(); before = self.managed.read_bytes()
        for status, allowed in ((None, None), ("collecting", None), ("active", [])):
            if status: self.batch(status=status, allowed=allowed)
            with self.assertRaises(ValueError): self.adopt()
            self.assertEqual(self.managed.read_bytes(), before)

    def test_stale_hash_and_changed_real_source_fail_before_import(self):
        self.batch(); self.landscape(); report = a.compare(self.managed, self.author)
        with self.assertRaisesRegex(ValueError, "since inspection"):
            a.adopt_layout(self.project, self.managed, self.author, managed_sha256="0" * 64, author_sha256=report["author_sha256"])
        before = self.managed.read_bytes(); self.source.write_text("Changed actual source")
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.adopt(report)
        self.assertEqual(self.managed.read_bytes(), before)

    def test_import_failure_rolls_back_only_its_actual_writes(self):
        self.batch(); self.landscape()
        files = [self.managed, self.project / buildproof.RECEIPTS, self.project / ".wf/revisions/R001.json"]
        before = {p: p.read_bytes() for p in files}
        with patch.object(a.revision, "record_build", side_effect=OSError("Synthetic receipt failure")):
            with self.assertRaisesRegex(OSError, "Synthetic"):
                self.adopt()
        self.assertEqual({p: p.read_bytes() for p in files}, before)
        self.assertFalse(list((self.project / ".wf/author_imports").glob("*.docx")))

    def test_bounded_cli_inspection_does_not_create_a_report_by_default(self):
        doc = Document(self.author)
        for i in range(12): doc.add_paragraph(f"Additional synthetic paragraph {i}.")
        doc.save(self.author)
        report = a.compare(self.managed, self.author, max_changes=1)
        self.assertLessEqual(len(report["shown_changes"]), 1)
        script = Path(__file__).resolve().parent / "manuscript/author_revision.py"
        proc = subprocess.run([sys.executable, str(script), "inspect", "--project", str(self.project),
                               "--managed", self.rel, "--author", self.author.name, "--max-changes", "1"],
                              capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("SOURCE_RECONCILIATION_REQUIRED", proc.stdout)
        self.assertFalse((self.project / ".wf/author_imports").exists())


    def test_pagination_cache_changes_share_the_builder_semantics(self):
        original=self.managed.read_bytes()
        fields=[b'<w:fldSimple w:instr="PAGE"><w:r><w:t>1</w:t></w:r></w:fldSimple>',
                b'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>']
        for field in fields:
            with self.subTest(field=field[:20]):
                self.author.write_bytes(original)
                self.edit_xml('word/document.xml',lambda raw:raw.replace(b'</w:body>',b'<w:p>'+field+b'</w:p></w:body>'))
                shutil.copy2(self.author,self.managed)
                self.edit_xml('word/document.xml',lambda raw:raw.replace(b'<w:t>1</w:t>',b'<w:t>9</w:t>'))
                report=a.compare(self.managed,self.author)
                self.assertEqual(report['classification'],'LAYOUT_CANDIDATE')
                self.assertFalse(report['numbers_changed'])
                self.assertEqual(buildproof.content_digest(self.managed),buildproof.content_digest(self.author))
        self.managed.write_bytes(original)

    def test_non_pagination_field_values_and_table_merges_are_not_layout(self):
        field=b'<w:p><w:fldSimple w:instr="SEQ Table"><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p>'
        self.edit_xml('word/document.xml',lambda raw:raw.replace(b'</w:body>',field+b'</w:body>'))
        shutil.copy2(self.author,self.managed)
        self.edit_xml('word/document.xml',lambda raw:raw.replace(b'<w:t>1</w:t>',b'<w:t>2</w:t>'))
        self.assertEqual(a.compare(self.managed,self.author)['classification'],'SOURCE_RECONCILIATION_REQUIRED')
        shutil.copy2(self.managed,self.author)
        doc=Document(self.author);doc.tables[0].cell(1,0).merge(doc.tables[0].cell(1,1));doc.save(self.author)
        self.assertEqual(a.compare(self.managed,self.author)['classification'],'SOURCE_RECONCILIATION_REQUIRED')

    def test_media_change_and_wrong_current_checkpoint_are_rejected(self):
        with ZipFile(self.author,'a') as archive: archive.writestr('word/media/synthetic.bin',b'Synthetic changed image')
        self.assertIn('media',a.compare(self.managed,self.author)['changed_categories'])
        self.batch();self.state.data['current']='S19_human_review';self.state.save()
        with self.assertRaisesRegex(ValueError,'S24'):self.adopt()

    def test_concurrent_source_change_cannot_be_rebound_as_an_author_layout_build(self):
        self.landscape();self.batch();before=self.managed.read_bytes()
        replace=a.os.replace
        def edit_source_then_replace(src,dst):
            result=replace(src,dst)
            if Path(dst)==self.managed:self.source.write_text('New author content while import was running.',encoding='utf-8')
            return result
        with patch.object(a.os,'replace',side_effect=edit_source_then_replace):
            with self.assertRaisesRegex(ValueError,'source inputs changed'):self.adopt()
        self.assertEqual(self.managed.read_bytes(),before)
        self.assertEqual(self.source.read_text(),'New author content while import was running.')


if __name__ == "__main__": unittest.main(verbosity=2)
