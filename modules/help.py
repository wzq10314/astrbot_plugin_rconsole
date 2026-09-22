def render() -> str:
    return """RConsole v1.0.1 · AstrBot 完整核心适配版
直接发送原版支持的平台分享链接可自动解析。
#RBQ — B站扫码登录（仅管理员私聊）
#RBS — B站登录状态（管理员）
#rnq / #rncq — 网易云 / 云盘扫码登录（管理员私聊）
#rns / #rncs — 网易云 / 云盘状态
#rkq / #rks — 酷狗扫码登录 / 状态
#点歌 关键词 [1|2] — 搜索歌曲，2 为网易云播客
#听1 / #播放 关键词 — 选曲 / 直接播放
#上传 / #我的云盘 / #云盘更新 / #上传云盘 / #清除云盘缓存
#总结一下 <网页链接> — 使用 AstrBot 当前模型总结（支持微信文章）
#R帮助 — 原版完整图文菜单
翻中/英/日 <文本> — 翻译
#医药查询 / #cat / #推荐软件 / #买家秀 / #累了
#设置海外解析 / #设置R信任用户 QQ / #R信任用户
#查询R信任用户 QQ / #删除R信任用户 QQ / 清理垃圾
#设置视频号Cookie <值> — 管理员私聊设置
#R插件版本 / #R插件更新
#rparse <分享链接/BV号> — 手动解析与发送
#解析 <链接> — 同上
#rhelp — 帮助
#rstatus — Python、系统和进程状态
#rquery ip [域名] — DNS 地址查询（管理员）
#rquery ping [域名] [端口] — TCP 连通性/耗时（管理员，非 ICMP）
#rtools deps — 检查可选媒体工具
#rtools engine — 检查完整核心依赖
#rtools install — 重试自动安装依赖（管理员）
#rtools cookies — 查看 Cookie 是否已配置（管理员，不显示内容）
#rtools url <URL> — 识别媒体平台（不下载）
#rshell <完整命令> — 管理员诊断命令，默认关闭且仅私聊
视频、图文、评论、B站动态/专栏/番剧/直播、音乐平台等功能见 FEATURE_MATRIX.md。
音乐服务和登录 Cookie 请在后台“原版功能配置”填写；新功能需要 Node.js，安装见 INSTALL.md。"""
