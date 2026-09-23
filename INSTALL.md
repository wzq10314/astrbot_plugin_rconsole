# 安装与升级 RConsole 1.0.2

适用于 AstrBot 4.28.1、Python 3.12、OneBot11 / NapCat；以下沿用你的容器名 `astrbot`。

## 1. 放入完整插件

后台停用旧版 RConsole，用 ZIP 中的 `astrbot_plugin_rconsole` 覆盖 `/AstrBot/data/plugins/astrbot_plugin_rconsole`。确认其中有 `main.py`、`metadata.yaml` 和 `engine/package-lock.json`，不要多套一层同名文件夹。

保留 `/AstrBot/data/config/` 的设置和 `/AstrBot/data/plugin_data/astrbot_plugin_rconsole/` 的状态。不要把 Windows 的 node_modules 复制到 Linux。

## 2. 准备 Node.js

在服务器进入容器：

```bash
docker exec -it astrbot bash
node --version
npm --version
```

需要 Node.js 22+。如果没有，推荐使用本包 `Dockerfile.rconsole` 制作持久化镜像：在宿主机插件文件夹运行下面命令，将参数替换为你当前使用的 AstrBot 镜像及标签。

```bash
docker build -f Dockerfile.rconsole --build-arg ASTRBOT_IMAGE=你的镜像及标签 -t astrbot-rconsole:1.0.2 .
```

把原 Compose 中 AstrBot 的 `image` 改为 `astrbot-rconsole:1.0.2`，保留原端口、网络和 `/AstrBot/data` 挂载，重新创建容器。此 Dockerfile 适用于 Debian 基础镜像（包含系统 Chromium）。

## 3. 自动安装插件依赖

1. 在 AstrBot 后台更新或安装完整插件；已有安装请重载一次。通过插件管理器安装 Python requirements.txt；手工复制的用户请使用 AstrBot 实际运行的 Python 执行 `python3 -m pip install -r requirements.txt`。
2. 默认开启 `engine_auto_install`，加载时会在后台执行锁定版本的 `npm ci`，安装后检查依赖是否可以加载；依赖清单、Node 主版本或系统变化时重新准备。安装期间普通媒体请求会返回进度。
3. 默认开启 `engine_auto_browser`，继续自动下载用于图文渲染的 Chromium。核心依赖就绪后即可发送媒体链接，不用等待浏览器下载完成。
4. 发送 `#rtools engine` 查看结果。失败时管理员发送 `#rtools install` 重试，无需进容器手工运行 npm。卸载或重载会停止当前安装，下次加载重新检查。

自动安装需要插件目录和 npm 缓存可写、容器能访问 npm 下载服务。下载缓慢时，可在后台 `engine_npm_registry` 填你信任的 HTTPS npm 镜像地址，再重试；留空沿用 npm 默认配置。每个安装阶段最多等待 10 分钟。

### 容器系统依赖（仍需准备一次）

默认 `engine_auto_browser_system: true`：如果是 Linux/root/apt 环境，插件可补齐缺失的 Chromium 系统库；Debian 上 Playwright 下载失败则自动执行 apt-get update，并安装 chromium 与 fonts-noto-cjk。不会执行 sudo 或提权。受管理的镜像可关闭该选项，由镜像预装。推荐使用附带的 Debian Dockerfile；其他媒体系统工具手工准备时在容器执行：

```bash
apt-get update
apt-get install -y ffmpeg git fonts-noto-cjk
python3 -m pip install -U yt-dlp
```

Node.js 22+ 和 npm 按第 2 节准备。浏览器就绪状态以实际启动并截图为准。发送 `#rtools browser` 可单独重试渲染准备，不强制重装已就绪的 npm 包。自动修复不适用或失败时：在核心依赖就绪后进入插件 `engine` 目录执行 `npx playwright install --with-deps chromium`；Debian 也可以 `apt-get update && apt-get install -y chromium fonts-noto-cjk`，再重载插件。Chromium 用于菜单、歌曲列表、评论图片与元宝浏览器模式；普通渲染失败会尝试文字输出。

如果主动关闭自动安装，可按原方式在 `engine` 目录执行 `npm ci` 和 `npx playwright install --with-deps chromium`。不要把 Windows 的 node_modules 复制到 Linux。

容器系统依赖随重建可能丢失；Dockerfile 包含 Node/npm、ffmpeg、yt-dlp 和中文字体。插件依赖重建后会自动检查补齐。Playwright 缓存可另行挂载持久化，避免重复下载。

## 4. 设置与登录

后台 → 插件 → RConsole → 配置，保存后重载。

