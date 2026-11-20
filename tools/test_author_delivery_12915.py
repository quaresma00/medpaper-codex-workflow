"""Editable author copies, bounded inventory and tracked auxiliary formats."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from openpyxl import Workbook, load_workbook

from wfcore import journalcontext as jc, journalportal as portal, packagefreeze
from wfcore.readiness import atomic_json


MANUSCRIPT = "08_submission/bundle/manuscript.docx"
SUPPLEMENT = "08_submission/bundle/supplement.pdf"


class AuthorDeliveryTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(prefix="medpaper-author-delivery-")
        self.addCleanup(root.cleanup)
        self.project = Path(root.name).resolve()
        target = {"journal": "Synthetic Delivery Journal", "issn": "1234-5678", "article_type": "Research article"}
        self.context = {"context_id": jc.digest(target), "identity": jc.identity(target), "sources": {}, "assets": {}}
        atomic_json(self.project / jc.TARGET, target)
        atomic_json(self.project / jc.CONTEXT, self.context)
        self.manuscript = self.project / MANUSCRIPT
        self.manuscript.parent.mkdir(parents=True)
        document = Document()
        document.add_paragraph("Author review of the observed clinical comparison.")
        document.save(self.manuscript)
        (self.project / SUPPLEMENT).write_bytes(b"%PDF-1.7\nSynthetic controlled supplement identity.\n")
        self.manifest = self.project / packagefreeze.MANIFEST_REL
        atomic_json(self.manifest, {"journal_context_id": self.context["context_id"], "items": [
            {"role": "manuscript", "file": MANUSCRIPT}, {"role": "supplementary", "file": SUPPLEMENT}]})

    def copy(self, mode="editable"):
        result = portal.deliver(self.project, mode)
        return result, self.project / result["directory"]

    def alternate(self, name="supplement.xlsx", count=11):
        path = self.project / "temp" / name
        path.parent.mkdir(exist_ok=True)
        book = Workbook()
        book.active.append(["Outcome", "Patients", "Notes"])
        book.active.append(["Clinical outcome", count, "Complete cases only"])
        book.save(path)
        return path

    def test_open_edit_save_reopen_author_docx_and_protect_original(self):
        ctx = (self.project / jc.CONTEXT).read_bytes()
        original = self.manuscript.read_bytes()
        self.manuscript.chmod(self.manuscript.stat().st_mode & ~stat.S_IWUSR)
        result, directory = self.copy()
        self.assertEqual(result["observed_file_mode"], "writable")
        copy_path = directory / self.manuscript.name
        doc = Document(copy_path)
        doc.add_paragraph("The author entered this comment while reviewing the file.")
        doc.save(copy_path)
        self.assertIn("author entered", Document(copy_path).paragraphs[-1].text)
        self.assertEqual(self.manuscript.read_bytes(), original)
        self.assertEqual((self.project / jc.CONTEXT).read_bytes(), ctx)
        with self.assertRaisesRegex(ValueError, "reconcile"):
            self.copy()
        # If the author change has been reconciled at its managed source,
        # exact agreement allows the existing copy receipt to be refreshed.
        self.manuscript.chmod(self.manuscript.stat().st_mode | stat.S_IWUSR)
        self.manuscript.write_bytes(copy_path.read_bytes())
        revised, same_directory = self.copy()
        self.assertEqual(revised["status"], "current")
        self.assertEqual(same_directory, directory)

    def test_current_mode_reflects_permission_and_lock_changes(self):
        result, directory = self.copy("read-only")
        self.assertEqual(result["observed_file_mode"], "read-only")
        manuscript = directory / self.manuscript.name
        manuscript.chmod(manuscript.stat().st_mode | stat.S_IWUSR)
        (directory / "~$nuscript.docx").write_bytes(b"synthetic lock file")
        result = portal.delivery_status(self.project)
        self.assertEqual(result["status"], "current")
        self.assertEqual(result["requested_file_mode"], "read-only")
        self.assertEqual(result["observed_file_mode"], "mixed")
        self.assertEqual(result["office_lock_count"], 1)
        file = portal.delivery_files(self.project, MANUSCRIPT)["uploads"][0]
        self.assertTrue(file["office_lock_file_present"])
        self.assertFalse(file["office_document_protected"])
        with patch.object(portal, "_sha256", side_effect=AssertionError("handoff must remain cheap")):
            self.assertEqual(portal.delivery_status(self.project, verify_files=False)["status"], "identity_not_checked")

    def test_actual_word_protection_is_separate_from_write_flag(self):
        doc = Document(self.manuscript)
        lock = OxmlElement("w:documentProtection")
        lock.set(qn("w:edit"), "readOnly")
        lock.set(qn("w:enforcement"), "1")
        doc.settings.element.append(lock)
        doc.save(self.manuscript)
        self.copy()
        row = portal.delivery_files(self.project, MANUSCRIPT)["uploads"][0]
        self.assertEqual(row["file_mode"], "writable")
        self.assertTrue(row["office_document_protected"])

    def test_auxiliary_tracks_role_without_touching_upload_manifest_context_or_freeze(self):
        _, directory = self.copy()
        frozen = packagefreeze.write_freeze(self.project)
        before = {p: p.read_bytes() for p in (self.manifest, self.project / jc.CONTEXT, frozen)}
        book = self.alternate()
        extra = book.with_suffix(".xlsx.inspect.ndjson")
        extra.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SDK reports"):
            portal.attach_format(self.project, SUPPLEMENT, extra)
        result = portal.attach_format(self.project, SUPPLEMENT, book)
        self.assertEqual(result["role"], "auxiliary_format")
        self.assertEqual(result["status"], "current")
        self.assertEqual({p.name for p in directory.iterdir()}, {"manuscript.docx", "supplement.pdf", book.name})
        workbook = load_workbook(self.project / result["file"])
        try:
            self.assertEqual(workbook.active["B2"].value, 11)
            workbook.active["B2"] = 12
            workbook.save(self.project / result["file"])
        finally:
            workbook.close()
        self.assertEqual(portal.delivery_status(self.project)["status"], "changed_or_missing")
        with self.assertRaisesRegex(ValueError, "Existing author file differs"):
            portal.attach_format(self.project, SUPPLEMENT, book)
        self.assertTrue(packagefreeze.verify_freeze(self.project)[0])
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        release = self.project / json.loads(frozen.read_text())["release_dir"]
        self.assertFalse((release / book.name).exists())
        self.assertFalse((release / "manuscript.docx").stat().st_mode & stat.S_IWUSR)

    def test_attach_accepts_identical_existing_copy_and_stays_current(self):
        _, directory = self.copy()
        book = self.alternate()
        shutil.copyfile(book, directory / book.name)
        self.assertEqual(portal.delivery_status(self.project)["status"], "changed_or_missing")
        portal.attach_format(self.project, SUPPLEMENT, directory / book.name)
        status = portal.delivery_status(self.project)
        self.assertEqual(status["status"], "current")
        self.assertEqual(set(status["auxiliary"]), {book.name})
        self.assertEqual(portal.delivery_files(self.project, SUPPLEMENT)["uploads"][0]["auxiliary"][0]["office_protected_worksheets"], 0)
        _, idempotent_directory = self.copy()
        self.assertEqual(idempotent_directory, directory)

    def test_old_alternate_stays_with_its_exact_source_version(self):
        _, directory = self.copy()
        book = self.alternate()
        portal.attach_format(self.project, SUPPLEMENT, book)
        (self.project / SUPPLEMENT).write_bytes(b"%PDF-1.7\nNew controlled supplement bytes\n")
        self.assertEqual(portal.delivery_status(self.project)["status"], "managed_uploads_changed")
        with self.assertRaisesRegex(ValueError, "Linked upload or manifest changed"):
            portal.attach_format(self.project, SUPPLEMENT, book)
        revised, next_directory = self.copy()
        self.assertEqual(revised["auxiliary"], {})
        self.assertTrue((directory / book.name).is_file())
        self.assertFalse((next_directory / book.name).exists())

    def test_legacy_read_only_record_can_be_read_and_get_separate_editable_copy(self):
        old, directory = self.copy("read-only")
        record = portal._delivery_record_path(self.project, self.context)
        legacy = json.loads(record.read_text(encoding="utf-8"))
        for key in ("mode", "auxiliary", "schema_version"):
            legacy.pop(key)
        atomic_json(self.project / jc.CONTEXT, {**self.context, "delivery": legacy})
        record.unlink()
        self.assertEqual(portal.delivery_status(self.project)["directory"], old["directory"])
        current, new_directory = self.copy()
        self.assertNotEqual(directory, new_directory)
        self.assertEqual(current["observed_file_mode"], "writable")
        self.assertFalse((directory / "manuscript.docx").stat().st_mode & stat.S_IWUSR)


if __name__ == "__main__":
    unittest.main(verbosity=2)
