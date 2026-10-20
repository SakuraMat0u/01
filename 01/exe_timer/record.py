"""记录文件的读写 —— 按程序汇总，每次运行更新对应条目。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .common import SEPARATOR, duration_text, parse_time


def load_entries(record: Path) -> dict[str, dict]:
    """读回"按程序汇总"的记录；读不懂的行直接跳过，不影响其它条目。"""
    if not record.exists():
        return {}

    text = record.read_text(encoding="utf-8-sig", errors="replace")
    entries: dict[str, dict] = {}
    current: dict | None = None

    def store(entry: dict | None) -> None:
        if entry and entry["path"]:
            entries[entry["path"].lower()] = entry

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("程序") and ":" in line:
            store(current)
            current = {
                "name": line.split(":", 1)[1].strip(),
                "path": "",
                "count": 0,
                "seconds": 0.0,
                "first": None,
                "last": None,
            }
        elif current is None:
            continue
        elif line.startswith("路径") and ":" in line:
            current["path"] = line.split(":", 1)[1].strip()
        elif line.startswith("次数") and ":" in line:
            match = re.search(r"(\d+)", line)
            current["count"] = int(match.group(1)) if match else 0
        elif line.startswith("累计") and ":" in line:
            match = re.search(r"（([\d.]+) 秒）", line)
            current["seconds"] = float(match.group(1)) if match else 0.0
        elif line.startswith("首次") and ":" in line:
            current["first"] = parse_time(line.split(":", 1)[1].strip())
        elif line.startswith("最近") and ":" in line:
            current["last"] = parse_time(line.split(":", 1)[1].strip())

    store(current)
    return entries


def last_used(entries: dict[str, dict]) -> Path | None:
    """最近一次计时过的程序，用于"直接回车复用"。"""
    if not entries:
        return None
    newest = max(entries.values(), key=lambda item: item["last"] or datetime.min)
    return Path(newest["path"]) if newest["path"] else None


def render_entries(entries: dict[str, dict]) -> str:
    """按累计时长从多到少，生成整份记录文本。"""
    items = sorted(entries.values(), key=lambda item: item["seconds"], reverse=True)
    total = sum(item["seconds"] for item in items)
    lines = [
        "程序运行计时记录（按程序汇总：同一个 .exe 只有一条，每次运行更新它）",
        f"更新于 {datetime.now():%Y-%m-%d %H:%M:%S}"
        f"    共 {len(items)} 个程序，总计 {duration_text(total)}",
    ]

    for item in items:
        first = item["first"] or item["last"]
        last = item["last"] or item["first"]

        lines.extend(
            [
                "",
                SEPARATOR,
                f"程序      : {item['name']}",
                f"路径      : {item['path']}",
                f"次数      : {item['count']} 次",
                f"累计      : {duration_text(item['seconds'])}（{item['seconds']:.1f} 秒）",
                f"首次      : {first:%Y-%m-%d %H:%M:%S}" if first else "首次      : -",
                f"最近      : {last:%Y-%m-%d %H:%M:%S}" if last else "最近      : -",
            ]
        )

    return "\n".join(lines) + "\n"


def record_run(
    entries: dict[str, dict],
    exe: Path,
    started: datetime,
    ended: datetime,
    seconds: float,
) -> dict:
    """把这次用时并进对应程序那一条，返回更新后的条目。"""
    key = str(exe).lower()
    entry = entries.get(key)
    if entry is None:
        entry = {
            "name": exe.name,
            "path": str(exe),
            "count": 0,
            "seconds": 0.0,
            "first": started,
            "last": ended,
        }
        entries[key] = entry

    entry["count"] += 1
    entry["seconds"] += seconds
    entry["first"] = entry["first"] or started
    entry["last"] = ended
    return entry


def save_entries(record: Path, entries: dict[str, dict]) -> None:
    """整份重写记录（先写临时文件再替换，避免写一半损坏）。"""
    record.parent.mkdir(parents=True, exist_ok=True)
    temp = record.with_name(record.name + ".tmp")
    temp.write_text(render_entries(entries), encoding="utf-8-sig")
    temp.replace(record)