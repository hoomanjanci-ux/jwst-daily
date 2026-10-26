"""D1 bridge for independent analysis delivery. Dedicated ai_* tables only."""
import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import quote
import requests
import cloudflare


def query(sql,params=None):
    ok,results=cloudflare.d1_query(sql,params)
    if not ok:raise RuntimeError('Analysis queue database unavailable')
    return results[0].get('results',[]) if results else []

def active():
    runtime=Path(__file__).with_name('analysis_runtime.json')
    if runtime.exists() and json.loads(runtime.read_text()).get('sender')=='cloudflare':
        return True # Fail closed on D1 outages; never enable a duplicate legacy sender.
    if not cloudflare.configured():return False
    try:return query("SELECT value FROM ai_control WHERE key='sender'")==[{'value':'cloudflare'}]
    except RuntimeError:return False


def sync(engine,state,checkpoint,archive):
    updated=[]
    for row in query("SELECT product,payload,slot,published_utc FROM ai_queue WHERE status='published' AND synced=0"):
        pid=row['product'];bundle=json.loads(row['payload']);rec=state['products'].get(pid)
        if not rec:continue
        cache=engine.ROOT/'analysis_ready'/pid
        rec.update(status='published',published_utc=row['published_utc'],analysis_slot=row['slot'],
                   channels={'fa_ai':'sent','en_ai':'sent'},
                   research_sha256=hashlib.sha256(json.dumps(bundle['canonical'],sort_keys=True).encode()).hexdigest())
        slotrow=query('SELECT * FROM ai_slots WHERE slot=?',[row['slot']])[0]
        receipts=query('SELECT * FROM ai_receipts WHERE slot=?',[row['slot']]);delivery={}
        for r in receipts:
            delivery.setdefault(r['lang'],{})[r['part']]={'status':r['status'],'message_ids':json.loads(r['ids'] or '[]'),'utc':r['updated_utc']}
        state.setdefault('analysis_slots',{})[row['slot']]={'start':slotrow['start_utc'],'end':slotrow['end_utc'],
            'status':'sent','product':pid,'delivery':delivery,'completed_utc':row['published_utc'],'sender':'cloudflare'}
        try:
            archive(engine,state,pid,bundle)
            ok,_=cloudflare.sync_analysis(pid,rec['published_utc'],bundle['meta'],
                rec.get('score') or 0,None,rec.get('channels',{}),bundle['analysis'])
            rec['d1_sync']='ok' if ok else 'failed'
            if not ok:raise RuntimeError('Analysis archive D1 sync pending')
            engine._trim_rec(rec)
            if cache.exists():shutil.rmtree(cache)
            checkpoint(engine,state) # Website archive MUST be durable before acknowledging.
            query('UPDATE ai_queue SET synced=1 WHERE product=?',[pid])
            updated.append(pid)
        except Exception as e:
            rec['site_archive']='error: '+type(e).__name__
    # Mirror missed/retryable slots for diagnostics, but never reset a sent slot.
    for row in query('SELECT * FROM ai_slots ORDER BY slot DESC LIMIT 16'):
        if row['status']=='sent':continue
        state.setdefault('analysis_slots',{})[row['slot']]={'start':row['start_utc'],'end':row['end_utc'],
            'status':row['status'],'product':row['product'],'note':row['note'],'sender':'cloudflare'}
    return updated


def enqueue(engine,state,checkpoint):
    checkpoint(engine,state) # Raw GitHub image URLs must exist before Telegram uses them.
    count=0
    seen=set()
    days=int(getattr(engine,'COMBO_MIN_DAYS',14))
    rows=query("SELECT product,payload,status FROM ai_queue WHERE status IN ('ready','reserved') OR (status='published' AND julianday(published_utc)>julianday('now')-?) ORDER BY CASE status WHEN 'reserved' THEN 0 WHEN 'published' THEN 1 ELSE 2 END,created_utc",[days])
    for row in rows:
        b=json.loads(row['payload']);m=b.get('meta',{})
        combo=b.get('combo') or '|'.join(str(m.get(k) or '') for k in ('TARGNAME','INSTRUME','FILTER'))
        if not combo.strip('|'):combo=row['product']
        if combo in seen and row['status']=='ready':
            changed=query("UPDATE ai_queue SET status='superseded' WHERE product=? AND status='ready' RETURNING product",[row['product']])
            if changed and row['product'] in state['products']:
                state['products'][row['product']]['status']='combo_cooldown'
            continue
        seen.add(combo)
        if row['status']=='ready' and not b.get('combo'):
            b['combo']=combo;b['repeat_after_days']=days
            query("UPDATE ai_queue SET payload=? WHERE product=? AND status='ready'",[json.dumps(b,ensure_ascii=False),row['product']])
    for pid,rec in state['products'].items():
        cache=engine.ROOT/'analysis_ready'/pid
        if rec.get('status')!='ready' or not (cache/'pair.json').exists():continue
        existing=query('SELECT status FROM ai_queue WHERE product=?',[pid])
        if existing:continue
        combo=rec.get('combo') or engine._combo_of(rec)
        if not combo.strip('|'):combo=pid
        if combo in seen:
            rec['status']='combo_cooldown'
            continue
        bundle=json.loads((cache/'pair.json').read_text())
        base='https://raw.githubusercontent.com/hoomanjanci-ux/jwst-daily/main/'
        urls=[base+quote(f'pipeline/analysis_ready/{pid}/{name}',safe='/') for name in bundle['images']]
        reachable=True
        for url in urls:
            try:
                r=requests.head(url,timeout=15)
                if r.status_code!=200 or not r.headers.get('Content-Type','').startswith('image/'):
                    reachable=False;break
            except requests.RequestException:reachable=False;break
        if not reachable:continue
        bundle['image_urls']=urls
        bundle['combo']=combo
        bundle['repeat_after_days']=days
        seen.add(combo)
        query("INSERT OR IGNORE INTO ai_queue(product,payload,status,created_utc) VALUES(?,?,'ready',?)",
              [pid,json.dumps(bundle,ensure_ascii=False),rec.get('paired_ready_utc') or ''])
        count+=1
    checkpoint(engine,state)
    return count