- `engine_enable`：开启完整核心；关闭后使用保留的三平台原生解析。
- `engine_auto_install`：默认开启，后台自动准备 Node 依赖。
- `engine_auto_browser`：默认开启，核心就绪后检查、下载或复用 Chromium。
- `engine_auto_browser_system`：默认开启，允许满足上述条件时通过 apt 补装浏览器及系统库。
- `engine_npm_registry`：可选 npm 镜像 HTTPS 地址。
- `engine_node`：默认 node，可填写可执行文件绝对路径。
- `engine_timeout`：单次处理超时 60～600 秒，默认 300。
- `media_groups`：留空允许所有群；填写 QQ 群号列表限制范围。
- `media_auto_parse`：自动解析开关，关闭后用 `#rparse 链接`。
- `media_max_size_mb`：单文件发送上限，默认 32MB。完整核心同时限制单次总发送量和缓存大小。
- `upstream`：原版功能配置，保留 77 个字段名称。下载目录、并发和总发送上限由适配层管理。

### 网易云、酷狗服务

网易云服务须兼容 NeteaseCloudMusicApi 的 `/search`、`/song/url/v1`、`/login/qr/*`、`/user/cloud` 等接口。酷狗服务须兼容 KuGouMusicApi 的 `/search`、`/song/url`、`/login/qr/*`、`/login/token` 等接口。

分别填写 `upstream.neteaseCloudAPIServer` 和 `upstream.kugouApiServer`。同一 Docker 网络中可以填 `http://netease-api:3000` 这类服务地址。容器内 127.0.0.1 指容器自身，不能用它访问另一容器。

按照[原版官方解答](https://zhiyu1998.github.io/rconsole-plugin/posts/QA官方解答.html)选择和部署对应服务。本包不托管这些登录服务，也不会把你的 Cookie 自动送到原版默认公共网易云服务。

管理员私聊机器人，使用对应平台 App 扫码：

```text
#rnq    网易云登录
#rncq   网易云云盘登录
#rkq    酷狗登录
#RBQ    B站登录
```

确认后凭据自动写入 AstrBot 配置。`use_file_config` 必须关闭才能使用自动保存。随后测试 `#rns`、`#rks`、`#RBS` 和 `#点歌 晴天`。

### Cookie 和文章总结

沿用已有 `douyin_cookie`、`xiaohongshu_cookie`、`bilibili_cookie`。Cookie-Editor 导出选择 **Header String**；YouTube 的 `youtubeCookiePath` 则填写容器内 **Netscape cookies.txt** 的绝对路径。

其他账号分别填 `upstream.qqMusicCookie`、`weiboCookie`、`xCookie`、`xiaoheiheCookie`。视频号填写 `weixinChannelYuanbaoCookie`，也可管理员私聊 `#设置视频号Cookie 内容`。

微信文章总结默认调用 AstrBot 当前会话模型，无需另填 AI Key。发送 `#总结一下 完整文章链接`。页面要求验证码或正文不足会返回错误。元宝模式保留，需 `linkSummaryResolveMode: yuanbao` 和自己的元宝 Cookie，仍受登录 IP 与平台风控影响。

### 可选工具

| 工具 | 对应功能 |
| --- | --- |
| ffmpeg / ffprobe | 音画合并、音频转换、直播片段 |
| yt-dlp | YouTube、TikTok 等原版下载流程 |
| BBDown | B站高清下载，安装后开启 biliUseBBDown |
| aria2c / axel / wget | 原版可选下载方式，默认不必全部安装 |
| tdl | Telegram/部分 X 内容，在 AstrBot 运行用户下自行登录，并用 #设置R信任用户 QQ 授权使用者 |
| freyr | Apple Music / Spotify 原版流程，受工具自身支持范围限制 |

所有程序都须能在 AstrBot 容器 PATH 中找到。移植不会使失效接口或无访问权限的内容自动可用。

## 5. 检查与日志

发送 `#rtools engine` 查看浏览器实际检查结果，再发送 `#R帮助`。如果仍是文字回退，管理员发送 `#rtools browser`，完成后重试帮助和视频链接。帮助回退不会再罗列 saveId、icon 等内部字段。

抖音/B站普通视频卡片包括封面、作者、简介和接口返回的互动统计；部分 API/SSR 不提供完整统计时显示“—”。B站关注数/粉丝数没有随视频接口返回时不显示，不额外要求用户登录。保留原有视频时长限制和视频发送逻辑。

```bash
docker logs --since 10m --tail 200 astrbot
```

适配层不输出原版含凭据的调试日志。AstrBot 和其他消息采集插件可能提前记录原始消息；向别人发送日志前删除 Cookie、token 和二维码参数。

信任列表、点歌选择与云盘缓存存放在 `data/plugin_data/astrbot_plugin_rconsole/engine-state.json`。媒体与渲染缓存位于其中的 `runtime` 子目录，定时清理仅作用于该缓存目录。`#R插件更新` 已改为 AstrBot 后台更新指引，避免原版 git 自更新破坏移植代码。
