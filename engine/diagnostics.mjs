// Diagnostics deliberately accept no free-form text, URLs, request options or errors.
import {isIP} from 'node:net';
import {performance} from 'node:perf_hooks';

const STAGES=new Set(['method','network','fetch','route','idle','shutdown','worker']);
const EVENTS=new Set(['begin','end','error','headers','timeout','pending','snapshot']);
const APPS=new Set(['help','query','songRequest','switchers','tools','update']);
const METHODS=new Set(['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS','CONNECT','TRACE']);
const ERRORS=new Set([
 'Error','TypeError','RangeError','SyntaxError','ReferenceError','AggregateError',
 'TimeoutError','AbortError','ProtocolError','PermissionError','PollingError',
 'ECONNABORTED','ECONNREFUSED','ECONNRESET','EHOSTUNREACH','ENETUNREACH',
 'ENOTFOUND','EAI_AGAIN','EPIPE','ETIMEDOUT','ERR_CANCELED','ERR_NETWORK',
 'ERR_BAD_REQUEST','ERR_BAD_RESPONSE','ERR_INVALID_URL','ERR_INVALID_ARG_TYPE',
 'ERR_HTTP_REQUEST_TIMEOUT','ERR_STREAM_PREMATURE_CLOSE','ERR_SOCKET_CLOSED',
 'ERR_TLS_CERT_ALTNAME_INVALID','CERT_HAS_EXPIRED','DEPTH_ZERO_SELF_SIGNED_CERT',
 'UNABLE_TO_VERIFY_LEAF_SIGNATURE','UND_ERR_CONNECT_TIMEOUT','UND_ERR_HEADERS_TIMEOUT',
 'UND_ERR_BODY_TIMEOUT','UND_ERR_SOCKET','UND_ERR_ABORTED','UND_ERR_RESPONSE_STATUS_CODE'
]);
const NUMBERS=['id','elapsed_ms','requests','children','background','intervals',
 'pending_methods','pending_network','pending_fetch','emitted','dropped'];
const nonnegative=value=>Number.isFinite(value)?Math.min(Number.MAX_SAFE_INTEGER,Math.max(0,Math.floor(value))):undefined;

export function safeError(error){
 try {
  for(const value of [error?.code,error?.cause?.code,error?.name])if(ERRORS.has(value))return value;
 }catch{}
 return 'Error';
}

export function safeHostname(value){
 if(typeof value!=='string'||value.length>4096)return undefined;
 try {
  let host=value.includes('://')?new URL(value).hostname:value;
  if(host.startsWith('[')&&host.endsWith(']'))host=host.slice(1,-1);
  if(isIP(host))return host.toLowerCase();
  if(host.length>253||!host.length)return undefined;
  if(!host.split('.').every(label=>/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label)))return undefined;
  return host.toLowerCase();
 }catch{return undefined}
}

export function sanitizeDiagnostic(data,names=new Set()){
 if(!data||!STAGES.has(data.stage)||!EVENTS.has(data.event))return null;
 const result={event:data.event,stage:data.stage};
 if(typeof data.name==='string'&&(METHODS.has(data.name)||names.has(data.name)))result.name=data.name;
 const host=safeHostname(data.host);
 if(host)result.host=host;
 if(ERRORS.has(data.error))result.error=data.error;
 for(const key of NUMBERS){const value=nonnegative(data[key]);if(value!==undefined)result[key]=value}
 if(Number.isInteger(data.status)&&data.status>=100&&data.status<=599)result.status=data.status;
 return result;
}

export function createDiagnostics({emit,now=()=>performance.now(),counters=()=>({}),
 maxNetworkBegins=200,maxOtherBegins=200,maxPending=200,maxSnapshotItems=8}={}){
 const names=new Set(),pending=new Map();
 const active={pending_methods:0,pending_network:0,pending_fetch:0};
 const countKey={method:'pending_methods',network:'pending_network',fetch:'pending_fetch'};
 let serial=0,networkBegins=0,otherBegins=0,emitted=0,dropped=0;
 const send=data=>{
  const clean=sanitizeDiagnostic(data,names);
  if(!clean)return;
  try{emit({op:'diagnostic',data:clean});emitted++}catch{}
 };
 function registerMethod(app,method){
  // Only called with names read from the fixed app modules' own prototypes.
  if(!APPS.has(app)||typeof method!=='string'||!/^[$A-Z_a-z][$\w]{0,95}$/.test(method))return undefined;
  const name=`${app}.${method}`;names.add(name);return name;
 }
 function begin(stage,fields={}){
  const id=++serial,started=now();
  const record=sanitizeDiagnostic({...fields,event:'begin',stage,id},names);
  if(!record)return {headers(){},timeout(){},end(){},error(){}};
  const key=countKey[stage];if(key)active[key]++;
  const isNetwork=stage==='network'||stage==='fetch';
  const detailed=isNetwork?networkBegins++<maxNetworkBegins:
   stage==='method'?otherBegins++<maxOtherBegins:true;
  if(detailed)send(record);else dropped++;
  if(pending.size<maxPending)pending.set(id,{record,started});else dropped++;
  let ended=false;
  const event=(kind,extra={})=>send({...record,...extra,event:kind,elapsed_ms:now()-started});
  function finish(error,extra){
   if(ended)return;ended=true;pending.delete(id);if(key)active[key]--;
   if(error!==undefined)event('error',{error:safeError(error)});
   else if(detailed)event('end',extra);
  }
  return {
   headers(status){if(!ended&&detailed)event('headers',{status})},
   timeout(){if(!ended)event('timeout',{error:'TimeoutError'})},
   end(extra={}){finish(undefined,extra)},
   error(error){finish(error??{name:'Error'})}
  };
 }
 function run(stage,fields,fn){
  const span=begin(stage,fields);
  try{return Promise.resolve(fn()).then(value=>{span.end();return value},error=>{span.error(error);throw error})}
  catch(error){span.error(error);throw error}
 }
 function snapshot(stage='idle'){
  send({...counters(),...active,emitted,dropped,event:'snapshot',stage});
  const shown={};
  for(const {record,started} of pending.values()){
   shown[record.stage]=(shown[record.stage]||0)+1;
   if(shown[record.stage]<=maxSnapshotItems)
    send({...record,event:'pending',elapsed_ms:now()-started});
  }
 }
 return {registerMethod,begin,run,snapshot,record:send};
}

export function installFetchDiagnostics(diagnostics,target=globalThis){
 if(typeof target.fetch!=='function')return;
 const original=target.fetch;
 target.fetch=function(input,options){
  // Read only known URL/Request fields. Never inspect headers or the response body.
  let host,method='GET';
  try {
   const url=typeof input==='string'?input:input instanceof URL?input.href:
    typeof Request!=='undefined'&&input instanceof Request?input.url:undefined;
   host=safeHostname(url);
   const requested=options?.method||(typeof Request!=='undefined'&&input instanceof Request?input.method:'GET');
   if(typeof requested==='string'&&METHODS.has(requested.toUpperCase()))method=requested.toUpperCase();
  }catch{}
  const span=diagnostics.begin('fetch',{host,name:method});
  try {
   return Promise.resolve(original.apply(this,arguments)).then(response=>{
    span.headers(response.status);span.end();return response;
   },error=>{span.error(error);throw error});
  }catch(error){span.error(error);throw error}
 };
}
