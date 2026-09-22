import readline from 'node:readline';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import YAML from 'yaml';
import {installNetwork} from './network.mjs';
import renderer from './lib/puppeteer/puppeteer.js';

const output=process.stdout.write.bind(process.stdout);
const emit=x=>output(JSON.stringify(x)+'\n');
// Source logs often contain signed URLs or cookies. Emit only error classes via RPC.
const silent=()=>{};
globalThis.logger=new Proxy({}, {get:()=>silent});
for(const k of ['log','info','warn','error','debug','trace']) console[k]=silent;
let serial=0;
const pending=new Map(),background=new Set(),intervals=new Set();
function track(promise){
 background.add(promise);promise.finally(()=>background.delete(promise)).catch(silent);return promise;
}
function call(op,data) {
 const id=++serial;
 const promise=new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});emit({id,op,data})});
 background.add(promise); promise.finally(()=>background.delete(promise)).catch(silent);
 return promise;
}
const lines=readline.createInterface({input:process.stdin});
let boot;
const first=new Promise(resolve=>boot=resolve);
lines.on('line',line=>{
 try {const x=JSON.parse(line);if(x.start){boot(x);return}
 const p=pending.get(x.id);if(!p)return;pending.delete(x.id);
 x.error?p.reject(new Error(x.error)):p.resolve(x.result);
 }catch{emit({op:'fatal',data:{type:'ProtocolError'}})}
});
const initial=await first;
const root=path.dirname(fileURLToPath(import.meta.url));
const work=path.resolve(initial.work);fs.mkdirSync(work,{recursive:true});process.chdir(work);
globalThis.rc={work,root,call,track,requests:0,children:0,config:initial.config,ignoreSchedule:silent};
installNetwork(initial.config);
const timer=setInterval;
const clear=clearInterval;
globalThis.setInterval=(fn,ms,...args)=>{
 let running=false;
 const handle=timer(async()=>{if(running)return;running=true;try{await fn(...args)}catch{emit({op:'diagnostic',data:{type:'PollingError'}})}finally{running=false}},ms);
 intervals.add(handle);return handle;
};
globalThis.clearInterval=handle=>{intervals.delete(handle);clear(handle)};
globalThis.plugin=class {
 constructor(options){Object.assign(this,options)}
 reply(...args){return this.e.reply(...args)}
};
const media=(type,file)=>({type,file:Buffer.isBuffer(file)?'base64://'+file.toString('base64'):file});
globalThis.segment={image:file=>media('image',file),video:file=>media('video',file),record:file=>media('record',file),
 text:text=>({type:'text',text}),at:qq=>({type:'at',qq}),file:file=>media('file',file),json:data=>({type:'json',data})};
globalThis.redis={get:key=>call('state_get',{key}),set:(key,value,...rest)=>call('state_set',{key,value,rest}),
 exists:async key=>Number(await call('state_get',{key})!==null),del:key=>call('state_del',{key})};
const msg=initial.event;
const api=(action,params={})=>call('onebot',{action,params});
globalThis.Bot={makeForwardMsg:async rows=>({type:'node',data:rows}),sendApi:api,
 pickUser:id=>({sendMsg:message=>call('reply',{message,private:true,user_id:id})}),
 pickGroup:id=>({sendMsg:message=>call('reply',{message,group_id:id})})};
const upload=file=>call('upload',{file});
const e={...msg,bot:Bot,reply:(message)=>call('reply',{message}),
 group:{sendFile:upload,fs:{upload}},friend:{sendFile:upload},
 runtime:{common:{makeForwardMsg:async(_e,rows)=>Bot.makeForwardMsg(rows)}},
 getReply:()=>call('get_reply',{}),getReplyMsg:()=>call('get_reply',{})};
try {
 const entries=[];
 for(const [file,key] of [['help','help'],['query','query'],['songRequest','songRequest'],['switchers','switchers'],['tools','tools'],['update','Update']]) {
  const module=await import(`./plugins/rconsole-plugin/apps/${file}.js`);
  const app=new module[key]();app.e=e;
  for(const name of Object.getOwnPropertyNames(Object.getPrototypeOf(app))){
   const original=app[name];
   if(typeof original==='function'&&original.constructor.name==='AsyncFunction')
    app[name]=(...args)=>track(original.apply(app,args));
  }
  entries.push([file,app]);
 }
 // Replace the generic summary path with AstrBot's selected model and bounded public fetch.
 const tool=entries.find(([name])=>name==='tools')[1];
 if(!initial.config.aiBaseURL||!initial.config.aiApiKey)
  tool._generalLinkShareSummary=async(_e,url)=>{await e.reply('正在读取文章并总结…');return e.reply(await call('summarize',{url}))};
 if(initial.inventory){emit({op:'inventory',data:entries.flatMap(([app,obj])=>obj.rule.map(r=>({app,...r})))})}
 else {
  const entry=entries.find(([name])=>name===initial.route.app);
  const rule=entry?.[1].rule.find(r=>r.fnc===initial.route.fnc);
  if(!rule || (rule.permission==='master'&&!e.isMaster)) throw Error('PermissionError');
  await entry[1][rule.fnc](e);
 }
 // Upstream QR methods create timers; wait for both their polling and un-awaited replies.
 let quiet=0;
 while(quiet<5){
  await new Promise(resolve=>setTimeout(resolve,100));
  quiet=(intervals.size||background.size||rc.requests||rc.children)?0:quiet+1;
 }
 await renderer.shutdown();emit({op:'done'});process.exit(0);
}catch(error){emit({op:'fatal',data:{type:error?.code||error?.name||'Error'}});process.exit(1)}
