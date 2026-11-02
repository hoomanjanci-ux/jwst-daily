import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import album_layout
class AlbumLayoutTests(unittest.TestCase):
 def bundle(self):
  return {'canonical':{'target':'2MASS J18022716+6043356','filter':'F460M','statistics':{'sample_count':100406,'above_5scatter_percent':0.234,'brightest_quadrant_percent':61.277}},'meta':{'INSTRUME':'NIRCAM','DATE-OBS':'2026-09-02'},'translations':{lang:{'text':'long body '*400+'<a href="https://example.com/source">MAST / STScI</a>\n\n———\n<a href="https://t.me/own">own</a>\n<a href="https://t.me/news">news</a>\n🌐 t.me/own'} for lang in ('fa','en')}}
 def test_caption_contains_complete_concise_research_and_all_links(self):
  b=self.bundle();before=copy.deepcopy(b)
  for lang in ('fa','en'):
   text=album_layout.caption(b,lang)
   self.assertLessEqual(album_layout.visible_units(text),1024)
   for fact in ('100,406','0.234','61.277','4.6','F460M','2026-09-02'):self.assertIn(fact,text)
   for link in ('https://example.com/source','https://t.me/own','https://t.me/news'):self.assertIn(link,text)
  self.assertEqual(b,before)
 def test_html_is_escaped_without_cutting_markup(self):
  b=self.bundle();b['canonical']['target']='<bad & target>'
  self.assertIn('&lt;bad &amp; target&gt;',album_layout.caption(b,'fa'))
 def test_missing_evidence_or_footer_is_held(self):
  b=self.bundle();b['canonical']['statistics']={}
  with self.assertRaises(ValueError):album_layout.caption(b,'en')
  b=self.bundle();b['translations']['fa']['text']='no footer'
  with self.assertRaises(ValueError):album_layout.caption(b,'fa')
 def test_oversize_never_silently_truncates_or_splits(self):
  b=self.bundle();b['translations']['en']['text']+='x'*2000
  with self.assertRaises(ValueError):album_layout.caption(b,'en')
 def test_utf16_limit_and_entity_parsing(self):
  self.assertEqual(album_layout.visible_units('<b>🛰 &amp; &#x1f52d;</b>'),7)
