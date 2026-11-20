"""Synthetic preproduction correction and optional supplement boundaries."""
import copy, json, os, subprocess, sys, tempfile, unittest

from pathlib import Path

from types import SimpleNamespace

from wfcore import registry, revision

from wfcore.state import State

from wfcore.checks import Ctx

from wfcore.checks.fsx import json_keys

ROOT=Path(__file__).resolve().parents[1]

class EarlyCorrections(unittest.TestCase):

 def setUp(self):

  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/'project';self.p.mkdir();self.pipe=registry.load()

  self.state=State(self.p).create('medpaper',self.pipe.meta['version'],'S07_artifacts')

  for s in self.pipe.stages[:6]: self.state.stage_info(s.id)['status']='done'

  self.state.save()

 def tearDown(self):self.tmp.cleanup()

 def put(self,path,obj):

  f=self.p/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(obj),encoding='utf-8');return f

 def run_batch(self,stage='S07_artifacts',kind='artifact-plan-or-legend',source='01_protocol/artifact_plan.json'):

  self.state.data['current']=stage;self.state.save();self.put(source,{'existing':True})

  plan=self.put('temp/plan.json',{'feedback_verbatim':'Please apply this bounded preproduction correction while preserving all unrelated scientific work.', 'interpretation':'Correct the existing source and validate only actual current dependencies.', 'items':[{'kind':kind,'change_type':'scientific' if kind=='analysis' else 'wording','request':'Correct the existing exported metadata without changing numerical results.','affected_sources':[source], 'acceptance_criteria':['Current owner checks run','Unrelated work is unchanged']}]})

  env={**os.environ,'MEDPAPER_PROJECT':str(self.p),'MEDPAPER_ROOT':str(ROOT),'PYTHONIOENCODING':'utf-8'}

  return subprocess.run([sys.executable,str(ROOT/'tools/rework.py'),'batch','--sealed','--plan',str(plan)],env=env,capture_output=True,text=True,encoding='utf-8')

 def test_optional_lists_but_required_items(self):

  self.put('01_protocol/artifact_plan.json',{'main_figures':[{'id':'Figure 1'}],'main_tables':[{'id':'Table 1'}],'supp_figures':[],'supp_tables':[],'supp_files':[]})

  spec=next(x for x in self.pipe.stage('S07_artifacts').gate if x['check']=='json_keys')

  ctx=Ctx(self.pipe,self.state,self.p,self.pipe.stage('S07_artifacts'),spec)

  self.assertTrue(json_keys(ctx).ok)

  self.put('01_protocol/artifact_plan.json',{'main_figures':[],'main_tables':[],'supp_figures':[],'supp_tables':[],'supp_files':[]})

  self.assertFalse(json_keys(ctx).ok)

 def test_current_owner_retained_and_future_outputs_rejected(self):

  previous=copy.deepcopy(self.state.data['stages']);r=self.run_batch();self.assertEqual(r.returncode,0,r.stdout+r.stderr)

  self.state.load();self.assertEqual(self.state.current,'S07_artifacts');self.assertEqual(previous,self.state.data['stages'])

  a=revision.active(self.p);self.assertIn('S07_artifacts',a['validation_stages']);self.assertNotIn('S10_tables',a['validation_stages'])

  self.assertTrue(any(x['spec']['check']=='medical_benchmark' for x in a['checks']))

  with self.assertRaises(ValueError):revision.guard_outputs(self.p,[self.p/'05_figures/out/Figure1.pdf'])

 def test_earlier_analysis_owner_and_no_future_manuscript(self):

  r=self.run_batch(kind='analysis',source='03_analysis/code/export.py');self.assertEqual(r.returncode,0,r.stdout+r.stderr)

  a=revision.active(self.p);self.assertIn('S05_analysis',a['validation_stages']);self.assertIn('S06_protocol_final',a['validation_stages']);self.assertIn('S07_artifacts',a['validation_stages']);self.assertNotIn('S17_assemble',a['validation_stages'])

 def test_frozen_master_rejects_preproduction_shortcut(self):

  self.put('07_manuscript/scientific_master_freeze.json',{'frozen':True});r=self.run_batch();self.assertNotEqual(r.returncode,0)

 def test_future_owner_not_permitted(self):

  r=self.run_batch(kind='tables',source='04_tables/build.py');self.assertNotEqual(r.returncode,0)

if __name__=='__main__':unittest.main()

