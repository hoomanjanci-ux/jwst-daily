// Independent scheduled sender. No official-news destinations, feeds or credentials.
const CHANNELS={fa:'@RazKeyhan',en:'@CosmicInsightJWST'};
const HOURS=[6,9,12,18];
export function slotAt(date=new Date()) {
 const local=new Date(date.getTime()+210*60000),hour=local.getUTCHours();
 if(!HOURS.includes(hour))return null;
 const day=local.toISOString().slice(0,10),start=new Date(`${day}T${String(hour).padStart(2,'0')}:00:00+03:30`);
 return {key:`${day}/${String(hour).padStart(2,'0')}`,start:start.toISOString(),end:new Date(+start+3600000).toISOString()};
}
const one=(env,sql,...args)=>env.DB.prepare(sql).bind(...args).first();
const run=(env,sql,...args)=>env.DB.prepare(sql).bind(...args).run();
async function setting(env,key,value) {
 await run(env,'INSERT INTO ai_control(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',key,String(value));
}
async function dispatch(env,force=false) {
 const count=await one(env,"SELECT count(*) AS n FROM ai_queue WHERE status='ready'");
 if(!force&&count.n>=8)return;
 const last=await one(env,"SELECT value FROM ai_control WHERE key='last_dispatch'");
 if(!force&&last&&Date.now()-Date.parse(last.value)<(count.n<4?900000:3600000))return;
 if(!env.GH_ANALYSIS_DISPATCH_TOKEN){await setting(env,'dispatch_error','missing token');return;}
 const r=await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/jwst-analysis.yml/dispatches`,{
  method:'POST',headers:{Authorization:`Bearer ${env.GH_ANALYSIS_DISPATCH_TOKEN}`,Accept:'application/vnd.github+json','User-Agent':'jwst-analysis-scheduler'},body:JSON.stringify({ref:'main'})});
 await setting(env,'dispatch_http',r.status);
 if(r.status===204)await setting(env,'last_dispatch',new Date().toISOString());
}
export function visibleUnits(text) {
 return text.replace(/<[^>]*>/g,'').replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos);/gi,(_,e)=>{
  if(e[0]==='#')return String.fromCodePoint(e[1].toLowerCase()==='x'?parseInt(e.slice(2),16):parseInt(e.slice(1),10));
  return {amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"}[e.toLowerCase()];
 }).length;
}
const esc=v=>String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;');
export function albumCaption(bundle,lang) {
 const c=bundle.canonical||{},m=bundle.meta||{},s=c.statistics||{},post=bundle.translations[lang];
 if(!Number.isFinite(s.sample_count)||!Number.isFinite(s.above_5scatter_percent))throw Error('Measured analysis evidence missing');
 const pos=post.text.lastIndexOf('———');if(pos<0)throw Error('Analysis footer missing');
 const footer=post.text.slice(pos),links=[...new Set(post.text.slice(0,pos).match(/<a\s+href="[^"]+"[^>]*>.*?<\/a>/gs)||[])];
 if(!links.length)throw Error('Analysis source link missing');
 const target=esc(c.target||m.TARGNAME||'JWST'),filter=c.filter||m.FILTER||'—';
 const facts=`${esc(m.INSTRUME||'JWST')}/${esc(filter)} · ${esc(String(m['DATE-OBS']||'—').slice(0,10))}`;
 const n=Number(s.sample_count).toLocaleString('en-US'),p=s.above_5scatter_percent;
 let extra='',wave='';
 if(s.brightest_quadrant_percent!=null)extra=lang==='fa'?` سهم پُرتراکم‌ترین ربع از این پیکسل‌ها: ${s.brightest_quadrant_percent}٪.`:` The most populated quadrant holds ${s.brightest_quadrant_percent}% of these pixels.`;
 const match=String(filter).match(/^F(\d{3})(?:W2|[WMN])$/);
 if(match&&String(m.INSTRUME).toUpperCase()==='NIRCAM'){
  const w=Number(match[1])/100;
  wave=lang==='fa'?` طول موج تقریبی: ${w} میکرومتر (فروسرخ نزدیک).`:` Approx. wavelength: ${w} µm (near-infrared).`;
 }
 const title=lang==='fa'?'راز کیهان | تحلیل داده':'COSMIC INSIGHT | Data analysis';
 const body=lang==='fa'?`از ${n} پیکسل معتبرِ نمونه، ${p}٪ بیش از پنج برابر پراکندگی مقاوم بالاتر از میانه‌اند.${extra}${wave}`:`Of ${n} valid sampled pixels, ${p}% exceed the median by more than five robust-scatter units.${extra}${wave}`;
 const note=lang==='fa'?'این سنجه الگوی روشنایی را توصیف می‌کند، نه شمارش ستاره یا کشف جرم.':'This describes brightness patterns, not a star count or a discovery.';
 const mode=lang==='fa'?(c.ai_assisted?'محاسبات FITS؛ انتخاب محور با کمک هوش مصنوعی.':'محاسبات مستقیم FITS؛ متن تولیدشده با مدل نیست.'):(c.ai_assisted?'FITS calculations; AI-assisted focus selection.':'Direct FITS calculations; not model-generated prose.');
 const text=`🔬 <b>${title}</b>\n<b>${target}</b> · ${facts}\n\n${body}\n\n${note}\n<i>${mode}</i>\n📡 ${links.join(' · ')} · median+5×1.4826×MAD\n\n${footer}`;
 if(visibleUnits(text)>1024)throw Error('Complete album caption exceeds Telegram limit');
 return text;
}
async function sendOnce(env,chat,part,post,images) {
 const method=['album','album_v1'].includes(part)?'sendMediaGroup':'sendMessage';
 const data=['album','album_v1'].includes(part)?{chat_id:chat,media:images.map((url,i)=>({type:'photo',media:url,...(i===0?{caption:post.caption,parse_mode:'HTML'}:{})}))}:{chat_id:chat,text:post.text,parse_mode:'HTML'};
 let r,json;
 try { r=await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/${method}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(35000)});json=await r.json(); }
 catch {return {status:'unverified'};}
 if(r.status>=400&&r.status<500)return {status:'rejected'};
 if(!r.ok||!json.ok)return {status:'unverified'};
 const messages=Array.isArray(json.result)?json.result:[json.result];
 const ids=messages.map(x=>x?.message_id).filter(Number.isInteger);
 return ids.length?{status:'sent',ids}:{status:'unverified'};
}
export async function deliver(env,slot) {
 await run(env,'INSERT OR IGNORE INTO ai_slots(slot,start_utc,end_utc,status) VALUES(?,?,?,?)',slot.key,slot.start,slot.end,'waiting');
 let record=await one(env,'SELECT * FROM ai_slots WHERE slot=?',slot.key);
 if(['sent','unverified','expired'].includes(record.status))return false;
 if(!record.product) {
  await run(env,`UPDATE ai_slots SET product=(SELECT product FROM ai_queue WHERE status='ready' AND product NOT IN (SELECT product FROM ai_slots WHERE product IS NOT NULL)
 AND (json_extract(payload,'$.combo') IS NULL OR json_extract(payload,'$.combo') NOT IN
 (SELECT json_extract(payload,'$.combo') FROM ai_queue WHERE json_extract(payload,'$.combo') IS NOT NULL
 AND (status='reserved' OR (status='published' AND julianday(published_utc)>julianday('now')-coalesce(json_extract(payload,'$.repeat_after_days'),14))))) ORDER BY created_utc LIMIT 1) WHERE slot=? AND product IS NULL`,slot.key);
  record=await one(env,'SELECT * FROM ai_slots WHERE slot=?',slot.key);
  if(!record.product){await run(env,'UPDATE ai_slots SET note=? WHERE slot=?','no approved paired reserve',slot.key);return false;}
  await run(env,"UPDATE ai_queue SET status='reserved',slot=? WHERE product=? AND status='ready'",slot.key,record.product);
 }
 const row=await one(env,'SELECT payload FROM ai_queue WHERE product=?',record.product),bundle=JSON.parse(row.payload);
 if(!bundle.translations?.fa||!bundle.translations?.en||bundle.image_urls?.length<2)throw Error('Invalid paired reserve');
 // Existing partial publications finish in their original format. Never replay
 // historical albums or mix layouts mid-publication. Unsent reserves upgrade now.
 const prior=await env.DB.prepare('SELECT part FROM ai_receipts WHERE slot=?').bind(slot.key).all();
 const legacy=prior.results.some(r=>r.part==='album'||r.part==='text');
 if(!legacy){
  for(const lang of ['fa','en']){
   bundle.translations[lang].caption=albumCaption(bundle,lang);
   bundle.translations[lang].delivery_layout='album_v1';
  }
  bundle.delivery_layout='album_v1';
  await run(env,'UPDATE ai_queue SET payload=? WHERE product=?',JSON.stringify(bundle),record.product);
 }
 for(const lang of ['fa','en'])for(const part of (legacy?['album','text']:['album_v1'])) {
  if(new Date()>=new Date(slot.end))return false;
  const existing=await one(env,'SELECT status,updated_utc FROM ai_receipts WHERE slot=? AND lang=? AND part=?',slot.key,lang,part);
  if(existing?.status==='sent')continue;
  // A persisted sending intent may be in-flight or crash-ambiguous. Never duplicate it.
  if(existing&&['sending','unverified'].includes(existing.status)) {
   if(existing.status==='unverified'||Date.now()-Date.parse(existing.updated_utc)>120000)
    await run(env,"UPDATE ai_slots SET status='unverified',note=? WHERE slot=?",`${lang}/${part}: ambiguous receipt`,slot.key);
   return false;
  }
  const now=new Date().toISOString();
  const claim=existing?await run(env,"UPDATE ai_receipts SET status='sending',updated_utc=? WHERE slot=? AND lang=? AND part=? AND status='rejected'",now,slot.key,lang,part):await run(env,"INSERT OR IGNORE INTO ai_receipts(slot,lang,part,status,updated_utc) VALUES(?,?,?,'sending',?)",slot.key,lang,part,now);
  if(claim.meta.changes!==1)return false;
  const result=await sendOnce(env,CHANNELS[lang],part,bundle.translations[lang],bundle.image_urls);
  await run(env,'UPDATE ai_receipts SET status=?,ids=?,updated_utc=? WHERE slot=? AND lang=? AND part=?',result.status,JSON.stringify(result.ids||[]),new Date().toISOString(),slot.key,lang,part);
  if(result.status!=='sent'){
   await run(env,'UPDATE ai_slots SET status=?,note=? WHERE slot=?',result.status==='unverified'?'unverified':'retryable',`${lang}/${part}: ${result.status}`,slot.key);return false;
  }
 }
 const now=new Date().toISOString();
 await env.DB.batch([
  env.DB.prepare("UPDATE ai_slots SET status='sent',completed_utc=?,note=NULL WHERE slot=?").bind(now,slot.key),
  env.DB.prepare("UPDATE ai_queue SET status='published',published_utc=? WHERE product=?").bind(now,record.product)
 ]);
 await dispatch(env,true); // archive/site sync immediately, not at the next GitHub cron.
 return true;
}
export async function tick(env) {
 await setting(env,'heartbeat',new Date().toISOString());
 const enabled=await one(env,"SELECT value FROM ai_control WHERE key='sender'");
 if(enabled?.value!=='cloudflare')return {active:false};
 const day=new Date(Date.now()+210*60000).toISOString().slice(0,10);
 for(const hour of HOURS){
  const start=new Date(`${day}T${String(hour).padStart(2,'0')}:00:00+03:30`),end=new Date(+start+3600000);
  await run(env,'INSERT OR IGNORE INTO ai_slots(slot,start_utc,end_utc,status) VALUES(?,?,?,?)',`${day}/${String(hour).padStart(2,'0')}`,start.toISOString(),end.toISOString(),new Date()>=end?'expired':'waiting');
 }
 const slot=slotAt();let published=false;
 if(slot)published=await deliver(env,slot);
 await run(env,"UPDATE ai_slots SET status='expired' WHERE end_utc<? AND status IN ('waiting','retryable')",new Date().toISOString());
 await dispatch(env);
 const ready=await one(env,"SELECT count(*) AS n FROM ai_queue WHERE status='ready'");
 return {active:true,published,ready:ready.n,slot:slot?.key||null};
}
export default {
 async scheduled(event,env,ctx){ctx.waitUntil(tick(env));},
 async fetch(request,env) {
  if(request.headers.get('Authorization')!==`Bearer ${env.ADMIN_TOKEN}`)return new Response('Not found',{status:404});
  try {
   if(new URL(request.url).pathname==='/tick'&&request.method==='POST')return Response.json(await tick(env));
   const heartbeat=await one(env,"SELECT value FROM ai_control WHERE key='heartbeat'");
   const slots=await env.DB.prepare('SELECT slot,status,completed_utc,note FROM ai_slots ORDER BY slot DESC LIMIT 8').all();
   return Response.json({heartbeat:heartbeat?.value,slots:slots.results});
  }catch(e){return Response.json({error_type:e.name},{status:500});}
 }
};
