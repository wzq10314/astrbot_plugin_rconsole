import Base from './base.js';

export function count(value){
 if(value===null||value===undefined||value===''||!Number.isFinite(Number(value)))return '—';
 const n=Number(value);
 return n>=1e8?(n/1e8).toFixed(1).replace(/\.0$/,'')+'亿':n>=1e4?(n/1e4).toFixed(1).replace(/\.0$/,'')+'万':n.toLocaleString('en-US');
}
export function date(value){
 if(!value)return '发布时间未知';
 const d=new Date(Number(value)*1000);
 return Number.isNaN(d.getTime())?'发布时间未知':d.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});
}
function picture(value){
 if(typeof value!=='string')return '';
 if(value.startsWith('//'))value='https:'+value;
 return /^https?:\/\//i.test(value)?value:'';
}
const avatar=a=>picture(a?.avatar_thumb?.url_list?.[0]||a?.avatar_medium?.url_list?.[0]||a?.face||'');
const metric=(label,value)=>({label,value:count(value)});

export default class VideoCard extends Base {
 constructor(){super();this.model='video-card'}
 data(card,fallback){return {...this.screenData,card:{...card,generated:date(Date.now()/1000)},fallback}}
 douyin(options,fallback){
  const a=options.author||{}, item=options.item||{}, s=item.statistics||{}, music=item.music||{};
  const seconds=Math.max(0,Number(options.durationSeconds)||0);
  return this.data({platform:'抖音',kind:'douyin',title:options.desc||'暂无简介',description:'',
   author:options.authorNickname||a.nickname||'抖音用户',avatar:avatar(a),cover:picture(options.coverUrl),
   published:date(item.create_time),duration:String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(Math.floor(seconds%60)).padStart(2,'0'),
   id:options.douId||'',userId:a.unique_id||a.short_id||a.uid||'—',
   music:music.title||'',musicAuthor:music.author||'',musicCover:picture(music.cover_thumb?.url_list?.[0]),
   stats:[metric('♥ 点赞',s.digg_count),metric('● 评论',s.comment_count),metric('★ 收藏',s.collect_count),metric('➜ 分享',s.share_count)],
   authorStats:[metric('获赞',a.total_favorited),metric('关注',a.following_count),metric('粉丝',a.follower_count)],
   subline:''},fallback);
 }
 bili(info,title,part,summary,fallback,settings={}){
  const a=info.owner||{}, s=info.stat||{};
  return this.data({platform:'哔哩哔哩',kind:'bilibili',title,description:summary||'',
   author:a.name||'UP主',avatar:avatar(a),cover:settings.biliDisplayCover===false?'':picture(info.pic),
   published:date(info.pubdate||info.ctime),duration:'',id:info.bvid||'',userId:String(a.mid||'—'),music:'',musicAuthor:'',musicCover:'',
   stats:settings.biliDisplayInfo===false?[]:[metric('♡ 点赞',s.like),metric('◉ 硬币',s.coin),metric('★ 收藏',s.favorite),metric('➜ 分享',s.share)],
   authorStats:[],subline:(part?part+' · ':'')+(settings.biliDisplayInfo===false?'':`播放 ${count(s.view)} · 评论 ${count(s.reply)} · 弹幕 ${count(s.danmaku)}`)},fallback);
 }
}
