import asyncio
import base64
from pathlib import Path
from ..services.models import MediaError


class OneBotSender:
    """Base64 payloads work across AstrBot/NapCat containers without shared paths."""
    def __init__(self, event, timeout=90):
        self.event, self.timeout = event, timeout

    async def text(self, message: str):
        await self.event.send(self.event.plain_result(message))

    async def file(self, path: Path, kind: str):
        if self.event.get_platform_name() != 'aiocqhttp' or not hasattr(self.event, 'bot'):
            raise MediaError('媒体发送目前仅支持 OneBot11/NapCat。')
        encoded = await asyncio.to_thread(lambda: base64.b64encode(path.read_bytes()).decode('ascii'))
        payload = [{'type': kind, 'data': {'file': 'base64://' + encoded}}]
        group = self.event.get_group_id()
        params = {'group_id': int(group)} if group else {'user_id': int(self.event.get_sender_id())}
        self_id = getattr(self.event.message_obj, 'self_id', None)
        if self_id:
            params['self_id'] = self_id
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.event.bot.call_action('send_group_msg' if group else 'send_private_msg',
                                                           message=payload, **params)
            if isinstance(response, dict) and (response.get('status') == 'failed' or response.get('retcode', 0) != 0):
                raise MediaError('NapCat 未接受媒体消息，请检查 QQ 风控和 OneBot 日志。')
        except TimeoutError:
            raise MediaError('媒体发送等待超时；请检查 NapCat 是否已收到，避免重复提交。') from None
        except MediaError:
            raise
        except Exception:
            raise MediaError('媒体发送失败，请检查 NapCat 连接、QQ 风控或调低文件大小上限。') from None
