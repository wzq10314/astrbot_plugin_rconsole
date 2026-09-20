# RConsole v0.3.2 安装说明

v0.3.1 修复小红书视频只读取 H.264 主地址的问题：增加备用地址、其他编码和 originVideoKey 原视频回退。优先 H.264，其他编码及编码未知的原视频通过 ffmpeg 转为 H.264/AAC 后发送；需要容器安装 ffmpeg（含 libx264）。保留 #RBQ 扫码登录。

升级时保留 WebUI 配置文件；若使用 config.yaml，请先备份并在覆盖后恢复。重载插件后重新发送分享链接即可，不必因本次更新重新填写 Cookie。

本次验证：42 项离线测试通过，网络、AstrBot 和转码进程使用测试替身验证流程；未完成用户这条视频的登录下载、真实转码和 QQ 发送验证。修复参考 yt-dlp 官方 Xiaohongshu 提取器的 stream/backupUrls/originVideoKey 字段：https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/xiaohongshu.py 。

v0.3.2 修复 #RBQ 在发送初始提示前停止事件、随后 yield 可能导致二维码流程中断的问题。初始提示改为直接发送，登录完成后才交回响应流程。增加安全阶段日志（RConsole RBQ）以及依赖缺失和超时提示。42 项离线测试通过，包含发送后停止事件的回归场景；尚未在真实 AstrBot/NapCat 上验证。

本版增加 B站、抖音、小红书的解析、下载和 QQ 媒体发送。原始项目来自用户上传的 Yunzai R-plugin 源码包，本版为 AstrBot 原生重实现。

v0.3.0 增加原版命令 `#RBQ` 的 B站二维码登录。已安装旧版时需要重新上传新版 ZIP，并让 AstrBot 安装新增的 `qrcode[pil]` 依赖。

## 安装或升级

1. 下载并解压 `astrbot_plugin_rconsole.zip`，得到同名插件目录。
2. 已安装旧版时先在 WebUI 停用插件，备份原插件目录和配置。默认 WebUI 配置位于 `/AstrBot/data/config/astrbot_plugin_rconsole_config.json`；手动配置还需备份插件内的 `config.yaml`，覆盖后恢复。
3. 将解压目录上传至 Ubuntu 宿主机，在该目录的上级目录执行：

```bash
docker cp ./astrbot_plugin_rconsole astrbot:/AstrBot/data/plugins/
docker exec astrbot python3 -m pip install -r /AstrBot/data/plugins/astrbot_plugin_rconsole/requirements.txt
docker exec -u root astrbot sh -c 'apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs'
docker restart astrbot
docker logs --tail 100 astrbot
```

这是**宿主机命令**，不要在容器内部运行 `docker`。若镜像没有 pip，请使用容器实际运行 AstrBot 的 Python 对应的 uv 环境安装依赖，例如已有 `/AstrBot/.venv/bin/python` 时用 `uv pip install --python /AstrBot/.venv/bin/python -r ...`。不要用宿主机 Python 安装插件依赖。

也可以使用 AstrBot WebUI 的本地 ZIP 安装入口导入插件，依赖安装后检查加载日志。最终入口应为 `/AstrBot/data/plugins/astrbot_plugin_rconsole/main.py`。

ffmpeg 用于 B站分段视频、FLV 或音画分离视频的合并。完整 MP4 及图集通常不需要它。Node.js 用于调用原版抖音 `a-bogus.cjs` 请求签名模块，无需安装 Yunzai 或 npm 包。Cookie 不会传给 Node 子进程。容器内手动安装的工具会在**重建容器**时丢失；正式部署可将安装步骤加入你现有镜像的 Dockerfile。插件目录应通过 `/AstrBot/data` 挂载持久化保存。

## 怎么使用

先按下方说明在 WebUI 配置登录 Cookie 并重载插件，再直接在群聊或私聊发送支持的分享链接，或：

```text
#rparse https://www.bilibili.com/video/实际BV号
#rparse 完整抖音分享链接
#rparse 完整小红书分享链接
#解析 完整分享链接
#RBQ
#rhelp
```

也支持单独发 BV 号、av 号，和含链接的 QQ JSON 分享卡片。每条消息只处理第一个支持的链接。

### B站扫码登录

用插件管理员 QQ **私聊机器人**发送：

```text
#RBQ
```

机器人发送二维码后，用哔哩哔哩 App 扫码并在 App 内确认。成功后，完整 B站 Cookie 和 `refresh_token` 会写入 AstrBot 插件配置，当前插件立即使用新 Cookie。二维码约 3 分钟有效；已扫码待确认、过期和超时都有明确提示。

群聊调用会被拒绝。启用 `use_file_config` 时自动回写也会被拒绝，请先切回 WebUI 配置并重载。扫码相当于授权机器人使用你的 B站账号凭据，请只在你自己管理的机器人上操作。当前版本保存刷新令牌但暂未自动续期；Cookie 失效后重新执行 `#RBQ`。

## 支持范围

| 平台 | 本版实现 | 限制 |
| --- | --- | --- |
| B站 | 普通视频信息、封面、视频发送；BV/av、b23/bili2233 短链、`?p=2` 分P | 不含直播、番剧、动态、专栏；部分视频/画质要求登录或特定权限 |
| 抖音 | 视频、图文图集；v.douyin 短链、video/note/share/slides | 动图按静态图发送，不合成 BGM；不含直播/主页 |
| 小红书 | 视频、图文图集；xhslink.com/cn 短链与笔记页 | 保留 `xsec_token`、`xsec_source`；可能需要有效 Cookie，不处理主页 |

