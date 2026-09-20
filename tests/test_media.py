import asyncio
import base64
import json
import os
import shutil
import sys
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import quote

from test_plugin import Event, RConsolePlugin
from astrbot_plugin_rconsole.services import pipeline
from astrbot_plugin_rconsole.services.bilibili import BilibiliService
from astrbot_plugin_rconsole.services.bilibili_login import create_login, cookies_from_headers, poll_login, LoginResult
from astrbot_plugin_rconsole.services.douyin import DouyinService, parse_aweme
from astrbot_plugin_rconsole.services.douyin_sign import signed_detail_url
from astrbot_plugin_rconsole.services.xiaohongshu import XiaohongshuService, parse_note
from astrbot_plugin_rconsole.services.media import extract_url, event_text
from astrbot_plugin_rconsole.services.models import MediaError, MediaResult
from astrbot_plugin_rconsole.services.downloader import Downloader
from astrbot_plugin_rconsole.adapters.onebot import OneBotSender
from astrbot_plugin_rconsole.utils.config import DEFAULTS, load_config
from astrbot_plugin_rconsole.utils.http import PublicHTTP, PublicResolver, validate_url
from astrbot_plugin_rconsole.utils.page_state import read_state, douyin_state, find_aweme

NOTE_ID = '674051740000000007027a15'
NOTE_URL = f'https://www.xiaohongshu.com/explore/{NOTE_ID}?xsec_token=test-token&xsec_source=pc_share'
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 100
JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 100


def note_state(kind='normal'):
    note = {'type': kind, 'title': '笔记', 'desc': 'undefined 保持原样', 'user': {'nickname': '作者'},
            'imageList': [{'urlDefault': 'https://cdn.example.com/a.jpg'}]}
    if kind == 'video':
        note['video'] = {'media': {'stream': {'h264': [{'masterUrl': 'https://cdn.example.com/v.mp4', 'duration': 12000}]}}}
    return {'note': {'noteDetailMap': {NOTE_ID: {'note': note}}}}


def aweme(kind='video'):
    value = {'aweme_id': '123456', 'desc': '分享', 'author': {'nickname': '作者'},
             'video': {'duration': 15000, 'play_addr': {'url_list': ['https://cdn.example.com/v.mp4']}}}
    if kind == 'image':
        value['images'] = [{'url_list': ['https://cdn.example.com/a.jpg']}]
    return value


