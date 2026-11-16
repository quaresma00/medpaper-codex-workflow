"""Typed Methods provenance survives exact assembly without global numeric waivers."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from wfcore.checks.numbers import _prose_offenders

class ComposedMethodsConstants(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.ctx=SimpleNamespace(project=self.root,p=lambda rel:self.root/rel)
        self.block="# Methods\n\nHistorical source archives start in 2004.\n"
        self.write("07_manuscript/methods.md",self.block)
        self.write("01_protocol/protocol.md","The received historical archive begins in 2004.")
        self.write("03_analysis/results/number_allowlist.tsv","2004\tconstant\t01_protocol/protocol.md\tHistorical source-window design year, not an outcome or patient statistic.\n")
    def write(self,rel,text):
        p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding="utf-8")
    def check(self,text):return _prose_offenders(self.ctx,"07_manuscript/full_manuscript.md",text,set(),set(),set())
    def test_exact_assembled_methods_keeps_actual_typed_constant(self):
        self.assertEqual(self.check("# Abstract\n\nNo new values.\n\n"+self.block+"\n# Results\n\nNo numerical result."),[])
    def test_same_number_in_results_remains_unproven(self):
        self.assertEqual(len(self.check(self.block+"\n# Results\n\nThere were 2004 events.")),1)
    def test_same_number_in_abstract_remains_unproven(self):
        self.assertEqual(len(self.check("# Abstract\n\nThere were 2004 events.\n\n"+self.block)),1)
    def test_changed_or_duplicate_methods_blocks_fail_closed(self):
        self.assertTrue(self.check(self.block.replace("archives","data")))
        self.assertEqual(len(self.check(self.block+"\n"+self.block)),2)
    def test_missing_or_untyped_constant_cannot_authorize_number(self):
        self.write("03_analysis/results/number_allowlist.tsv","2004\n");self.assertTrue(self.check(self.block))
    def test_source_must_really_contain_the_constant(self):
        self.write("01_protocol/protocol.md","No historical year is supplied.");self.assertTrue(self.check(self.block))
    def test_standalone_results_never_borrow_the_methods_allowance(self):
        self.assertTrue(_prose_offenders(self.ctx,"07_manuscript/results.md","There were 2004 events.",set(),set(),set()))

if __name__=="__main__":unittest.main()
