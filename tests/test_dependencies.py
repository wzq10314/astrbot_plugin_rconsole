import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from test_plugin import Event, RConsolePlugin
from astrbot_plugin_rconsole.services.dependencies import EngineDependencies
from astrbot_plugin_rconsole.services.models import MediaError
from astrbot_plugin_rconsole.utils.config import load_config
from astrbot_plugin_rconsole.utils.process import ProcessResult


class DependencyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ('package.json', 'package-lock.json'):
            (self.root / name).write_text('{}', encoding='utf-8')
        self.dep = EngineDependencies({'engine_auto_browser': False}, self.root)
        self.calls = []
        self.which = patch('astrbot_plugin_rconsole.services.dependencies.shutil.which', return_value='/test/node')
        self.which.start(); self.addCleanup(self.which.stop)
        self.npm = patch.object(self.dep, 'npm_command', return_value=['/test/node', '/test/npm-cli.js'])
        self.npm.start(); self.addCleanup(self.npm.stop)
        self.runner = patch('astrbot_plugin_rconsole.services.dependencies.run_process', side_effect=self.fake_process)
        self.runner.start(); self.addCleanup(self.runner.stop)

    async def fake_process(self, argv, *args, **kwargs):
        self.calls.append((argv, kwargs))
        if '--version' in argv: return ProcessResult(0, 'v22.20.0')
        if 'ci' in argv: (self.root / 'node_modules').mkdir(exist_ok=True)
        return ProcessResult(0, '')

    async def test_first_install_cached_reload_and_changed_lock(self):
        await self.dep.ensure()
        self.assertTrue(self.dep.ready)
        self.assertTrue(self.dep.marker.exists())
        await self.dep.ensure()
        self.assertEqual(sum('ci' in c[0] for c in self.calls), 1)
        (self.root / 'package-lock.json').write_text('{"updated":true}', encoding='utf-8')
        await self.dep.ensure()
        self.assertEqual(sum('ci' in c[0] for c in self.calls), 2)
        install = next(c for c in self.calls if 'ci' in c[0])
        self.assertEqual(install[1]['cwd'], self.root)
        self.assertIn('PATH', install[1]['env'])

    async def test_force_and_failed_cached_probe_reinstall(self):
        await self.dep.ensure()
        await self.dep.ensure(force=True)
        with patch.object(self.dep, 'probe', AsyncMock(side_effect=[False, True])):
            await self.dep.ensure()
        self.assertEqual(sum('ci' in c[0] for c in self.calls), 3)

    async def test_missing_node_old_node_and_missing_npm(self):
        with patch('astrbot_plugin_rconsole.services.dependencies.shutil.which', return_value=None):
            await self.dep.ensure()
        self.assertIn('未找到 Node.js', self.dep.message)
        with patch('astrbot_plugin_rconsole.services.dependencies.run_process', AsyncMock(return_value=ProcessResult(0,'v18.0.0'))):
            await self.dep.ensure()
        self.assertIn('版本不符合', self.dep.message)
        with patch.object(self.dep, 'npm_command', return_value=None):
            await self.dep.ensure()
        self.assertIn('未找到 npm', self.dep.message)
        self.assertFalse(self.dep.ready)
        self.assertFalse(self.dep.marker.exists())

    async def test_install_failure_does_not_mark_complete_or_echo_output(self):
        await self.dep.ensure()
        with patch('astrbot_plugin_rconsole.services.dependencies.run_process', AsyncMock(side_effect=[
            ProcessResult(0,'v22.0.0'), ProcessResult(1,'EACCES https://secret:password@example.test/')])):
            await self.dep.ensure(force=True)
        self.assertFalse(self.dep.ready)
        self.assertFalse(self.dep.marker.exists())
        self.assertIn('写入权限', self.dep.message)
        self.assertNotIn('password', self.dep.message)

    async def test_failed_postinstall_probe_does_not_mark_ready(self):
        with patch.object(self.dep, 'probe', AsyncMock(return_value=False)):
            await self.dep.ensure()
        self.assertFalse(self.dep.ready)
        self.assertFalse(self.dep.marker.exists())

    async def test_browser_failure_keeps_core_usable(self):
        self.dep.settings['engine_auto_browser'] = True
        async def run(argv, *args, **kwargs):
            if 'chromium' in argv: return ProcessResult(1, 'network failure')
            return await self.fake_process(argv, *args, **kwargs)
        with patch('astrbot_plugin_rconsole.services.dependencies.run_process', side_effect=run), \
             patch.object(self.dep,'browser_probe',AsyncMock(return_value='browser_missing')), \
             patch.object(self.dep,'system_install_allowed',return_value=False):
            await self.dep.ensure()
        self.assertTrue(self.dep.ready)
        self.assertIn('自动下载未成功', self.dep.browser_message)

    async def test_existing_browser_is_probed_without_download(self):
        with patch.object(self.dep,'browser_probe',AsyncMock(return_value='ready')):
            await self.dep.prepare_browser('/test/node',{})
        self.assertFalse(self.calls)
        self.assertIn('实际启动',self.dep.browser_message)

    async def test_debian_download_failure_uses_system_browser(self):
        async def run(argv,*args,**kwargs):
            self.calls.append((argv,kwargs))
            return ProcessResult(1 if 'chromium' in argv and 'apt-get' not in argv else 0,'')
        with patch.object(self.dep,'browser_probe',AsyncMock(side_effect=['browser_missing','browser_missing','ready'])), \
             patch.object(self.dep,'system_install_allowed',return_value=True), \
             patch.object(self.dep,'is_debian',return_value=True), \
             patch('astrbot_plugin_rconsole.services.dependencies.run_process',side_effect=run):
            await self.dep.prepare_browser('/test/node',{})
        self.assertIn(['apt-get','install','-y','--no-install-recommends','chromium','fonts-noto-cjk'],[c[0] for c in self.calls])
        self.assertIn('已就绪',self.dep.browser_message)

    async def test_missing_system_libraries_repaired_then_verified(self):
        with patch.object(self.dep,'browser_probe',AsyncMock(side_effect=['system_libraries','system_libraries','ready'])), \
             patch.object(self.dep,'system_install_allowed',return_value=True):
            await self.dep.prepare_browser('/test/node',{})
        self.assertTrue(any('install-deps' in c[0] for c in self.calls))
        self.assertIn('已就绪',self.dep.browser_message)

    async def test_system_repair_requires_opt_in_root_linux_and_apt(self):
        self.dep.settings['engine_auto_browser_system']=False
        self.assertFalse(self.dep.system_install_allowed())
        self.dep.settings['engine_auto_browser_system']=True
        with patch('platform.system',return_value='Windows'):
            self.assertFalse(self.dep.system_install_allowed())

    async def test_render_help_fallback_and_reason_are_readable(self):
        p=RConsolePlugin(None,{})
        response=await p.engine.handle('render_text',{'code':'browser_missing','data':{
            'saveId':'help','helpData':[{'group':'工具','list':[{'icon':'secret_icon','title':'#点歌 歌名','desc':'搜索音乐'}]}]}})
        self.assertIn('未找到可用 Chromium',response['text'])
        self.assertIn('#点歌 歌名 — 搜索音乐',response['text'])
        self.assertNotIn('saveId',response['text'])
        self.assertNotIn('secret_icon',response['text'])

    async def test_render_asset_blocks_private_network(self):
        p=RConsolePlugin(None,{})
        p.engine.data=self.root
        (self.root/'runtime').mkdir()
        self.assertIsNone(await p.engine.handle('render_asset',{'url':'http://127.0.0.1/secret.png'}))

    async def test_render_asset_validates_format_and_sends_bili_referer(self):
        p=RConsolePlugin(None,{})
        p.engine.data=self.root
        (self.root/'runtime').mkdir()
        calls=[]
        class HTTP:
            def __init__(self,*args): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def download(self,url,target,limit,**kwargs):
                calls.append((limit,kwargs))
                target.write_bytes(b'\x89PNGfixture')
        with patch('astrbot_plugin_rconsole.services.engine.PublicHTTP',HTTP):
            result=await p.engine.handle('render_asset',{'url':'https://i0.hdslb.com/example.png'})
        self.assertEqual(result['mime'],'image/png')
        self.assertEqual(calls,[(5*1024*1024,{'referer':'https://www.bilibili.com/'})])
        self.assertFalse(list((self.root/'runtime').iterdir()))

    async def test_cancellation_does_not_mark_ready(self):
        with patch('astrbot_plugin_rconsole.services.dependencies.run_process', AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError): await self.dep.ensure()
        self.assertFalse(self.dep.ready)
        self.assertFalse(self.dep.marker.exists())

    async def test_registry_and_failure_hints(self):
        self.dep.settings['engine_npm_registry'] = 'https://registry.example.test'
        await self.dep.ensure()
        self.assertIn('--registry', next(c[0] for c in self.calls if 'ci' in c[0]))
        for url in ('http://example.test', 'https://user:secret@example.test', 'https://example.test?a=b'):
            with self.assertRaises(ValueError): load_config({'engine_npm_registry':url}, self.root)
        for output, timed_out, expected in [('ENOSPC',False,'磁盘'), ('ENOTFOUND',False,'网络'), ('',True,'10 分钟')]:
            self.assertIn(expected, self.dep.failure_hint(output,timed_out))

    async def test_admin_only_dedup_and_terminate_cancels_install(self):
        plugin = RConsolePlugin(None, {})
        self.addAsyncCleanup(plugin.terminate)
        gate = asyncio.Event()
        async def prepare(**kwargs): await gate.wait()
        with patch.object(plugin.dependencies, 'ensure', side_effect=prepare) as ensure:
            self.assertIn('仅管理员', await plugin.dispatch(Event(), 'tools', 'install'))
            ensure.assert_not_called()
            self.assertIn('已开始', await plugin.dispatch(Event(admin=True), 'tools', 'install'))
            self.assertIn('正在进行', plugin.start_dependency_install())
            await asyncio.sleep(0)
            ensure.assert_awaited_once()
            with self.assertRaisesRegex(MediaError,'自动安装'):
                await plugin.engine.execute(Event('https://v.douyin.com/example/'))
            await plugin.terminate()
            self.assertTrue(plugin.install_task.done())

    async def test_busy_engine_refuses_dependency_replacement(self):
        plugin = RConsolePlugin(None, {})
        async with plugin.engine.lock:
            self.assertIn('正在解析', plugin.start_dependency_install(force=True))
        self.assertIsNone(plugin.install_task)

    async def test_initialize_starts_only_when_enabled(self):
        for enabled in (True, False):
            plugin = RConsolePlugin(None, {'engine_auto_install':enabled})
            with patch.object(plugin, 'start_dependency_install') as start:
                await plugin.initialize()
                self.assertEqual(start.call_count, int(enabled))
            await plugin.terminate()
