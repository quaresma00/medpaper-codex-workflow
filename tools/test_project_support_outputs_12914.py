"""Exact local support declarations preserve shared workflow and owner gates."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from wfcore import registry
from wfcore.checks.fsx import no_orphans,no_future_artifacts


class ProjectSupportTests(unittest.TestCase):
    def row(self,**changes):
        return {"file":"01_protocol/custom_support_record.json","owning_stage":"S07_artifacts",
                "purpose":"Study-owned source definition record generated from its actual source codebook.",**changes}

    def test_local_file_is_declared_without_polluting_global_defaults(self):
        baseline=registry.load();path=self.row()["file"]
        current=registry.load({"support_outputs":[self.row()]})
        self.assertIn(path,current.stage("S07_artifacts").outputs)
        self.assertNotIn(path,baseline.all_declared_outputs())
        self.assertNotIn(path,registry.load().all_declared_outputs())
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);file=project/path;file.parent.mkdir();file.write_text('{}')
            ctx=SimpleNamespace(project=project,pipeline=current,spec={})
            self.assertTrue(no_orphans(ctx).ok)
            ctx.pipeline=baseline;self.assertFalse(no_orphans(ctx).ok)

    def test_exact_paths_and_meaningful_owners_are_required(self):
        for value in ('../escape.json','01_protocol/*.json','C:/private.json','01_protocol/../escape.json','01_protocol\\case.json','.wf/state.json','01_protocol//case.json'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                registry.load({"support_outputs":[self.row(file=value)]})
        for row in (self.row(owning_stage='missing'),self.row(purpose='OK')):
            with self.assertRaises(ValueError):registry.load({"support_outputs":[row]})

    def test_existing_owners_cannot_be_reassigned_or_duplicated(self):
        for rows in ([self.row(),self.row()], [self.row(file='07_manuscript/full_manuscript.md')]):
            with self.assertRaises(ValueError):registry.load({"support_outputs":rows})

    def test_declared_future_output_still_obeys_owner_stage(self):
        pipeline=registry.load({"support_outputs":[self.row()]})
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);file=project/self.row()["file"];file.parent.mkdir();file.write_text('{}')
            state=SimpleNamespace(is_done=lambda _:False,stage_info=lambda _: {})
            ctx=SimpleNamespace(pipeline=pipeline,stage=pipeline.stages[0],state=state,p=lambda p:project/p)
            self.assertFalse(no_future_artifacts(ctx).ok)


if __name__=='__main__':unittest.main(verbosity=2)
