import shutil
import asyncio
import aiohttp
from dataclasses import replace
from pathlib import Path
from ..utils.process import run_process
from .models import MediaError


def dependencies() -> dict[str, bool]:
    return {tool: shutil.which(tool) is not None for tool in ("ffmpeg", "node", "BBDown", "yt-dlp", "aria2c")}


class Downloader:
    def __init__(self, http, config, directory: Path):
        self.http, self.config, self.directory = http, config, directory
        self.limit = config['media_max_size_mb'] * 1024 * 1024
        self.used = 0

    async def fetch(self, url: str, name: str, referer: str, image=False) -> Path:
        path = self.directory / name
        maximum = min(self.limit - self.used, 8 * 1024 * 1024) if image else self.limit - self.used
        if maximum <= 0:
            raise MediaError('本条内容下载总量已达到配置上限。')
        self.used += await self.http.download(url, path, maximum, referer=referer)
        with path.open('rb') as stream:
            magic = stream.read(64)
        if image:
            valid = (magic.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n', b'GIF87a', b'GIF89a'))
                     or (magic.startswith(b'RIFF') and magic[8:12] == b'WEBP'))
        else:
            valid = b'ftyp' in magic[:32] or magic.startswith(b'FLV')
        if not valid:
            raise MediaError('返回内容不是受支持的图片/MP4/FLV 文件，可能为验证页面。')
        return path

    async def video(self, result, *, transcode=False) -> Path:
        if result.video_candidates:
            last_error = None
            for address, convert in result.video_candidates[:6]:
                try:
                    return await self.video(replace(result, videos=[address], video_candidates=[]), transcode=convert)
                except (MediaError, aiohttp.ClientError, asyncio.TimeoutError) as error:
                    last_error = error
            if isinstance(last_error, MediaError):
                raise last_error
            raise MediaError('小红书视频主地址和备用地址下载均失败，请稍后重试或更新分享链接。')
        if len(result.videos) > 12:
            raise MediaError('视频分段过多，暂不下载。')
        needs_mux = bool(transcode or result.audio or len(result.videos) > 1)
        if needs_mux and not shutil.which('ffmpeg'):
            raise MediaError('此视频需要转换编码或合并音画，请在 AstrBot 容器安装 ffmpeg。')
        tracks = [await self.fetch(url, f'video-{i}.bin', result.referer) for i, url in enumerate(result.videos)]
        if not tracks:
            raise MediaError('没有可下载的视频地址。')
        with tracks[0].open('rb') as stream:
            needs_mux |= stream.read(3) == b'FLV'
        if not needs_mux:
            return tracks[0]
        executable = shutil.which('ffmpeg')
        if not executable:
            raise MediaError('此视频需要转换容器，请在 AstrBot 容器安装 ffmpeg。')
        args = [executable, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y']
        if len(tracks) > 1:
            listing = self.directory / 'segments.txt'
            listing.write_text('\n'.join(f"file '{path.name}'" for path in tracks), encoding='utf-8')
            args += ['-protocol_whitelist', 'file,pipe', '-f', 'concat', '-safe', '1', '-i', str(listing)]
        else:
            args += ['-protocol_whitelist', 'file,pipe', '-i', str(tracks[0])]
        if result.audio:
            audio = await self.fetch(result.audio, 'audio.bin', result.referer)
            args += ['-protocol_whitelist', 'file,pipe', '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0']
        target = self.directory / 'result.mp4'
        if transcode:
            args += ['-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'veryfast',
                     '-crf', '25', '-pix_fmt', 'yuv420p', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:a', 'aac']
        else:
            args += ['-c', 'copy']
        args += ['-movflags', '+faststart', '-fs', str(self.limit + 1024 * 1024), str(target)]
        process = await run_process(args, 60, 1000)
        if process.timed_out or process.code != 0 or not target.exists():
            raise MediaError('视频合并失败或超时，请检查 ffmpeg 和平台提供的媒体格式。')
        if target.stat().st_size > self.limit:
            raise MediaError('合并后的视频超过大小上限，不发送截断文件。')
        return target
