export class Update extends plugin {
 constructor(){super({name:'R插件版本',rule:[{reg:'^#*R(插件)?版本$',fnc:'version'}, {reg:'^#*R(插件)?(强制更新|更新)$',fnc:'update',permission:'master'}]})}
 async version(e){return e.reply('AstrBot RConsole 1.0.3 · 上游协议核心 + AstrBot 适配层。')}
 async update(e){return e.reply('请在 AstrBot 后台 → 插件 → RConsole → 更新。离线安装请用新版完整 ZIP 覆盖后重载；原版 Yunzai 自更新已改为 AstrBot 更新入口。')}
}
