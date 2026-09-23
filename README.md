<div align="center">

# AstrBot RConsole

**把 R-plugin 的视频、音乐、图文和工具带到 AstrBot**

![版本](https://img.shields.io/badge/version-1.0.3-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-4.28.1%2B-purple)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Node](https://img.shields.io/badge/Node.js-22%2B-green)
![OneBot](https://img.shields.io/badge/OneBot11-NapCat-orange)
![许可](https://img.shields.io/badge/license-MulanPSL--2.0-green)
![浏览量](https://visitor-badge.laobi.icu/badge?page_id=wzq10314.astrbot_plugin_rconsole)
![Stars](https://img.shields.io/github/stars/wzq10314/astrbot_plugin_rconsole?style=social)
![Forks](https://img.shields.io/github/forks/wzq10314/astrbot_plugin_rconsole?style=social)

[安装说明](INSTALL.md) · [功能对照](FEATURE_MATRIX.md) · [验证记录](TEST_REPORT.md) · [原版官方解答](https://zhiyu1998.github.io/rconsole-plugin/posts/QA官方解答.html)

</div>

浏览量徽章是第三方计数，不等同于 GitHub 官方独立访客数。

本项目是 [R-console / R-plugin](https://gitee.com/kyrzy0416/rconsole-plugin) 的 AstrBot 适配版，由 **wzq10314** 维护。1.0.3 将原版协议核心随插件打包，通过 Python 适配 AstrBot 的消息、权限、配置与 AI 服务。**不需要安装 Yunzai 或 Redis，但完整功能需要 Node.js。**

原版的 6 类应用、53 条命令路由已纳入适配范围。这表示代码和入口已接入，不代表所有第三方接口、地区网络和账号权益均已在线验证，具体见[功能对照表](FEATURE_MATRIX.md)。

## 功能

| 类别 | 内容 |
| --- | --- |
| B站 | 视频、分P、专栏、动态、番剧、直播片段、音乐提取、评论、在线人数、平台 AI 总结、BBDown、`#RBQ` 扫码 |
| 国内视频与图文 | 抖音视频/图集/直播/BGM/评论，小红书视频/图集，快手、西瓜、微博、微视、最右、皮皮虾、皮皮搞笑、即刻、AcFun |
| 海外平台 | YouTube、TikTok、X、Instagram、Telegram；部分需要代理、Cookie 或已登录的 tdl |
| 音乐 | 网易云、QQ音乐、酷狗、波点、汽水、Apple Music / Spotify；点歌、选曲、播放、文件上传、网易云云盘 |
| 登录 | B站、网易云、网易云云盘、酷狗扫码，管理员私聊操作并自动保存 |
| 文章与社区 | 微信公众号及网页总结、微信视频号、米游社、贴吧、小黑盒 |
| 工具 | 翻译、医药资料查询、猫图、软件推荐、买家秀、图片查询、信任用户、代理模式、缓存清理、运行诊断 |

## 安装

在 AstrBot 后台更新本插件，或用完整 ZIP 覆盖 `/AstrBot/data/plugins/astrbot_plugin_rconsole`，然后重载插件。保留后台配置和 plugin_data。

**1.0.3 起默认自动安装 Node 依赖和 Chromium**：加载后在后台检查，首次下载可能需要几分钟。发送 `#rtools engine` 查看进度；看到“原版核心依赖已就绪”后直接重发链接，无需再次重载。失败后管理员可发送 `#rtools install` 重试。依赖清单未变化且完整性检查通过时，不重复运行 npm ci。

容器仍须预先具备 **Node.js 22+ 和 npm**；系统工具 ffmpeg / ffprobe 和可选 yt-dlp 请按 [INSTALL.md](INSTALL.md) 或 Dockerfile 准备。图片渲染优先复用已有 Chromium；默认允许在 Linux/root/apt 容器补齐浏览器系统库，Debian 上下载失败时通过系统软件源安装 Chromium 和中文字体，可用 `engine_auto_browser_system` 关闭。通过 AstrBot 插件管理器安装 Python requirements.txt；手工复制安装的用户需在 AstrBot 的 Python 环境执行 `python3 -m pip install -r requirements.txt`。

抖音普通视频、B站普通视频现默认发送完整信息卡片，并保留后续视频发送。沿用 `upstream.douyinDisplayCover` / `biliDisplayCover` 开关；缺失的统计显示“—”，不会当作零。帮助菜单继续使用原版模板，浏览器启动和截图检查通过后才显示渲染就绪。

## 普通网页自动截图

直接发送普通网页链接即可获得截图，默认开启，无需指定命令。已有平台解析和文章总结优先：B站、抖音、小红书、音乐、微信公众号等沿用原流程；这些解析失败时不会再转网页截图。一条消息混有媒体链接和普通网页时也优先媒体，普通网页每条消息只截第一个有效地址。

后台设置 `webpage_enable` 可关闭；`webpage_timeout` 默认 45 秒；`webpage_max_height` 默认 6000 像素（更长页面截断）。沿用 `media_enable`、`media_auto_parse`、`media_groups` 和 `media_cooldown`，同会话相同链接 60 秒内去重。以 # 开头的其他命令不会被自动截图接管。

截图使用匿名独立浏览器环境，不携带插件 Cookie。支持公开网页的 HTML、CSS、图片和 JavaScript；只加载 GET 资源，不提交表单或登录，不访问内网和本地文件。需要登录、验证码或依赖 POST 数据的网站可能无法完整显示；不绕过验证。资源有并发、数量及下载大小上限。

如果浏览器尚未准备好，先发送 `#rtools engine` 查看，管理员可用 `#rtools browser` 修复。更新插件不会自动解决服务器的下载网络问题。

## 常用命令

```text
#rhelp                        文字帮助
#R帮助                        原版图文菜单
#rtools engine                查看依赖准备进度
#rtools browser               检查并修复图片渲染（管理员）
#rtools install               重试安装依赖（管理员）
#RBQ / #RBS                   B站扫码 / 状态
#rnq / #rncq                  网易云 / 云盘扫码
#rns / #rncs                  网易云 / 云盘状态
#rkq / #rks                   酷狗扫码 / 状态
#点歌 晴天                    搜索歌曲
#听1                          播放第 1 首
#播放 晴天                    直接播放
#我的云盘                     网易云云盘
#总结一下 https://mp.weixin.qq.com/s/…
```

直接发送分享链接也可以解析。`音乐 <B站链接>` 提取音频。所有管理和登录命令继续执行权限检查。

## 配置

后台 → 插件 → RConsole → 配置。已有 B站、抖音、小红书 Cookie 继续使用。新增功能集中在 **原版功能配置 `upstream`**，保留原版字段名。

| 用途 | 配置 |
| --- | --- |
| 网易云 | `neteaseCloudAPIServer`，再私聊 `#rnq`；云盘单独 `#rncq` |
| 酷狗 | `kugouApiServer`，再私聊 `#rkq` |
| 点歌平台 | `songRequestPlatform`：`netease` / `kugou` / `qq` |
| QQ音乐 | `qqMusicCookie`、`qqMusicAudioQuality` |
| 抖音评论/BGM | `douyinComments`、`douyinMusic`、`douyinBGMSendType` |
| 番剧与高清 | `biliBangumiDirect`、`biliUseBBDown` |
| 微信文章 | 默认使用 AstrBot 当前模型，无需重复填写 AI Key |
| 元宝总结/视频号 | `linkSummaryResolveMode: yuanbao`、`weixinChannelYuanbaoCookie` |
| 海外内容 | `proxyAddr`、`proxyPort`，或直连模式 `forceOverseasServer` |
| 自动清理 | `autoclearTrashtime`，默认 08:00，以 AstrBot 进程时区为准 |

网易云/酷狗服务地址由管理员自行部署或选择。发行包不提供他人的 Cookie 或私有密钥。登录不改变歌曲版权、付费权限或地区限制。

## 致谢

首先感谢 **知雨 / zhiyu1998** 及 [rconsole-plugin 的所有贡献者](https://github.com/zhiyu1998/rconsole-plugin)。原版的平台适配和持续维护是这个移植版的基础；本项目保留原始署名和许可证，并记录适配修改。

感谢 [AstrBot](https://github.com/AstrBotDevs/AstrBot)、[NapCatQQ](https://github.com/NapNeko/NapCatQQ)、yt-dlp、BBDown、tdl、freyr，以及原版引用的音乐 API、解析与签名项目。第三方代码以各自附带的许可和说明为准。

本项目不代表上述项目官方。来源版本、修改范围和许可见 [NOTICE.md](NOTICE.md)。
