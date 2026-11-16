"""S20 presentation planning must coexist with the pristine scientific-copy gate."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from wfcore.checks.projectquality import journal_display_fit

REASON='Retain all approved main and supplementary displays because each answers a distinct clinical reader question; only their journal placement changes.'

class JournalReasonTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name)
        self.plan={'main_figures':[{}, {}, {}],'main_tables':[{}, {}, {}, {}],'supp_figures':[{}],'supp_tables':[{}]}
        self.target={'journal_adaptation_reason':REASON}
        self.requirements={'article_type':'Original Research','display_limits':{'main_figures':{'status':'required','value':3,'source':'https://journal.example/guide'}}}
    def write(self,rel,value):
        p=self.project/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value),encoding='utf-8');return p
    def run_check(self,stage='S20_journal'):
        self.write('08_submission/integration/artifact_plan.json',self.plan)
        self.write('08_submission/target_journal.json',self.target)
        self.write('08_submission/submission_requirements.json',self.requirements)
        return journal_display_fit(SimpleNamespace(project=self.project,stage=SimpleNamespace(id=stage)))
    def test_s20_reads_target_reason_without_changing_pristine_plan(self):
        self.assertTrue(self.run_check().ok)
        self.assertEqual(json.loads((self.project/'08_submission/integration/artifact_plan.json').read_text()),self.plan)
        self.assertNotIn('journal_adaptation_reason',self.plan)
    def test_s20_missing_reason_fails(self):
        self.target={};self.assertFalse(self.run_check().ok)
    def test_short_reason_fails(self):
        self.target['journal_adaptation_reason']='retain';self.assertFalse(self.run_check().ok)
    def test_whitespace_does_not_count_as_a_reason(self):
        self.target['journal_adaptation_reason']=' '*50;self.assertFalse(self.run_check().ok)
    def test_object_does_not_count_as_a_reason(self):
        self.target['journal_adaptation_reason']={'invented':REASON};self.assertFalse(self.run_check().ok)
    def test_display_cap_still_fails(self):
        self.plan['main_figures'].append({});self.assertFalse(self.run_check().ok)
    def test_later_owner_requires_the_actual_plan_reason(self):
        self.assertFalse(self.run_check('S22_polish').ok)
    def test_later_owner_accepts_the_actual_plan_reason(self):
        self.plan['journal_adaptation_reason']=REASON;self.assertTrue(self.run_check('S22_polish').ok)

if __name__=='__main__':unittest.main()
