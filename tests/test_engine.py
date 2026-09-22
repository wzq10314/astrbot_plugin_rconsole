import asyncio
import base64
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from threading import Thread

from test_plugin import Event, RConsolePlugin
from astrbot_plugin_rconsole.services.engine import ENGINE, EngineHost, Article
from astrbot_plugin_rconsole.services.models import MediaError

class Config(dict):
    def save_config(self): self.saved=True

class Api(BaseHTTPRequestHandler):
    seen=[]
    def log_message(self,*args): pass
    def do_GET(self):
        self.seen.append(self.path)
        if self.path.startswith('/audio'):
            data=b'ID3'+b'\x00'*2048
            self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        if self.path.startswith(('/search','/cloudsearch')):
            payload={'code':200,'result':{'songs':[{'id':12345,'name':'测试歌曲','artists':[{'name':'测试歌手'}],'album':{'picUrl':''},'duration':180000}]}}
        elif self.path.startswith('/song/url'):
            payload={'code':200,'data':[{'url':f'http://127.0.0.1:{self.server.server_port}/audio.mp3','type':'mp3','size':2051,'level':'exhigh'}]}
        elif self.path.startswith('/login/qr/key'): payload={'data':{'unikey':'fixture-key'}}
        elif self.path.startswith('/login/qr/create'): payload={'data':{'qrurl':'https://music.163.com/login?code=fixture'}}
        elif self.path.startswith('/login/qr/check'): payload={'code':803,'cookie':'MUSIC_U=fixture-cookie-never-real; os=pc;'}
        elif self.path.startswith('/login/status'): payload={'data':{'account':{'id':123},'profile':{'userId':123,'nickname':'测试用户'}}}
        elif self.path.startswith('/user/detail'): payload={'code':200,'profile':{'userId':123,'nickname':'测试用户'},'level':1,'listenSongs':1}
        elif self.path.startswith('/user/cloud'): payload={'code':200,'data':[],'count':0,'hasMore':False,'size':0,'maxSize':1000000}
        else: payload={'code':200,'data':[]}
        data=json.dumps(payload).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

