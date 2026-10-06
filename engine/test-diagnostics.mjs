import assert from 'node:assert/strict';
import test from 'node:test';
import {createDiagnostics,installFetchDiagnostics,safeError,safeHostname,sanitizeDiagnostic} from './diagnostics.mjs';

test('diagnostic fields, identifiers, errors and hostname are strictly filtered',()=>{
 const secret='private-cookie-token-user-123';
 const data=sanitizeDiagnostic({event:'error',stage:'network',name:secret,
  host:`https://user:${secret}@Example.COM/private/${secret}?token=${secret}`,
  error:secret,message:secret,cookie:secret,headers:{authorization:secret},
  route:secret,url:secret,path:secret,user_id:123,requests:4.9,elapsed_ms:-1,status:200});
 assert.deepEqual(data,{event:'error',stage:'network',host:'example.com',elapsed_ms:0,requests:4,status:200});
 assert.equal(JSON.stringify(data).includes(secret),false);
 assert.equal(sanitizeDiagnostic({event:secret,stage:'method'}),null);
 assert.equal(safeHostname('good.test/path?secret=1'),undefined);
 assert.equal(safeHostname('user:secret@good.test'),undefined);
 assert.equal(safeHostname('https://user:secret@[2001:db8::1]/?secret=1'),'2001:db8::1');
 assert.equal(safeHostname('example.test\r\nsecret'),undefined);
 assert.equal(safeError({name:secret,code:secret,message:secret}),'Error');
 assert.equal(safeError({name:'TypeError',message:secret,cause:{code:'UND_ERR_HEADERS_TIMEOUT'}}),'UND_ERR_HEADERS_TIMEOUT');
 assert.equal(safeError({get code(){throw Error(secret)}}),'Error');
});

test('concurrent spans retain bounded pending details and accurate counters',()=>{
 const packets=[];let time=0;
 const diagnostics=createDiagnostics({emit:packet=>packets.push(packet),now:()=>time,
  counters:()=>({requests:3,background:2,children:0,intervals:0,cookie:'do-not-log'}),maxPending:2});
 const name=diagnostics.registerMethod('tools','bili');
 assert.equal(name,'tools.bili');
 assert.equal(diagnostics.registerMethod('unknown','bili'),undefined);
 assert.equal(diagnostics.registerMethod('tools','bad/path'),undefined);
 const method=diagnostics.begin('method',{name});
 const first=diagnostics.begin('network',{host:'api.bilibili.com',name:'GET'});
 const second=diagnostics.begin('network',{host:'www.douyin.com',name:'POST'});
 time=10500;diagnostics.snapshot();
 let snapshot=packets.findLast(packet=>packet.data.event==='snapshot').data;
 assert.equal(snapshot.pending_methods,1);assert.equal(snapshot.pending_network,2);
 assert.equal(snapshot.requests,3);assert.equal(snapshot.background,2);assert.equal(snapshot.dropped,1);
 assert.equal(packets.filter(packet=>packet.data.event==='pending').length,2);
 assert.equal(packets.find(packet=>packet.data.event==='pending').data.elapsed_ms,10500);
 assert.equal(JSON.stringify(packets).includes('do-not-log'),false);
 first.headers(200);first.end();first.end();first.error(new Error('late error'));
 second.error({code:'ETIMEDOUT',message:'secret'});method.end();diagnostics.snapshot('worker');
 snapshot=packets.findLast(packet=>packet.data.event==='snapshot').data;
 assert.equal(snapshot.pending_methods,0);assert.equal(snapshot.pending_network,0);
 assert.equal(packets.filter(packet=>packet.data.event==='error').length,1);
 assert.equal(packets.find(packet=>packet.data.event==='error').data.error,'ETIMEDOUT');
 assert.ok(packets.every(packet=>packet.op==='diagnostic'&&!('id' in packet)));
});

