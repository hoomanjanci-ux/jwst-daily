"""Exercise the real orchestrator AST with network/astronomy mocked out."""
import ast
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import cadence

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)
class BalancedRunTests(unittest.TestCase):
    def exercise(self, s, refill=0):
        tree=ast.parse((ROOT/'pipeline/run_daily.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        publish=Mock(return_value=True)
        def process(state,*a,**kw):
            for i in range(refill):
                state['products']['new'+str(i)]={'status':'analyzed','score':80-i}
            return refill,True
        ns=dict(load_state=lambda:s, os=os, publish_targets=lambda:[],
                Path=Path,tempfile=tempfile,shutil=shutil,json=json,
                cadence=cadence,mode=SimpleNamespace(status_line=lambda:'LIVE',
                    ai_targets=lambda:[('fa_ai','@RazKeyhan','fa')]),
                _iso_now=lambda:NOW.isoformat(), _combo_blocked=lambda *a:False,
                save_state=Mock(),process_batch=Mock(side_effect=process),
                log=lambda *a:None,publish_one=publish,
                news_rss=SimpleNamespace(publish=Mock(return_value={'unchanged':True})),
                cloudflare=SimpleNamespace(configured=lambda:False))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),
                     '<real-run>','exec'),ns)
        with patch.dict(os.environ,{'TG_BOT_TOKEN':'dummy'}), patch('builtins.print'):
            ns['run']()
        return ns
    def test_empty_queue_refills_without_waiting_20_hours(self):
        s={'products':{},'last_batch_utc':NOW.isoformat()}
        ns=self.exercise(s,3)
        ns['process_batch'].assert_called_once()
        ns['publish_one'].assert_called_once()
        self.assertEqual(s['runs'][-1]['news'],{'unchanged':True})
    def test_recent_publish_does_not_burst_after_refill(self):
        s={'products':{'old':{'status':'published','published_utc':NOW.isoformat(),
                            'channels':{'fa_ai':'sent'}}}}
        ns=self.exercise(s,3)
        ns['publish_one'].assert_not_called()
    def test_full_reserve_no_download_and_only_one_publish(self):
        s={'products':{str(i):{'status':'analyzed','score':80-i} for i in range(6)}}
        ns=self.exercise(s)
        ns['process_batch'].assert_not_called()
        ns['publish_one'].assert_called_once()
    def test_empty_failed_refill_does_not_invent_content(self):
        s={'products':{}}
        ns=self.exercise(s)
        ns['publish_one'].assert_not_called()
        self.assertIsNone(s['runs'][-1]['analysis_cadence']['next_publish_not_before_utc'])

if __name__=='__main__':unittest.main()
