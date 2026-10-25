import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import bilingual_analysis as bilingual

class BilingualTests(unittest.TestCase):
    def test_one_canonical_then_translation_not_two_research_calls(self):
        en={'hook':'A measured observation','body':'JWST observed target X.','why':'Public data permit comparison.'}
        fa={'hook':'یک رصد اندازه‌گیری‌شده','body':'جیمز وب هدف X را رصد کرد.','why':'داده عمومی امکان مقایسه می‌دهد.'}
        with patch.object(bilingual.ai_message,'_qai_chat',side_effect=[json.dumps(en),json.dumps(fa)]) as chat, \
             patch.object(bilingual.ai_message,'_ai_narrative',side_effect=AssertionError('second research')):
            bundle=bilingual.build_pair({'TARGNAME':'X','DATE-OBS':'2024-01-01'},'42',{'target':'X'})
        self.assertEqual(chat.call_count,2)
        self.assertEqual(bundle['canonical'],en)
        self.assertEqual(set(bundle['translations']),{'fa','en'})
        self.assertIn('JWST observed target X.',chat.call_args_list[1].args[0][0]['content'])
    def test_no_template_when_model_unavailable(self):
        with patch.object(bilingual.ai_message,'_qai_chat',return_value=None):
            with self.assertRaises(ValueError):bilingual.build_pair({},'',{})
    def test_missing_translation_holds_whole_pair(self):
        en={'hook':'Observation','body':'Data only.','why':'A comparison.'}
        with patch.object(bilingual.ai_message,'_qai_chat',side_effect=[json.dumps(en),None,None]):
            with self.assertRaises(ValueError):bilingual.build_pair({},'',{})
