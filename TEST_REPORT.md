# v0.3.2 发布验证

本次发布重新运行42项测试全部通过，使用真实aiohttp、PyYAML与Node.js签名子进程；AstrBot、平台网络与QQ发送为测试替身。以下为历次验证记录，不代表当前所有线上链接已实测。

# v0.3.0 验证报告

日期：2026-09-19。目标环境：AstrBot 4.28.1 / Python 3.12 / OneBot11 + NapCat。

## 本地测试

使用 Python 3.12.14，39 项 unittest 全部通过，包括：

- 基础命令和权限、配置校验、上游 Cookie 字段兼容。
- B站分P和播放地址失败后保留元信息。
- 抖音视频/图文数据解析、Cookie 签名接口优先、可开关 SSR 备用路径。
- 小红书图文/视频、Cookie/分享参数缺失提示、保留 xsec_token。
- 原版 a-bogus JS 模块通过真实 Node.js 子进程生成签名（不是签名占位）。未使用登录账号验证该签名当前是否被平台接受。
- 短链跳转、公网地址检查、连接时 DNS 校验、Cookie 跨域隔离。
- 下载超限、部分文件删除、非媒体 HTML 拒绝、输出截断与超时。
- 群聊/私聊 OneBot Base64 负载、自动/手动解析、去重和群范围。
- 下载→发送替身→临时文件清理，以及多图数量限制。

测试中的 AstrBot、QQ 发送和多数 HTTP 响应采用替身，确保不向真实 QQ 发送测试消息。它们不等同于完整 AstrBot/NapCat 集成测试。

## 真实网络读取

| 项目 | 结果 |
| --- | --- |
| B站 av170001 | 无 Cookie 读取到 199 秒视频信息、播放地址；CDN HTTP 200，文件头为 MP4 |
| 用户提供的抖音 `https://v.douyin.com/VIGxeKx8sNE/` | 移动分享页与匿名访客方式成功解析；本地完整下载封面 115,292 字节、MP4 3,531,756 字节，并清理临时文件。对应本版显式启用 `douyin_ssr_fallback` 的备用方式 |
| 小红书公开旧示例 | 无登录 Cookie 请求落入验证/不可见页，未取得媒体；最终版本改为按原版先要求 Cookie 和完整 xsec_token，而不是将失败当成功 |

## 尚未实测

- 没有用户登录 Cookie，因此抖音登录主流程和小红书登录态的真实平台验收仍待部署后完成。
- 没有连接用户的 AstrBot/NapCat，真实 QQ 视频/图片发送、QQ 风控、WebSocket 消息大小限制待现场验收。
- 本地测试为 Windows Python 3.12，未在用户 Ubuntu 容器实际加载；Linux 进程组清理逻辑已实现，但不是此次实际测试平台。
- 本机未运行真实 ffmpeg 音画合并；已覆盖缺少 ffmpeg 的提示，普通 MP4 下载不依赖此合并分支。

## 复现离线测试

安装 requirements.txt 和 Node.js 后，在插件父目录执行：

```bash
python3 -m unittest discover -s astrbot_plugin_rconsole/tests -v
```

无 Node.js 时签名执行测试明确跳过，不应将跳过视为验证成功。部署验收可依次发送 `#rtools deps`、`#rtools cookies`（管理员）、短视频及图文分享链接。
