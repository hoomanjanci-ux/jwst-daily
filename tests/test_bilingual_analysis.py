import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import bilingual_analysis as bilingual

STATS={'width':200,'height':100,'sample_count':20000,'finite_fraction':1,
       'median':5.0,'robust_scatter':1.2,'above_5scatter_percent':2.5}
class BilingualTests(unittest.TestCase):
    def test_both_versions_share_one_measured_research(self):
        bundle=bilingual.build_pair({'TARGNAME':'X','INSTRUME':'NIRCAM','FILTER':'F335M'},'42',
                                    {'measured_image_statistics':STATS})
        self.assertEqual(bundle['canonical']['statistics'],STATS)
        self.assertEqual(set(bundle['translations']),{'fa','en'})
        for post in bundle['translations'].values():
            self.assertIn('2.5',post['text']);self.assertIn('3.35',post['text'])
    def test_api_outage_cannot_stop_real_computational_analysis(self):
        with patch.object(bilingual.ai_message,'_qai_chat',side_effect=RuntimeError('503')) as api:
            b=bilingual.build_pair({'TARGNAME':'X'},'42',{'measured_image_statistics':STATS})
        api.assert_not_called()
        self.assertIn('not model-generated',b['translations']['en']['text'])
    def test_missing_measured_data_is_not_replaced_by_fake_template(self):
        with self.assertRaises(ValueError):bilingual.build_pair({},'',{})
    def test_html_is_escaped(self):
        b=bilingual.build_pair({'TARGNAME':'<script>X</script>'},'42',{'measured_image_statistics':STATS})
        self.assertNotIn('<script>',b['translations']['fa']['text'])
