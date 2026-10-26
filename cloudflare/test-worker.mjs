import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {slotAt,deliver} from './analysis-worker.mjs';
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
for(const scenario of ['normal','duplicate','rejected','timeout','race']){
 const dir=mkdtempSync(join(tmpdir(),'analysis-worker-'));const db=new DB(join(dir,'db.sqlite'));
 try {
  db.sql(readFileSync(new URL('./analysis.sql',import.meta.url),'utf8'),[],'schema');
  const bundle={translations:{fa:{caption:'FA',text:'FA same research'},en:{caption:'EN',text:'EN same research'}},image_urls:['https://example.com/0.jpg','https://example.com/1.jpg']};
  db.sql("INSERT INTO ai_queue(product,payload,status,created_utc) VALUES(?,?,'ready',?)",['p',JSON.stringify(bundle),new Date().toISOString()]);
  const env={DB:db,TG_BOT_TOKEN:'dummy'},slot={key:'test/06',start:new Date(Date.now()-60000).toISOString(),end:new Date(Date.now()+300000).toISOString()};
  let sent=0,requests=0,reject=true;
  globalThis.fetch=async(url,opts)=>{
   assert.ok(url.startsWith('https://api.telegram.org/'));
   const body=JSON.parse(opts.body);assert.ok(['@RazKeyhan','@CosmicInsightJWST'].includes(body.chat_id));
   requests++;
   if(scenario==='timeout')throw new Error('uncertain acceptance');
   if(scenario==='rejected'&&reject){reject=false;return Response.json({ok:false},{status:429});}
   sent++;return Response.json({ok:true,result:url.endsWith('sendMediaGroup')?[{message_id:sent}]:{message_id:sent}});
  };
  if(scenario==='race')await Promise.all([deliver(env,slot),deliver(env,slot)]);
  else await deliver(env,slot);
  if(scenario==='rejected')await deliver(env,slot);
  if(scenario==='duplicate'||scenario==='timeout')await deliver(env,slot);
  const status=db.sql('SELECT status FROM ai_slots WHERE slot=?',[slot.key]).results[0].status;
  if(scenario==='timeout'){assert.equal(status,'unverified');assert.equal(requests,1);}
  else {assert.equal(status,'sent');assert.equal(sent,4);}
  checks++;
 } finally{rmSync(dir,{recursive:true,force:true});}
}
console.log('PASS: four Tehran windows, boundary checks, paired delivery, duplicate/race prevention, safe retry, ambiguous timeout ('+checks+' delivery scenarios)');
