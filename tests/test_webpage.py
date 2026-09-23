import asyncio
import unittest
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock,patch
from test_plugin import Event,RConsolePlugin
from astrbot_plugin_rconsole.services.webpage import webpage_url,screenshot_and_send
from astrbot_plugin_rconsole.services.models import MediaError
from astrbot_plugin_rconsole.utils.config import load_config
from astrbot_plugin_rconsole.utils.process import run_process

class WebpageTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_and_config(self):
        self.assertEqual(webpage_url('看看 https://example.org/page?a=1&amp;b=2。'),'https://example.org/page?a=1&b=2')
        for url in ('http://127.0.0.1/','http://localhost/','https://name:pass@example.org/','file:///etc/passwd'):
            self.assertIsNone(webpage_url(url))
        for setting in ({'webpage_timeout':0},{'webpage_max_height':20000},{'webpage_enable':'true'}):
            with self.assertRaises(ValueError):load_config(setting,Path('.'))

    async def test_unmatched_page_captured_once_and_stopped(self):
        plugin=RConsolePlugin(None,{'media_cooldown':0})
        with patch('astrbot_plugin_rconsole.main.screenshot_and_send',AsyncMock()) as capture:
            for _ in range(2):
                event=Event('看看 https://example.org/article')
                self.assertEqual([x async for x in plugin.on_media(event)],[])
            capture.assert_awaited_once()
            self.assertEqual(capture.call_args.args[0],'https://example.org/article')

    async def test_existing_engine_routes_never_fall_back_even_on_failure(self):
        plugin=RConsolePlugin(None,{})
        with patch('astrbot_plugin_rconsole.main.screenshot_and_send',AsyncMock()) as capture, \
             patch.object(plugin.engine,'execute',AsyncMock(side_effect=MediaError('模拟解析失败'))) as execute:
            for url in ('https://v.douyin.com/example/','https://www.bilibili.com/video/BV1234567890','https://mp.weixin.qq.com/s/example','https://music.163.com/song?id=123'):
                replies=[x async for x in plugin.on_media(Event(url))]
                self.assertEqual(replies,['模拟解析失败'])
            self.assertEqual(execute.await_count,4)
            capture.assert_not_awaited()

    async def test_native_xhs_has_priority_in_mixed_message(self):
        plugin=RConsolePlugin(None,{'media_cooldown':0})
        with patch('astrbot_plugin_rconsole.main.screenshot_and_send',AsyncMock()) as capture, \
             patch('astrbot_plugin_rconsole.main.parse_and_send',AsyncMock()) as parse:
            event=Event('https://example.org/ https://xhslink.cn/o/example')
            self.assertEqual([x async for x in plugin.on_media(event)],[])
            parse.assert_awaited_once();capture.assert_not_awaited()

    async def test_switches_groups_self_and_commands_do_not_capture(self):
        with patch('astrbot_plugin_rconsole.main.screenshot_and_send',AsyncMock()) as capture:
            for settings,event in [({'webpage_enable':False},Event('https://example.org')),
                    ({'media_auto_parse':False},Event('https://example.org')),
                    ({'media_enable':False},Event('https://example.org')),
                    ({'media_groups':['999']},Event('https://example.org',private=False)),
                    ({},Event('#其他命令 https://example.org')),
                    ({'engine_enable':False},Event('https://mp.weixin.qq.com/s/example'))]:
                plugin=RConsolePlugin(None,settings)
                self.assertEqual([x async for x in plugin.on_media(event)],[])
            own=Event('https://example.org');own.get_sender_id=lambda:'999'
            self.assertEqual([x async for x in RConsolePlugin(None,{}).on_media(own)],[])
            capture.assert_not_awaited()

    async def test_failure_and_cancellation_release_lock(self):
        plugin=RConsolePlugin(None,{})
        with patch('astrbot_plugin_rconsole.main.screenshot_and_send',AsyncMock(side_effect=MediaError('截图失败'))):
            event=Event('https://example.org')
            self.assertEqual([x async for x in plugin.on_media(event)],['截图失败'])
            self.assertTrue(event.stopped)
        self.assertFalse(plugin.media_busy.locked());self.assertFalse(plugin.tasks)
        plugin=RConsolePlugin(None,{})
        with patch('astrbot_plugin_rconsole.main.screenshot_and_send',AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):await plugin.capture_webpage(Event(),'https://example.org')
        self.assertFalse(plugin.media_busy.locked());self.assertFalse(plugin.tasks)

    async def test_private_target_rejected_before_launch(self):
        with patch('astrbot_plugin_rconsole.services.webpage.run_process',AsyncMock()) as run:
            with self.assertRaises(MediaError):await screenshot_and_send('http://169.254.169.254/',{},AsyncMock())
            run.assert_not_awaited()

    async def test_timeout_stops_child_process_heartbeat(self):
        with tempfile.TemporaryDirectory() as directory:
            heartbeat=Path(directory)/'heartbeat.txt'
            child=f"import time; from pathlib import Path; p=Path({str(heartbeat)!r});\nfor i in range(30):\n p.write_text(str(i)); time.sleep(0.1)"
            parent=f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(10)"
            result=await run_process([sys.executable,'-c',parent],0.8,200)
            self.assertTrue(result.timed_out)
            self.assertTrue(heartbeat.exists())
            value=heartbeat.read_text()
            await asyncio.sleep(0.35)
            self.assertEqual(heartbeat.read_text(),value,'Child must stop when screenshot worker times out')
