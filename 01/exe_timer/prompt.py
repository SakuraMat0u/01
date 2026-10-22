"""交互提示 —— 问路径、回应用户输入。"""

from __future__ import annotations

import sys
from pathlib import Path

from .common import RECORD_FILENAME
from .parse import parse_exe, split_interactive_line


def ask_exe(default: Path | None) -> tuple[Path, set[str], Path | None]:
    """交互式导入路径，返回 (程序, 选项, 记录目录)；有历史时回车即复用上次的程序。"""
    if default and default.is_file():
        print(f"上次计时的是：{default}")
        print("直接回车继续用它，或粘贴新的 .exe 路径：")
    else:
        print("请把 .exe 文件拖到本窗口（或粘贴完整路径），然后回车：")
    print("也可以带参数：--check 只检查、--no-open 不弹记事本、-d 目录 换记录位置")

    flags: set[str] = set()
    chosen_dir: Path | None = None

    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            print('\n× 没有读到输入。可以直接把路径写在命令里：exe_timer.py "D:\\a.exe"')
            raise SystemExit(2)
        except KeyboardInterrupt:
            print("\n已取消。")
            raise SystemExit(130)

        if not raw and default and default.is_file():
            return default, flags, chosen_dir

        text, found, directory, unknown = split_interactive_line(raw)
        flags.update(found)
        if directory is not None:
            chosen_dir = directory
        if unknown:
            print(f"  ！忽略了不认识的参数：{' '.join(unknown)}")

        if not text:
            # 只写了 -d 目录，改完位置继续等路径
            if chosen_dir is not None:
                print(f"记录位置改为：{chosen_dir / RECORD_FILENAME}")
            continue

        try:
            return parse_exe(text), flags, chosen_dir
        except (ValueError, FileNotFoundError) as exc:
            print(f"  × {exc}，请重新输入（Ctrl+C 退出）")


def ask_tag(default_tag: str, existing_tags: set[str]) -> str:
    """交互式询问标签；直接回车用默认，输入新名字则创建 / 合并。"""
    print(f"标签（直接回车 = {default_tag!r}）：")
    if existing_tags:
        print(f"已有标签：{', '.join(sorted(existing_tags))}")
    try:
        raw = input("> ").strip()
    except EOFError:
        print()
        return default_tag
    return raw if raw else default_tag