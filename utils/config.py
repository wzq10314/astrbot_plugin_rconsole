from pathlib import Path
import yaml

DEFAULTS = {
    "webpage_enable": True,
    "webpage_timeout": 45,
    "webpage_max_height": 6000,
    "engine_enable": True,
    "engine_auto_install": True,
    "engine_auto_browser": True,
    "engine_auto_browser_system": True,
    "engine_npm_registry": "",
    "engine_node": "node",
    "engine_timeout": 300,
    "upstream": {},
    "use_file_config": False,
    "admins": [],
    "shell_enable": False,
    "shell_private_only": True,
    "shell_allowlist": ["uname -a", "python3 --version", "df -h"],
    "command_timeout": 8,
    "max_output_chars": 2000,
    "query_host": "example.com",
    "query_port": 443,
    "media_enable": True,
    "media_auto_parse": True,
    "bilibili_enable": True,
    "douyin_enable": True,
    "xiaohongshu_enable": True,
    "media_groups": [],
    "media_max_size_mb": 32,
    "media_max_duration": 600,
    "media_max_images": 9,
    "media_request_timeout": 20,
    "media_total_timeout": 240,
    "media_cooldown": 10,
    "bilibili_quality": 32,
    "bilibili_cookie": "",
    "bilibili_refresh_token": "",
    "douyin_cookie": "",
    "douyin_ssr_fallback": False,
    "xiaohongshu_cookie": "",
}


def load_config(config, root: Path) -> dict:
    values = dict(config or {})
    if values.get("use_file_config") is True:
        values = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8")) or {}
        if not isinstance(values, dict):
            raise ValueError("config.yaml 必须是键值映射")
    # Accept upstream names in manual YAML to make Cookie migration easier.
    for old, new in {'douyinCookie': 'douyin_cookie', 'xiaohongshuCookie': 'xiaohongshu_cookie',
                     'douyinEnableSsrBackup': 'douyin_ssr_fallback'}.items():
        if old in values and new not in values:
            values[new] = values[old]
    result = {**DEFAULTS, **values}
    upstream = result.get('upstream')
    if isinstance(upstream, dict):
        for old,new in {'douyinCookie':'douyin_cookie','xiaohongshuCookie':'xiaohongshu_cookie'}.items():
            if not result.get(new) and upstream.get(old): result[new]=upstream[old]
    for name in (key for key, value in DEFAULTS.items() if type(value) is bool):
        if not isinstance(result[name], bool):
            raise ValueError(f"{name} 必须是布尔值 true/false")
    for name in ("admins", "shell_allowlist", "media_groups"):
        if not isinstance(result[name], list):
            raise ValueError(f"{name} 必须是列表")
    result["admins"] = [str(value) for value in result["admins"]]
    result["media_groups"] = [str(value) for value in result["media_groups"]]
    if not all(isinstance(value, str) and value.strip() for value in result["shell_allowlist"]):
        raise ValueError("shell_allowlist 必须包含完整命令字符串")
    for name, minimum, maximum in (
        ("command_timeout", 1, 30), ("max_output_chars", 100, 4000), ("query_port", 1, 65535),
        ("media_max_size_mb", 1, 64), ("media_max_duration", 1, 3600), ("media_max_images", 1, 30),
        ("media_request_timeout", 5, 60), ("media_total_timeout", 30, 600), ("media_cooldown", 0, 300),
        ("engine_timeout", 60, 600), ("webpage_timeout", 15, 90), ("webpage_max_height", 900, 10000)
    ):
        value = result[name]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{name} 必须是 {minimum}～{maximum} 的整数")
    if not isinstance(result["query_host"], str) or not result["query_host"].strip():
        raise ValueError("query_host 不能为空")
    if type(result['bilibili_quality']) is not int or result['bilibili_quality'] not in (16, 32, 64, 80):
        raise ValueError('bilibili_quality 只支持 16/32/64/80（360P/480P/720P/1080P）')
    for name in ('bilibili_cookie', 'bilibili_refresh_token', 'douyin_cookie', 'xiaohongshu_cookie'):
        if not isinstance(result[name], str) or '\r' in result[name] or '\n' in result[name]:
            raise ValueError(f'{name} 必须为单行 Cookie 字符串')
        result[name] = result[name].strip()
    if not isinstance(result['upstream'], dict):
        raise ValueError('upstream 必须为配置对象')
    if not isinstance(result['engine_node'], str) or not result['engine_node'].strip():
        raise ValueError('engine_node 必须为 Node 可执行文件路径')
    from urllib.parse import urlsplit
    registry = result['engine_npm_registry']
    if not isinstance(registry,str): raise ValueError('engine_npm_registry 必须为字符串')
    if registry.strip():
        url=urlsplit(registry.strip())
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or any(ord(c)<33 for c in registry.strip()):
            raise ValueError('engine_npm_registry 必须是无账号密码的 HTTPS 地址')
    return result
