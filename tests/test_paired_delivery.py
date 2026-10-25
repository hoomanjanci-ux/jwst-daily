import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import analysis_worker as worker

NOW=datetime(2026,10,25,2,40,tzinfo=timezone.utc) # 06:10 Tehran
class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)/'pipeline';root.mkdir()
        cache=root/'analysis_ready'/'p.fits';cache.mkdir(parents=True)
        for name in ['0.jpg','1.jpg']:(cache/name).write_bytes(b'JPEG fixture')
        folder=root.parent/'analyses/2026/10/25';folder.mkdir(parents=True)
        self.bundle={'product':'p.fits','canonical':{'body':'ONE research'},'analysis':'analyses/2026/10/25/p.fits.json',
                     'images':['0.jpg','1.jpg'],'translations':{
                         'fa':{'caption':'FA caption','text':'FA translation','generator':'shared'},
                         'en':{'caption':'EN caption','text':'ONE research','generator':'shared'}}}
        (cache/'pair.json').write_text(json.dumps(self.bundle))
        self.state={'products':{'p.fits':{'status':'ready','score':80,'channels':{},'combo':'X|N|F'}}}
        self.slot={'status':'waiting','end':(NOW+timedelta(minutes=50)).isoformat()}
        self.state['analysis_slots']={'2026-10-25/06':self.slot}
        self.engine=SimpleNamespace(ROOT=root,save_state=Mock(),_combo_blocked=lambda *a:False,
                                    _combo_of=lambda r:r['combo'],mode=SimpleNamespace(ai_targets=lambda:[
                                        ('fa_ai','FA','fa'),('en_ai','EN','en')]))
    def tearDown(self):self.tmp.cleanup()
    def deliver(self,api):
        with patch.object(worker,'utcnow',return_value=NOW),patch.object(worker,'api_once',api), \
             patch.dict('os.environ',{'GITHUB_ACTIONS':'false'}):
            return worker.deliver(self.engine,self.state,'2026-10-25/06',self.slot,'dummy')
    def test_both_languages_one_product_and_no_repeat(self):
        api=Mock(return_value=[123]);self.assertEqual(self.deliver(api),['p.fits'])
        self.assertEqual(api.call_count,4);self.assertEqual(self.slot['status'],'sent')
        self.assertEqual(self.state['products']['p.fits']['channels'],{'fa_ai':'sent','en_ai':'sent'})
        self.deliver(api);self.assertEqual(api.call_count,4)
    def test_missing_one_destination_blocks_both(self):
        self.engine.mode.ai_targets=lambda:[('en_ai','EN','en')]
        api=Mock();self.assertEqual(self.deliver(api),[]);api.assert_not_called()
    def test_known_rejection_retries_only_unsent_components(self):
        api=Mock(side_effect=[[1],[2],worker.Rejected('429')]);self.deliver(api)
        self.assertEqual(self.slot['status'],'retryable')
        api2=Mock(return_value=[3]);self.deliver(api2)
        self.assertEqual(api2.call_count,2)
        self.assertTrue(all(c.args[1]=='EN' for c in api2.call_args_list))
    def test_timeout_is_unverified_not_blindly_resent(self):
        api=Mock(side_effect=TimeoutError());self.deliver(api)
        self.assertEqual(self.slot['status'],'unverified')
        api2=Mock();self.deliver(api2);api2.assert_not_called()
    def test_crash_after_intent_does_not_duplicate(self):
        self.slot.update(product='p.fits',delivery={'fa':{'album':{'status':'sending'}}})
        api=Mock();self.deliver(api);api.assert_not_called()
        self.assertEqual(self.slot['status'],'unverified')
    def test_expired_window_never_sends(self):
        self.slot['end']=(NOW-timedelta(minutes=1)).isoformat()
        api=Mock();self.deliver(api);api.assert_not_called()
    def test_archive_keeps_both_languages_and_shared_identity(self):
        self.deliver(Mock(return_value=[1]))
        doc=json.loads((self.engine.ROOT.parent/'analyses/2026/10/25/p.post.json').read_text())
        self.assertEqual(set(doc['items']),{'ai_fa','ai_en'})
        self.assertTrue(doc['research_sha256'])
        self.assertTrue(json.loads((self.engine.ROOT/'site_sync.json').read_text())['pending'])
    def test_checkpoint_failure_prevents_telegram_send(self):
        api=Mock()
        with patch.object(worker,'checkpoint',side_effect=RuntimeError('push failed')):
            with self.assertRaises(RuntimeError):self.deliver(api)
        api.assert_not_called()
