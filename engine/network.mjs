// Guard direct HTTP clients, including node-fetch and axios redirects.
import http from 'node:http';
import https from 'node:https';
import dns from 'node:dns';
import net from 'node:net';
import {urlToHttpOptions} from 'node:url';
import {syncBuiltinESMExports} from 'node:module';
import ipaddr from 'ipaddr.js';
import axios from 'axios';
function publicAddress(ip){
 try {let value=ipaddr.parse(ip);if(value.kind()==='ipv6'&&value.isIPv4MappedAddress())value=value.toIPv4Address();return value.range()==='unicast'}catch{return false}
}
export function installNetwork(config){
 const trusted=new Set();
 for(const key of ['neteaseCloudAPIServer','kugouApiServer','aiBaseURL']) {
  if(config[key])try{trusted.add(new URL(config[key]).host)}catch{}
 }
 if(config.proxyAddr && config.proxyPort) trusted.add(`${config.proxyAddr}:${config.proxyPort}`);
 for(const mod of [http,https]) {
  const original=mod.request;
  const protocol=mod===https?'https:':'http:';
  mod.request=function(input,options,callback){
   let opts;
   if(typeof input==='string'||input instanceof URL){
    opts=urlToHttpOptions(new URL(input));
    if(typeof options==='object')Object.assign(opts,options);
    else if(typeof options==='function')callback=options;
   }else{opts={...input};if(typeof options==='function')callback=options;}
   const host=String(opts.hostname||opts.host||'').replace(/^\[|\]$/g,'');
   const port=String(opts.port||(protocol==='https:'?443:80));
   const allowed=trusted.has(`${host}:${port}`)||trusted.has(host);
   if(!allowed){
    if(host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||(net.isIP(host)&&!publicAddress(host)))throw Error('已阻止非公网目标');
    opts.lookup=(name,lookupOptions,cb)=>{
     dns.lookup(name,{all:true},(error,rows)=>{
      if(error)return cb(error);
      if(!rows.length||rows.some(r=>!publicAddress(r.address)))return cb(Error('已阻止非公网解析结果'));
      if(lookupOptions?.all)return cb(null,rows);
      const selected=rows.find(r=>!lookupOptions?.family||r.family===lookupOptions.family)||rows[0];
      cb(null,selected.address,selected.family);
     });
    };
   }
   const req=original.call(this,opts,callback);
   if(globalThis.rc){
    rc.requests++;
    let ended=false;
    const finish=()=>{if(!ended){ended=true;rc.requests--}};
    req.once('error',finish);req.once('close',finish);
    req.once('response',response=>{response.once('end',finish);response.once('close',finish)});
   }
   return req;
  };
  mod.get=function(...args){const req=mod.request(...args);req.end();return req};
 }
 syncBuiltinESMExports();
 axios.defaults.timeout=30000;
 axios.defaults.maxContentLength=64*1024*1024;
 axios.defaults.maxBodyLength=64*1024*1024;
}
