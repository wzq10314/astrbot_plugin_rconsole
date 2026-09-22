# 安装与升级 RConsole 1.0.0

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
docker build -f Dockerfile.rconsole --build-arg ASTRBOT_IMAGE=你的镜像及标签 -t astrbot-rconsole:1.0.0 .
```

把原 Compose 中 AstrBot 的 `image` 改为 `astrbot-rconsole:1.0.0`，保留原端口、网络和 `/AstrBot/data` 挂载，重新创建容器。此 Dockerfile 适用于 Debian/Ubuntu 基础镜像。

## 3. 安装依赖

以下在 **AstrBot 容器内**执行，已有 Node 的用户直接从这里开始：

```bash
apt-get update
apt-get install -y ffmpeg git fonts-noto-cjk
cd /AstrBot/data/plugins/astrbot_plugin_rconsole
python3 -m pip install -r requirements.txt
python3 -m pip install -U yt-dlp
cd engine
npm ci
npx playwright install --with-deps chromium
```

使用 AstrBot 实际运行的 Python；如果镜像采用虚拟环境，就使用该环境的 Python。Chromium 用于菜单、歌曲列表、评论图片与元宝浏览器模式；普通渲染失败会尝试文字输出。

退出容器，在宿主机重启：

```bash
exit
docker restart astrbot
```

手工安装在容器系统中的依赖会随重建丢失。Dockerfile 已包含 Node、ffmpeg、yt-dlp 和中文字体；重建后还要检查插件 Python/Node 依赖及 Chromium。可将 Playwright 缓存目录另行挂载持久化，或重复安装 Chromium。

## 4. 设置与登录

后台 → 插件 → RConsole → 配置，保存后重载。

- `engine_enable`：开启完整核心；关闭后使用保留的三平台原生解析。
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

发送 `#rtools engine`、`#R插件版本`、`#R帮助`，再逐项测试已配置的平台。

```bash
docker logs --since 10m --tail 200 astrbot
```

适配层不输出原版含凭据的调试日志。AstrBot 和其他消息采集插件可能提前记录原始消息；向别人发送日志前删除 Cookie、token 和二维码参数。

信任列表、点歌选择与云盘缓存存放在 `data/plugin_data/astrbot_plugin_rconsole/engine-state.json`。媒体与渲染缓存位于其中的 `runtime` 子目录，定时清理仅作用于该缓存目录。`#R插件更新` 已改为 AstrBot 后台更新指引，避免原版 git 自更新破坏移植代码。
