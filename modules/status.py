import os
import platform
import time
import tomllib
from pathlib import Path


def render(started: float) -> str:
    version = "未知"
    try:
        project = tomllib.loads(Path("/AstrBot/pyproject.toml").read_text(encoding="utf-8"))
        version = project["project"]["version"]
    except (OSError, ValueError, KeyError):
        pass
    lines = ["RConsole v0.3.2", f"AstrBot: {version}", f"Python: {platform.python_version()}",
             f"系统: {platform.system()} {platform.machine()}",
             f"插件运行: {int(time.monotonic() - started)} 秒", f"可见逻辑 CPU: {os.cpu_count()}"]
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                lines.append(f"AstrBot 进程内存 RSS: {int(line.split()[1]) / 1024:.1f} MiB")
                break
    except (OSError, ValueError):
        pass
    return "\n".join(lines)