class FakeResponse:
    def __init__(self, url, data=b'', status=200, headers=None):
        self.url, self.status = url, status
        self.headers = headers or {}
        self.data = data
        self.content = self
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def iter_chunked(self, n):
        for i in range(0, len(self.data), n):
            yield self.data[i:i+n]
    async def json(self, **kwargs):
        return json.loads(self.data)


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class MediaTests(unittest.IsolatedAsyncioTestCase):
    def test_bili_login_cookie_parsing(self):
        headers = types.SimpleNamespace(getall=lambda name, default: [
            'SESSDATA=abc%2Cdef; Path=/; HttpOnly', 'bili_jct=csrf; Path=/',
            'DedeUserID=123; Path=/', 'ignored=value; Path=/'])
        cookie = cookies_from_headers(headers)
        self.assertIn('SESSDATA=abc%2Cdef', cookie)
        self.assertIn('bili_jct=csrf', cookie)
        self.assertNotIn('ignored', cookie)

    async def test_bili_login_poll_success(self):
        payload = json.dumps({'code': 0, 'data': {'code': 0, 'refresh_token': 'refresh'}}).encode()
        headers = types.SimpleNamespace(getall=lambda name, default: ['SESSDATA=session; Path=/', 'bili_jct=csrf; Path=/'])
        response = FakeResponse('https://passport.bilibili.com/', payload, headers=headers)
        http = types.SimpleNamespace(open=lambda *args, **kwargs: response)
        with patch('astrbot_plugin_rconsole.services.bilibili_login.asyncio.sleep', AsyncMock()):
            result = await poll_login(http, 'key', AsyncMock(), timeout=5)
        self.assertIn('SESSDATA=session', result.cookie)
        self.assertEqual(result.refresh_token, 'refresh')

    async def test_bili_login_qr_creation(self):
        saved = []
        fake_image = types.SimpleNamespace(save=lambda path: saved.append(path))
        fake_qrcode = types.SimpleNamespace(make=lambda value: fake_image)
        http = types.SimpleNamespace(json=AsyncMock(return_value={
            'code': 0, 'data': {'url': 'https://passport.bilibili.com/h5-app/passport/login/scan?navhide=1', 'qrcode_key': 'key'}}))
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {'qrcode': fake_qrcode}):
            target = Path(directory) / 'qr.png'
            self.assertEqual(await create_login(http, target), 'key')
        self.assertEqual(saved, [target])

    async def test_rbq_permissions(self):
        plugin = RConsolePlugin(None, {})
        self.assertIn('仅允许', ([x async for x in plugin.bili_qr_login(Event())])[0])
        self.assertIn('私聊', ([x async for x in plugin.bili_qr_login(Event(admin=True, private=False))])[0])

    async def test_rbq_success_saves_config(self):
        class Config(dict):
            saved = False
            def save_config(self): self.saved = True
        config = Config(admins=['123'])
        plugin = RConsolePlugin(None, config)
        event = Event(admin=True)
        class HTTP:
            def __init__(self, *args): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        async def make_qr(http, path):
            self.assertFalse(event.stopped)
            self.assertTrue(any('即将获取' in text for text in event.sent))
            path.write_bytes(JPEG)
            return 'key'
        result = LoginResult('SESSDATA=session; bili_jct=csrf', 'refresh')
        with patch('astrbot_plugin_rconsole.main.PublicHTTP', HTTP), \
             patch('astrbot_plugin_rconsole.main.create_login', make_qr), \
             patch('astrbot_plugin_rconsole.main.poll_login', AsyncMock(return_value=result)):
            replies = []
            generator = plugin.bili_qr_login(event)
            try:
                async for reply in generator:
                    replies.append(reply)
                    # Model an after_message_sent hook stopping propagation.
                    event.stop_event()
                    break
            finally:
                await generator.aclose()
        self.assertIn('登录成功', replies[-1])
        self.assertTrue(config.saved)
        self.assertEqual(config['bilibili_refresh_token'], 'refresh')
        self.assertEqual(plugin.settings['bilibili_cookie'], result.cookie)
        event.bot.call_action.assert_awaited_once()
        self.assertFalse(plugin.bili_login_lock.locked())
        self.assertFalse(plugin.tasks)

    def test_share_extraction(self):
        self.assertEqual(extract_url('看看 https://xhslink.cn/a/test，复制打开'), 'https://xhslink.cn/a/test')
        self.assertEqual(extract_url('#解析 BV1xx411c7mD'), 'https://www.bilibili.com/video/BV1xx411c7mD')
        self.assertEqual(extract_url('#rparse av170001'), 'https://www.bilibili.com/video/av170001')
        self.assertEqual(extract_url(NOTE_URL), NOTE_URL)
        self.assertIsNone(extract_url('https://bilibili.com.attacker.test/x'))
        event = Event('')
        event.get_messages = lambda: [types.SimpleNamespace(type='Json', data={'url': 'https://b23.tv/abc'})]
        self.assertEqual(extract_url(event_text(event)), 'https://b23.tv/abc')

    def test_embedded_json(self):
        self.assertEqual(read_state('window.__INITIAL_STATE__={"s":"undefined", "n":undefined};</script>', 'window.__INITIAL_STATE__'), {'s': 'undefined', 'n': None})
        nested = json.dumps(json.dumps({'x': 'a}b'}))
        self.assertEqual(read_state('window._ROUTER_DATA=JSON.parse(' + nested + ');', 'window._ROUTER_DATA'), {'x': 'a}b'})
        self.assertEqual(douyin_state('<script id="RENDER_DATA">' + quote('{"x":1}') + '</script>'), {'x': 1})
        with self.assertRaises(MediaError): read_state('window.__INITIAL_STATE__=alert(1)', 'window.__INITIAL_STATE__')

    def test_douyin_video_and_images(self):
        self.assertEqual(parse_aweme(aweme(), '123456').duration, 15)
        self.assertEqual(len(parse_aweme(aweme('image'), '123456').images), 1)
        self.assertEqual(find_aweme({'wrong': {'aweme_id': '999', 'video': {}}, 'correct': aweme()}, '123456'), aweme())
        with self.assertRaises(MediaError): find_aweme(aweme(), '999')

    async def test_douyin_shortlink_and_ssr(self):
        http = types.SimpleNamespace(douyin_guest_cookie=AsyncMock(return_value='ttwid=guest'), text=AsyncMock(side_effect=[
            ('https://www.douyin.com/video/123456', ''),
            ('https://www.iesdouyin.com/share/video/123456/', 'window._ROUTER_DATA=' + json.dumps({'loaderData': aweme()}))]))
        result = await DouyinService().resolve('https://v.douyin.com/test', http, {**DEFAULTS, 'douyin_ssr_fallback': True})
        self.assertEqual(len(result.videos), 1)
        self.assertIn('iesdouyin.com/share/video/123456', http.text.call_args[0][0])
        self.assertIn('iPhone', http.text.call_args.kwargs['user_agent'])

    def test_xhs_video_and_images(self):
        self.assertEqual(len(parse_note(note_state(), NOTE_ID, NOTE_URL).images), 1)
        result = parse_note(note_state('video'), NOTE_ID, NOTE_URL)
        self.assertEqual(result.duration, 12)
        self.assertEqual(len(result.videos), 1)
        with self.assertRaises(MediaError): parse_note({}, NOTE_ID, NOTE_URL)

    async def test_xhs_preserves_token(self):
        http = types.SimpleNamespace(text=AsyncMock(return_value=(NOTE_URL, 'window.__INITIAL_STATE__=' + json.dumps(note_state()))))
        config = {**DEFAULTS, 'xiaohongshu_cookie': 'web_session=test'}
        result = await XiaohongshuService().resolve(NOTE_URL, http, config)
        self.assertEqual(http.text.call_args[0][0], NOTE_URL)
        self.assertEqual(result.url, NOTE_URL)
        http.text.return_value = ('https://www.xiaohongshu.com/captcha', '')
        with self.assertRaises(MediaError): await XiaohongshuService().resolve(NOTE_URL, http, config)

    def test_xhs_alternative_formats(self):
        state = note_state('video')
        video = state['note']['noteDetailMap'][NOTE_ID]['note']['video']
        video['media']['stream'] = {
            'h265': [{'masterUrl': 'https://cdn.example.com/hevc', 'duration': 23000}],
            'h264': {'backupUrls': ['https://cdn.example.com/backup'], 'size': 'unknown'}}
        video['consumer'] = {'originVideoKey': 'original/video.mp4'}
        result = parse_note(state, NOTE_ID, NOTE_URL)
        self.assertEqual(result.video_candidates, [
            ('https://cdn.example.com/backup', False), ('https://cdn.example.com/hevc', True),
            ('https://sns-video-bd.xhscdn.com/original/video.mp4', True)])
        self.assertEqual(result.duration, 23)
        video['media'] = None
        self.assertEqual(len(parse_note(state, NOTE_ID, NOTE_URL).video_candidates), 1)
        video['consumer'] = None
        with self.assertRaisesRegex(MediaError, '均缺失'):
            parse_note(state, NOTE_ID, NOTE_URL)

    async def test_xhs_backup_download_not_concatenated(self):
        async def download(url, target, maximum, **kwargs):
            if url.endswith('bad'):
                raise MediaError('HTTP 403')
            target.write_bytes(MP4)
            return len(MP4)
        http = types.SimpleNamespace(download=AsyncMock(side_effect=download))
        result = MediaResult('小红书', '', '', NOTE_URL, videos=['https://cdn.example.com/bad'],
            video_candidates=[('https://cdn.example.com/bad', False), ('https://cdn.example.com/good', False)])
        with tempfile.TemporaryDirectory() as directory:
            downloader = Downloader(http, DEFAULTS, Path(directory))
            with patch('astrbot_plugin_rconsole.services.downloader.shutil.which', return_value=None):
                self.assertEqual((await downloader.video(result)).read_bytes(), MP4)
            self.assertEqual(http.download.await_count, 2)

    async def test_xhs_hevc_transcodes(self):
        async def download(url, target, maximum, **kwargs):
            target.write_bytes(MP4)
            return len(MP4)
        async def process(args, *unused):
            self.assertIn('libx264', args)
            self.assertIn('yuv420p', args)
            Path(args[-1]).write_bytes(MP4)
            return types.SimpleNamespace(timed_out=False, code=0)
        result = MediaResult('小红书', '', '', NOTE_URL, videos=['https://cdn.example.com/hevc'],
            video_candidates=[('https://cdn.example.com/hevc', True)])
        with tempfile.TemporaryDirectory() as directory:
            downloader = Downloader(types.SimpleNamespace(download=download), DEFAULTS, Path(directory))
            with patch('astrbot_plugin_rconsole.services.downloader.shutil.which', return_value=None):
                with self.assertRaisesRegex(MediaError, 'ffmpeg'):
                    await downloader.video(result)
            with patch('astrbot_plugin_rconsole.services.downloader.shutil.which', return_value='ffmpeg'), \
                 patch('astrbot_plugin_rconsole.services.downloader.run_process', side_effect=process):
                self.assertEqual((await downloader.video(result)).name, 'result.mp4')

    async def test_cookie_requirements_match_upstream(self):
        http = types.SimpleNamespace(text=AsyncMock(), json=AsyncMock())
        with self.assertRaisesRegex(MediaError, '未配置抖音 Cookie'):
            await DouyinService().resolve('https://www.douyin.com/video/123456', http, DEFAULTS)
        with self.assertRaisesRegex(MediaError, '未配置小红书 Cookie'):
            await XiaohongshuService().resolve(NOTE_URL, http, DEFAULTS)
        http.text.assert_not_awaited()
        with self.assertRaisesRegex(MediaError, '缺少 xsec_token'):
            await XiaohongshuService().resolve(NOTE_URL.split('?')[0], http, {**DEFAULTS, 'xiaohongshu_cookie': 'a=b'})

    async def test_douyin_cookie_primary_signed_request(self):
        http = types.SimpleNamespace(text=AsyncMock(), json=AsyncMock(return_value={'aweme_detail': aweme('image')}))
        with patch('astrbot_plugin_rconsole.services.douyin.signed_detail_url', AsyncMock(return_value='https://www.douyin.com/detail?a_bogus=signed')):
            result = await DouyinService().resolve('https://www.douyin.com/note/123456', http, {**DEFAULTS, 'douyin_cookie': 'sessionid=test'})
        self.assertTrue(result.images)
        self.assertIn('a_bogus=signed', http.json.call_args.args[0])
        self.assertEqual(http.json.call_args.kwargs['cookie'], 'sessionid=test')
        http.text.assert_not_awaited()

    async def test_cookie_status_does_not_expose_values(self):
        plugin = RConsolePlugin(None, {'douyin_cookie': 'sessionid=TOP_SECRET'})
        result = await plugin.dispatch(Event(admin=True), 'tools', 'cookies')
        self.assertIn('未校验有效性', result)
        self.assertNotIn('TOP_SECRET', result)
        self.assertIn('仅管理员', await plugin.dispatch(Event(), 'tools', 'cookies'))

    async def test_original_signer_runtime(self):
        executable = os.environ.get('RCONSOLE_TEST_NODE') or shutil.which('node')
        if not executable:
            self.skipTest('Node.js is needed to execute the original signing helper')
        with patch('astrbot_plugin_rconsole.services.douyin_sign.shutil.which', return_value=executable):
            result = await signed_detail_url('7685973540454561253')
        self.assertIn('a_bogus=', result)
        self.assertIn('aweme_id=7685973540454561253', result)
        self.assertNotIn('sessionid', result)

    def test_upstream_cookie_config_aliases(self):
        config = load_config({'douyinCookie': 'sid=a', 'xiaohongshuCookie': 'web_session=b',
                              'douyinEnableSsrBackup': True}, Path('.'))
        self.assertEqual(config['douyin_cookie'], 'sid=a')
        self.assertEqual(config['xiaohongshu_cookie'], 'web_session=b')
        self.assertTrue(config['douyin_ssr_fallback'])

    async def test_bili_page_selection(self):
        info = {'code': 0, 'data': {'bvid': 'BV1xx411c7mD', 'title': '标题', 'pages': [
            {'cid': 1, 'duration': 20}, {'cid': 2, 'duration': 30, 'part': '第二段'}]}}
        http = types.SimpleNamespace(json=AsyncMock(side_effect=[info, {'code': 0, 'data': {'durl': [{'url': 'https://cdn.example.com/v.mp4'}]}}]))
        result = await BilibiliService().resolve('https://www.bilibili.com/video/BV1xx411c7mD?p=2', http, DEFAULTS)
        self.assertEqual(result.duration, 30)
        self.assertIn('P2', result.title)
        self.assertIn('cid=2', http.json.call_args[0][0])
        http.json = AsyncMock(return_value=info)
        with self.assertRaises(MediaError): await BilibiliService().resolve('https://www.bilibili.com/video/BV1xx411c7mD?p=3', http, DEFAULTS)

    async def test_bili_playback_failure_keeps_metadata(self):
        info = {'code': 0, 'data': {'bvid': 'BV1xx411c7mD', 'title': '标题', 'cid': 1, 'duration': 10}}
        http = types.SimpleNamespace(json=AsyncMock(side_effect=[info, {'code': -403}]))
        result = await BilibiliService().resolve('https://www.bilibili.com/video/BV1xx411c7mD', http, DEFAULTS)
        self.assertEqual(result.title, '标题')
        self.assertTrue(result.notice)
        self.assertFalse(result.videos)

    def test_ssrf_addresses(self):
        for url in ('http://127.0.0.1/a', 'http://[::1]/', 'http://169.254.169.254/', 'http://192.168.1.1/',
                    'http://user:pass@www.bilibili.com/', 'file:///etc/passwd', 'http://example.com:8000/'):
            with self.subTest(url=url), self.assertRaises(MediaError): validate_url(url)
        self.assertEqual(validate_url('https://www.bilibili.com/a', ('bilibili.com',)), 'www.bilibili.com')

    async def test_dns_private_rejected_at_connection(self):
        resolver = PublicResolver()
        resolver.delegate.resolve = AsyncMock(return_value=[{'host': '127.0.0.1'}])
        with self.assertRaises(OSError): await resolver.resolve('cdn.example.com')
        await resolver.close()

    async def test_redirect_and_cookie_scoping(self):
        http = PublicHTTP()
        http.session = FakeSession([FakeResponse('https://xhslink.cn/a', status=302, headers={'Location': NOTE_URL}),
                                    FakeResponse(NOTE_URL, b'hello')])
        final, body = await http.text('https://xhslink.cn/a', domains=('xhslink.cn', 'xiaohongshu.com'), cookie='secret=value', cookie_domains=('xiaohongshu.com',))
        self.assertEqual(final, NOTE_URL)
        self.assertNotIn('Cookie', http.session.calls[0][1]['headers'])
        self.assertEqual(http.session.calls[1][1]['headers']['Cookie'], 'secret=value')
        http.session = FakeSession([FakeResponse('https://xhslink.cn/a', status=302, headers={'Location': 'http://127.0.0.1'})])
        with self.assertRaises(MediaError): await http.text('https://xhslink.cn/a')
        self.assertEqual(len(http.session.calls), 1)

    async def test_download_limit_removes_partial(self):
        http = PublicHTTP()
        http.session = FakeSession([FakeResponse('https://cdn.example.com/a', b'x' * 70000)])
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'partial'
            with self.assertRaises(MediaError): await http.download('https://cdn.example.com/a', target, 66000)
            self.assertFalse(target.exists())

    async def test_download_rejects_html(self):
        async def download(url, target, maximum, **kwargs):
            target.write_bytes(b'<html>login required</html>')
            return target.stat().st_size
        with tempfile.TemporaryDirectory() as directory:
            downloader = Downloader(types.SimpleNamespace(download=download), DEFAULTS, Path(directory))
            with self.assertRaises(MediaError): await downloader.fetch('https://cdn.example.com/v', 'v.bin', '')

    async def test_onebot_group_private_base64(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'v.mp4'
            file.write_bytes(MP4)
            for private in (True, False):
                event = Event(private=private)
                await OneBotSender(event).file(file, 'video')
                args, kwargs = event.bot.call_action.call_args
                self.assertEqual(args[0], 'send_private_msg' if private else 'send_group_msg')
                encoded = kwargs['message'][0]['data']['file']
                self.assertEqual(base64.b64decode(encoded.removeprefix('base64://')), MP4)
                self.assertNotIn('file://', encoded)
            event.bot.call_action = AsyncMock(side_effect=RuntimeError('contains secret'))
            with self.assertRaisesRegex(MediaError, '发送失败'): await OneBotSender(event).file(file, 'video')

    async def test_media_entry_auto_and_explicit(self):
        plugin = RConsolePlugin(None, {'media_cooldown': 0})
        with patch('astrbot_plugin_rconsole.main.parse_and_send', AsyncMock()) as handler:
            event = Event('https://v.douyin.com/test')
            self.assertEqual([x async for x in plugin.on_media(event)], [])
            handler.assert_awaited_once()
            self.assertTrue(event.stopped)
            await anext_or_empty(plugin.on_media(Event('https://v.douyin.com/test')))
            handler.assert_awaited_once()  # duplicate suppressed
        plugin = RConsolePlugin(None, {'media_auto_parse': False})
        with patch('astrbot_plugin_rconsole.main.parse_and_send', AsyncMock()) as handler:
            await anext_or_empty(plugin.on_media(Event('https://v.douyin.com/test')))
            handler.assert_not_awaited()
            await anext_or_empty(plugin.on_media(Event('#rparse https://v.douyin.com/test')))
            handler.assert_awaited_once()

    async def test_media_scope_and_own_messages(self):
        plugin = RConsolePlugin(None, {'media_groups': ['789']})
        with patch('astrbot_plugin_rconsole.main.parse_and_send', AsyncMock()) as handler:
            await anext_or_empty(plugin.on_media(Event('https://v.douyin.com/test', private=False)))
            event = Event('https://v.douyin.com/test')
            event.message_obj.self_id = '123'
            await anext_or_empty(plugin.on_media(event))
            handler.assert_not_awaited()
        plugin = RConsolePlugin(None, {'douyin_enable': False})
        replies = [x async for x in plugin.on_media(Event('#rparse https://v.douyin.com/test'))]
        self.assertIn('关闭', replies[0])

    async def test_pipeline_download_send_cleanup(self):
        paths = []
        class HTTP:
            def __init__(self, *args): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def download(self, url, target, maximum, **kwargs):
                target.write_bytes(JPEG if url.endswith('.jpg') else MP4)
                paths.append(target)
                return target.stat().st_size
        result = MediaResult('抖音', '标题', '作者', 'https://www.douyin.com/video/123', cover='https://cdn.example.com/a.jpg', videos=['https://cdn.example.com/v.mp4'])
        sender = types.SimpleNamespace(text=AsyncMock(), file=AsyncMock())
        with patch.object(pipeline, 'PublicHTTP', HTTP), patch.object(DouyinService, 'resolve', AsyncMock(return_value=result)):
            await pipeline.parse_and_send(result.url, DEFAULTS, sender)
        self.assertEqual([call.args[1] for call in sender.file.await_args_list], ['image', 'video'])
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() for path in paths))

    async def test_pipeline_image_limit(self):
        result = MediaResult('小红书', '笔记', '', NOTE_URL, images=['https://cdn.example.com/a.jpg'] * 3)
        class HTTP:
            def __init__(self, *args): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def download(self, url, target, maximum, **kwargs):
                target.write_bytes(JPEG)
                return len(JPEG)
        sender = types.SimpleNamespace(text=AsyncMock(), file=AsyncMock())
        with patch.object(pipeline, 'PublicHTTP', HTTP), patch.object(XiaohongshuService, 'resolve', AsyncMock(return_value=result)):
            await pipeline.parse_and_send(NOTE_URL, {**DEFAULTS, 'media_max_images': 2}, sender)
        self.assertEqual(sender.file.await_count, 2)
        self.assertIn('前 2 张', sender.text.call_args[0][0])

    async def test_missing_ffmpeg_before_downloading(self):
        with tempfile.TemporaryDirectory() as directory:
            http = types.SimpleNamespace(download=AsyncMock())
            downloader = Downloader(http, DEFAULTS, Path(directory))
            result = MediaResult('B站', '', '', '', videos=['https://cdn.example.com/v'], audio='https://cdn.example.com/a')
            with patch('astrbot_plugin_rconsole.services.downloader.shutil.which', return_value=None):
                with self.assertRaisesRegex(MediaError, 'ffmpeg'): await downloader.video(result)
            http.download.assert_not_awaited()


async def anext_or_empty(generator):
    return [value async for value in generator]
