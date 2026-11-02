"""Read-only preview of UNSENT reserves; no Telegram sends or history edits."""
import json,os,sys,subprocess
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipeline'))
import album_layout
url='https://api.cloudflare.com/client/v4/accounts/'+os.environ['CF_ACCOUNT_ID']+'/d1/database/'+os.environ['CF_D1_DATABASE_ID']+'/query'
r=requests.post(url,headers={'Authorization':'Bearer '+os.environ['CF_API_TOKEN']},json={
    'sql':"SELECT product,payload,status FROM ai_queue WHERE status IN ('ready','reserved') ORDER BY created_utc LIMIT 12"},timeout=40)
if r.status_code!=200 or not r.json().get('success'):raise RuntimeError('Read-only reserve check failed')
rows=r.json()['result'][0]['results']
bundles=[json.loads(row['payload']) for row in rows]
js="""import {albumCaption} from './cloudflare/analysis-worker.mjs';let s='';for await(const chunk of process.stdin)s+=chunk;console.log(JSON.stringify(JSON.parse(s).map(b=>Object.fromEntries(['fa','en'].map(l=>[l,albumCaption(b,l)])))));"""
result=subprocess.run(['node','--input-type=module','-e',js],cwd=ROOT,input=json.dumps(bundles),text=True,capture_output=True,check=True)
worker_previews=json.loads(result.stdout)
previews=[]
for row,b,worker in zip(rows,bundles,worker_previews):
    captions={l:album_layout.caption(b,l) for l in ('fa','en')}
    if captions!=worker:raise RuntimeError('Python/Worker caption disagreement')
    image_count=len(b.get('image_urls',[]))
    if not 2<=image_count<=10:raise RuntimeError('Invalid existing analysis album size')
    previews.append({'product':row['product'],'status':row['status'],'image_count':image_count,
        'visible_units':{l:album_layout.visible_units(t) for l,t in captions.items()},
        'captions':captions,'standalone_text_messages':0})
Path('analysis-album-preview.json').write_text(json.dumps({'layout':'album_v1','checked_reserves':len(rows),
    'telegram_sends':0,'history_mutations':0,'previews':previews},ensure_ascii=False,indent=2))
print('Album captions validated against live unsent reserves:',len(rows))
for p in previews:print(p['product'],p['visible_units'])
