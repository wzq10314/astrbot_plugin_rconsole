import re
import shutil
from pathlib import Path
from urllib.parse import quote_plus
from ..utils.process import run_process
from .models import MediaError

# Same UA and ordered query fields used by the uploaded R-plugin.
API_AGENT = 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.25 Mobile Safari/537.36'


def detail_query(identifier: str) -> str:
    if not identifier.isdigit():
        raise MediaError('无效的抖音内容 ID。')
    return ('device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id=' + identifier
            + '&pc_client_type=1&version_code=190500&version_name=19.5.0&cookie_enabled=true'
            '&screen_width=1344&screen_height=756&browser_language=zh-CN&browser_platform=Win32'
            '&browser_name=Firefox&browser_version=118.0&browser_online=true&engine_name=Gecko'
            '&engine_version=109.0&os_name=Windows&os_version=10&cpu_core_num=16&device_memory=&platform=PC')


async def signed_detail_url(identifier: str) -> str:
    executable = shutil.which('node') or shutil.which('nodejs')
    if not executable:
        raise MediaError('抖音 Cookie 主流程需要原版签名模块，请在 AstrBot 容器安装 nodejs；无需安装 Yunzai。')
    query = detail_query(identifier)
    script = Path(__file__).resolve().parents[1] / 'vendor' / 'sign_douyin.cjs'
    result = await run_process([executable, str(script), query, API_AGENT], 5, 2048)
    signature = result.output.strip()
    if result.timed_out or result.code != 0 or not re.fullmatch(r'[A-Za-z0-9/+=_-]{80,1024}', signature):
        raise MediaError('抖音请求签名生成失败，请检查容器 Node.js 环境。')
    return 'https://www.douyin.com/aweme/v1/web/aweme/detail/?' + query + '&a_bogus=' + quote_plus(signature)
