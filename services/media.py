import html
import json
import re
from typing import Protocol
from urllib.parse import urlsplit

PLATFORMS = {
    "bilibili": ("bilibili.com", "b23.tv", "bili2233.cn"),
    "douyin": ("douyin.com", "iesdouyin.com"),
    "youtube": ("youtube.com", "youtu.be"),
    "weibo": ("weibo.com", "weibo.cn"),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com", "xhslink.cn"),
    "netease_music": ("music.163.com", "163cn.tv"),
    "qq_music": ("y.qq.com",),
    "kugou": ("kugou.com",),
}


def identify_url(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("请输入无账号密码的 http/https URL")
    host = parsed.hostname.lower().rstrip(".")
    return next((name for name, domains in PLATFORMS.items()
                 if any(host == domain or host.endswith("." + domain) for domain in domains)), None)


class MediaProvider(Protocol):
    async def resolve(self, url, http, config):
        """Return a MediaResult without downloading media."""
        ...


SUPPORTED = {'bilibili', 'douyin', 'xiaohongshu'}
MEDIA_PATTERN = r'(?is)(?:^#(?:rparse|解析|b站解析|抖音解析|小红书解析)(?:\s|$)|https?://|\bBV[0-9A-Za-z]{10}\b|^av\d+$)'
EXPLICIT_PATTERN = re.compile(r'^#(?:rparse|解析|b站解析|抖音解析|小红书解析)(?:\s|$)', re.I)


def extract_url(text: str) -> str | None:
    text = html.unescape(text.replace('\\/', '/'))
    for match in re.finditer(r'https?://[^\s<>"\'，。；！、）】]+', text, re.I):
        url = match[0].rstrip(').,;!?]}')
        try:
            if identify_url(url) in SUPPORTED:
                return url
        except ValueError:
            continue
    match = re.search(r'(?<![A-Za-z0-9])BV[0-9A-Za-z]{10}(?![A-Za-z0-9])', text)
    if match:
        return f'https://www.bilibili.com/video/{match[0]}'
    cleaned = EXPLICIT_PATTERN.sub('', text).strip()
    if re.fullmatch(r'av\d+', cleaned, re.I):
        return f'https://www.bilibili.com/video/{cleaned}'
    return None


def event_text(event) -> str:
    parts = [event.get_message_str()]
    # QQ mini-app share cards expose the original URL inside a Json component.
    for component in event.get_messages():
        kind = getattr(component, 'type', '')
        if str(getattr(kind, 'value', kind)).lower() == 'json':
            data = getattr(component, 'data', '')
            parts.append(json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data))
    return '\n'.join(parts)
