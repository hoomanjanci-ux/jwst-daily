import ast
from pathlib import Path
import os
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / 'pipeline/quality.py'
tree = ast.parse(source.read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='passes_gate')
ns={'os':os}
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(source),'exec'),ns)
gate=ns['passes_gate']

class QualityGateTests(unittest.TestCase):
    def test_high_image_cannot_override_bad_text(self):
        self.assertFalse(gate({'heuristic':{'score':95},'ai_message':{'score':20}}))
    def test_good_text_and_usable_image(self):
        self.assertTrue(gate({'heuristic':{'score':55},'ai_message':{'score':85}}))
    def test_blank_image_held_even_with_good_text(self):
        self.assertFalse(gate({'heuristic':{'score':5},'ai_message':{'score':95}}))
    def test_no_judge_requires_good_heuristic(self):
        self.assertFalse(gate({'heuristic':{'score':30}}))
        self.assertTrue(gate({'heuristic':{'score':75}}))
    def test_nan_and_malformed_fail_closed(self):
        for value in ['bad',float('nan'),None]:
            self.assertFalse(gate({'heuristic':{'score':value}}))
    def test_zero_does_not_disable_gate(self):
        with patch.dict(os.environ,{'QAI_MIN_SCORE':'0'}):
            self.assertFalse(gate({'heuristic':{'score':20}}))
