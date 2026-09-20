<div align="center">

# RConsole · 媒体解析助手

把分享链接，变成聊天里可以直接查看的视频与图片。

![版本](https://img.shields.io/badge/version-0.3.2-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-4.28.1%2B-purple)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![平台](https://img.shields.io/badge/OneBot11-NapCat-green)
![许可证](https://img.shields.io/badge/license-MulanPSL--2.0-orange)
[![文档访问](https://visitor-badge.laobi.icu/badge?page_id=wzq10314.astrbot_plugin_rconsole)](https://github.com/wzq10314/astrbot_plugin_rconsole)
[![Stars](https://img.shields.io/github/stars/wzq10314/astrbot_plugin_rconsole?style=social)](https://github.com/wzq10314/astrbot_plugin_rconsole/stargazers)
[![Forks](https://img.shields.io/github/forks/wzq10314/astrbot_plugin_rconsole?style=social)](https://github.com/wzq10314/astrbot_plugin_rconsole/forks)

访问徽章为第三方服务请求计数，不是 GitHub 官方独立访客数。

</div>

> 感谢 **[kyrzy0416 / rconsole-plugin](https://gitee.com/kyrzy0416/rconsole-plugin)** 原项目作者与贡献者的开源分享。本项目根据用户提供的 Yunzai R-plugin 源码，借助AI工具进行AstrBot原生Python重实现，并保留原始资源声明。
> 本版聚焦 B站、抖音、小红书媒体解析，不是原项目全部功能的完整移植。

## ✨ 功能

| 平台或模块 | 支持内容 |
| --- | --- |
| B站 | 普通视频、分P、BV/av号、短链接、封面与视频发送 |
| B站登录 | 管理员私聊 `#RBQ`，生成二维码并保存登录Cookie |
| 抖音 | 视频、图文图集、分享短链接；使用Cookie及原版签名模块 |
| 小红书 | 视频、图文图集、完整分享链接；保留校验参数 |
| 聊天解析 | 自动识别分享文字、支持的链接和QQ JSON分享卡片 |
| 基础工具 | 帮助、状态、网络诊断、依赖与Cookie配置状态检查 |

直接分享链接即可触发自动解析，不需要LLM。本版未注册自然语言LLM工具。音乐、直播、主页解析、番剧、评论截图及原Yunzai更新器不在当前实现范围。

## 📦 安装与更新

在AstrBot插件管理中使用本仓库地址安装，或上传插件ZIP：

```text
https://github.com/wzq10314/astrbot_plugin_rconsole
```

适配 AstrBot 4.28.1、Python 3.12、OneBot11/NapCat。Python依赖见 [requirements.txt](requirements.txt)。

容器还需要 **ffmpeg（含libx264）** 和 **Node.js**。ffmpeg用于音画合并/转码；Node.js运行原版抖音签名模块，不需要Yunzai或npm安装，Cookie不会传给Node子进程。

Docker用户可在Ubuntu宿主机执行：

```bash
docker exec -u root astrbot sh -c 'apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs'
docker restart astrbot
```

容器重建会丢失临时安装的工具，长期使用请加入自己的Dockerfile。详细安装、Python环境与升级步骤见 [INSTALL.md](INSTALL.md)。

更新前备份 WebUI 配置；使用文件配置时另备份插件目录的 config.yaml。升级不要覆盖自己保存的Cookie。默认发行配置所有Cookie均为空。

## ⚙️ 配置

在WebUI修改后保存并重载：

| 配置项 | 说明 |
| --- | --- |
| `admins` | 插件管理员QQ字符串列表；同时接受AstrBot管理员 |
| `media_auto_parse` | 默认开启；关闭后需显式解析命令 |
| `bilibili_enable` / `douyin_enable` / `xiaohongshu_enable` | 各平台解析开关 |
| `media_groups` | 允许解析的群号列表，空表示全部群；私聊不受此项限制 |
| `bilibili_cookie` | B站登录Cookie，可通过RBQ保存 |
| `douyin_cookie` | 自己的抖音完整登录Cookie |
| `xiaohongshu_cookie` | 小红书登录Cookie；还需完整分享参数 |
| `douyin_ssr_fallback` | 默认关闭，可开启普通视频分享页备用解析 |
| `media_max_size_mb` | 默认32MiB下载上限 |
| `media_max_duration` | 默认最长600秒 |
| `media_max_images` | 默认最多9张图片 |
| `bilibili_quality` | 默认32（480P），实际画质受账号及平台权限限制 |
| `use_file_config` | 默认关闭；开启后使用config.yaml，其他WebUI字段不生效 |

Cookie-Editor导出请选择 **Header String**，填Cookie值，不带 `Cookie:` 前缀；不要直接粘贴JSON或Netscape格式。请仅使用自己的账号Cookie，勿公开到群聊或仓库。

小红书复制APP完整分享内容，不要删除 `xsec_token`、`xsec_source` 等参数。有效Cookie也不能保证绕过平台的验证或访问限制。

## ⌨️ 使用方法

```text
#rhelp
#rparse 完整分享链接
#解析 完整分享链接
#RBQ
#rstatus
#rtools deps
#rtools cookies
```

开启自动解析时，也可直接发送分享文字、BV/av号。每条消息只处理第一个支持链接；同一时间只处理一个媒体任务。

`#rtools cookies` 仅管理员可用，只显示是否配置，不回显Cookie，也不代表Cookie有效。

### B站扫码登录

1. 插件管理员私聊发送 `#RBQ`。
2. 用哔哩哔哩App扫描机器人发来的二维码，在App内确认。
3. 成功后保存Cookie和refresh_token到WebUI配置，并立即使用新Cookie。

二维码约3分钟有效。群聊操作、文件配置模式下自动回写会被拒绝。当前不自动续期，Cookie失效后重新扫码。只在自己信任的机器人上授权。

### 诊断命令

管理员可用 `#rquery ip [域名]`、`#rquery ping [域名] [端口]`、`#rtools url 链接`。ping是TCP连接测试。

`#rshell 完整命令` 默认关闭，仅管理员、默认仅私聊、完整命令白名单精确匹配。普通QQ群管理员不会因此取得服务器权限。

## 🧩 部署与限制

- 媒体通过OneBot Base64消息发送，适合AstrBot与NapCat分开容器，无需共享媒体路径。
- B站音画分离视频需要ffmpeg合并。小红书优先H.264，必要时将其他编码转成H.264/AAC。
- 超时、超出大小或时长限制会明确提示；不会把未发送当成成功。
- 抖音图文中的动图按静态图发送，不合成背景音乐。
- Cookie、平台风控、内容权限及网络变化可能导致解析失败，不承诺所有分享都成功。

## 🧪 验证与反馈

离线测试使用真实Python依赖、模拟AstrBot与网络响应，包含解析、权限、消息发送流程与RBQ流程中断回归；详见 [TEST_REPORT.md](TEST_REPORT.md)。不等同于真实QQ环境完整验收。

先试 `#rhelp` 和 `#rtools deps`，再分享一条短视频。反馈时提供版本、命令和脱敏错误日志，勿发送Cookie、刷新令牌或账号凭据。

## 🙏 致谢与许可证

- [kyrzy0416 / rconsole-plugin](https://gitee.com/kyrzy0416/rconsole-plugin)：Yunzai原项目及抖音签名流程。
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：小红书视频字段适配时参考其公开提取器实现。
- AstrBot、NapCat及相关开源依赖的维护者。

新增Python实现采用 **Mulan PSL v2**，保留原项目 [LICENSE](LICENSE)。第三方 `vendor/a-bogus.cjs` 自带仅学习交流、禁止商业及非法使用的声明，未重新授权；请阅读 [NOTICE.md](NOTICE.md) 与文件原始声明。徽章不覆盖第三方文件的额外声明。

本项目不是哔哩哔哩、抖音、小红书、AstrBot或NapCat官方产品，不暗示原作者为本移植版提供支持。
