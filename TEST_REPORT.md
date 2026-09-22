# 1.0.1 自动依赖安装验证

日期：2026-09-22。

- 63 项 Python 测试通过，包括 11 项新增自动安装/初始化测试与原有 52 项回归。
- 实际从缺少 engine/node_modules 的状态启动自动安装器，成功执行 npm ci、导入全部直接依赖并准备 Chromium；第二次检查复用已安装依赖，完成标记未改写。
- 覆盖锁文件变化、强制重试、缓存损坏、缺少 Node/npm、Node 版本过低、安装失败、安装后检查失败、取消、浏览器下载失败仍可解析、管理员权限、重复请求、媒体处理期间拒绝重装和启动开关。
- Node 核心的命令解析、execFile 返回结构和网络边界回归通过；全部 Python/JavaScript 源码通过语法检查。
- 发行包不包含 node_modules、安装完成标记或个人登录凭据。后台配置、YAML 默认值与版本信息已核对。

验证边界：真实安装测试在 Windows 开发环境执行，沿用本地 npm 下载缓存与已存在的 Chromium；没有验证用户 Linux 容器的网络、写入权限或系统库。媒体回归使用模拟 AstrBot/NapCat 与本地 API，没有新增真实账号平台验证。容器仍需 Node.js 22+、npm 及对应系统工具。

测试新增依赖由 requirements.txt 提供（包含 APScheduler）。历史版本验证记录如下。

---

# 1.0.0 完整核心适配验证

日期：2026-09-22。源码依据：7e1f0eed107e1c5181baec6fc83d3a9fdb6a1eef。

- 52 项 Python 测试通过，包括原有 42 项回归与 10 项核心适配测试。
- 使用真实 Node 子进程加载上游全部 6 类应用、53 条路由；所有 Python/JavaScript 文件通过语法检查。
- 真实 Node 核心对接本地模拟网易云 API：搜索、用户隔离、二维码 PNG 发送、轮询成功保存 Cookie、播放后音频下载、跨消息文件上传。
- 真实 Playwright Chromium 渲染完整帮助菜单成功，已目视检查文字、布局与新增命令。
- 已测试管理员/私聊限制、音乐卡片群私聊转换、合并转发、输出凭据隐藏、路径边界和退出清理。
- 已验证文章总结入口在未配置单独 AI Key 时使用 AstrBot 宿主回调，网页内容作为不可信数据传入模型。
- Node 运行时测试：无 shell 命令解析、命令替换/管道拒绝、execFile Promise 返回结构、非公网 HTTP 目标拒绝。
- 配置字段默认无个人凭据；发行包排除 node_modules、测试运行数据、登录态、.git 与 Python 缓存。

**验证范围**：AstrBot 和 NapCat 发送使用测试替身；网易云服务使用本地兼容 API 测试数据。未用真实账号扫码，没有声称所有平台当前在线可用。Chromium 在 Windows 开发环境实测；用户 Linux 容器、Dockerfile、BBDown/tdl/freyr 以及真实第三方接口需按 INSTALL.md 配置后逐项验收。

复现 Python 测试：安装 requirements.txt、engine 中 npm ci，并设置 RCONSOLE_TEST_NODE（可选）后，令 PYTHONPATH 指向包含插件目录的父目录，运行 `python -m unittest discover -s tests -q`。Node 检查运行 `node engine/test-runtime.mjs`。不要使用真实账号 Cookie 运行夹具测试。

以下为旧版历史记录，不能代替上述新版本验证边界。

---

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
