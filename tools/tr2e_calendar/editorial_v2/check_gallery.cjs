// Run with Playwright available on NODE_PATH. Opens only local generated files.
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const assert=require('node:assert/strict');

(async()=>{
  const out=path.resolve(__dirname,'../../../artifacts/tr2e_calendar_2027_editorial_v2_1');
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:1280,height:1000}});
  await context.setOffline(true);
  const page=await context.newPage();
  const errors=[],remoteRequests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(/^https?:/.test(r.url()))remoteRequests.push(r.url())});
  await page.goto(pathToFileURL(path.join(out,'index.html')).href);
  assert.equal(await page.locator('.card').count(),31);
  await page.getByRole('button',{name:'2月',exact:true}).click();
  assert.equal(await page.locator('.card').count(),28);
  await page.getByRole('button',{name:'全年',exact:true}).click();
  assert.equal(await page.locator('.card').count(),365);
  const images=await page.evaluate(async()=>{
    const data=JSON.parse(document.getElementById('calendar-data').textContent);
    return Promise.all(data.cards.map(d=>new Promise(resolve=>{
      const im=new Image();im.onload=()=>resolve({date:d.date,ok:im.naturalWidth===400&&im.naturalHeight===600});
      im.onerror=()=>resolve({date:d.date,ok:false});im.src=d.image;
    })));
  });
  assert(images.every(x=>x.ok));
  await page.locator('#search').fill('库切');
  assert((await page.locator('.card').count())>0);
  assert((await page.locator('#grid').innerText()).includes('库切'));
  await page.locator('#search').fill('');
  await page.locator('#anchors').click();
  assert.equal(await page.locator('.card').count(),41);
  await page.locator('#anchors').click();
  await page.locator('#jump').fill('2027-06-21');
  assert(await page.locator('#viewer').evaluate(e=>e.open));
  assert((await page.locator('#detail').innerText()).includes('默契'));
  assert(!(await page.locator('#viewer').innerText()).includes('结婚'));
  await page.keyboard.press('ArrowRight');
  assert((await page.locator('#viewer-date').innerText()).includes('2027-06-22'));
  await page.locator('#close').click();
  await page.locator('#jump').fill('2027-08-08');
  assert((await page.locator('#viewer-date').innerText()).includes('七夕·立秋'));
  await page.screenshot({path:'/tmp/tr2e-2027-detail.png'});
  await page.keyboard.press('Escape');
  assert(!(await page.locator('#viewer').evaluate(e=>e.open)));
  await page.getByRole('button',{name:'1月',exact:true}).click();
  await page.screenshot({path:'/tmp/tr2e-2027-desktop.png'});
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  assert.equal(await page.locator('.card').count(),31);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'/tmp/tr2e-2027-mobile.png'});
  await page.locator('#jump').fill('2027-11-11');
  assert((await page.locator('#detail').innerText()).includes('好奇心'));
  assert(await page.locator('#viewer').evaluate(e=>e.scrollWidth<=e.clientWidth));
  await page.locator('#close').click();
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  const result={offline_file_url:true,all_images_loaded:images.length,desktop_month_filter:true,
    search:true,anchor_filter_count:41,date_jump:true,keyboard_navigation:true,
    overlapping_festivals:true,private_meaning_not_labeled:true,mobile_no_horizontal_overflow:true,
    javascript_errors:errors,remote_requests:remoteRequests};
  fs.writeFileSync(path.join(out,'browser_audit.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result,null,2));
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
