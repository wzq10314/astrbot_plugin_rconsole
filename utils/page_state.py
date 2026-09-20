"""Read embedded JSON without evaluating JavaScript."""
import json
import re
from urllib.parse import unquote
from ..services.models import MediaError


def read_state(page: str, marker: str):
    match = re.search(re.escape(marker) + r'\s*=\s*', page)
    if not match:
        raise MediaError('页面未提供内容数据，可能需要登录、验证，或内容已不可见。')
    raw = page[match.end():].lstrip()
    decoder = json.JSONDecoder()
    try:
        if raw.startswith('JSON.parse('):
            value, _ = decoder.raw_decode(raw[len('JSON.parse('):].lstrip())
            return json.loads(value)
        raw = re.sub(r'"(?:\\.|[^"\\])*"|\bundefined\b',
                     lambda m: 'null' if m[0] == 'undefined' else m[0], raw)
        return decoder.raw_decode(raw)[0]
    except (ValueError, TypeError):
        raise MediaError('页面数据格式已变化，暂时无法解析。') from None


def douyin_state(page: str):
    if re.search(r'window\._ROUTER_DATA\s*=', page):
        return read_state(page, 'window._ROUTER_DATA')
    match = re.search(r'<script[^>]+id=[\"\']RENDER_DATA[\"\'][^>]*>(.*?)</script>', page, re.S)
    if match:
        try:
            return json.loads(unquote(match[1]))
        except ValueError:
            pass
    raise MediaError('抖音页面未提供可解析内容，可能需要有效 Cookie 或网页验证。')


def find_aweme(root, expected_id: str):
    stack = [root]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            if str(value.get('aweme_id', '')) == expected_id and (value.get('video') or value.get('images')):
                return value
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    raise MediaError('没有找到此条抖音内容，可能已删除、设为私密或需要登录。')
