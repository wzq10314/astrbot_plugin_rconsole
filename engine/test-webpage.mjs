// Test-only loopback transport for a public-name fixture; production keeps its DNS/network guard.
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const seen=[];
const server=http.createServer((req,res)=>{
 seen.push({url:req.url,method:req.method,cookie:req.headers.cookie});
 if(req.url==='/redirect'){res.writeHead(302,{location:'http://127.0.0.1/private'});res.end();return}
 if(req.url==='/bad'){res.writeHead(403);res.end('Denied');return}
 if(req.url==='/app.js'){res.setHeader('Content-Type','application/javascript');res.end(`document.querySelector('h1').textContent='网页自动截图 · JavaScript 已加载';fetch('/loaded');fetch('http://127.0.0.1/private').catch(()=>{});fetch('/write',{method:'POST',body:'no'}).catch(()=>{});`);return}
 if(req.url==='/loaded'){res.end('ok');return}
 if(req.url==='/style.css'){res.setHeader('Content-Type','text/css');res.end('body{margin:0;background:#eff3f8;color:#17324a;font:24px sans-serif}main{margin:60px;max-width:1000px}h1{font-size:48px;color:#136d70}.box{padding:30px;background:white;margin:28px 0;border-radius:20px}');return}
 res.setHeader('Content-Type','text/html;charset=utf-8');
 res.end(`<!doctype html><html><head><link rel="stylesheet" href="/style.css"></head><body><main><h1>Loading</h1><div class="box">普通网页直接截图，已有解析平台继续优先处理。</div><div class="box">动态脚本、样式与长页面测试</div><div style="height:2200px">下方留白用于验证截图高度上限</div></main><script src="/app.js"></script></body></html>`);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const original=http.request;
http.request=function(options,callback){
 if(options.hostname==='fixture.test')return original.call(this,{...options,hostname:'127.0.0.1',port:server.address().port},callback);
 return original.call(this,options,callback);
};
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'rconsole-web-test-'));
try{
 const {capture,validWebUrl}=await import('./webpage.mjs');
 assert.equal(validWebUrl('https://user:password@example.com/'),false);
 assert.equal(validWebUrl('file:///etc/passwd'),false);
 assert.equal(validWebUrl('http://example.com:8000/'),false);
 const output=path.join(temp,'page.jpg');
 const result=await capture({url:'http://fixture.test/page',height:1500,timeout:30,output});
 assert.equal(result.ok,true,JSON.stringify(result));assert.equal(result.height,1500);
 assert.ok((await fs.stat(output)).size>15000);
 const jpeg=await fs.readFile(output);let dimensions;
 for(let offset=2;offset+9<jpeg.length;){
  const marker=jpeg[offset+1];offset+=2;
  if([0xc0,0xc1,0xc2].includes(marker)){dimensions=[jpeg.readUInt16BE(offset+5),jpeg.readUInt16BE(offset+3)];break}
  if(marker===0xda)break;offset+=jpeg.readUInt16BE(offset);
 }
 assert.deepEqual(dimensions,[1280,1500],'Output must include below-the-fold content');
 assert.ok(seen.some(x=>x.url==='/loaded'),'Browser JS should execute');
 assert.ok(seen.every(x=>x.method==='GET'&&!x.cookie));
 assert.ok(!seen.some(x=>x.url==='/private'||x.url==='/write'));
 if(process.argv[2])await fs.copyFile(output,process.argv[2]);
 assert.equal((await capture({url:'http://fixture.test/bad',height:900,timeout:30,output})).code,'web_http');
 assert.equal((await capture({url:'http://fixture.test/redirect',height:900,timeout:30,output})).ok,false);
 assert.equal((await capture({url:'http://127.0.0.1/private',height:900,timeout:30,output})).ok,false);
 console.log('Webpage capture passed: real Chromium, JavaScript/CSS, height limit, HTTP error, private navigation/redirect/subresource and POST denial.');
}finally{
 server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
 if(!path.resolve(temp).startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('Unsafe temporary cleanup path');
 await fs.rm(temp,{recursive:true,force:true});
}
