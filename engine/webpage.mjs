// Anonymous, bounded webpage capture. All browser HTTP is fetched through guarded Node HTTP.
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright';
import fetch from 'node-fetch';
import {installNetwork} from './network.mjs';
import {browserOptions,renderFailure} from './browser-runtime.mjs';

installNetwork({});
export function validWebUrl(value){
 try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&['','80','443'].includes(u.port)&&!value.includes('\\')}catch{return false}
}
export async function capture(options){
 let browser,timer,stage='launch',mainStatus=0,requests=0,total=0,active=0,closing=false;
 const queue=[];
 const acquire=async()=>{if(active<4){active++;return}await new Promise(resolve=>queue.push(resolve))};
 const release=()=>{const next=queue.shift();if(next)next();else active--};
 try{
  if(!validWebUrl(options.url))return {ok:false,code:'web_address'};
  browser=await chromium.launch({...browserOptions(),args:[...browserOptions().args,'--force-webrtc-ip-handling-policy=disable_non_proxied_udp','--proxy-bypass-list=<-loopback>']});
  timer=setTimeout(()=>browser.close().catch(()=>{}),Math.max(1000,(options.timeout||45)*1000-5000));
  stage='page';
  const context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,
   locale:'zh-CN',serviceWorkers:'block',acceptDownloads:false,proxy:{server:'http://127.0.0.1:9'}});
  await context.addInitScript(()=>{for(const key of ['RTCPeerConnection','webkitRTCPeerConnection','WebTransport'])Object.defineProperty(globalThis,key,{value:undefined,configurable:false})});
  await context.routeWebSocket('**/*',route=>route.close());
  await context.route('**/*',async route=>{
   const request=route.request();const url=request.url();
   let acquired=false;
   try{
    if(++requests>150||total>25*1024*1024||request.method()!=='GET'||!validWebUrl(url))return await route.abort();
    if(['media','websocket'].includes(request.resourceType()))return await route.abort();
    await acquire();acquired=true;
    if(closing||total>25*1024*1024)return await route.abort();
    const response=await fetch(url,{redirect:'manual',size:5*1024*1024,signal:AbortSignal.timeout(request.isNavigationRequest()?12000:6000),
     headers:{'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36','Accept-Language':'zh-CN,zh;q=0.9'}});
    const body=Buffer.from(await response.arrayBuffer());total+=body.length;
    if(total>25*1024*1024)return await route.abort();
    if(request.isNavigationRequest()&&request.frame()===request.frame().page().mainFrame())mainStatus=response.status;
    const headers={};
    for(const key of ['content-type','location','content-security-policy','x-frame-options']){
     const value=response.headers.get(key);if(value)headers[key]=value;
    }
    if(/attachment/i.test(response.headers.get('content-disposition')||''))return await route.abort();
    await route.fulfill({status:response.status,headers,body});
   }catch{await route.abort().catch(()=>{})}finally{if(acquired)release()}
  });
  const page=await context.newPage();
  await page.goto(options.url,{waitUntil:'domcontentloaded',timeout:20000});
  if(mainStatus>=400)return {ok:false,code:'web_http',status:mainStatus};
  await page.waitForTimeout(1800);
  for(let i=1;i<=4;i++){await page.evaluate(y=>window.scrollTo(0,y),Math.min(options.height, i*900));await page.waitForTimeout(200)}
  await page.evaluate(()=>window.scrollTo(0,0));
  const height=Math.min(options.height,Math.max(900,await page.evaluate(()=>Math.max(document.body?.scrollHeight||0,document.documentElement.scrollHeight))));
  await page.screenshot({path:options.output,type:'jpeg',quality:82,fullPage:true,clip:{x:0,y:0,width:1280,height},animations:'disabled',timeout:12000});
  return {ok:true,height};
 }catch(error){return {ok:false,code:stage==='launch'?renderFailure(error):'web_load'}}
 finally{closing=true;clearTimeout(timer);await browser?.close()}
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href && process.argv[2]){
 const result=await capture(JSON.parse(await fs.readFile(process.argv[2],'utf8')));
 console.log(JSON.stringify(result));process.exit(result.ok?0:1);
}
