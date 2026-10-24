"""Offline regression tests: no credentials, astronomy dependencies or sends."""
import ast
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
import mode
import telegram_publish

class AnalysisRoutingTests(unittest.TestCase):
    def test_test_channel_is_never_a_target(self):
        with patch.dict(os.environ, {'TG_TEST_CHANNEL': 'obsolete',
                                    'TG_CH_FA_AI': '@RazKeyhan',
                                    'TG_CH_EN_AI': '@CosmicInsightJWST'}, clear=True):
            self.assertEqual(mode.publish_targets(), [
                ('fa_ai', '@RazKeyhan', 'fa'),
                ('en_ai', '@CosmicInsightJWST', 'en')])

    def test_emergency_stop(self):
        with patch.dict(os.environ, {'PROD_UNLOCKED': 'no',
                                    'TG_CH_FA_AI': '@RazKeyhan'}, clear=True):
            self.assertEqual(mode.publish_targets(), [])

    def test_analysis_boundary_rejects_news_and_old_test_targets(self):
        tree = ast.parse((ROOT / 'pipeline/run_daily.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'publish_one')
        # Execute the actual boundary statements, then return accepted targets.
        fn.body = fn.body[:2] + [ast.Return(value=ast.Name(id='targets', ctx=ast.Load()))]
        module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
        scope = {}
        exec(compile(module, '<analysis-boundary>', 'exec'), scope)
        targets = [('fa_ai', 'fa', 'fa'), ('en_ai', 'en', 'en'),
                   ('fa_official', 'news', 'fa'), ('en_official', 'news2', 'en'),
                   ('test_fa', 'deleted', 'fa')]
        self.assertEqual(scope['publish_one'](None, None, None, targets, None), targets[:2])
        self.assertFalse(scope['publish_one'](None, None, None, targets[2:], None))

    def test_legacy_publisher_only_sends_to_ai(self):
        env = {'TG_CH_FA_AI': '@RazKeyhan', 'TG_CH_EN_AI': '@CosmicInsightJWST',
               'TG_CH_FA_OFF': 'news-fa', 'TG_CH_EN_OFF': 'news-en',
               'TG_TEST_CHANNEL': 'deleted'}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(telegram_publish, 'send_photo') as photo, \
             patch.object(telegram_publish, 'send_message'):
            report = telegram_publish.publish_to_all('dummy', 'unused', 'fa', 'en', 'fa', 'en')
        self.assertEqual(set(report), {'fa_ai', 'en_ai'})
        self.assertEqual([c.args[1] for c in photo.call_args_list],
                         ['@RazKeyhan', '@CosmicInsightJWST'])

if __name__ == '__main__':
    unittest.main()
