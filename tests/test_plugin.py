import asyncio
import importlib
import logging
from pathlib import Path
import re
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp
import yaml

# Explicit offline API doubles: these tests do not start an AstrBot server.
api = types.ModuleType('astrbot.api')
api.AstrBotConfig = dict
api.logger = logging.getLogger('test')
event_api = types.ModuleType('astrbot.api.event')
event_api.AstrMessageEvent = object

def regex(pattern):
    re.compile(pattern)
    def decorate(method):
        method.pattern = pattern
        return method
    return decorate

event_api.filter = types.SimpleNamespace(regex=regex)
event_api.filter.event_message_type = lambda *args: lambda method: method
event_api.filter.EventMessageType = types.SimpleNamespace(ALL='all')
star_api = types.ModuleType('astrbot.api.star')
class Star:
    def __init__(self, context):
        self.context = context
star_api.Star = Star
star_api.Context = object
star_api.register = lambda *args: lambda cls: cls
for name, module in {'astrbot': types.ModuleType('astrbot'), 'astrbot.api': api,
                     'astrbot.api.event': event_api, 'astrbot.api.star': star_api}.items():
    sys.modules[name] = module

from astrbot_plugin_rconsole.main import RConsolePlugin
from astrbot_plugin_rconsole.core.command import parse_command
from astrbot_plugin_rconsole.modules import query, tools
from astrbot_plugin_rconsole.services.media import identify_url
from astrbot_plugin_rconsole.utils.config import load_config, DEFAULTS
from astrbot_plugin_rconsole.utils.process import run_process

class Event:
    def __init__(self, text='#rhelp', admin=False, private=True, platform='aiocqhttp'):
        self.text, self.admin, self.private, self.platform = text, admin, private, platform
        self.stopped = False
        self.message_obj = types.SimpleNamespace(self_id='999')
        self.unified_msg_origin = 'onebot:group:456'
        self.bot = types.SimpleNamespace(call_action=AsyncMock(return_value={'message_id': 1}))
        self.sent = []
    def get_message_str(self): return self.text
    def is_admin(self): return self.admin
    def get_sender_id(self): return '123'
    def get_platform_name(self): return self.platform
    def is_private_chat(self): return self.private
    def plain_result(self, text): return text
    def stop_event(self): self.stopped = True
    def get_messages(self): return []
    def get_group_id(self): return '' if self.private else '456'
    async def send(self, message): self.sent.append(message)

class Tests(unittest.IsolatedAsyncioTestCase):
    def test_parse(self):
        self.assertEqual(parse_command(' #Rquery ip example.com '), ('query', 'ip example.com'))
        self.assertIsNone(parse_command('#rhelpful'))
        self.assertIsNone(parse_command('hello #rhelp'))

    def test_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config.yaml').write_text('admins: [123]\nshell_enable: false\n', encoding='utf-8')
            self.assertEqual(load_config({'use_file_config': True}, root)['admins'], ['123'])
            self.assertFalse(load_config({}, root)['shell_enable'])
            with self.assertRaises(ValueError): load_config({'shell_enable': 'false'}, root)
            with self.assertRaises(ValueError): load_config({'query_port': 99999}, root)

    async def test_message_entry(self):
        plugin = RConsolePlugin(None, {})
        for command in ('#rhelp', '#rstatus', '#rtools deps'):
            event = Event(command)
            replies = [item async for item in plugin.on_command(event)]
            self.assertEqual(len(replies), 1)
            self.assertTrue(event.stopped)
        event = Event('#rquery ping https://bad', admin=True)
        self.assertIn('参数错误', ([item async for item in plugin.on_command(event)])[0])

    async def test_permissions(self):
        plugin = RConsolePlugin(None, {})
        self.assertIn('仅允许', await plugin.dispatch(Event(), 'query', 'ip'))
        self.assertIn('默认关闭', await plugin.dispatch(Event(admin=True), 'shell', 'uname -a'))
        plugin = RConsolePlugin(None, {'admins': ['123'], 'shell_enable': True})
        self.assertIn('仅允许私聊', await plugin.dispatch(Event(private=False), 'shell', 'uname -a'))
        self.assertIn('仅允许', await plugin.dispatch(Event(platform='telegram'), 'shell', 'uname -a'))
        self.assertIn('白名单', await plugin.dispatch(Event(), 'shell', 'uname -a; echo injected'))

    def test_url_matching(self):
        self.assertEqual(identify_url('https://www.bilibili.com/video/x'), 'bilibili')
        self.assertIsNone(identify_url('https://bilibili.com.evil.test/x'))
        with self.assertRaises(ValueError): identify_url('file:///tmp/test')

    async def test_dns(self):
        loop = asyncio.get_running_loop()
        with patch.object(loop, 'getaddrinfo', AsyncMock(return_value=[(socket.AF_INET, 1, 6, '', ('203.0.113.1', 0))])):
            self.assertIn('203.0.113.1', await query.handle('ip example.com', DEFAULTS))

    async def test_tcp(self):
        async def handler(reader, writer):
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            self.assertIn('连接成功', await query.handle(f'ping 127.0.0.1 {port}', DEFAULTS))

    async def test_network_errors(self):
        with patch.object(asyncio, 'open_connection', AsyncMock(side_effect=TimeoutError)):
            self.assertIn('超时', await query.handle('ping', DEFAULTS))
        with patch.object(asyncio, 'open_connection', AsyncMock(side_effect=OSError)):
            self.assertIn('失败', await query.handle('ping', DEFAULTS))

    async def test_process_limits(self):
        result = await run_process([sys.executable, '-c', 'print("x"*10000)'], 5, 100)
        self.assertEqual(result.code, 0)
        self.assertEqual(len(result.output), 100)
        self.assertTrue(result.truncated)
        result = await run_process([sys.executable, '-c', 'import time; time.sleep(10)'], 0.15, 100)
        self.assertTrue(result.timed_out)

    async def test_unload_cancels_work(self):
        plugin = RConsolePlugin(None, {})
        started = asyncio.Event()
        async def slow(*args):
            started.set()
            await asyncio.sleep(30)
        with patch.object(query, 'handle', slow):
            task = asyncio.create_task(plugin.dispatch(Event(admin=True), 'query', 'ip'))
            await started.wait()
            self.assertIn('已有', await plugin.dispatch(Event(admin=True), 'query', 'ip'))
            await plugin.terminate()
            with self.assertRaises(asyncio.CancelledError): await task
            self.assertFalse(plugin.tasks)

if __name__ == '__main__':
    unittest.main()
