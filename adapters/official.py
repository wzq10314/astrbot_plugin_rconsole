"""Portable QQ Official delivery for the existing validated media pipeline."""
import base64
import hashlib
from pathlib import Path
import tempfile

from ..services.models import MediaError

PLATFORMS = frozenset({'qq_official', 'qq_official_webhook'})


def is_official(event):
    return event.get_platform_name() in PLATFORMS


def state_namespace(event):
    """The upstream Redis keys are account-local; retain existing NapCat storage."""
    if not is_official(event):
        return None
    platform = getattr(getattr(event, 'bot', None), 'platform', None)
    appid = str(getattr(platform, 'appid', '') or event.get_platform_id())
    return hashlib.sha256((str(event.get_platform_id()) + ':' + appid).encode()).hexdigest()[:24]


def portable_segments(parts):
    rows = []
    for component in parts:
        kind = str(getattr(getattr(component, 'type', ''), 'value', getattr(component, 'type', ''))).lower()
        if kind == 'plain':
            rows.append({'type': 'text', 'text': str(component.text)})
        elif kind == 'at':
            rows.append({'type': 'at', 'qq': str(component.qq)})
        elif kind == 'reply':
            rows.append({'type': 'reply', 'id': str(component.id)})
        elif kind in {'image', 'video', 'record', 'file'}:
            # File.file is a downloading property; inspect stored fields only.
            value = getattr(component, 'url', '') or getattr(component, 'file_', '')
            if not value and kind != 'file':
                value = getattr(component, 'file', '')
            rows.append({'type': kind, 'url': str(value or ''), 'file': str(value or ''),
                         'name': str(getattr(component, 'name', '') or '')})
    return rows


def event_segments(event):
    if is_official(event):
        return portable_segments(event.get_messages())
    raw = getattr(event.message_obj, 'raw_message', {})
    raw = raw if isinstance(raw, dict) else {}
    return [{**s.get('data', {}), 'type': s.get('type')}
            for s in raw.get('message', []) if isinstance(s, dict)]


def quoted_message(event, requested_id=None):
    for component in event.get_messages():
        kind = str(getattr(getattr(component, 'type', ''), 'value', getattr(component, 'type', ''))).lower()
        if kind != 'reply' or (requested_id is not None and str(component.id) != str(requested_id)):
            continue
        content = portable_segments(getattr(component, 'chain', []) or [])
        if content:
            return {'message_id': str(component.id), 'message': [
                {'type': item['type'], 'data': {k:v for k,v in item.items() if k != 'type'}} for item in content]}
    raise MediaError('QQ 官方消息未提供被引用内容，不能读取任意聊天记录。请直接发送链接，或使用本人的点歌缓存。')


def hint(event):
    if hasattr(event, 'set_extra'):
        event.set_extra('qq_official_card', {'title': 'RConsole 解析结果', 'family': 'rconsole'})


async def send_file(event, path, kind):
    import astrbot.api.message_components as Comp
    cls = {'image': Comp.Image, 'video': Comp.Video, 'record': Comp.Record}.get(kind)
    if cls:
        part = cls.fromFileSystem(path)
    elif kind == 'file':
        part = Comp.File(name=Path(path).name, file=str(path))
    else:
        raise MediaError('QQ 官方媒体类型不受支持。')
    hint(event)
    return await event.send(event.chain_result([part]))


def _confirmed_receipt(result):
    if isinstance(result, dict):
        if result.get('status') == 'failed' or any(
            result.get(key) not in (None, 0, '0')
            for key in ('code', 'retcode', 'errcode')
        ):
            return False
        # OfficialCards emits this only after checking every underlying API ID.
        if result.get('_qqofficial_send_confirmed') is True:
            return True
        message_id = result.get('id') or result.get('message_id')
    else:
        message_id = getattr(result, 'id', None)
    return ((isinstance(message_id, str) and bool(message_id.strip()))
            or (type(message_id) is int and message_id != 0))


async def _send_confirmed(event, message):
    """Observe each real send while preserving AstrBot's void public wrapper."""
    original = getattr(event, '_post_send_one', None)
    if not callable(original):
        raise MediaError('QQ 官方发送适配器不支持回执确认。')
    absent = object()
    previous = vars(event).get('_post_send_one', absent)
    confirmed = 0

    async def checked_send(*args, **kwargs):
        nonlocal confirmed
        result = await original(*args, **kwargs)
        if not _confirmed_receipt(result):
            raise MediaError('QQ 官方平台未确认消息发送成功。')
        confirmed += 1
        return result

    event._post_send_one = checked_send
    try:
        result = await event.send(message)
        if not confirmed or (result is not None and not _confirmed_receipt(result)):
            raise MediaError('QQ 官方平台未确认消息发送成功。')
        # An internal completion flag is not a fabricated QQ message ID.
        return {'rconsole_official_sent': True}
    finally:
        if vars(event).get('_post_send_one') is checked_send:
            if previous is absent:
                del event._post_send_one
            else:
                event._post_send_one = previous


async def send_segments(event, segments):
    """Convert already validated OneBot segments; files exist until send finishes."""
    import astrbot.api.message_components as Comp
    with tempfile.TemporaryDirectory(prefix='rconsole-official-send-') as directory:
        serial = 0

        def convert(rows):
            nonlocal serial
            result, nodes = [], []
            for item in rows:
                kind, data = item.get('type'), item.get('data') or {}
                if kind == 'node':
                    nodes.append(Comp.Node(name=str(data.get('name') or 'RConsole'),
                        uin=str(data.get('uin') or event.get_sender_id()), content=convert(data.get('content', []))))
                    continue
                if nodes:
                    result.append(Comp.Nodes(nodes)); nodes = []
                if kind == 'text':
                    result.append(Comp.Plain(str(data.get('text', ''))))
                elif kind == 'at':
                    result.append(Comp.At(qq=str(data.get('qq', '')), name=str(data.get('name', ''))))
                elif kind in {'image', 'video', 'record', 'file'}:
                    value = str(data.get('file', ''))
                    if not value.startswith('base64://'):
                        raise MediaError('QQ 官方发送只接受已验证的媒体缓存。')
                    encoded = value.removeprefix('base64://')
                    if kind in {'file', 'video'}:
                        serial += 1
                        target = Path(directory) / (str(serial) + ('.mp4' if kind == 'video' else ''))
                        target.write_bytes(base64.b64decode(encoded, validate=True))
                        if kind == 'video':
                            result.append(Comp.Video.fromFileSystem(target))
                        else:
                            result.append(Comp.File(name=str(data.get('name') or 'RConsole文件'), file=str(target)))
                    else:
                        cls = {'image': Comp.Image, 'record': Comp.Record}[kind]
                        result.append(cls.fromBase64(encoded))
                elif kind == 'music':
                    # Raising lets the original engine use its actual audio/file fallback.
                    raise MediaError('QQ 官方不支持 OneBot 音乐卡，请改用音频或文件发送。')
                else:
                    raise MediaError('QQ 官方暂不支持此消息类型：' + str(kind))
            if nodes:
                result.append(Comp.Nodes(nodes))
            return result

        parts = convert(segments)
        if not parts:
            raise MediaError('核心没有返回可发送内容。')
        hint(event)
        return await _send_confirmed(event, event.chain_result(parts))
