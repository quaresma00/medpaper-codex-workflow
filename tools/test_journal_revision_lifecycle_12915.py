"""Real synthetic transfer metadata, revision scope and archive lifecycle."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import rework
from wfcore import journalcontext as jc, registry, revision
from wfcore.checks.revisions import revision_rounds_closed
from wfcore.readiness import atomic_json
from wfcore.state import State


class JournalRevisionLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="medpaper-journal-closures-")
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        self.state = State(self.project).create("medpaper", "1.29.14", "S24_package_human_review")
        self.pipe = registry.load()
        self.kinds = sorted([*rework.ROUTES, "manuscript-copyedit", "word-format-only"])
        self.science = "07_manuscript/full_manuscript.md"
        self.text(self.science, "Synthetic approved scientific material.")
        self.text("08_submission/user_notes.md", "Unrelated private working notes.")
        patcher = patch("wfcore.scientificfreeze.verify", return_value=(True, [], {"freeze_id": "synthetic-fixture"}))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.initial = self.begin("A")

    def text(self, rel, text):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def begin(self, code, item=None):
        return jc.begin(self.project, {"journal": f"Synthetic journal {code}", "issn": "1234-5678",
            "article_type": "Original article", "guidelines_url": f"https://{code.lower()}.example.org/authors"},
            revision_item=item)

    def batch(self, serial, kind, sources, *, sealed=True):
        plan = self.project / "temp/plan.json"
        request = f"Apply the synthetic revision request {serial} to its actual owner."
        atomic_json(plan, {"feedback_verbatim": request,
            "interpretation": "Run a focused journal and revision lifecycle synthetic regression.",
            "items": [{"kind": kind, "request": request, "affected_sources": sources,
                       "acceptance_criteria": ["Check the applicable actual artifact"]}]})
        with contextlib.redirect_stdout(io.StringIO()):
            rework._cmd_batch(SimpleNamespace(plan=plan, sealed=sealed, why=request,
                confirm_scientific_route=False), self.project, self.pipe, self.state.load(), self.kinds)
        return self.record()["items"][-1]["id"]

    def record(self):
        return rework._load_round(self.state.load())[1]

    def settle(self, item, successor, archive=None):
        with contextlib.redirect_stdout(io.StringIO()):
            rework._cmd_supersede_journal(SimpleNamespace(item=item, successor=successor, archive=archive,
                why="The author selected a different journal and redirected the obsolete packaging request."),
                self.project, self.pipe, self.state.load())

    def test_consecutive_a_b_c_switches_do_not_mix_active_obligations_or_fingerprints(self):
        letter = "08_submission/cover_letter.md"
        self.text(letter, "Only journal A.")
        first = self.batch("letter A", "cover-letter-or-package-structure", [letter])
        second = self.batch("to B", "journal-switch", [jc.TARGET])
        b = self.begin("B")
        self.assertIn(first, revision.scope_problems(self.project, self.record())[-1])
        self.settle(first, second)
        b_attachment = "08_submission/bundle/legacy-format.pdf"
        attachment = self.batch("attachment B", "cover-letter-or-package-structure", [b_attachment])
        self.text(b_attachment, "Only journal B.")
        third = self.batch("to C", "journal-switch", [jc.TARGET])
        c = self.begin("C")
        self.settle(second, third)
        self.settle(attachment, third)
        last = self.batch("cover letter C", "cover-letter-or-package-structure", [letter])
        self.text(letter, "Only journal C.")
        record = self.record()
        self.assertEqual([row["id"] for row in record["items"]], [third, last])
        self.assertTrue(all(row["journal_context_id"] == c["context_id"] for row in record["items"]))
        self.assertEqual(len(record["retired_journal_items"]), 3)
        self.assertTrue(all(row["item"]["status"] == "pending" and row["disposition"] == "superseded"
                            for row in record["retired_journal_items"]))
        self.assertEqual(len({first, second, attachment, third, last}), 5)
        self.assertEqual((self.project / b["previous_archive"] / "cover_letter.md").read_text(), "Only journal A.")
        old_attachment = self.project / c["previous_archive"] / "bundle/legacy-format.pdf"
        self.assertEqual(old_attachment.read_text(), "Only journal B.")
        self.assertNotIn(b_attachment, record["rebuild_files"])
        self.assertEqual(revision.scope_problems(self.project, record), [])
        self.assertEqual((self.project / self.science).read_text(), "Synthetic approved scientific material.")
        old_attachment.write_text("Unexpected edit in archived attachment.")
        self.assertTrue(any("journal archive missing or changed" in detail
                            for detail in revision.scope_problems(self.project, record)))
        old_attachment.unlink()
        self.assertTrue(any("journal archive missing or changed" in detail
                            for detail in revision.scope_problems(self.project, record)))

    def test_shared_author_source_and_scientific_item_cannot_be_superseded(self):
        owner = self.batch("shared author info", "title-page-or-statements", ["00_input/author_info.json"])
        switch = self.batch("to B", "journal-switch", [jc.TARGET])
        self.begin("B")
        with self.assertRaisesRegex(ValueError, "scientific and shared author-source work"):
            self.settle(owner, switch)
        record = self.record()
        record["items"][0].update(kind="methods", change_type="scientific", affected_sources=[self.science])
        path, _ = rework._load_round(self.state.load())
        atomic_json(path, record)
        with self.assertRaisesRegex(ValueError, "scientific and shared author-source work"):
            self.settle(owner, switch)

    def test_legacy_unbound_item_requires_exact_archived_source_attribution(self):
        letter = "08_submission/cover_letter.md"
        self.text(letter, "Only old journal A.")
        first = self.batch("old unbound item", "cover-letter-or-package-structure", [letter])
        path, record = rework._load_round(self.state.load())
        record["items"][0].pop("journal_context_id")
        atomic_json(path, record)
        switch = self.batch("to B", "journal-switch", [jc.TARGET])
        b = self.begin("B")
        with self.assertRaisesRegex(ValueError, "requires --archive"):
            self.settle(first, switch)
        self.settle(first, switch, b["previous_archive"])
        self.assertEqual(self.record()["retired_journal_items"][0]["journal_context_id"], self.initial["context_id"])

    def test_switch_ambiguity_and_unplanned_science_drift_abort_without_writes(self):
        first = self.batch("switch selection one", "journal-switch", [jc.TARGET])
        self.batch("switch selection two", "journal-switch", [jc.TARGET])
        with self.assertRaisesRegex(ValueError, "--revision-item"):
            self.begin("B")
        self.text(self.science, "Unplanned change in an integrity fixture.")
        with self.assertRaisesRegex(ValueError, "out-of-scope"):
            self.begin("B", first)
        self.assertEqual(jc.current(self.project)["context_id"], self.initial["context_id"])

    def test_switch_failure_restores_round_state_and_archived_author_edit(self):
        letter = self.text("08_submission/cover_letter.md", "Author's actual old letter.")
        switch = self.batch("will roll back", "journal-switch", [jc.TARGET])
        round_path, _ = rework._load_round(self.state.load())
        previous = {file: file.read_bytes() for file in (letter, round_path, self.state.file, self.project / jc.CONTEXT)}
        with patch.object(State, "save", side_effect=OSError("Synthetic state-save failure")):
            with self.assertRaises(OSError):
                self.begin("B", switch)
        self.assertEqual({file: file.read_bytes() for file in previous}, previous)

    def test_closed_revision_checks_the_actual_archived_receipt(self):
        from wfcore.determinism import receipt
        letter = "08_submission/cover_letter.md"
        file = self.text(letter, "Previously checked old journal letter.")
        proof = receipt(file, letter)
        atomic_json(self.state.dir / "revisions/R001.json", {"schema_version": 2, "status": "complete",
            "closed_journal_context_id": self.initial["context_id"],
            "validation": {"ok": True, "input_signature": "synthetic", "results": [{"ok": True}]},
            "items": [{"id": "R001-01", "status": "done", "changed_files": [proof], "validated_by": ["fixture"]}]})
        b = self.begin("B")
        self.text(letter, "New current journal B letter.")
        ctx = SimpleNamespace(state=self.state.load(), project=self.project)
        self.assertTrue(revision_rounds_closed(ctx).ok, revision_rounds_closed(ctx).detail)
        (self.project / b["previous_archive"] / "cover_letter.md").write_text("Archive drift.")
        self.assertFalse(revision_rounds_closed(ctx).ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
