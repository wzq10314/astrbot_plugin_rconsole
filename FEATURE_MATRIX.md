# 功能对照与验证边界

依据上游提交 `7e1f0eed107e1c5181baec6fc83d3a9fdb6a1eef`，核对其六个 apps 文件，而不是仅按 README 中的平台名称推测功能。

## 已接入的实现

下表列出的代码均已随包提供并有实际路由，不是空方法。上游核心运行在 Node 子进程，Python 负责 AstrBot 适配。**接入不等于所有账号和平台都已在线验收。**

| 功能 | 实现与条件 |
| --- | --- |
| B站视频、分P、动态、专栏、番剧、直播片段、音频、评论、在线人数、平台总结、BBDown | 原版 tools.bili 及其内部方法；#RBQ 沿用已修复的 Python 登录。需要相应 Cookie/权益，高清合并需要 ffmpeg 或 BBDown。 |
| 抖音视频、图集、直播、BGM、评论 | 原版 tools.douyin 及评论/签名模块。完整 Cookie，直播与音频转换需 ffmpeg。 |
| 小红书视频、图集 | Python 原生解析，保留 H.264/H.265 备用地址与转码修复。需要 Cookie；需要转换编码时使用 ffmpeg。 |
| YouTube、TikTok、X、Instagram | 保留原版各自协议和 yt-dlp/tdl/浏览器指纹相关流程，需要对应依赖、代理或 Cookie。 |
| 快手、西瓜、皮皮虾、皮皮搞笑、即刻、微视、最右、AcFun | 保留原版通用接口、SSR 或独立平台实现，部分第三方接口可能失效。 |
| 微博、米游社、贴吧、小黑盒 | 保留图文、视频及原版支持的评论/资料流程；微博、小黑盒部分请求需要 Cookie。 |
| 网易云、QQ音乐、酷狗、波点、汽水 | 保留音乐链接、音质选择、语音/音乐卡片。网易云、酷狗须配置自己的兼容 API 服务；其他平台同样受权限和上游接口限制。 |
| 点歌、听N、播放、上传、网易云云盘与云盘上传 | 原版 songRequest 全部 8 条路由，选曲按用户和会话隔离。上传为 OneBot/NapCat 文件操作；云盘管理为管理员功能。 |
| 网易云、网易云云盘、酷狗扫码与状态 | 原版轮询协议，消息通过 AstrBot 发送，Cookie 写入 AstrBot 配置。只允许管理员私聊扫码。 |
| Apple Music / Spotify | 原版 freyr 流程，需要安装 freyr；不是绕过账号权限的任意音乐下载器。 |
| Telegram | 原版 tdl 下载与相关流程；需要已登录 tdl 和 R 信任用户。 |
| 微信公众号及普通网页总结 | 通用模式改为有界正文提取 + AstrBot 当前模型；元宝模式保留。需要可访问的正文或有效元宝登录态。 |
| 微信视频号 | 保留元宝解析 + 视频号接口流程，需要自己的元宝 Cookie。 |
| 翻译、医药资料、猫图、推荐软件、买家秀、图片查询 | 原版 query/trans 流程；第三方服务不可用时可能失败。医药接口恢复正常证书验证。 |
| 信任用户、海外解析切换、视频号 Cookie、清理垃圾 | 原版管理命令保留；修正布尔开关。定时清理迁移到 AstrBot 生命周期，只操作本插件缓存。 |
| 帮助与版本、插件更新 | 帮助保留原版图文风格并补命令；版本显示 AstrBot 版；更新命令改为 AstrBot 后台更新指引，不执行 Yunzai 的 git reset/pull。 |

## 尚需在用户环境验收

已有测试覆盖原生解析回归、真实 Node 核心加载、网易云搜索和扫码（模拟兼容 API）、权限、状态保存、消息转换及模型调用。未使用用户账号验证酷狗/网易云/B站真实扫码、会员音质、云盘上传、各平台在线解析、NapCat 真实送达、tdl/freyr 和 BBDown 的完整下载。Docker 镜像示例也尚未在用户服务器构建。

没有把无登录态、缺依赖或平台失效的情况标成“已实测可用”。返回验证码、风控、地区限制、无播放地址时需要按具体平台进一步核对。

源帮助曾列出 `#竹白`，但此提交的 apps 中没有对应实现；未将该历史菜单项伪造为可用功能。原版机器人自更新已明确改成 AstrBot 更新入口。

小红书优先使用 Python 路径，因此其发送上限、开关与 Cookie 以原有顶层 xiaohongshu_* / media_* 设置为准。原版下载模式可能受总文件大小与超时保护限制。

## 53 条原版路由核对

表中的 `biliScan` 入口实际由 Python #RBQ 接管，`xhs` 由已有 Python 解析接管；其余使用随包核心。各入口内部继续调用原版的平台子方法。

