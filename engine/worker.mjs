import readline from 'node:readline';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import YAML from 'yaml';
import {installNetwork} from './network.mjs';
import {createDiagnostics,installFetchDiagnostics,safeError} from './diagnostics.mjs';
import renderer from './lib/puppeteer/puppeteer.js';

const output=process.stdout.write.bind(process.stdout);
const emit=x=>output(JSON.stringify(x)+'\n');
// Source logs often contain signed URLs or cookies. Emit only error classes via RPC.
const silent=()=>{};
globalThis.logger=new Proxy({}, {get:()=>silent});
for(const k of ['log','info','warn','error','debug','trace']) console[k]=silent;
let serial=0;
const pending=new Map(),background=new Set(),intervals=new Set();
const diagnostics=createDiagnostics({emit,counters:()=>({
 requests:globalThis.rc?.requests||0,children:globalThis.rc?.children||0,
 background:background.size,intervals:intervals.size
})});
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
installNetwork(initial.config,diagnostics);
installFetchDiagnostics(diagnostics);
const timer=setInterval;
const clear=clearInterval;
let diagnosticStage='worker';
// Use the native timer so diagnostics never keep the upstream idle loop alive.
const diagnosticTimer=timer(()=>diagnostics.snapshot(diagnosticStage),10000);
diagnosticTimer.unref();
globalThis.setInterval=(fn,ms,...args)=>{
 let running=false;
 const handle=timer(async()=>{if(running)return;running=true;try{await fn(...args)}catch(error){diagnostics.record({stage:'idle',event:'error',error:safeError(error)})}finally{running=false}},ms);
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
const workerSpan=diagnostics.begin('worker');
try {
 const entries=[],methodNames=new Map();
 for(const [file,key] of [['help','help'],['query','query'],['songRequest','songRequest'],['switchers','switchers'],['tools','tools'],['update','Update']]) {
  const module=await import(`./plugins/rconsole-plugin/apps/${file}.js`);
  const app=new module[key]();app.e=e;
  const names=new Map();methodNames.set(file,names);
  for(const name of Object.getOwnPropertyNames(Object.getPrototypeOf(app))){
   const original=app[name];
   if(typeof original==='function'&&original.constructor.name==='AsyncFunction'){
    const diagnosticName=diagnostics.registerMethod(file,name);names.set(name,diagnosticName);
    app[name]=(...args)=>track(diagnostics.run('method',{name:diagnosticName},()=>original.apply(app,args)));
   }
  }
  entries.push([file,app]);
 }
 // Replace the generic summary path with AstrBot's selected model and bounded public fetch.
 const tool=entries.find(([name])=>name==='tools')[1];
 if(!initial.config.aiBaseURL||!initial.config.aiApiKey)
  tool._generalLinkShareSummary=(_e,url)=>track(diagnostics.run('method',
   {name:methodNames.get('tools').get('_generalLinkShareSummary')},
   async()=>{await e.reply('正在读取文章并总结…');return e.reply(await call('summarize',{url}))}));
 if(initial.inventory){emit({op:'inventory',data:entries.flatMap(([app,obj])=>obj.rule.map(r=>({app,...r})))})}
 else {
  const entry=entries.find(([name])=>name===initial.route.app);
  const rule=entry?.[1].rule.find(r=>r.fnc===initial.route.fnc);
  if(!rule || (rule.permission==='master'&&!e.isMaster)) throw Error('PermissionError');
  diagnosticStage='route';
  await diagnostics.run('route',{name:methodNames.get(entry[0]).get(rule.fnc)},()=>entry[1][rule.fnc](e));
 }
 // Upstream QR methods create timers; wait for both their polling and un-awaited replies.
 diagnosticStage='idle';
 const idleSpan=diagnostics.begin('idle');
 let quiet=0;
 while(quiet<5){
  await new Promise(resolve=>setTimeout(resolve,100));
  quiet=(intervals.size||background.size||rc.requests||rc.children)?0:quiet+1;
 }
 idleSpan.end();diagnosticStage='shutdown';
 await diagnostics.run('shutdown',{},()=>renderer.shutdown());
 workerSpan.end();diagnostics.snapshot('worker');clear(diagnosticTimer);
 emit({op:'done'});process.exit(0);
}catch(error){workerSpan.error(error);diagnostics.snapshot(diagnosticStage);clear(diagnosticTimer);emit({op:'fatal',data:{type:safeError(error)}});process.exit(1)}
