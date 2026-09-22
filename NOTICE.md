# 来源、许可证与改动

原版：知雨 / zhiyu1998 及 rconsole-plugin 贡献者。

- 用户提供入口：https://gitee.com/kyrzy0416/rconsole-plugin
- 同源 GitHub：https://github.com/zhiyu1998/rconsole-plugin
- 本次依据提交：`7e1f0eed107e1c5181baec6fc83d3a9fdb6a1eef`
- 核对日期：2026-09-22。
- 原始文件校验见 `engine/UPSTREAM_HASHES.json`；它记录修改前来源，不是发行文件的哈希。

`engine/plugins/rconsole-plugin` 包含原版 apps、utils、model、constants、config、resources。保留其源码注释、署名及 MulanPSL-2.0 LICENSE。新增 AstrBot 适配层同用 MulanPSL-2.0；第三方文件自己的许可或额外说明继续适用。

`vendor/a-bogus.cjs` 和引擎中的同源签名模块保留原声明，包括其学习交流、禁止商业和非法使用说明；本项目不将其重新授权为无此限制的代码。

主要适配：消息段/合并转发/文件上传转换，权限和私聊登录，Redis 替换为插件独立状态文件，配置写回 AstrBot，原版渲染接入 Playwright，文章总结接入 AstrBot 模型，关闭 Yunzai git 自更新，定时清理迁入插件生命周期。修正点歌用户隔离、医药查询缺失导入、代理模式布尔切换、下载命令无 shell 执行及资源路径。

小红书继续使用之前修复的 Python 编码回退流程；B站扫码继续使用已修复的直接发图流程。未提供任何个人账号 Cookie、私有密钥或登录状态。上游公开的协议常量与公开接口定义随源码保留。
