import re
import aiohttp
from urllib.parse import parse_qs, urlsplit, urlencode
from ..utils.page_state import douyin_state, find_aweme
from .models import MediaError, MediaResult
from .douyin_sign import API_AGENT, signed_detail_url

DOMAINS = ('douyin.com', 'iesdouyin.com')
REFERER = 'https://www.douyin.com/'
MOBILE_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Version/16.0 Mobile/15E148 Safari/604.1'


def first_url(value):
    if not isinstance(value, dict):
        return ''
    return next((u for u in value.get('url_list', []) if isinstance(u, str) and u.startswith(('http://', 'https://'))), '')


def parse_aweme(aweme, identifier):
    video = aweme.get('video') or {}
    images = [first_url(item) for item in aweme.get('images') or []]
    result = MediaResult('抖音', str(aweme.get('desc') or '抖音分享'),
                         str((aweme.get('author') or {}).get('nickname') or ''),
                         f'https://www.douyin.com/{"note" if images else "video"}/{identifier}',
                         duration=float(video.get('duration') or aweme.get('duration') or 0) / 1000,
                         cover=first_url(video.get('cover') or {}), images=[u for u in images if u], referer=REFERER)
    if images:
        result.duration = 0
        if any(item.get('video') for item in aweme.get('images', [])):
            result.notice = '动图笔记按静态图集发送，暂不合成背景音乐。'
    else:
        play = first_url(video.get('play_addr_h264') or {}) or first_url(video.get('play_addr') or {})
        if not play:
            identifier_uri = (video.get('play_addr') or {}).get('uri', '')
            if re.fullmatch(r'[A-Za-z0-9_-]{8,160}', identifier_uri):
                play = 'https://aweme.snssdk.com/aweme/v1/play/?' + urlencode({'video_id': identifier_uri, 'ratio': '720p', 'line': 0})
        if not play:
            raise MediaError('抖音页面没有提供视频地址，可能需要登录或内容不可见。')
        result.videos = [play]
    return result


class DouyinService:
    async def resolve(self, url, http, config):
        options = dict(domains=DOMAINS, cookie=config['douyin_cookie'], cookie_domains=DOMAINS,
                       referer=REFERER, user_agent=MOBILE_AGENT)
        if not options['cookie'] and not config['douyin_ssr_fallback']:
            raise MediaError('未配置抖音 Cookie。请浏览器登录抖音，将请求头 Cookie 填入插件 douyin_cookie 后重载；普通视频可另行开启 douyin_ssr_fallback。')
        if urlsplit(url).hostname == 'v.douyin.com':
            url, _ = await http.text(url, **options)
        parsed = urlsplit(url)
        match = re.search(r'/(?:video|note|slides)/(\d+)', parsed.path)
        identifier = match[1] if match else parse_qs(parsed.query).get('modal_id', [''])[0]
        if not identifier.isdigit():
            raise MediaError('当前支持抖音视频和图文笔记，不支持直播或用户主页。')
        primary_error = None
        if config['douyin_cookie']:
            try:
                target = await signed_detail_url(identifier)
                api_options = {**options, 'user_agent': API_AGENT, 'origin': 'https://open.douyin.com'}
                detail = await http.json(target, **api_options)
                if not detail.get('aweme_detail'):
                    raise MediaError('抖音主接口未返回内容：Cookie 可能失效、请求被验证或作品不可见，请更新 Cookie 后重试。')
                return parse_aweme(find_aweme(detail, identifier), identifier)
            except MediaError as exc:
                primary_error = exc
            except (aiohttp.ClientError, TimeoutError, OSError):
                primary_error = MediaError('抖音主接口请求失败，请检查容器网络。')
        # Match the original: SSR is an explicit fallback for ordinary videos only.
        eligible = config['douyin_ssr_fallback'] and not any(x in parsed.path for x in ('/note/', '/slides/', '/live/'))
        if not eligible:
            raise primary_error or MediaError('抖音图文需要登录 Cookie；SSR 备用解析仅用于普通视频。')
        if not options['cookie']:
            try:
                options['cookie'] = await http.douyin_guest_cookie()
            except (aiohttp.ClientError, TimeoutError, OSError):
                pass
        kinds = ['note', 'video'] if any(x in parsed.path for x in ('/note/', '/slides/')) else ['video', 'note']
        last_error = None
        for target in [f'https://www.iesdouyin.com/share/{kind}/{identifier}/' for kind in kinds] + [url]:
            try:
                _, page = await http.text(target, **options)
                aweme = find_aweme(douyin_state(page), identifier)
                if aweme.get('images'):
                    raise MediaError('此内容是抖音图文，请配置登录 Cookie 后通过主接口解析。')
                return parse_aweme(aweme, identifier)
            except MediaError as exc:
                last_error = exc
            except (aiohttp.ClientError, TimeoutError, OSError):
                last_error = MediaError('抖音分享页连接失败，请检查容器网络或稍后重试。')
        raise primary_error or last_error or MediaError('抖音解析失败，请检查分享链接和 Cookie。')
