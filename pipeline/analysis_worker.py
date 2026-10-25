"""Analysis-only preparation and delivery. No official-news calls or destinations.
Slot ledger + durable checkpoints prevent cron retries from sending another product.
Telegram cannot atomically deliver to two channels: ambiguous transport outcomes are
held for review, never blindly re-sent. Known 4xx rejection is safe to retry in-window.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import requests
import analysis_slots
import cadence


class Rejected(Exception):
    """Telegram explicitly rejected the request: no message was accepted."""


def utcnow():return datetime.now(timezone.utc)


def checkpoint(engine, state):
    engine.save_state(state)
    if os.environ.get('GITHUB_ACTIONS') != 'true':return
    # A local JSON write is NOT crash-durable across runners. Push before sending.
    root=engine.ROOT.parent
    for args in [
        ['git','config','user.name','jwst-pipeline-bot'],
        ['git','config','user.email','bot@users.noreply.github.com'],
        ['git','add','pipeline/state.json','pipeline/analysis_ready/','analyses/','pipeline/site_sync.json'],
    ]:subprocess.run(args,cwd=root,check=True,capture_output=True)
    diff=subprocess.run(['git','diff','--cached','--quiet'],cwd=root)
    if diff.returncode==1:
        subprocess.run(['git','commit','-m','analysis: durable delivery checkpoint [skip ci]'],
                       cwd=root,check=True,capture_output=True)
        subprocess.run(['git','pull','--rebase','origin','main'],cwd=root,check=True,capture_output=True)
        subprocess.run(['git','push'],cwd=root,check=True,capture_output=True)
    elif diff.returncode!=0:raise RuntimeError('Cannot verify durable checkpoint')


def api_once(token, chat, part, post, images):
    # Single request, no hidden 5xx/time-out retry (acceptance could be ambiguous).
    method='sendMediaGroup' if part=='album' else 'sendMessage'
    url=f'https://api.telegram.org/bot{token}/{method}'
    files={}
    try:
        if part=='album':
            media=[]
            for i,path in enumerate(images):
                key=f'file{i}';files[key]=open(path,'rb')
                item={'type':'photo','media':f'attach://{key}'}
                if i==0:item.update(caption=post['caption'],parse_mode='HTML')
                media.append(item)
            response=requests.post(url,data={'chat_id':chat,'media':json.dumps(media)},
                                   files=files,timeout=35)
        else:
            response=requests.post(url,data={'chat_id':chat,'text':post['text'],
                                   'parse_mode':'HTML'},timeout=35)
        result=response.json()
        if 400<=response.status_code<500 or (response.status_code==200 and not result.get('ok')):
            raise Rejected(f'Telegram rejected {part}: status={response.status_code}')
        response.raise_for_status()
        if not result.get('ok') or not result.get('result'):
            raise RuntimeError('Telegram acceptance could not be verified')
        records=result['result'] if isinstance(result['result'],list) else [result['result']]
        ids=[r['message_id'] for r in records]
        if not ids:raise RuntimeError('Telegram returned no receipt')
        return ids
    finally:
        for f in files.values():f.close()


def ready_records(engine,state):
    reserved={s.get('product') for s in state.get('analysis_slots',{}).values() if s.get('product')}
    return sorted([(pid,r) for pid,r in state['products'].items()
                   if r.get('status')=='ready' and pid not in reserved
                   and not engine._combo_blocked(state,r)
                   and (engine.ROOT/'analysis_ready'/pid/'pair.json').exists()],
                  key=lambda x:-(x[1].get('score') or 0))


def archive(engine,state,pid,bundle):
    rec=state['products'][pid]
    folder=(engine.ROOT.parent/bundle['analysis']).parent
    stem=Path(pid).stem
    doc={'product':pid,'published_utc':rec['published_utc'],
         'research_sha256':rec['research_sha256'],
         'items':{f'ai_{lang}':post for lang,post in bundle['translations'].items()}}
    (folder/(stem+'.post.json')).write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8')
    src=engine.ROOT/'analysis_ready'/pid/bundle['images'][0]
    (folder/(stem+'.jpg')).write_bytes(src.read_bytes())
    (engine.ROOT/'site_sync.json').write_text(json.dumps({'pending':True,'product':pid}),encoding='utf-8')
    rec['site_archive']='ok'
    state.setdefault('combo_seen',{})[engine._combo_of(rec)]=rec['published_utc']


def deliver(engine,state,slot_key,slot,token,now=None):
    now=now or utcnow()
    if slot.get('status')=='sent':return []
    # Both destinations are required. Never intentionally start an English-only pair.
    targets={lang:(key,chat) for key,chat,lang in engine.mode.ai_targets()}
    if not token or set(targets)!={'fa','en'}:
        slot['note']='both AI destinations and token required';return []
    pid=slot.get('product')
    if not pid:
        ready=ready_records(engine,state)
        if not ready:
            slot['note']='no quality-approved bilingual reserve';return []
        pid=ready[0][0];slot.update(product=pid,status='reserved',delivery={})
        state['products'][pid]['status']='paired_reserved'
        checkpoint(engine,state)
    rec=state['products'][pid]
    cache=engine.ROOT/'analysis_ready'/pid
    bundle=json.loads((cache/'pair.json').read_text())
    if set(bundle['translations'])!={'fa','en'}:
        raise ValueError('Incomplete pair cannot be delivered')
    images=[cache/name for name in bundle['images']]
    if len(images)<2 or not all(p.is_file() for p in images):
        raise ValueError('Pair image reserve missing')
    for lang in ('fa','en'):
        key,chat=targets[lang]
        parts=slot.setdefault('delivery',{}).setdefault(lang,{})
        for part in ('album','text'):
            status=parts.get(part,{}).get('status')
            if status=='sent':continue
            if status in ('sending','unverified'):
                parts[part]={'status':'unverified'};slot['status']='unverified'
                checkpoint(engine,state);return []
            if utcnow()>=datetime.fromisoformat(slot['end']):
                slot['status']='partial_expired';checkpoint(engine,state);return []
            parts[part]={'status':'sending','utc':utcnow().isoformat()}
            checkpoint(engine,state) # Must reach GitHub BEFORE Telegram sees request.
            try:
                ids=api_once(token,chat,part,bundle['translations'][lang],images)
            except Rejected:
                parts[part]={'status':'rejected'};slot['status']='retryable'
                checkpoint(engine,state);return []
            except Exception as e:
                parts[part]={'status':'unverified','error_type':type(e).__name__}
                slot['status']='unverified';checkpoint(engine,state);return []
            parts[part]={'status':'sent','message_ids':ids,'utc':utcnow().isoformat()}
            if part=='text':rec.setdefault('channels',{})[key]='sent'
            checkpoint(engine,state)
    slot.update(status='sent',completed_utc=utcnow().isoformat())
    rec.update(status='published',published_utc=slot['completed_utc'],analysis_slot=slot_key,
               research_sha256=hashlib.sha256(json.dumps(bundle['canonical'],sort_keys=True).encode()).hexdigest())
    try:archive(engine,state,pid,bundle)
    except Exception as e:rec['site_archive']='error: '+type(e).__name__
    if rec.get('site_archive')=='ok':
        if getattr(engine, 'cloudflare', None) and engine.cloudflare.configured():
            try:
                ok,_=engine.cloudflare.sync_analysis(pid,rec['published_utc'],bundle['meta'],
                    rec.get('score') or 0,None,rec.get('channels',{}),bundle['analysis'])
                rec['d1_sync']='ok' if ok else 'failed'
            except Exception:
                rec['d1_sync']='failed'
        getattr(engine,'_trim_rec',lambda r:None)(rec)
        shutil.rmtree(cache)
    checkpoint(engine,state)
    return [pid]


def cycle(state,token,tmp,engine,max_bytes=450_000_000,max_products=3):
    (engine.ROOT/'analysis_ready').mkdir(exist_ok=True)
    (engine.ROOT/'analysis_ready'/'.gitkeep').touch()
    for pid,rec in state['products'].items():
        cache=engine.ROOT/'analysis_ready'/pid
        if rec.get('status')=='published' and rec.get('site_archive','').startswith('error') and (cache/'pair.json').exists():
            try:
                archive(engine,state,pid,json.loads((cache/'pair.json').read_text()))
                shutil.rmtree(cache)
                checkpoint(engine,state)
            except Exception:
                pass
    key,slot=analysis_slots.refresh(state)
    out={'timezone':'Asia/Tehran','windows':['06–07','09–10','12–13','18–19'],
         'active_slot':key,'published':[]}
    # Fast path: serve a prepared pair before discovery/AI can eat the window.
    if slot and slot['status'] not in ('sent','unverified','missed','partial_expired'):
        out['published']=deliver(engine,state,key,slot,token)
    ready=len(ready_records(engine,state))
    now=utcnow()
    last=cadence.parse(state.get('paired_prepare_attempt_utc'))
    enough_time=not slot or datetime.fromisoformat(slot['end'])-now>timedelta(minutes=20)
    if ready<6 and enough_time and (last is None or now-last>=timedelta(hours=1)):
        state['paired_prepare_attempt_utc']=now.isoformat();engine.save_state(state)
        candidates=lambda:[(pid,r) for pid,r in state['products'].items()
                           if r.get('status')=='analyzed' and not engine._combo_blocked(state,r)]
        if len(candidates())<3:
            usage=state.get('analysis_byte_budget',{})
            spent=int(usage.get('bytes',0)) if usage.get('day')==now.date().isoformat() else 0
            remaining=max(0,900_000_000-spent)
            if remaining:
                engine.process_batch(state,min(max_bytes,remaining),min(max_products,3),tmp,
                                     wall_seconds=600)
        prepared=0
        for pid,r in sorted(candidates(),key=lambda x:-(x[1].get('score') or 0))[:3]:
            if slot and datetime.fromisoformat(slot['end'])-utcnow()<timedelta(minutes=15):break
            if engine.publish_one(pid,state,token,engine.mode.ai_targets(),tmp):prepared+=1
        out['prepared']=prepared
        checkpoint(engine,state)
    # Preparation may have filled an empty current slot; never publish outside it.
    key,slot=analysis_slots.refresh(state)
    if slot and slot['status'] not in ('sent','unverified','missed','partial_expired'):
        out['published']+=deliver(engine,state,key,slot,token)
    out['slot_status']=slot.get('status') if slot else 'outside publication windows'
    out['ready_pairs']=len(ready_records(engine,state))
    out['next_window']=analysis_slots.next_window()[1].isoformat()
    engine.save_state(state)
    return out
