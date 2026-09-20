import asyncio
import ipaddress
import re
import socket
import time


def validate_host(host: str) -> str:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        name = host.rstrip(".").encode("idna").decode("ascii")
        if len(name) > 253 or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", p) for p in name.split(".")):
            raise ValueError("请输入有效 IP 或域名，不要包含 URL、路径或端口")
        return name


async def handle(argument: str, config: dict) -> str:
    parts = argument.split()
    if not parts or parts[0].lower() not in {"ip", "ping"}:
        return "用法：#rquery ip [域名] 或 #rquery ping [域名] [端口]"
    action = parts[0].lower()
    if len(parts) > (2 if action == "ip" else 3):
        return "参数过多。请使用 #rhelp 查看格式。"
    host = validate_host(parts[1] if len(parts) > 1 else config["query_host"])
    port = int(parts[2]) if len(parts) > 2 else config["query_port"]
    if not 1 <= port <= 65535:
        raise ValueError("端口范围是 1～65535")
    try:
        async with asyncio.timeout(config["command_timeout"]):
            if action == "ip":
                results = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
                addresses = sorted({item[4][0] for item in results})
                return f"DNS 查询 {host}\n" + "\n".join(addresses[:20])
            start = time.monotonic()
            _, writer = await asyncio.open_connection(host, port)
            elapsed = (time.monotonic() - start) * 1000
            writer.close()
            await writer.wait_closed()
            return f"TCP {host}:{port} 连接成功\n耗时 {elapsed:.0f} ms（含 DNS 解析，非 ICMP ping）"
    except TimeoutError:
        return "网络查询超时。"
    except OSError:
        return "网络查询失败：域名无法解析、端口拒绝连接或网络不可达。"
