import sys,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import news_rss as n
ITEM={'id':'https://nasa.gov/test-webb','link':'https://nasa.gov/test-webb','title':'NASA Webb telescope observes a distant galaxy','summary':'The space telescope captured a new image of a galaxy.','source':'NASA','source_fa':'ناسا','date':datetime.now(timezone.utc).isoformat(),'dt':datetime.now(timezone.utc)}
FA={'title':'تلسکوپ وب کهکشانی دوردست را رصد کرد','body':'تلسکوپ فضایی جیمز وب تصویری تازه از یک کهکشان ثبت کرده است.'}
class PersianNewsTests(unittest.TestCase):
 def test_good_persian_retains_format_and_source(self):
  text=n._post_text(ITEM,'fa',False,FA)
  self.assertIn(FA['title'],text);self.assertIn(FA['body'],text)
  self.assertIn('href="https://nasa.gov/test-webb"',text);self.assertIn('📡 منبع: ناسا',text)
 def test_english_unchanged(self):
  text=n._post_text(ITEM,'en',False)
  self.assertIn(ITEM['title'],text);self.assertIn(ITEM['summary'],text);self.assertIn('Full story',text)
 def test_english_fallback_is_forbidden(self):
  with patch.object(n,'_fa_rewrite',return_value=None):
   with self.assertRaises(ValueError):n._post_text(ITEM,'fa',False)
 def test_tiny_persian_prefix_does_not_pass(self):
  self.assertFalse(n._valid_fa_rewrite({'title':'خبر تازه '+ITEM['title'],'body':'خبر تازه '+ITEM['summary']}))
 def test_provider_outage_uses_real_persian_backup(self):
  with patch.object(n.ai_message,'_qai_chat',side_effect=RuntimeError('503')),patch.object(n,'_translate_fa',side_effect=[FA['title'],FA['body']]):
   self.assertEqual(n._fa_rewrite(ITEM),FA)
 def test_garbled_output_is_not_published(self):
  with patch.object(n.ai_message,'_qai_chat',return_value='{"title":"خبر جدید 人間", "body":"خبر جدید 人間"}'),patch.object(n,'_translate_fa',return_value='English is not Persian'):
   self.assertIsNone(n._fa_rewrite(ITEM))
 def test_fa_failure_does_not_block_english_or_mark_fa_seen(self):
  state={}
  with patch.object(n,'fetch_feed',return_value=[dict(ITEM)]),patch.object(n,'_fa_rewrite',return_value=None),patch.object(n.telegram_publish,'send_message') as send:
   out=n.publish(state,'dummy',[('fa_official','@NabzeKeyhan1','fa'),('en_official','@CosmicNewsJWST','en')])
  self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.args[1],'@CosmicNewsJWST')
  self.assertNotIn('fa',state['news_seen'][ITEM['id']]);self.assertIn('en',state['news_seen'][ITEM['id']])
  self.assertFalse(state.get('news_archive'));self.assertTrue(out['errors'])
 def test_retry_fa_does_not_resend_english(self):
  state={'news_seen':{ITEM['id']:{'en':'already'}}}
  with patch.object(n,'fetch_feed',return_value=[dict(ITEM)]),patch.object(n,'_fa_rewrite',return_value=FA),patch.object(n.telegram_publish,'send_message') as send:
   n.publish(state,'dummy',[('fa_official','@NabzeKeyhan1','fa'),('en_official','@CosmicNewsJWST','en')])
  self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.args[1],'@NabzeKeyhan1')
  self.assertEqual(state['news_archive'][ITEM['id']]['summary'],FA['body'])
 def test_independent_backup_when_google_is_blocked(self):
  response=Mock();response.raise_for_status.return_value=None
  response.json.return_value={'responseStatus':200,'responseData':{'translatedText':FA['title']}}
  with patch.object(n.requests,'get',side_effect=[RuntimeError('blocked'),RuntimeError('blocked'),response]):
   self.assertEqual(n._translate_fa(ITEM['title']),FA['title'])
if __name__=='__main__':unittest.main()
