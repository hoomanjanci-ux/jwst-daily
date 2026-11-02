import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {slotAt,deliver,albumCaption,visibleUnits} from './analysis-worker.mjs';
const py=`import sqlite3,json,sys
c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row
sql=sys.argv[2];args=json.loads(sys.argv[3])
if sys.argv[4]=='schema':c.executescript(sql);r=[];n=0
else:
 q=c.execute(sql,args);r=[dict(x) for x in q.fetchall()];n=max(q.rowcount,0)
c.commit();print(json.dumps({'results':r,'meta':{'changes':n}}))`;
class DB {
 constructor(path){this.path=path;}
 sql(sql,args=[],mode='run') {const r=spawnSync('python3',['-c',py,this.path,sql,JSON.stringify(args),mode],{encoding:'utf8'});if(r.status!==0)throw Error(r.stderr);return JSON.parse(r.stdout);}
 prepare(sql){const db=this;return {bind(...args){return {first:async()=>db.sql(sql,args).results[0]||null,run:async()=>db.sql(sql,args),all:async()=>db.sql(sql,args)}} ,all:async()=>db.sql(sql).results};}
 async batch(statements){return Promise.all(statements.map(x=>x.run()));}
}
for(const hour of [6,9,12,18]){
 const d=new Date(`2026-10-26T${String(hour).padStart(2,'0')}:05:00+03:30`);
 assert.equal(slotAt(d).key,`2026-10-26/${String(hour).padStart(2,'0')}`);
 assert.equal(slotAt(new Date(+d+55*60000)),null);
}
assert.equal(slotAt(new Date('2026-10-26T03:00:00+03:30')),null);
let checks=0;
for(const scenario of ['normal','duplicate','rejected','timeout','race','legacy_partial','historic','bad_caption']){
 const dir=mkdtempSync(join(tmpdir(),'analysis-worker-'));const db=new DB(join(dir,'db.sqlite'));
 try {
  db.sql(readFileSync(new URL('./analysis.sql',import.meta.url),'utf8'),[],'schema');
  const baseText='Full long research '+ 'details '.repeat(200)+'<a href="https://archive.stsci.edu/proposal-id/1">MAST / STScI</a>\n\n———\n<a href="https://t.me/test">Channel</a>\n<a href="https://t.me/news">News</a>\nt.me/test';
  const bundle={canonical:{target:'2MASS J18022716+6043356',filter:'F460M',statistics:{sample_count:100406,above_5scatter_percent:0.234,brightest_quadrant_percent:61.277}},meta:{INSTRUME:'NIRCAM','DATE-OBS':'2026-09-02'},translations:{fa:{caption:'FA old brief',text:baseText},en:{caption:'EN old brief',text:baseText}},image_urls:[0,1,2,3].map(i=>`https://example.com/${i}.jpg`)};
  if(scenario==='bad_caption')for(const p of Object.values(bundle.translations))p.text+='x'.repeat(2000);

  db.sql("INSERT INTO ai_queue(product,payload,status,created_utc) VALUES(?,?,'ready',?)",['p',JSON.stringify(bundle),new Date().toISOString()]);
  const env={DB:db,TG_BOT_TOKEN:'dummy'},slot={key:'test/06',start:new Date(Date.now()-60000).toISOString(),end:new Date(Date.now()+300000).toISOString()};
  if(scenario==='legacy_partial'){
   db.sql("INSERT INTO ai_slots(slot,start_utc,end_utc,status,product) VALUES(?,?,?,'retryable','p')",[slot.key,slot.start,slot.end]);
   db.sql("UPDATE ai_queue SET status='reserved',slot=? WHERE product='p'",[slot.key]);
   db.sql("INSERT INTO ai_receipts(slot,lang,part,status,ids,updated_utc) VALUES(?,'fa','album','sent','[9]',?)",[slot.key,new Date().toISOString()]);
  }
  if(scenario==='historic')db.sql("INSERT INTO ai_slots(slot,start_utc,end_utc,status,product) VALUES(?,?,?,'sent','p')",[slot.key,slot.start,slot.end]);
  let sent=0,requests=0,reject=true;
  globalThis.fetch=async(url,opts)=>{
   assert.ok(url.startsWith('https://api.telegram.org/'));
   const body=JSON.parse(opts.body);assert.ok(['@RazKeyhan','@CosmicInsightJWST'].includes(body.chat_id));
   if(scenario!=='legacy_partial'){
    assert.ok(url.endsWith('/sendMediaGroup'),'no standalone text permitted');
    assert.equal(body.media.length,4);
    assert.ok(visibleUnits(body.media[0].caption)<=1024);
    assert.ok(body.media[0].caption.includes('100,406'));
    assert.ok(body.media[0].caption.includes('https://t.me/news'));
    assert.equal(body.media.filter(x=>x.caption).length,1);
   }
   requests++;
   if(scenario==='timeout')throw new Error('uncertain acceptance');
   if(scenario==='rejected'&&reject){reject=false;return Response.json({ok:false},{status:429});}
   sent++;return Response.json({ok:true,result:url.endsWith('sendMediaGroup')?[{message_id:sent}]:{message_id:sent}});
  };
  if(scenario==='bad_caption'){await assert.rejects(()=>deliver(env,slot));assert.equal(requests,0);checks++;continue;}
  if(scenario==='race')await Promise.all([deliver(env,slot),deliver(env,slot)]);
  else await deliver(env,slot);
  if(scenario==='rejected')await deliver(env,slot);
  if(scenario==='duplicate'||scenario==='timeout')await deliver(env,slot);
  const status=db.sql('SELECT status FROM ai_slots WHERE slot=?',[slot.key]).results[0].status;
  if(scenario==='timeout'){assert.equal(status,'unverified');assert.equal(requests,1);}
  else {assert.equal(status,'sent');assert.equal(sent,scenario==='historic'?0:scenario==='legacy_partial'?3:2);}
  if(scenario==='historic')assert.equal(db.sql("SELECT payload FROM ai_queue WHERE product='p'").results[0].payload,JSON.stringify(bundle));
  checks++;
 } finally{rmSync(dir,{recursive:true,force:true});}
}
console.log('PASS: four Tehran windows, boundary checks, paired delivery, duplicate/race prevention, safe retry, ambiguous timeout ('+checks+' delivery scenarios)');
