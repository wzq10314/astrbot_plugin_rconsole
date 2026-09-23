import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import template from 'art-template';
import {chromium} from 'playwright';
import {browserOptions,renderFailure} from '../../browser-runtime.mjs';

export default {
 browser:null,
 async browserInit(){if(!this.browser?.isConnected())this.browser=await chromium.launch(browserOptions());return this.browser},
 async shutdown(){await this.browser?.close();this.browser=null},
 async screenshot(name,data) {
  let browser,file,stage='template';
  try {
    const html=template(data.tplFile,{resPath:data.pluResPath,...data});
    file=path.join(globalThis.rc.work,`render-${String(name).replace(/[^a-z0-9_-]/gi,'_')}-${Date.now()}.html`);
    await fs.writeFile(file,html);
    stage='launch';
    browser=await chromium.launch(browserOptions());
    stage='page';
    const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1,javaScriptEnabled:false});
    const assets=new Map();
    await page.route(/^https?:\/\//,async route=>{
      try {
        if(route.request().resourceType()!=='image')return await route.abort();
        const url=route.request().url();
        if(!assets.has(url)){
          if(assets.size>=32)return await route.abort();
          assets.set(url,globalThis.rc.call('render_asset',{url}));
        }
        const asset=await assets.get(url);
        if(!asset?.data)return await route.abort();
        await route.fulfill({status:200,contentType:asset.mime,body:Buffer.from(asset.data,'base64')});
      }catch{await route.abort().catch(()=>{})}
    });
    await page.goto(pathToFileURL(file).href,{waitUntil:'domcontentloaded',timeout:20000});
    // Remote covers must not make a static card wait for network-idle forever.
    let timer;
    try {await Promise.race([
      page.evaluate(()=>Promise.all([document.fonts.ready,...Array.from(document.images).map(i=>i.complete?Promise.resolve():new Promise(r=>{i.onload=r;i.onerror=r}))])),
      new Promise(r=>{timer=setTimeout(r,8000)})
    ])}finally{clearTimeout(timer)}
    const element=page.locator('#container,.container').first();
    const buffer=await element.count()?await element.screenshot({timeout:15000,animations:'disabled'}):await page.screenshot({fullPage:true,animations:'disabled'});
    await globalThis.rc.call('render_status',{code:'ready'});
    return segment.image(buffer);
  } catch(e) {
    // Keep the query usable without Chromium; never dump credentials from model data.
    return globalThis.rc.call('render_text',{name,data,code:renderFailure(e,stage)});
  } finally {await browser?.close();if(file)await fs.unlink(file).catch(()=>{})}
}};
