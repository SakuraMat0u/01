"""标签记忆 —— 记住每个 .exe 上次用的标签，下次自动提示。"""

from __future__ import annotations

from pathlib import Path

MEMORY_FILENAME = "标签记忆.txt"


def load_tag_memory(record_dir: Path) -> dict[str, str]:
    """返回 {路径小写: 标签}。"""
    file = record_dir / MEMORY_FILENAME
    if not file.exists():
        return {}

    text = file.read_text(encoding="utf-8-sig", errors="replace")
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if "=" in line:
            key, val = line.split("=", 1)
            result[key.strip().lower()] = val.strip()
    return result


def save_tag_memory(record_dir: Path, memory: dict[str, str]) -> None:
    """写回标签记忆文件。"""
    file = record_dir / MEMORY_FILENAME
    file.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in memory.items()]
    file.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")