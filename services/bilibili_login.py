import asyncio
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import quote
from .models import MediaError

GENERATE = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
POLL = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key='
DOMAINS = ('bilibili.com',)
COOKIE_NAMES = ('SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5', 'sid')


@dataclass
class LoginResult:
    cookie: str
    refresh_token: str


def cookies_from_headers(headers) -> str:
    jar = SimpleCookie()
    for value in headers.getall('Set-Cookie', []):
        try:
            jar.load(value)
        except Exception:
            continue
    return '; '.join(f'{name}={jar[name].value}' for name in COOKIE_NAMES if name in jar)


async def create_login(http, image_path: Path) -> str:
    import qrcode
    data = await http.json(GENERATE, domains=DOMAINS, referer='https://www.bilibili.com/')
    payload = data.get('data') or {}
    if data.get('code') != 0 or not payload.get('url') or not payload.get('qrcode_key'):
        raise MediaError('B站登录二维码获取失败，请稍后重试。')
    await asyncio.to_thread(qrcode.make(payload['url']).save, image_path)
    return str(payload['qrcode_key'])


async def poll_login(http, key: str, notify, timeout: int = 180) -> LoginResult:
    deadline = asyncio.get_running_loop().time() + timeout
    scanned_notified = False
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(3)
        async with http.open(POLL + quote(key, safe=''), domains=DOMAINS,
                             referer='https://www.bilibili.com/') as response:
            try:
                body = await response.json(content_type=None)
            except ValueError:
                raise MediaError('B站扫码状态返回异常，请稍后重试。') from None
            payload = body.get('data') or {}
            code = payload.get('code')
            if body.get('code') != 0:
                raise MediaError('B站扫码状态查询失败，请重新执行 #RBQ。')
            if code == 0:
                cookie = cookies_from_headers(response.headers)
                if 'SESSDATA=' not in cookie:
                    raise MediaError('扫码已确认，但响应中没有 SESSDATA，请重新执行 #RBQ。')
                return LoginResult(cookie, str(payload.get('refresh_token') or ''))
            if code == 86090 and not scanned_notified:
                scanned_notified = True
                await notify('二维码已扫描，请在哔哩哔哩 App 中确认登录。')
            elif code == 86038:
                raise MediaError('B站登录二维码已过期，请重新执行 #RBQ。')
            elif code not in (86101, 86090):
                raise MediaError(f'B站返回未知扫码状态（{code}），请重新执行 #RBQ。')
    raise MediaError('等待扫码超时，请重新执行 #RBQ。')
