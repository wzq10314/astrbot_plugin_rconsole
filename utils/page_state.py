"""Read embedded JSON without evaluating JavaScript."""
import json
import re
from urllib.parse import unquote
from ..services.models import MediaError


_STRING = re.compile(r'"(?:\\.|[^"\\])*"', re.S)
_CONSTRUCTOR = re.compile(r'new\s+(?:Map|Set)\s*\(')


def normalize_js_literals(raw):
    """Read JSON-like state without executing page code or changing string values."""
    out, index, depth = [], 0, 0
    while index < len(raw):
        if raw[index] == '"':
            match = _STRING.match(raw, index)
            if not match:
                raise ValueError('Unterminated string')
            out.append(match[0]); index = match.end(); continue
        boundary = index == 0 or not (raw[index - 1].isalnum() or raw[index - 1] in '_$')
        constructor = _CONSTRUCTOR.match(raw, index) if boundary else None
        if constructor:
            cursor, parentheses = constructor.end(), 1
            while cursor < len(raw) and parentheses:
                if raw[cursor] == '"':
                    match = _STRING.match(raw, cursor)
                    if not match:
                        raise ValueError('Unterminated constructor string')
                    cursor = match.end(); continue
                if raw[cursor] == '(':
                    parentheses += 1
                elif raw[cursor] == ')':
                    parentheses -= 1
                cursor += 1
            if parentheses:
                raise ValueError('Unterminated constructor')
            out.append('{}'); index = cursor; continue
        end = index + len('undefined')
        if boundary and raw.startswith('undefined', index) and (
            end == len(raw) or not (raw[end].isalnum() or raw[end] in '_$')
        ):
            out.append('null'); index = end; continue
        char = raw[index]
        out.append(char); index += 1
        if char in '[{':
            depth += 1
        elif char in ']}':
            depth -= 1
            if depth == 0:
                break  # Later script statements are not part of the state literal.
    return ''.join(out)


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
        try:
            return decoder.raw_decode(raw)[0]
        except ValueError:
            return decoder.raw_decode(normalize_js_literals(raw))[0]
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
