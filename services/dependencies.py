"""Install the bundled, locked Node dependencies asynchronously on first load."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil

from ..utils.process import run_process


class EngineDependencies:
    def __init__(self, settings, root):
        self.settings = settings
        self.root = Path(root)
        self.lock = asyncio.Lock()
        self.started = False
        self.ready = False
        self.message = '尚未检查'
        self.browser_message = ''

    @property
    def marker(self):
        return self.root / 'node_modules/.astrbot-dependencies.json'

    def fingerprint(self, version):
        digest = hashlib.sha256()
        for name in ('package.json', 'package-lock.json'):
            digest.update((self.root / name).read_bytes())
        digest.update(f'{version.split(".")[0]}:{platform.system()}:{platform.machine()}'.encode())
        return digest.hexdigest()

    def npm_command(self, node):
        # Run npm's JS entry with the selected Node, avoiding Windows .cmd shells.
        executable = shutil.which('npm')
        candidates = []
        if executable:
            path = Path(executable).resolve()
            if path.suffix == '.js': candidates.append(path)
            candidates += [path.parent/'node_modules/npm/bin/npm-cli.js',
                           path.parent.parent/'lib/node_modules/npm/bin/npm-cli.js']
        parent = Path(node).resolve().parent
        candidates += [parent/'node_modules/npm/bin/npm-cli.js',
                       parent.parent/'lib/node_modules/npm/bin/npm-cli.js',
                       Path('/usr/share/nodejs/npm/bin/npm-cli.js')]
        for candidate in candidates:
            if candidate.is_file(): return [node, str(candidate)]
        if executable and os.name != 'nt': return [executable]
        return None

    async def probe(self, node, env):
        result = await run_process([node, str(self.root/'probe.mjs')], 45, 2000, cwd=self.root, env=env)
        return result.code == 0 and not result.timed_out

    async def ensure(self, *, force=False):
        async with self.lock:
            self.started = True
            self.ready = False
            self.browser_message = ''
            self.message = '正在检查 Node.js 和依赖…'
            try:
                node = shutil.which(self.settings.get('engine_node') or 'node')
                if not node:
                    self.message = '未找到 Node.js。请先在 AstrBot 容器安装 Node.js 22+（含 npm），然后重载；插件会自动安装其余 Node 依赖。'
                    return
                version = await run_process([node, '--version'], 15, 200)
                match = re.match(r'v?(\d+)\.\d+\.\d+', version.output.strip())
                if version.code or not match or int(match[1]) < 22:
                    self.message = 'Node.js 版本不符合要求，请安装 Node.js 22+（含 npm），再重载插件。'
                    return
                fingerprint = self.fingerprint(version.output.strip())
                env = dict(os.environ)
                env['PATH'] = str(Path(node).parent) + os.pathsep + env.get('PATH', '')
                env['npm_config_update_notifier'] = 'false'
                env['npm_config_fetch_retries'] = '2'
                env['npm_config_fetch_timeout'] = '60000'
                try: saved = json.loads(self.marker.read_text(encoding='utf-8'))
                except (OSError, ValueError): saved = {}
                current = not force and saved.get('fingerprint') == fingerprint
                if not current or not await self.probe(node, env):
                    npm = self.npm_command(node)
                    if not npm:
                        self.message = '已找到 Node.js，但未找到 npm。请在容器补装 npm 后，管理员发送 #rtools install 重试。'
                        return
                    self.marker.unlink(missing_ok=True)
                    self.message = '正在自动安装原版核心依赖，首次下载可能需要几分钟。完成后直接重发链接，无需重载。'
                    args = npm + ['ci', '--no-audit', '--no-fund', '--prefer-offline']
                    registry = self.settings.get('engine_npm_registry', '').strip()
                    if registry: args += ['--registry', registry]
                    result = await run_process(args, 600, 16000, cwd=self.root, env=env)
                    if result.code or result.timed_out:
                        self.message = self.failure_hint(result.output, result.timed_out)
                        return
                    if not await self.probe(node, env):
                        self.message = '依赖下载结束，但完整性检查未通过。管理员可发送 #rtools install 重试，或在 engine 目录执行 npm ci 排查。'
                        return
                    self.marker.write_text(json.dumps({'fingerprint': fingerprint}), encoding='utf-8')
                self.ready = True
                self.message = '原版核心依赖已就绪，可以直接发送链接。'
                if self.settings.get('engine_auto_browser', True):
                    self.browser_message = 'Chromium 图片渲染依赖正在准备，媒体解析已可使用。'
                    browser = await run_process([node, str(self.root/'node_modules/playwright/cli.js'),
                                                 'install', 'chromium'], 600, 4000, cwd=self.root, env=env)
                    self.browser_message = ('Chromium 下载已完成；系统库仍由容器提供。' if browser.code == 0 and not browser.timed_out
                                            else 'Chromium 自动下载失败；核心解析仍可用，图文菜单会尝试文字回退。可重试 #rtools install。')
            except asyncio.CancelledError:
                if not self.ready: self.message = '依赖安装已随插件卸载停止，下次加载会重新检查。'
                raise
            except PermissionError:
                self.message = '插件目录不可写，无法自动安装依赖。请给 AstrBot 运行用户该插件目录的写入权限后重试。'
            except (OSError, ValueError):
                self.message = '依赖准备失败，请检查 Node/npm、磁盘空间和完整插件文件，再发送 #rtools install。'

    @staticmethod
    def failure_hint(output, timed_out):
        if timed_out: reason = '下载超过 10 分钟，已停止'
        elif any(x in output for x in ('EACCES', 'EPERM')): reason = '插件目录或 npm 缓存没有写入权限'
        elif 'ENOSPC' in output: reason = '容器磁盘空间不足'
        elif any(x in output for x in ('ENOTFOUND','EAI_AGAIN','ETIMEDOUT','ECONNRESET','ECONNREFUSED','CERT_')): reason = '无法正常连接依赖下载服务，请检查容器网络或 npm 镜像设置'
        else: reason = 'npm 安装未成功，请检查容器网络及 Node/npm 环境'
        # Never echo npm output: private registry URLs may contain credentials.
        return '自动安装失败：' + reason + '。管理员发送 #rtools install 可重试。'
