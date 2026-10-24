// Run after npm run build, against a server serving out/ (or the live site).
// Optional test dependency: npm install --no-save --package-lock=false playwright
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const data = JSON.parse(fs.readFileSync('data/content.json', 'utf8'));
const base = process.env.TEST_SITE_URL || 'http://127.0.0.1:8080';
const posts = data.analyses.filter(a => a.text_fa && !a.is_mock);
const forbidden = /CosmicNewsJWST|CosmicInsightJWST|COSMIC INSIGHT|COSMIC NEWS|دو کانال انگلیسی|نسخه‌های انگلیسی/i;
(async () => {
 const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
 let checks = 0;
 try {
  for (const width of [320,360,375,390,414,560,640,767,768,1440]) {
   const context = await browser.newContext({viewport:{width,height:844},isMobile:width<768,hasTouch:width<768});
   const page = await context.newPage();
   for (const a of posts) {
    const response = await page.goto(`${base}/post/${a.slug}`,{waitUntil:'networkidle'});
    assert.equal(response.status(),200,a.slug);
    const metrics = await page.evaluate(() => ({
      viewport:document.documentElement.clientWidth,inner:innerWidth,
      scroll:document.documentElement.scrollWidth,
      outside:[...document.querySelectorAll('main *')].filter(e=>{
       const r=e.getBoundingClientRect();return r.left < -1 || r.right > document.documentElement.clientWidth+1;
      }).map(e=>e.tagName+':'+e.className).slice(0,5)
    }));
    assert.equal(metrics.inner,width,`${width} ${a.slug}: inflated viewport ${JSON.stringify(metrics)}`);
    assert.ok(metrics.scroll<=width+1,`${width}: horizontal scrolling`);
    assert.deepEqual(metrics.outside,[],`${width} ${a.slug}: cropped content`);
    assert.ok(!forbidden.test(await page.content()),'English channel leaked');
    checks++;
   }
   await context.close();
  }
  const p=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  await p.goto(base,{waitUntil:'networkidle'});
  assert.ok(!forbidden.test(await p.content()),'English channel on homepage');
  await p.goto(base+'/?tab=analysis#tazeha',{waitUntil:'networkidle'});
  const card=p.locator(`a[href="/post/${posts[0].slug}"]`).first();
  await card.scrollIntoViewIfNeeded();
  await card.tap();
  await p.waitForURL(new RegExp('/post/'+posts[0].slug+'/?$'));
  assert.equal(await p.evaluate(()=>innerWidth),390,'Tap navigation changed mobile viewport');
  console.log(`PASS: ${checks} analysis/viewport combinations + mobile tap navigation + Persian-only links`);
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
