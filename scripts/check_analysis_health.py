"""Read-only acceptance evidence. No Telegram sends, no secret values in output."""
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import requests
base='https://api.cloudflare.com/client/v4/accounts/'+os.environ['CF_ACCOUNT_ID']
h={'Authorization':'Bearer '+os.environ['CF_API_TOKEN']}
def q(sql):
 r=requests.post(base+'/d1/database/'+os.environ['CF_D1_DATABASE_ID']+'/query',headers=h,json={'sql':sql},timeout=30)
 if r.status_code!=200:raise RuntimeError('D1 health HTTP '+str(r.status_code))
 j=r.json()
 if not j.get('success'):raise RuntimeError('D1 health query failed')
 return j['result'][0]['results']
rows=q("SELECT product,payload,status,created_utc FROM ai_queue WHERE status IN ('ready','reserved')")
reserve=[]
for r in rows:
 b=json.loads(r['payload']);texts=b['translations'];stats=b['canonical'].get('statistics',{})
 urls=b.get('image_urls',[]);image_ok=True
 for url in urls:
  try:
   x=requests.head(url,timeout=15);image_ok &= x.status_code==200 and x.headers.get('Content-Type','').startswith('image/')
  except requests.RequestException:image_ok=False
 reserve.append({'product':r['product'],'status':r['status'],'target':b['meta'].get('TARGNAME'),'filter':b['meta'].get('FILTER'),
  'revision':b['canonical'].get('revision'),'research_sha256':hashlib.sha256(json.dumps(b['canonical'],sort_keys=True).encode()).hexdigest(),
  'text_lengths':{lang:len(texts[lang]['text']) for lang in ['fa','en']},'sample_count':stats.get('sample_count'),
  'image_count':len(urls),'images_reachable':bool(image_ok and len(urls)>=2),'combo':b.get('combo')})
def tg(method,**params):
 try:
  r=requests.post('https://api.telegram.org/bot'+os.environ['TG_BOT_TOKEN']+'/'+method,json=params,timeout=20)
  j=r.json();return j.get('result') if r.ok and j.get('ok') else None
 except (requests.RequestException,ValueError):return None
me=tg('getMe');destinations={}
for lang,chat in [('fa','@RazKeyhan'),('en','@CosmicInsightJWST')]:
 member=tg('getChatMember',chat_id=chat,user_id=me['id']) if me else None
 destinations[lang]={'channel':chat,'can_publish':bool(member and (member.get('status')=='creator' or (member.get('status')=='administrator' and member.get('can_post_messages'))))}
schedules=requests.get(base+'/workers/scripts/jwst-analysis-scheduler/schedules',headers=h,timeout=30)
result={'checked_utc':datetime.now(timezone.utc).isoformat(),'control':q('SELECT key,value FROM ai_control'),
 'queue_counts':q('SELECT status,count(*) AS count FROM ai_queue GROUP BY status'),'reserve':reserve,'destinations':destinations,
 'slots':q('SELECT * FROM ai_slots ORDER BY slot DESC LIMIT 8'),'receipts':q('SELECT slot,lang,part,status,ids,updated_utc FROM ai_receipts ORDER BY updated_utc DESC LIMIT 16'),
 'schedules':schedules.json().get('result') if schedules.ok else {'http_status':schedules.status_code}}
Path('analysis-health.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'queue_counts':result['queue_counts'],'destinations':destinations,'reserve_items':len(reserve),'images_reachable':all(x['images_reachable'] for x in reserve)},ensure_ascii=False))
