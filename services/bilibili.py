import re
import aiohttp
from urllib.parse import parse_qs, urlencode, urlsplit
from .models import MediaError, MediaResult

DOMAINS = ('bilibili.com', 'b23.tv', 'bili2233.cn')
REFERER = 'https://www.bilibili.com/'


class BilibiliService:
    async def resolve(self, url, http, config):
        options = dict(domains=DOMAINS, cookie=config['bilibili_cookie'], cookie_domains=('bilibili.com',), referer=REFERER)
        if urlsplit(url).hostname in ('b23.tv', 'bili2233.cn'):
            url, _ = await http.text(url, **options)
        parsed = urlsplit(url)
        match = re.search(r'/video/(BV[0-9A-Za-z]{10}|av\d+)', parsed.path, re.I)
        if not match:
            raise MediaError('当前支持 B站普通视频、BV/av 号、b23 短链与分P；直播、番剧、动态暂不支持。')
        identifier = match[1]
        params = {'aid': identifier[2:]} if identifier.lower().startswith('av') else {'bvid': 'BV' + identifier[2:]}
        response = await http.json('https://api.bilibili.com/x/web-interface/view?' + urlencode(params), **options)
        if response.get('code') != 0 or not response.get('data'):
            raise MediaError('无法读取 B站视频：可能不可见、已删除、需要登录或请求受限。')
        data = response['data']
        pages = data.get('pages') or [{'cid': data.get('cid'), 'duration': data.get('duration', 0)}]
        try:
            index = int(parse_qs(parsed.query).get('p', ['1'])[0])
            if not 1 <= index <= len(pages):
                raise ValueError
        except ValueError:
            raise MediaError('B站分P参数超出有效范围。') from None
        page = pages[index - 1]
        result = MediaResult('哔哩哔哩', str(data.get('title', '视频')), str(data.get('owner', {}).get('name', '')),
                             f"https://www.bilibili.com/video/{data['bvid']}?p={index}",
                             description=str(data.get('desc', '')), duration=float(page.get('duration') or 0),
                             cover=data.get('pic', ''), referer=REFERER)
        if len(pages) > 1:
            result.title += f" · P{index} {page.get('part', '')}"
        if result.duration > config['media_max_duration']:
            result.notice = '视频超过时长上限，仅发送信息和封面。'
            return result
        params = {'bvid': data['bvid'], 'cid': page['cid'], 'qn': config['bilibili_quality'], 'fnval': 1, 'fourk': 0}
        try:
            play = await http.json('https://api.bilibili.com/x/player/playurl?' + urlencode(params), **options)
            payload = play.get('data') or {}
            if play.get('code') != 0:
                raise MediaError('播放地址不可用，请检查登录状态或视频访问权限。')
            if payload.get('durl'):
                result.videos = [item['url'] for item in payload['durl'] if item.get('url')]
            elif payload.get('dash'):
                dash = payload['dash']
                tracks = [v for v in dash.get('video', []) if v.get('codecid') == 7 and v.get('id', 0) <= config['bilibili_quality']]
                if not tracks:
                    raise MediaError('没有符合画质设置的 H.264 视频流。')
                video = max(tracks, key=lambda v: (v.get('id', 0), v.get('bandwidth', 0)))
                audio = max(dash.get('audio') or [{}], key=lambda a: a.get('bandwidth', 0))
                result.videos = [video.get('baseUrl') or video.get('base_url')]
                result.audio = audio.get('baseUrl') or audio.get('base_url') or ''
                if not result.audio:
                    raise MediaError('平台未提供完整音频流，暂不发送无声视频。')
            else:
                raise MediaError('平台未提供可下载地址，可能需要有效 Cookie。')
        except MediaError as exc:
            result.videos = []
            result.notice = str(exc)
        except (aiohttp.ClientError, TimeoutError, OSError):
            result.videos = []
            result.notice = '已获取信息，但播放地址请求失败，请稍后重试。'
        return result
