import {fileURLToPath} from 'node:url';
export default class Base {
 static pluginName='rconsole-plugin';
 constructor(e={}) {this.e=e; this.userId=e?.user_id; this.model=Base.pluginName;}
 get prefix(){return `Yz:rconsole-plugin:${this.model}:`}
 get screenData(){return {saveId:this.userId,
  tplFile:fileURLToPath(new URL(`../resources/html/${this.model}/${this.model}.html`,import.meta.url)),
  pluResPath:new URL('../resources/',import.meta.url).href}}
}
