import re
from urllib.parse import urlsplit, parse_qs, urlencode, urljoin
from ..utils.page_state import read_state
from .models import MediaError, MediaResult

DOMAINS = ('xiaohongshu.com', 'xhslink.com', 'xhslink.cn')
REFERER = 'https://www.xiaohongshu.com/'
XHS_AGENT = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 UBrowser/6.2.4098.3 Safari/537.36'


def image_url(item):
    return item.get('urlDefault') or item.get('urlPre') or next(
        (entry.get('url') for entry in item.get('infoList', []) if entry.get('url')), '')


def number(value):
    try:
        value = float(value or 0)
        return value if 0 <= value < float('inf') else 0
    except (TypeError, ValueError):
        return 0


def video_candidates(video):
    candidates = []
    streams = (video.get('media') or {}).get('stream') or {}
    for codec, entries in streams.items() if isinstance(streams, dict) else []:
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            encoding = str(entry.get('videoCodec') or codec).lower()
            transcode = encoding not in ('h264', 'h.264', 'avc', 'avc1')
            backups = entry.get('backupUrls') or []
            if isinstance(backups, str):
                backups = [backups]
            if not isinstance(backups, list):
                backups = []
            for address in [entry.get('masterUrl'), *backups]:
                if isinstance(address, str) and address.startswith(('https://', 'http://')):
                    candidates.append((transcode, number(entry.get('avgBitrate') or entry.get('size')),
                                       address, number(entry.get('duration')) / 1000))
    candidates.sort(key=lambda item: (item[0], item[1]))
    key = (video.get('consumer') or {}).get('originVideoKey')
    if isinstance(key, str) and key.strip():
        # Original streams may use HEVC; normalize before sending to QQ.
        from urllib.parse import quote
        candidates.append((True, 0, 'https://sns-video-bd.xhscdn.com/' + quote(key.lstrip('/'), safe='/'), 0))
    unique = []
    seen = set()
    for convert, _, address, duration in candidates:
        if address not in seen:
            seen.add(address)
            unique.append((address, convert, duration))
    return unique


def parse_note(state, identifier, url):
    note = (state.get('note', {}).get('noteDetailMap', {}).get(identifier, {}) or {}).get('note')
    if not note:
        raise MediaError('小红书笔记不可见：请使用含 xsec_token 的完整分享链接，并检查 Cookie 是否有效。')
    images = [image_url(item) for item in note.get('imageList', [])]
    result = MediaResult('小红书', str(note.get('title') or '小红书笔记'),
                         str((note.get('user') or {}).get('nickname') or ''), url,
                         description=str(note.get('desc') or ''), cover=next((u for u in images if u), ''), referer=REFERER)
    if note.get('type') == 'video':
        video = note.get('video') or {}
        playable = video_candidates(video)
        if not playable:
            raise MediaError('小红书笔记已读取，但没有可用的视频地址（主地址、备用地址、原视频均缺失）。请确认该视频在浏览器可播放，并更新 Cookie 后重试。')
        result.videos = [playable[0][0]]
        result.video_candidates = [(address, convert) for address, convert, _ in playable]
        result.duration = max((duration for _, _, duration in playable), default=0) or number((video.get('capa') or {}).get('duration')) / 1000
    else:
        result.images = [u for u in images if u]
    return result


class XiaohongshuService:
    async def resolve(self, url, http, config):
        if not config['xiaohongshu_cookie'].strip():
            raise MediaError('未配置小红书 Cookie。请浏览器登录小红书，将请求头 Cookie 填入插件 xiaohongshu_cookie 后重载，并使用完整分享链接。')
        options = dict(domains=DOMAINS, cookie=config['xiaohongshu_cookie'],
                       cookie_domains=('xiaohongshu.com',), referer=REFERER, user_agent=XHS_AGENT,
                       accept='text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8')
        target = url
        if urlsplit(url).hostname in ('xhslink.cn', 'xhslink.com'):
            target, _ = await http.text(url, **options)
        parsed = urlsplit(target)
        params = parse_qs(parsed.query)
        # Recover the original note URL from a verification redirect, as upstream does.
        # This does not solve or bypass a challenge; the ensuing page may still refuse access.
        if 'captcha' in parsed.path and params.get('redirectPath'):
            from ..utils.http import validate_url
            target = urljoin(REFERER, params['redirectPath'][0])
            validate_url(target, ('xiaohongshu.com',))
            parsed = urlsplit(target)
            params = parse_qs(parsed.query)
        match = re.search(r'/(?:explore|discovery/item|item)/([0-9a-fA-F]{24})(?:/|$)', parsed.path)
        if not match:
            raise MediaError('小红书链接未落到笔记页，可能触发验证；请换用 APP 的完整分享链接并检查 Cookie。')
        token = params.get('xsec_token', [''])[0]
        if not token:
            raise MediaError('小红书分享链接缺少 xsec_token，请重新复制 APP 完整分享链接，不要删除问号后的参数。')
        canonical = REFERER + 'explore/' + match[1] + '?' + urlencode({
            'xsec_token': token, 'xsec_source': params.get('xsec_source', ['pc_feed'])[0]})
        final_url, page = await http.text(canonical, **options)
        if 'captcha' in urlsplit(final_url).path or '/404' in urlsplit(final_url).path:
            raise MediaError('小红书返回验证/不可见页面，请在浏览器确认内容可见并更新 Cookie 和分享链接。')
        return parse_note(read_state(page, 'window.__INITIAL_STATE__'), match[1], canonical)