视频由 AstrBot 下载后通过 OneBot Base64 媒体消息发送，适合 AstrBot 与 NapCat 分属不同容器的部署，不要求共享本地文件路径。默认单条内容下载上限 **32 MiB**、视频最长 **10 分钟**、图集前 **9 张**；超过限制会提示，不会宣称已经发送。默认一次只处理一个媒体任务，自动解析遇忙跳过，手动解析遇忙会提示。

## 配置

在 WebUI 的 RConsole 插件配置中修改，保存后重载插件。默认自动解析开启。

- `media_auto_parse`：关掉后只响应 `#rparse`/`#解析` 等显式命令。
- `bilibili_enable` / `douyin_enable` / `xiaohongshu_enable`：各平台开关。
- `media_groups`：允许解析的群号字符串列表；空列表为所有群，私聊不受影响。
- `media_max_size_mb`、`media_max_duration`、`media_max_images`：大小、时长、图片数量限制。
- `bilibili_quality`：默认 32（480P），也支持 16/64/80。实际画质由平台访问权限决定。
- `bilibili_cookie`：公开普通视频可留空；部分视频或更高画质需要你的登录 Cookie。
- `douyin_cookie`：按原版填写浏览器登录后的完整 Cookie，优先用于签名详情接口。
- `xiaohongshu_cookie`：按原版要求必填，还需要带校验参数的完整分享链接。
- `douyin_ssr_fallback`：同原版默认 false；显式开启后，普通视频无 Cookie 或主接口失败时可尝试分享页备用解析。图文仍使用登录 Cookie 主接口。

### 如何填写登录 Cookie

原版的 `guoba.support.js` 提示在浏览器登录后通过开发者工具获取 Cookie；它没有为抖音和小红书实现机器人内扫码登录。本版沿用这个配置方式：

1. 在你自己的浏览器打开抖音或小红书官网，正常登录并确认分享内容能打开。
2. 按 F12 打开开发者工具，进入 Network（网络），刷新页面，选择官网页面或 API 请求。
3. 从 Request Headers（请求头）复制整行 **Cookie 的值**，不包含 `Cookie:` 字样；不要复制响应的 Set-Cookie。
4. 填入 AstrBot WebUI 的 `douyin_cookie` / `xiaohongshu_cookie`，保存并重载插件。
5. 管理员发送 `#rtools cookies` 可检查是否已配置；该命令不会展示原文，也不声称 Cookie 一定有效。

抖音常见字段包括 `sessionid`、`sid_guard`、`uid_tt`、`ttwid` 等，但请复制你的完整真实请求头，不要照抄占位值。小红书同样复制实际请求头中的完整 Cookie。

原版配置对应关系：`douyinCookie` → `douyin_cookie`，`xiaohongshuCookie` → `xiaohongshu_cookie`，`douyinEnableSsrBackup` → `douyin_ssr_fallback`。手动 YAML 也兼容原版这三个字段名；如同时存在新旧字段，以新字段为准。不要在 QQ 群或公开日志中粘贴 Cookie。

小红书请复制 APP 的**整段分享内容或完整链接**，不要删掉 `xsec_token` 和 `xsec_source`。短链展开后会保留参数，`xsec_source` 未提供时按原版默认 `pc_feed`。Cookie 不保证可以消除平台的 IP 验证、登录挑战或内容访问限制；遇到验证需在正常浏览器处理。

若要使用文件配置，在 WebUI 启用 `use_file_config`，再编辑插件内 `config.yaml` 并重载。此时其他 WebUI 字段不生效；升级前务必备份手动 YAML。

## 原基础功能

保留 `#rhelp`、`#rstatus`、`#rquery ip [域名]`、`#rquery ping [域名] [端口]`、`#rtools deps`、`#rtools url <链接>` 和 `#rshell <完整命令>`，新增管理员 `#rtools cookies`。

query 仅管理员可用，其中 ping 是 TCP 连接测试，不是 ICMP。rshell 默认关闭，仅管理员私聊且按完整命令白名单执行。配置 QQ 管理员仅对 OneBot 生效，QQ群管理员不会自动获得服务器权限。

## 验证边界

见插件内 `TEST_REPORT.md`。离线测试覆盖三平台数据解析、权限、消息路由、下载限制、跨容器媒体负载和文件清理。真实 QQ/NapCat 发送仍需在你的机器人上验收。平台 Cookie 和网络环境会影响实时解析结果，不能承诺所有链接都成功。

测试顺序：先 `#rhelp`，再一条短 B站视频，接着自己的抖音与小红书分享链接。若失败，保留错误提示和不含 Cookie 的日志用于排查。

## 实现与来源

`modules/` 保留基础命令；`services/bilibili.py`、`douyin.py`、`xiaohongshu.py` 实现平台解析；`services/downloader.py` 处理有大小上限的下载/合并；`adapters/onebot.py` 发送群聊/私聊媒体；`utils/http.py` 校验公网地址、跳转和 Cookie 发送范围。

`vendor/a-bogus.cjs` 从用户提供的原版源码包原样保留，`vendor/sign_douyin.cjs` 是调用入口；详见 `NOTICE.md`。B站与抖音、小红书以外的音乐、直播、评论截图、自动更新等功能不在本版实现范围。

参考：[上游 R-plugin](https://gitee.com/kyrzy0416/rconsole-plugin)、[AstrBot 4.28.1 源码](https://github.com/AstrBotDevs/AstrBot/tree/v4.28.1)、[NapCat OneBot 接口](https://napneko.github.io/onebot/api)。
