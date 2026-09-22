import fs from 'node:fs';
import YAML from 'yaml';
export default {
 getConfig(name) {return this.getYaml(name)},
 getYaml(name) {return name === 'tools' ? globalThis.rc.config : YAML.parse(fs.readFileSync(new URL('../config/'+name+'.yaml',import.meta.url),'utf8'))},
 getField(name,field) {return this.getConfig(name)[field]},
 updateField(name,field,value) {if(name!=='tools') throw Error('配置类型不支持'); globalThis.rc.config[field]=value; return globalThis.rc.call('config',{field,value})},
 deleteField(name,field) {return this.updateField(name,field,'')},
 saveAllConfig(name,data) {return Promise.all(Object.entries(data).map(([k,v])=>this.updateField(name,k,v)))}
};
