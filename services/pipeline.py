import tempfile
import aiohttp
from pathlib import Path
from .bilibili import BilibiliService
from .douyin import DouyinService
from .xiaohongshu import XiaohongshuService
from .downloader import Downloader
from .media import identify_url
from .models import MediaError
from ..utils.http import PublicHTTP

PROVIDERS = {'bilibili': BilibiliService, 'douyin': DouyinService, 'xiaohongshu': XiaohongshuService}


async def parse_and_send(url: str, config: dict, sender):
    platform = identify_url(url)
    if platform not in PROVIDERS:
        raise MediaError('当前解析支持 B站、抖音、小红书。')
    async with PublicHTTP(config['media_request_timeout']) as http:
        result = await PROVIDERS[platform]().resolve(url, http, config)
        await sender.text(result.summary())
        with tempfile.TemporaryDirectory(prefix='rconsole-media-') as temp:
            downloader = Downloader(http, config, Path(temp))
            if result.images:
                images = result.images[:config['media_max_images']]
                failed = 0
                for index, image in enumerate(images):
                    try:
                        file = await downloader.fetch(image, f'image-{index}.bin', result.referer, image=True)
                        await sender.file(file, 'image')
                    except (MediaError, aiohttp.ClientError, TimeoutError, OSError):
                        failed += 1
                if failed:
                    await sender.text(f'{failed} 张图片下载或发送失败，可打开原链接查看。')
                if len(result.images) > len(images):
                    await sender.text(f'图集共 {len(result.images)} 张，按配置仅处理前 {len(images)} 张。')
                return
            if result.cover:
                try:
                    cover = await downloader.fetch(result.cover, 'cover.bin', result.referer, image=True)
                    await sender.file(cover, 'image')
                except (MediaError, aiohttp.ClientError, TimeoutError, OSError):
                    await sender.text('封面获取或发送失败，继续尝试视频。')
            if result.duration > config['media_max_duration']:
                if not result.notice:
                    await sender.text('视频超过时长上限，仅发送信息和封面。')
                return
            if result.videos:
                video = await downloader.video(result)
                await sender.file(video, 'video')
            elif not result.notice:
                await sender.text('已获取文字信息，但页面没有提供可发送的图片或视频。')
