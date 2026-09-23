import asyncio
import html
import json
import re
import shutil
import tempfile
from pathlib import Path

from .engine import ENGINE
from .dependencies import browser_hint
from .models import MediaError
from ..utils.http import validate_url
from ..utils.process import run_process


def webpage_url(text):
    text=html.unescape(text.replace('\\/','/'))
    for match in re.finditer(r'https?://[^\s<>"\'，。；！、）】]+',text,re.I):
        url=match[0].rstrip(').,;!?]}')
        try: validate_url(url)
        except MediaError: continue
        return url
    return None


async def screenshot_and_send(url,settings,sender):
    validate_url(url)
    node=shutil.which(settings['engine_node'])
    if not node: raise MediaError('网页截图需要 Node.js，请检查 #rtools engine。')
    if not (ENGINE/'node_modules/playwright/package.json').exists():
        raise MediaError('网页截图依赖尚未就绪，请查看 #rtools engine，管理员可发送 #rtools browser。')
    with tempfile.TemporaryDirectory(prefix='rconsole-webpage-') as directory:
        root=Path(directory);output=root/'page.jpg';options=root/'request.json'
        options.write_text(json.dumps({'url':url,'output':str(output),'height':settings['webpage_max_height'],'timeout':settings['webpage_timeout']}),encoding='utf-8')
        result=await run_process([node,'--max-old-space-size=256',str(ENGINE/'webpage.mjs'),str(options)],settings['webpage_timeout'],3000,cwd=ENGINE)
        if result.timed_out: raise MediaError('网页截图超时，任务已停止。')
        try: data=json.loads(result.output)
        except ValueError: raise MediaError('网页截图失败，请检查 #rtools engine。') from None
        if not data.get('ok'):
            code=data.get('code')
            if code=='web_http': raise MediaError('网页返回 HTTP '+str(data.get('status'))+'，暂时无法截图。')
            if code in {'web_load','web_address'}: raise MediaError('网页无法打开，可能是网络、访问验证、非网页文件或不受支持的地址。')
            raise MediaError(browser_hint(code))
        if not output.is_file() or output.stat().st_size>settings['media_max_size_mb']*1024*1024:
            raise MediaError('网页截图文件不存在或超过发送大小上限。')
        await sender.file(output,'image')
