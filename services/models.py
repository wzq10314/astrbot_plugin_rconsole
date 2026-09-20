from dataclasses import dataclass, field


class MediaError(Exception):
    """Safe user-facing error; never include cookies or response bodies."""


@dataclass
class MediaResult:
    platform: str
    title: str
    author: str
    url: str
    description: str = ""
    duration: float = 0
    cover: str = ""
    images: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    audio: str = ""
    referer: str = ""
    notice: str = ""
    # Alternative whole-video downloads: (URL, requires H.264 conversion).
    # Unlike videos, these must never be concatenated as segments.
    video_candidates: list[tuple[str, bool]] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"{self.platform}｜{self.title[:200]}"]
        if self.author:
            lines.append(f"作者：{self.author[:80]}")
        if self.duration:
            lines.append(f"时长：{self.duration:.0f} 秒")
        if self.description and self.description != self.title:
            lines.append(self.description[:600])
        lines.append(self.url)
        if self.notice:
            lines.append(self.notice)
        return "\n".join(lines)
