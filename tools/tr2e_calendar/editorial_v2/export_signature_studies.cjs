// Render the code-native signature overlays at exactly 400 x 600 pixels.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('url');
(async()=>{
 const out=path.resolve(__dirname,'../../../artifacts/tr2e_signature_studies');
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});
 await context.setOffline(true);
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(out,'index.html')).href);
 assert.equal(await page.locator('.card').count(),6);
 const data=await page.locator('#study-data').evaluate(e=>JSON.parse(e.textContent));
 await page.evaluate(data=>{
  const overview=document.createElement('section');overview.id='overview';
  overview.style.cssText='position:absolute;left:20px;top:20px;z-index:100;background:#f3f0e9;width:1000px;padding:32px;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif';
  overview.innerHTML='<div style="font-size:26px;margin-bottom:8px">Tr2e · 六种落款方向</div><p style="font-size:14px;color:#70756e;margin:0 0 24px">细节放大对比 · 完整日签效果请打开对比页</p><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px">'+data.variants.map(v=>`<div style="padding:18px;border:1px solid #d4d7cd;background:#fff"><div style="font-size:17px">${v.code} · ${v.name}${v.code==='C'?'　<span style="font-size:12px;color:#3d5b4b">推荐</span>':''}</div><img src="${v.patch}" style="display:block;width:195px;height:120px;image-rendering:pixelated;margin:12px auto 0"></div>`).join('')+'</div>';
  document.body.append(overview);
 },data);
 await page.locator('#overview img').evaluateAll(ims=>Promise.all(ims.map(im=>im.decode())));
 await page.locator('#overview').screenshot({path:path.join(out,'overview.png')});
 await page.locator('#overview').evaluate(e=>e.remove());
 if(process.argv.includes('--overview-only')){await browser.close();return}
 let exports=0;
 for(const date of data.dates){
  await page.locator(`[data-date="${date}"]`).click();
  for(const v of data.variants){
   await page.locator(`.card[data-variant="${v.code}"] .sheet`).click();
   const sheet=page.locator('#dialog-page .sheet');
   await sheet.locator('img').evaluateAll(ims=>Promise.all(ims.map(im=>im.decode())));
   // Centered dialogs can start at a half-pixel, which makes a 600px element
   // export as 601px and softens its bitmap. Snap the sheet to the pixel grid.
   await sheet.evaluate(el=>{const r=el.getBoundingClientRect();el.style.transform=`translate(${Math.round(r.x)-r.x}px,${Math.round(r.y)-r.y}px)`});
   const box=await sheet.boundingBox();assert.equal(box.width,400);assert.equal(box.height,600);
   // Export the same two UI layers on an integer canvas, so the device PNG
   // never inherits subpixel compositing/antialiasing from the modal window.
   const layers={base:'data:image/png;base64,'+fs.readFileSync(path.resolve(out,data.source,date+'.png')).toString('base64'),
                 patch:'data:image/png;base64,'+fs.readFileSync(path.join(out,v.patch)).toString('base64')};
   const png=await sheet.evaluate(async(el,layers)=>{
    const canvas=document.createElement('canvas');canvas.width=400;canvas.height=600;
    const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;
    const base=new Image(),patch=new Image();base.src=layers.base;patch.src=layers.patch;
    await Promise.all([base.decode(),patch.decode()]);
    ctx.drawImage(base,0,0,400,600);
    ctx.drawImage(patch,300,530,65,40);
    return canvas.toDataURL('image/png').split(',')[1];
   },layers);
   fs.writeFileSync(path.join(out,`${v.code}-${date}.png`),Buffer.from(png,'base64'));exports++;
   await page.locator('#close').click();
  }
 }
 await page.locator(`[data-date="${data.dates[0]}"]`).click();
 await page.screenshot({path:'/tmp/tr2e-signature-studies-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:'/tmp/tr2e-signature-studies-mobile.png'});
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'browser_audit.json'),JSON.stringify({exports,offline:true,variants:6,days:3,mobile_no_overflow:true,errors},null,2)+'\n');
 console.log(JSON.stringify({exports,errors}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
