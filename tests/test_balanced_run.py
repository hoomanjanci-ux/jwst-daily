"""Regression: the existing news call keeps its original targets and behaviour.
The additional analysis-only worker must never invoke it.
"""
import ast
import json
import os
import sys
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
class WorkerIsolationTests(unittest.TestCase):
    def run_real(self,only=False):
        tree=ast.parse((ROOT/'pipeline/run_daily.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        state={'products':{}};targets=[('fa_official','untouched-fa','fa'),('en_official','untouched-en','en')]
        news=Mock(return_value={'unchanged':True});worker=SimpleNamespace(cycle=Mock(return_value={'published':[]}))
        ns=dict(load_state=lambda:state,os=os,publish_targets=lambda:targets,
                tempfile=tempfile,Path=Path,shutil=shutil,json=json,sys=sys,__name__='test_orchestrator',
                mode=SimpleNamespace(status_line=lambda:'LIVE'),_iso_now=lambda:'2026-10-25T10:00:00+00:00',
                save_state=Mock(),news_rss=SimpleNamespace(publish=news),
                cloudflare=SimpleNamespace(configured=lambda:False))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<run>','exec'),ns)
        with patch.dict(sys.modules,{'analysis_worker':worker,'test_orchestrator':SimpleNamespace()}), \
             patch.dict(os.environ,{'ANALYSIS_ONLY':'1' if only else '0','TG_BOT_TOKEN':'dummy'}), \
             patch('builtins.print'):
            ns['run']()
        return state,news,targets,worker
    def test_default_worker_preserves_official_news_targets(self):
        state,news,targets,worker=self.run_real()
        news.assert_called_once_with(state,'dummy',targets)
        worker.cycle.assert_called_once()
    def test_dedicated_analysis_worker_never_invokes_news(self):
        state,news,_,_=self.run_real(True)
        news.assert_not_called()
        self.assertIn('not invoked',state['runs'][-1]['news']['note'])
    def test_news_failure_remains_isolated(self):
        # The existing exception boundary is retained around news_rss.publish.
        source=(ROOT/'pipeline/run_daily.py').read_text()
        self.assertIn('except Exception as e:  # noqa: BLE001\n            summary["news"]',source)
    def test_analysis_workflow_has_no_official_channel_credentials(self):
        source=(ROOT/'.github/workflows/jwst-analysis.yml').read_text()
        self.assertNotIn('TG_CH_FA_OFF:',source)
        self.assertNotIn('TG_CH_EN_OFF:',source)
        self.assertIn('ANALYSIS_ONLY: "1"',source)
