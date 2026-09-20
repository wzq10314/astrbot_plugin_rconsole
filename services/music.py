from typing import Protocol


class MusicProvider(Protocol):
    async def search(self, keyword: str) -> list[dict[str, str]]:
        """Reserved for NetEase / QQ / Kugou implementations."""
        ...