test('network event budget preserves errors and pending summaries',()=>{
 const packets=[];
 const diagnostics=createDiagnostics({emit:packet=>packets.push(packet),maxNetworkBegins:1,maxSnapshotItems:1});
 diagnostics.begin('network',{host:'a.example',name:'GET'}).end();
 const waiting=diagnostics.begin('network',{host:'b.example',name:'GET'});
 const failure=diagnostics.begin('fetch',{host:'c.example',name:'GET'});
 failure.error({name:'TypeError',message:'secret',cause:{code:'UND_ERR_CONNECT_TIMEOUT'}});
 diagnostics.snapshot();waiting.timeout();waiting.end();
 assert.equal(packets.filter(packet=>packet.data.event==='begin').length,1);
 assert.equal(packets.filter(packet=>packet.data.event==='end').length,1);
 assert.equal(packets.filter(packet=>packet.data.event==='error').length,1);
 assert.equal(packets.find(packet=>packet.data.event==='snapshot').data.dropped,2);
 assert.equal(packets.find(packet=>packet.data.event==='snapshot').data.pending_fetch,0);
 assert.equal(packets.find(packet=>packet.data.event==='pending').data.host,'b.example');
 assert.equal(packets.find(packet=>packet.data.event==='timeout').data.error,'TimeoutError');
});

test('observed methods preserve results and original failures',async()=>{
 const packets=[];const diagnostics=createDiagnostics({emit:packet=>packets.push(packet)});
 const name=diagnostics.registerMethod('tools','douyin');const value={unchanged:true};
 assert.equal(await diagnostics.run('method',{name},async()=>value),value);
 const error=new Error('secret');
 await assert.rejects(diagnostics.run('method',{name},async()=>{throw error}),caught=>caught===error);
 assert.throws(()=>diagnostics.run('method',{name},()=>{throw error}),caught=>caught===error);
 diagnostics.snapshot();
 assert.equal(packets.findLast(packet=>packet.data.event==='snapshot').data.pending_methods,0);
 assert.equal(JSON.stringify(packets).includes('secret'),false);
});

test('fetch observation preserves receiver, arguments, response and unread body',async()=>{
 const packets=[];let now=0,received;
 const diagnostics=createDiagnostics({emit:packet=>packets.push(packet),now:()=>now});
 const response=new Response('private response body',{status:201});
 let resolve;
 const target={fetch(...args){received={receiver:this,args};return new Promise(done=>resolve=done)}};
 installFetchDiagnostics(diagnostics,target);
 const url='https://user:password@api.example/private-user?cookie=secret';
 const options={method:'post',headers:{cookie:'secret'},body:'private-body'};
 const pending=target.fetch(url,options);
 diagnostics.snapshot();
 assert.equal(packets.findLast(packet=>packet.data.event==='snapshot').data.pending_fetch,1);
 now=1234;resolve(response);
 assert.equal(await pending,response);assert.equal(response.bodyUsed,false);
 assert.equal(received.receiver,target);assert.deepEqual(received.args,[url,options]);
 diagnostics.snapshot();
 assert.equal(packets.findLast(packet=>packet.data.event==='snapshot').data.pending_fetch,0);
 const headers=packets.find(packet=>packet.data.event==='headers').data;
 assert.equal(headers.host,'api.example');assert.equal(headers.name,'POST');assert.equal(headers.status,201);
 assert.equal(headers.elapsed_ms,1234);
 for(const secret of ['password','private-user','cookie','secret','private-body','private response'])assert.equal(JSON.stringify(packets).includes(secret),false);
 assert.equal(await response.text(),'private response body');
});

test('fetch observation preserves synchronous throws and rejections',async()=>{
 const packets=[];const diagnostics=createDiagnostics({emit:packet=>packets.push(packet)});
 const error=Object.assign(new Error('secret'),{code:'ETIMEDOUT'});
 const sync={fetch(){throw error}};installFetchDiagnostics(diagnostics,sync);
 assert.throws(()=>sync.fetch('https://api.example/private'),caught=>caught===error);
 const asyncTarget={fetch(){return Promise.reject(error)}};installFetchDiagnostics(diagnostics,asyncTarget);
 await assert.rejects(asyncTarget.fetch(new Request('https://api.example/private',{method:'HEAD'})),caught=>caught===error);
 assert.equal(packets.filter(packet=>packet.data.event==='error').length,2);
 assert.equal(packets.findLast(packet=>packet.data.event==='begin').data.name,'HEAD');
 assert.equal(JSON.stringify(packets).includes('secret'),false);
});

test('diagnostic delivery failure does not break the observed operation',async()=>{
 const diagnostics=createDiagnostics({emit(){throw new Error('output unavailable')}});
 assert.equal(await diagnostics.run('method',{},async()=>42),42);
 diagnostics.snapshot();
});
