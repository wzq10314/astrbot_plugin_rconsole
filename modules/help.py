def render() -> str:
    return """RConsole v0.3.2
直接发送 B站、抖音、小红书分享链接可自动解析。
#RBQ — B站扫码登录（仅管理员私聊）
#rparse <分享链接/BV号> — 手动解析与发送
#解析 <链接> — 同上
#rhelp — 帮助
#rstatus — Python、系统和进程状态
#rquery ip [域名] — DNS 地址查询（管理员）
#rquery ping [域名] [端口] — TCP 连通性/耗时（管理员，非 ICMP）
#rtools deps — 检查可选媒体工具
#rtools cookies — 查看 Cookie 是否已配置（管理员，不显示内容）
#rtools url <URL> — 识别媒体平台（不下载）
#rshell <完整命令> — 管理员诊断命令，默认关闭且仅私聊
B站普通视频/分P；抖音和小红书视频/图集。
抖音/小红书请先在插件配置填写登录 Cookie。
直播、番剧、点歌、自动更新暂不支持。"""