class EngineTests(unittest.IsolatedAsyncioTestCase):
    def plugin(self,**settings):
        config=Config(media_cooldown=0,engine_node=os.environ.get('RCONSOLE_TEST_NODE','node'),**settings)
        plugin=RConsolePlugin(None,config)
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        plugin.engine.data=Path(tmp.name)
        self.addAsyncCleanup(plugin.terminate)
        return plugin

    def test_all_routes_and_representative_platforms(self):
        plugin=self.plugin()
        self.assertEqual(len(plugin.engine.rules),53)
        for r in plugin.engine.rules:re.compile(r['reg'])
        cases={'#点歌 晴天':'pickSong','#听2':'pickSong','#rnq':'netease_scan','#rkq':'kugou_scan',
               'https://www.bilibili.com/bangumi/play/ep1':'bili','https://t.bilibili.com/123':'bili',
               'https://mp.weixin.qq.com/s/example':'linkShareSummary','https://weixin.qq.com/sph/example':'weixinChannel',
               'https://open.spotify.com/track/a':'freyr','https://www.instagram.com/p/test/':'instagram',
               'https://t.me/channel/123':'aircraft','https://music.163.com/song?id=123':'netease'}
        for text,fnc in cases.items():self.assertEqual(plugin.engine.match(text)['fnc'],fnc,text)
        migrated=self.plugin(upstream={'xiaohongshuCookie':'web_session=fixture'})
        self.assertEqual(migrated.settings['xiaohongshu_cookie'],'web_session=fixture')

    async def test_login_permissions_before_process(self):
        plugin=self.plugin()
        with self.assertRaisesRegex(MediaError,'管理员'):await plugin.engine.execute(Event('#rnq'))
        with self.assertRaisesRegex(MediaError,'私聊'):await plugin.engine.execute(Event('#rnq',admin=True,private=False))
        with self.assertRaisesRegex(MediaError,'自己的网易云'):await plugin.engine.execute(Event('#rnq',admin=True))

    async def test_real_worker_version_and_trust_persistence(self):
        plugin=self.plugin()
        for text in ['#R插件版本','#设置R信任用户 456','#R信任用户']:
            event=Event(text,admin=True)
            await plugin.engine.execute(event)
            self.assertTrue(event.bot.call_action.await_count)
        saved=json.loads((plugin.engine.data/'engine-state.json').read_text())
        self.assertIn('456',json.dumps(saved))

    async def test_real_worker_search_and_user_isolation(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Api);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        plugin=self.plugin(upstream={'neteaseCloudAPIServer':f'http://127.0.0.1:{server.server_port}','useNeteaseSongRequest':True})
        event=Event('#点歌 测试')
        await plugin.engine.execute(event)
        state=(plugin.engine.data/'engine-state.json').read_text(encoding='utf-8')
        self.assertIn('测试歌曲',state)
        self.assertTrue(event.bot.call_action.await_count)
        self.assertTrue(any(p.startswith('/search') for p in Api.seen))
        other=Event('#听1');other.get_sender_id=lambda:'456'
        await plugin.engine.execute(other)
        self.assertIn('请先使用',json.dumps(other.bot.call_action.call_args_list,default=str,ensure_ascii=False))

    async def test_real_worker_qr_sent_then_cookie_persisted(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Api);Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        plugin=self.plugin(upstream={'neteaseCloudAPIServer':f'http://127.0.0.1:{server.server_port}'})
        event=Event('#rnq',admin=True)
        await plugin.engine.execute(event)
        calls=event.bot.call_action.call_args_list
        segments=[s for call in calls for s in call.kwargs.get('message',[])]
        image=next(s for s in segments if s['type']=='image')
        self.assertTrue(base64.b64decode(image['data']['file'].removeprefix('base64://')).startswith(b'\x89PNG'))
        self.assertIn('fixture-cookie',plugin.raw_config['upstream']['neteaseCookie'])
        self.assertTrue(plugin.raw_config.saved)
        self.assertNotIn('fixture-cookie',str(calls))

    async def test_real_worker_play_download_and_later_upload(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Api);Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        plugin=self.plugin(upstream={'neteaseCloudAPIServer':f'http://127.0.0.1:{server.server_port}','neteaseCookie':'MUSIC_U=fixture-cookie'})
        event=Event('#播放 测试')
        await plugin.engine.execute(event)
        self.assertTrue(any(p.read_bytes().startswith(b'ID3') for p in (plugin.engine.data/'runtime').rglob('*.mp3')))
        later=Event('#上传')
        await plugin.engine.execute(later)
        self.assertEqual(later.bot.call_action.call_args.args[0],'upload_private_file')
        self.assertTrue(later.bot.call_action.call_args.kwargs['file'].startswith('base64://'))

    async def test_forward_and_private_music_mapping(self):
        plugin=self.plugin();host=plugin.engine;host.event=Event();host.sent=0;host.bytes_sent=0
        await host.handle('onebot',{'action':'send_group_msg','params':{'group_id':'999','message':[{'type':'music','data':{'type':'163','id':'123'}}]}})
        args,kwargs=host.event.bot.call_action.call_args
        self.assertEqual(args[0],'send_private_msg');self.assertEqual(kwargs['user_id'],'123')
        await host.reply({'message':{'type':'node','data':[{'nickname':'原作者','user_id':'123','message':'一条内容'}]}})
        self.assertEqual(host.event.bot.call_action.call_args.args[0],'send_private_forward_msg')

    async def test_real_worker_summary_uses_astrbot_without_extra_key(self):
        plugin=self.plugin()
        plugin.engine.summarize=AsyncMock(return_value='文章核心内容：测试。')
        event=Event('#总结一下 https://mp.weixin.qq.com/s/fixture')
        await plugin.engine.execute(event)
        plugin.engine.summarize.assert_awaited_once_with('https://mp.weixin.qq.com/s/fixture')
        self.assertIn('文章核心内容',str(event.bot.call_action.call_args_list))

    async def test_file_boundary_and_summary_injection_separation(self):
        plugin=self.plugin();host=plugin.engine;host.event=Event();host.bytes_sent=0
        with self.assertRaises(MediaError):await host.local_file(str(Path(__file__).resolve()))
        parser=Article();parser.feed('<article>正文</article><script>隐藏恶意脚本</script>')
        self.assertEqual(parser.parts,['正文'])
        plugin.context=type('Context',(),{'get_current_chat_provider_id':AsyncMock(return_value='current'),'llm_generate':AsyncMock(return_value=type('R',(),{'completion_text':'总结'})())})()
        class HTTP:
            def __init__(self,*args):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def text(self,url):return url,'<article>'+('正文事实。'*30)+'</article>'
        with patch('astrbot_plugin_rconsole.services.engine.PublicHTTP',HTTP):
            result=await host.summarize('https://example.com/article')
        self.assertIn('来源',result)
        kwargs=plugin.context.llm_generate.call_args.kwargs
        self.assertEqual(kwargs['chat_provider_id'],'current');self.assertIn('不可信',kwargs['system_prompt'])

    async def test_shutdown_stops_process(self):
        plugin=self.plugin();process=Mock();process.wait=AsyncMock();process.returncode=None;process.pid=123456
        plugin.engine.process=process
        with patch('os.killpg',create=True),patch.object(process,'kill'):
            await plugin.engine.close()
        process.wait.assert_awaited_once()
        plugin.engine.process=None
