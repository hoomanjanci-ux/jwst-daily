"""Provision only the named analysis Worker/tables. Never touches news resources."""
import json,os,secrets,time
from pathlib import Path
import requests
BASE='https://api.cloudflare.com/client/v4'
account=os.environ['CF_ACCOUNT_ID'];db=os.environ['CF_D1_DATABASE_ID'];token=os.environ['CF_API_TOKEN']
headers={'Authorization':'Bearer '+token}
name='jwst-analysis-scheduler'
def api(method,path,**kwargs):
    r=requests.request(method,BASE+path,headers=headers,timeout=60,**kwargs)
    data=r.json()
    if not r.ok or not data.get('success'):
        raise RuntimeError('Cloudflare request failed: '+str(r.status_code)+' '+str([x.get('code') for x in data.get('errors',[])]))
    return data.get('result')
def query(sql,params=None):
    return api('POST',f'/accounts/{account}/d1/database/{db}/query',json={'sql':sql,'params':params or []})
import subprocess,sys
subprocess.run([sys.executable,'scripts/verify_analysis_album_layout.py'],check=True)
query(Path('cloudflare/analysis.sql').read_text())
from datetime import datetime,timezone
state=json.loads(Path('pipeline/state.json').read_text())
for key,slot in state.get('analysis_slots',{}).items():
    if slot.get('status')!='sent':continue
    start=datetime.fromisoformat(slot['start']).astimezone(timezone.utc).isoformat()
    end=datetime.fromisoformat(slot['end']).astimezone(timezone.utc).isoformat()
    query("INSERT OR IGNORE INTO ai_slots(slot,start_utc,end_utc,status,product,completed_utc) VALUES(?,?,?,'sent',?,?)",
          [key,start,end,slot.get('product'),slot.get('completed_utc')])
metadata={'main_module':'worker.mjs','compatibility_date':'2026-10-01','bindings':[
    {'type':'d1','name':'DB','id':db},
    {'type':'plain_text','name':'GITHUB_REPO','text':os.environ['GITHUB_REPOSITORY']}]}
api('PUT',f'/accounts/{account}/workers/scripts/{name}',files={
    'metadata':(None,json.dumps(metadata),'application/json'),
    'worker.mjs':('worker.mjs',Path('cloudflare/analysis-worker.mjs').read_bytes(),'application/javascript+module')})
admin=secrets.token_urlsafe(32)
for key,value in [('TG_BOT_TOKEN',os.environ['TG_BOT_TOKEN']),
                  ('GH_ANALYSIS_DISPATCH_TOKEN',os.environ['GH_ANALYSIS_DISPATCH_TOKEN']),('ADMIN_TOKEN',admin)]:
    api('PUT',f'/accounts/{account}/workers/scripts/{name}/secrets',json={'name':key,'text':value,'type':'secret_text'})
api('POST',f'/accounts/{account}/workers/scripts/{name}/subdomain',json={'enabled':True})
subdomain=api('GET',f'/accounts/{account}/workers/subdomain')['subdomain']
url=f'https://{name}.{subdomain}.workers.dev'
api('PUT',f'/accounts/{account}/workers/scripts/{name}/schedules',json=[{'cron':'*/5 * * * *'}])
# Only activate the new sender after the Worker is reachable; no send during shadow probe.
for attempt in range(18):
    r=requests.get(url+'/status',headers={'Authorization':'Bearer '+admin},timeout=45)
    if r.status_code==200 and r.json().get('delivery_layout')=='album_v1':break
    if attempt==17:r.raise_for_status()
    time.sleep(5) # Worker route/secret propagation is not instantaneous.
r.raise_for_status()
query("INSERT INTO ai_control(key,value) VALUES('sender','cloudflare') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
# Layout update is read-only: do not trigger a publication or a forced wake-up.
verified={'active':True,'delivery_layout':r.json()['delivery_layout'],'publication_test':'not sent; next scheduled publication only'}
Path('pipeline/analysis_runtime.json').write_text(json.dumps({'sender':'cloudflare','worker_url':url}))
print('Independent analysis scheduler deployed:',url)
print('Cron: every five minutes; timezone windows: Tehran 06/09/12/18')
print('Warm-up:',json.dumps(verified))
query("INSERT INTO ai_control(key,value) VALUES('worker_url',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",[url])
Path('analysis-deployment.json').write_text(json.dumps({'worker_url':url,'cron':'*/5 * * * *','warmup':verified}))
