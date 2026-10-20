"""常量与公共工具函数。"""

from __future__ import annotations

import sys
from datetime import datetime

RECORD_FILENAME = "运行计时记录.txt"
SEPARATOR = "=" * 60


def force_utf8_when_redirected() -> None:
    """输出被重定向到管道或文件时统一用 UTF-8，避免中文在日志里变成乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def duration_text(seconds: float) -> str:
    """把秒数写成"X 小时 Y 分 Z 秒"。"""
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} 小时 {minutes} 分 {secs} 秒"
    if minutes:
        return f"{minutes} 分 {secs} 秒"
    return f"{secs} 秒"


def normalize_exit_code(code: int) -> int:
    """Windows 上被强制结束的进程会返回 4294967295，换成 -1 更好读。"""
    return code - 0x1_0000_0000 if code > 0x7FFF_FFFF else code


def parse_time(text: str) -> datetime | None:
    """把字符串解析成 datetime；读不懂就返回 None。"""
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None