import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import renderer from './lib/puppeteer/puppeteer.js';
import VideoCard,{count} from './plugins/rconsole-plugin/model/video-card.js';
import Help from './plugins/rconsole-plugin/model/help.js';
import {renderFailure,checkBrowser} from './browser-runtime.mjs';

const work=await fs.mkdtemp(path.join(os.tmpdir(),'rconsole-render-'));
globalThis.plugin=class {};
globalThis.logger=new Proxy({},{get:()=>()=>{}});
globalThis.Bot={};
globalThis.segment={image:buffer=>({type:'image',data:{file:buffer}})};
const asset=await fs.readFile(new URL('./plugins/rconsole-plugin/resources/img/default.png',import.meta.url));
const statuses=[];
globalThis.rc={work,config:{},call:async(op,data)=>{
 if(op==='render_status'){statuses.push(data.code);return true}
 if(op==='render_asset')return {mime:'image/png',data:asset.toString('base64')};
 throw Error('Unexpected rendering fallback: '+JSON.stringify({op,code:data.code}));
}};
try{
 const timeout=setTimeout(()=>{console.error('Render test timed out');process.exit(1)},90000);timeout.unref();
 assert.equal(count(undefined),'—');assert.equal(count(0),'0');assert.equal(count(38200),'3.8万');
 assert.equal(renderFailure(Error("Executable doesn't exist")),'browser_missing');
 assert.equal(renderFailure(Error('error while loading shared libraries: libnss3.so')),'system_libraries');
 assert.equal(renderFailure(Error('bad template'),'template'),'template_error');
 assert.equal((await checkBrowser()).ok,true);
 console.log('Browser launch and screenshot check passed');
 const {tools}=await import('./plugins/rconsole-plugin/apps/tools.js');
 console.log('Production handlers loaded');
 const instance=Object.create(tools.prototype);
 Object.assign(instance,{identifyPrefix:'',douyinDuration:600,douyinDisplayCover:true,
  biliDisplayCover:true,biliDisplayInfo:true,biliDisplayIntro:true,biliDisplayOnline:true,
  toolsConfig:{biliIntroLenLimit:150},biliOnlineTotal:async()=>({total:18,count:7})});
 const sent=[];let videos=0;
 const e={reply:async msg=>{sent.push(msg);return {message_id:1}}};
 instance.downloadVideo=async()=> 'mock.mp4';instance.sendVideoToUpload=async()=>{videos++};
 await instance.handleDouyinResolvedVideo(e,{douId:'123456789',authorNickname:'示例创作者',desc:'记录生活里的美好瞬间。中文简介、视频封面与互动信息卡片。',
  author:{nickname:'示例创作者',avatar_thumb:{url_list:['https://fixture.test/avatar.png']},unique_id:'sample_user',total_favorited:31002000,following_count:0,follower_count:1384000},
  durationSeconds:162,coverUrl:'https://fixture.test/cover.png',videoUrl:'https://fixture.test/video.mp4',
  item:{create_time:1790157600,statistics:{digg_count:38200,comment_count:674,collect_count:1958,share_count:4786},music:{title:'原创音乐 · 美好时刻',author:'示例创作者'}}});
 assert.equal(videos,1);assert.equal(sent[0][0].type,'image');
 const dy=sent[0][0];
 console.log('Douyin card rendered');
 const bili=(await instance.constructBiliInfo({title:'一起记录这个世界',pic:'https://fixture.test/cover.png',owner:{name:'示例UP主',mid:12345,face:'https://fixture.test/avatar.png'},
  stat:{view:7446,reply:56,danmaku:1,like:119,coin:16,favorite:73,share:54},desc:'这是 B站卡片渲染测试，包含中文简介、视频数据、在线人数与作者信息。',bvid:'BV1fixture',cid:123,pubdate:1784170500},'一起记录这个世界',null,null))[0];
 assert.equal(bili.type,'image');
 console.log('Bilibili card rendered');
 const help=await renderer.screenshot('help',await Help.get({}));assert.equal(help.type,'image');
 for(const image of [dy,bili,help])assert.ok(image.data.file.length>10000);
 assert.equal(statuses.length,3);
 if(process.argv[2]){
  await fs.mkdir(process.argv[2],{recursive:true});
  for(const [name,value] of [['douyin',dy],['bilibili',bili],['help',help]])await fs.writeFile(path.join(process.argv[2],name+'.png'),value.data.file);
 }
 instance.douyinDuration=1;await instance.handleDouyinResolvedVideo(e,{durationSeconds:2,authorNickname:'无详细数据'});
 assert.equal(videos,1,'Duration limit must not be bypassed by card rendering');
 const sparse=new VideoCard().douyin({},'fallback');assert.equal(sparse.card.stats[0].value,'—');
 console.log('Rendered Douyin/Bilibili through production handlers and original help template; video flow and missing data verified.');
}finally{await renderer.shutdown();await fs.rm(work,{recursive:true,force:true})}
