import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import template from 'art-template';
import {chromium} from 'playwright';

export default {
 browser:null,
 async browserInit(){if(!this.browser?.isConnected())this.browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});return this.browser},
 async shutdown(){await this.browser?.close();this.browser=null},
 async screenshot(name,data) {
  let browser;
  try {
    const html=template(data.tplFile,{resPath:data.pluResPath,...data});
    const file=path.join(globalThis.rc.work,`render-${name}-${Date.now()}.html`);
    await fs.writeFile(file,html);
    browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
    const page=await browser.newPage({viewport:{width:1000,height:900},deviceScaleFactor:1});
    await page.goto(pathToFileURL(file).href,{waitUntil:'networkidle',timeout:20000});
    const element=page.locator('#container,.container').first();
    const buffer=await element.count()?await element.screenshot({timeout:15000}):await page.screenshot({fullPage:true});
    return segment.image(buffer);
  } catch(e) {
    // Keep the query usable without Chromium; never dump credentials from model data.
    return globalThis.rc.call('render_text',{name,data});
  } finally {await browser?.close()}
}};