| 应用 | 处理方法 | 原版触发规则 |
| --- | --- | --- |
| help | `help` | `^#*(R&#124;r)(插件)?(命令&#124;帮助&#124;菜单&#124;help&#124;说明&#124;功能&#124;指令&#124;使用说明)$` |
| query | `doctor` | `^#医药查询(.*)$` |
| query | `cat` | `^#cat$` |
| query | `softwareRecommended` | `^#推荐软件$` |
| query | `buyerShow` | `^#买家秀$` |
| query | `cospro` | `^#累了$` |
| songRequest | `pickSong` | `^#点歌\s*(.+?)(?:\s+([12]))?$&#124;#听[1-9][0-9]*&#124;#听[1-9]*$` |
| songRequest | `playSong` | `^#播放\s*(.+?)(?:\s+([12]))?$` |
| songRequest | `upLoad` | `^#?上传$` |
| songRequest | `myCloud` | `^#?我的云盘$&#124;^#rnc$&#124;^#RNC$` |
| songRequest | `songCloudUpdate` | `^#?云盘更新$&#124;#?更新云盘$` |
| songRequest | `uploadCloud` | `^#?上传云盘&#124;#?上传网盘$&#124;#rnu&#124;#RNU` |
| songRequest | `cleanCloudData` | `^#?清除云盘缓存$` |
| switchers | `setOversea` | `^#设置海外解析$` |
| switchers | `clearTrash` | `^清理垃圾$` |
| switchers | `setWhiteList` | `^#设置R信任用户(.*)` |
| switchers | `getWhiteList` | `^#R信任用户$` |
| switchers | `searchWhiteList` | `^#查询R信任用户(.*)` |
| switchers | `deleteWhiteList` | `^#删除R信任用户(.*)` |
| switchers | `setWeixinChannelCookie` | `^#设置视频号[Cc]ookie\s*(.*)$` |
| tools | `trans` | `^(翻&#124;trans)[中&#124;日&#124;文&#124;英&#124;俄&#124;韩]` |
| tools | `douyin` | `((v&#124;live).douyin.com&#124;webcast.amemv.com&#124;iesdouyin.com&#124;www.douyin.com/(video&#124;note&#124;live&#124;share&#124;jingxuan&#124;discover))` |
| tools | `tiktok` | `(www.tiktok.com)&#124;(vt.tiktok.com)&#124;(vm.tiktok.com)` |
| tools | `biliScan` | `^#(RBQ&#124;rbq)$` |
| tools | `biliState` | `^#(RBS&#124;rbs)$` |
| tools | `bili` | `(bilibili.com&#124;b23.tv&#124;bili2233.cn&#124;m.bilibili.com&#124;t.bilibili.com&#124;^BV[1-9a-zA-Z]{10}$)` |
| tools | `twitter_x` | `https?:\/\/(x&#124;r&#124;twitter)\.com\/[0-9-a-zA-Z_]{1,20}\/status\/([0-9]*)(\?.*)?` |
| tools | `instagram` | `https?:\/\/(www\.)?instagram\.com\/(p&#124;reel&#124;reels)\/` |
| tools | `acfun` | `(acfun.cn&#124;^ac[0-9]{8}$)` |
| tools | `xhs` | `(xhslink\.(com&#124;cn)&#124;xiaohongshu\.com)` |
| tools | `bodianMusic` | `(h5app.kuwo.cn)` |
| tools | `general` | `(chenzhongtech.com&#124;kuaishou.com&#124;ixigua.com&#124;h5.pipix.com&#124;h5.pipigx.com&#124;s.xsj.qq.com&#124;m.okjike.com)` |
| tools | `sy2b` | `(youtube.com&#124;youtu.be&#124;music.youtube.com)` |
| tools | `miyoushe` | `(miyoushe.com)` |
| tools | `netease` | `(music.163.com&#124;163cn.tv)` |
| tools | `weibo` | `(weibo.com&#124;m.weibo.cn)` |
| tools | `weishi` | `(weishi.qq.com)` |
| tools | `zuiyou` | `share.xiaochuankeji.cn` |
| tools | `freyr` | `(music.apple.com&#124;open.spotify.com)` |
| tools | `linkShareSummary` | `(^#总结一下\s*(http&#124;https):\/\/.*&#124;mp.weixin.qq.com&#124;arxiv.org&#124;sspai.com&#124;chinadaily.com.cn&#124;zhihu.com&#124;github.com&#124;v2ex.com)` |
| tools | `qqMusic` | `(y.qq.com)` |
| tools | `kugouMusic` | `(t1.kugou.com&#124;m.kugou.com/share/song.html&#124;www.kugou.com/share/&#124;h5.kugou.com/v2/)` |
| tools | `qishuiMusic` | `(qishui.douyin.com)` |
| tools | `aircraft` | `https:\/\/t\.me\/(?:c\/\d+\/\d+\/\d+&#124;c\/\d+\/\d+&#124;\w+\/\d+\/\d+&#124;\w+\/\d+\?\w+=\d+&#124;\w+\/\d+)` |
| tools | `tieba` | `tieba.baidu.com` |
| tools | `xiaoheihe` | `xiaoheihe.cn` |
| tools | `weixinChannel` | `(weixin\.qq\.com/sph/)` |
| tools | `neteaseStatus` | `^#(网易云状态&#124;rns&#124;RNS&#124;网易云云盘状态&#124;rncs&#124;RNCS)$` |
| tools | `netease_scan` | `^#(rnq&#124;RNQ&#124;rncq&#124;RNCQ)$` |
| tools | `kugouStatus` | `^#(酷狗状态&#124;rks&#124;RKS)$` |
| tools | `kugou_scan` | `^#(rkq&#124;RKQ)$` |
| update | `version` | `^#*R(插件)?版本$` |
| update | `update` | `^#*R(插件)?(强制更新&#124;更新)$` |
