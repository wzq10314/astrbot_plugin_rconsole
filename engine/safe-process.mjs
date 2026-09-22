// Upstream command strings are parsed as arguments, never evaluated by a shell.
import cp from 'node:child_process';
import path from 'node:path';
import {parse} from 'shell-quote';
import {promisify} from 'node:util';
const allowed=new Set(['ffmpeg','ffprobe','yt-dlp','BBDown','aria2c','axel','wget','tdl','freyr','node']);
export function commandArgs(command) {
  if (/[`\r\n\0]/.test(command) || command.includes('$(')) throw Error('不支持命令替换');
  const args=parse(command, {});
  if (!args.length || args.some(x=>typeof x!=='string') || !allowed.has(path.basename(args[0]).replace(/\.exe$/i,'')))
    throw Error('不支持此下载命令，请检查依赖及参数');
  return args;
}
const options=o=>({...o,shell:false,windowsHide:true,timeout:Math.min(o?.timeout||240000,600000),maxBuffer:8*1024*1024});
function watch(child){
 if(globalThis.rc){rc.children++;child.once('close',()=>rc.children--)}return child;
}
export function exec(command,opts,callback) {
  if(typeof opts==='function'){callback=opts; opts={}}
  const [file,...args]=commandArgs(command);
  return watch(cp.execFile(file,args,options(opts),callback));
}
export function execSync(command,opts={}) {
  const [file,...args]=commandArgs(command); return cp.execFileSync(file,args,options(opts));
}
export function spawn(file,args=[],opts={}) {
  if(!allowed.has(path.basename(file).replace(/\.exe$/i,''))) throw Error('不支持此程序');
  return watch(cp.spawn(file,args,options(opts)));
}
export function execFile(file,args=[],opts={},callback) {
  if(typeof opts==='function'){callback=opts;opts={}}
  if(!allowed.has(path.basename(file).replace(/\.exe$/i,'')))throw Error('不支持此程序');
  return watch(cp.execFile(file,args,options(opts),callback));
}
execFile[promisify.custom]=(file,args,opts)=>new Promise((resolve,reject)=>{
 execFile(file,args,opts,(error,stdout,stderr)=>error?reject(error):resolve({stdout,stderr}));
});
export default {exec,execSync,spawn,execFile};
