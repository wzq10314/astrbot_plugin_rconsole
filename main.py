import asyncio
import time
import tempfile
from collections import OrderedDict
from pathlib import Path
import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .core.command import PATTERN, parse_command
from .core.permission import is_admin
from .modules import help, query, status, tools
from .utils.config import load_config
from .adapters.onebot import OneBotSender
from .services.media import EXPLICIT_PATTERN, event_text, extract_url, identify_url
from .services.models import MediaError
from .services.pipeline import parse_and_send
from .services.bilibili_login import create_login, poll_login
from .utils.http import PublicHTTP


@register("astrbot_plugin_rconsole", "RConsole Port Contributors", "B站、抖音、小红书解析与基础工具", "0.3.2")
class RConsolePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.settings = load_config(config, Path(__file__).parent)
        self.started = time.monotonic()
        self.busy = asyncio.Lock()
        self.tasks: set[asyncio.Task] = set()
        self.media_busy = asyncio.Lock()
        self.media_recent = OrderedDict()
        self.media_duplicates = OrderedDict()
        self.raw_config = config
        self.bili_login_lock = asyncio.Lock()

    async def terminate(self):
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @filter.regex(r'(?i)^#rbq$')
    async def bili_qr_login(self, event: AstrMessageEvent):
        if not is_admin(event, self.settings):
            yield event.plain_result('此命令仅允许 AstrBot 管理员或插件配置中的管理员使用。')
            event.stop_event()
            return
        if not event.is_private_chat():
            yield event.plain_result('为保护登录凭据，#RBQ 只能在机器人私聊中使用。')
            event.stop_event()
            return
        if self.settings['use_file_config']:
            yield event.plain_result('当前启用了 config.yaml 文件配置，无法安全自动回写。请先关闭 use_file_config、重载插件，再执行 #RBQ。')
            event.stop_event()
            return
        if self.bili_login_lock.locked():
            yield event.plain_result('已有 B站扫码登录正在进行，请完成当前二维码或等待超时。')
            event.stop_event()
            return
        async with self.bili_login_lock:
            task = asyncio.current_task()
            if task:
                self.tasks.add(task)
            try:
                # Do not yield to the response pipeline midway through login:
                # after_message_sent hooks can stop the event and close this generator.
                sender = OneBotSender(event)
                await sender.text('即将获取 B站登录二维码。扫码会授权机器人使用你的 B站登录凭据进行视频解析；请确认这是你自己的机器人。二维码约 3 分钟内有效。')
                logger.info('RConsole RBQ: requesting QR code')
                with tempfile.TemporaryDirectory(prefix='rconsole-bili-login-') as directory:
                    image = Path(directory) / 'bilibili-login.png'
                    async with PublicHTTP(20) as http:
                        key = await create_login(http, image)
                        logger.info('RConsole RBQ: QR image generated; sending')
                        await sender.file(image, 'image')
                        logger.info('RConsole RBQ: QR image sent; waiting for scan')
                        await sender.text('请使用哔哩哔哩 App 扫码，并在 App 内确认登录。')
                        result = await poll_login(http, key, sender.text)
                self.raw_config['bilibili_cookie'] = result.cookie
                self.raw_config['bilibili_refresh_token'] = result.refresh_token
                self.raw_config.save_config()
                self.settings['bilibili_cookie'] = result.cookie
                self.settings['bilibili_refresh_token'] = result.refresh_token
                yield event.plain_result('B站扫码登录成功，Cookie 和刷新令牌已保存到插件配置。')
            except MediaError as exc:
                logger.warning('RConsole RBQ: operation failed (MediaError)')
                yield event.plain_result(str(exc))
            except ImportError:
                logger.warning('RConsole RBQ: missing QR dependency')
                yield event.plain_result('二维码依赖缺失，请在 AstrBot 的 Python 环境安装本插件 requirements.txt 中的 qrcode[pil]，然后重载插件。')
            except TimeoutError:
                logger.warning('RConsole RBQ: request timed out')
                yield event.plain_result('B站扫码登录请求超时，请检查容器网络后重新发送 #RBQ。')
            except (aiohttp.ClientError, OSError):
                logger.warning('RConsole RBQ: network or file operation failed')
                yield event.plain_result('B站登录服务连接失败，请检查容器网络后重试。')
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning('RConsole Bilibili login failed: %s', type(exc).__name__)
                yield event.plain_result('B站扫码登录失败，请查看 AstrBot 日志。')
            finally:
                if task:
                    self.tasks.discard(task)
        event.stop_event()

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_media(self, event: AstrMessageEvent):
        if event.get_platform_name() != 'aiocqhttp':
            return
        text = event_text(event).strip()
        # The tools URL inspection command must not also trigger a download.
        if parse_command(event.get_message_str()) is not None:
            return
        explicit = bool(EXPLICIT_PATTERN.match(text))
        if not explicit and not self.settings['media_auto_parse']:
            return
        url = extract_url(text)
        if not url:
            if explicit:
                yield event.plain_result('请发送 #rparse <B站/抖音/小红书分享链接>，也支持单独的 BV 号。')
                event.stop_event()
            return
        platform = identify_url(url)
        if not self.settings['media_enable'] or not self.settings[f'{platform}_enable']:
            if explicit:
                yield event.plain_result('该平台的媒体解析已在插件配置中关闭。')
                event.stop_event()
            return
        groups = self.settings['media_groups']
        if groups and event.get_group_id() and str(event.get_group_id()) not in groups:
            return
        # Do not parse the bot's own echoed share links.
        if str(event.get_sender_id()) == str(getattr(event.message_obj, 'self_id', '')):
            return
        origin = str(event.unified_msg_origin)
        user_key = (origin, str(event.get_sender_id()))
        duplicate_key = (origin, url)
        now = time.monotonic()
        if not explicit and now - self.media_duplicates.get(duplicate_key, -1000) < 60:
            return
        if now - self.media_recent.get(user_key, -1000) < self.settings['media_cooldown']:
            if explicit:
                yield event.plain_result('解析请求过于频繁，请稍后重试。')
                event.stop_event()
            return
        if self.media_busy.locked():
            if explicit:
                yield event.plain_result('正在处理其他媒体，请稍后重试。')
                event.stop_event()
            return
        self.media_recent[user_key] = now
        self.media_recent.move_to_end(user_key)
        while len(self.media_recent) > 1024:
            self.media_recent.popitem(last=False)
        async with self.media_busy:
            task = asyncio.create_task(parse_and_send(url, self.settings, OneBotSender(event)))
            self.tasks.add(task)
            try:
                async with asyncio.timeout(self.settings['media_total_timeout']):
                    await task
                self.media_duplicates[duplicate_key] = time.monotonic()
                self.media_duplicates.move_to_end(duplicate_key)
                while len(self.media_duplicates) > 512:
                    self.media_duplicates.popitem(last=False)
            except MediaError as exc:
                yield event.plain_result(str(exc))
            except TimeoutError:
                yield event.plain_result('媒体处理超时，已停止任务；若已发送部分内容，请勿立即重复提交。')
            except (aiohttp.ClientError, OSError):
                yield event.plain_result('平台连接或文件处理失败，请检查 AstrBot 容器网络和存储空间。')
            except Exception as exc:
                # Log type only: exception strings can include signed URLs or cookies.
                logger.warning('RConsole media parse failed: %s', type(exc).__name__)
                yield event.plain_result('平台数据格式暂不兼容，解析失败；可更换完整分享链接后重试。')
            finally:
                self.tasks.discard(task)
        event.stop_event()

    @filter.regex(PATTERN)
    async def on_command(self, event: AstrMessageEvent):
        parsed = parse_command(event.get_message_str())
        if parsed is None:
            return
        command, argument = parsed
        try:
            response = await self.dispatch(event, command, argument)
        except ValueError as exc:
            response = f"参数错误：{exc}"
        except Exception:
            logger.exception("RConsole command failed")
            response = "执行失败，请查看 AstrBot 日志。"
        yield event.plain_result(response)
        event.stop_event()

    async def dispatch(self, event, command: str, argument: str) -> str:
        if command == "help":
            return help.render()
        if command == "status":
            return status.render(self.started)
        if command == "tools":
            if argument.strip() == 'cookies':
                if not is_admin(event, self.settings):
                    return 'Cookie 配置状态仅管理员可查看。'
                labels = {'bilibili_cookie': 'B站', 'douyin_cookie': '抖音', 'xiaohongshu_cookie': '小红书'}
                return '\n'.join(f"{label} Cookie：{'已配置（未校验有效性）' if self.settings[key].strip() else '未配置'}"
                                  for key, label in labels.items()) + '\n抖音 SSR 备用解析：' + ('开启' if self.settings['douyin_ssr_fallback'] else '关闭')
            return tools.handle(argument)
        if not is_admin(event, self.settings):
            return "此命令仅允许 AstrBot 管理员或插件配置中的管理员使用。"
        if command == "shell":
            if not self.settings["shell_enable"]:
                return "诊断命令默认关闭，请先在插件配置中启用 shell_enable。"
            if self.settings["shell_private_only"] and not event.is_private_chat():
                return "诊断命令仅允许私聊使用。"
        if self.busy.locked():
            return "已有查询或诊断任务在执行，请稍后重试。"
        async with self.busy:
            task = asyncio.create_task(query.handle(argument, self.settings) if command == "query"
                                       else tools.shell(argument, self.settings))
            self.tasks.add(task)
            try:
                return await task
            finally:
                self.tasks.discard(task)
