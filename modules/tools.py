import shlex
from ..services.downloader import dependencies
from ..services.media import identify_url
from ..utils.process import run_process


def handle(argument: str) -> str:
    parts = argument.split(maxsplit=1)
    if parts == ["deps"]:
        return "媒体工具（B站部分格式需要 ffmpeg；抖音签名需要 node；其他工具可选）：\n" + "\n".join(
            f"{name}: {'已安装' if present else '未安装'}" for name, present in dependencies().items())
    if len(parts) == 2 and parts[0] == "url":
        name = identify_url(parts[1])
        return f"识别平台：{name or '未知'}。使用 #rparse <链接> 解析 B站、抖音或小红书内容。"
    return "用法：#rtools deps 或 #rtools url <URL>"


async def shell(argument: str, config: dict) -> str:
    argv = shlex.split(argument)
    allowed = [shlex.split(item) for item in config["shell_allowlist"]]
    if not argv or argv not in allowed:
        return "命令不在完整命令白名单中，请由管理员在插件配置中设置。"
    try:
        result = await run_process(argv, config["command_timeout"], config["max_output_chars"])
    except FileNotFoundError:
        return "容器内未找到该可执行程序。"
    text = f"退出码：{result.code}\n{result.output or '（无输出）'}"
    if result.timed_out:
        text += "\n命令超时，已终止。"
    if result.truncated:
        text += "\n输出已截断。"
    return text
