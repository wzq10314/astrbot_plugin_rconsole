import re

PATTERN = r"(?is)^#r(help|status|query|tools|shell)(?:\s+(.*))?$"


def parse_command(text: str) -> tuple[str, str] | None:
    match = re.fullmatch(PATTERN, text.strip())
    return (match[1].lower(), (match[2] or "").strip()) if match else None
