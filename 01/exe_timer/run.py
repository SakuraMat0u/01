"""主流程：解析参数 → 启动程序 → 计时 → 更新记录。"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .common import (
    RECORD_FILENAME,
    duration_text,
    force_utf8_when_redirected,
    normalize_exit_code,
)
from .parse import parse_exe
from .prompt import ask_exe
from .record import last_used, load_entries, record_run, save_entries

# 工作区根目录（exe_timer.py 所在位置），也是记录文件的默认存放位置。
SCRIPT_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    force_utf8_when_redirected()

    parser = argparse.ArgumentParser(
        description="导入一个 .exe 自动计时，所有运行结果追加保存到同一个 txt",
        epilog='交互输入时同样支持 --check / --no-open / -d 目录，例如："D:\\a.exe" --check',
    )
    parser.add_argument("exe", nargs="?", help=".exe 路径；省略则交互输入")
    parser.add_argument("-d", "--out-dir", help="记录文件所在目录，默认与脚本同目录")
    parser.add_argument("--no-open", action="store_true", help="写完后不要自动用记事本打开")
    parser.add_argument("--check", action="store_true", help="只检查路径和记录文件，不启动程序")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else SCRIPT_DIR
    extra: set[str] = set()
    chosen_dir: Path | None = None

    try:
        if args.exe:
            exe = parse_exe(args.exe)
        else:
            known = load_entries(out_dir / RECORD_FILENAME)
            exe, extra, chosen_dir = ask_exe(last_used(known))
    except (ValueError, FileNotFoundError) as exc:
        print(f"× {exc}")
        return 2

    if chosen_dir is not None:
        out_dir = chosen_dir

    record = out_dir / RECORD_FILENAME
    entries = load_entries(record)

    check = args.check or "--check" in extra
    no_open = args.no_open or "--no-open" in extra

    if check:
        print(f"✓ 路径有效：{exe}")
        print(f"  记录文件：{record}（已有 {len(entries)} 个程序记录）")
        print("  （--check：只检查，没有启动程序）")
        return 0

    print(f"程序：{exe}")
    print("计时开始…（关闭这个程序后会自动停止并追加到记录）", flush=True)

    started = datetime.now()
    begin = time.monotonic()

    try:
        proc = subprocess.Popen([str(exe)], cwd=str(exe.parent))
    except OSError as exc:
        print(f"× 启动失败：{exc}")
        return 1

    try:
        exit_code = proc.wait()
    except KeyboardInterrupt:
        print("\n× 已中断计时（被计时的程序可能仍在运行），本次不写入记录。")
        return 130

    seconds = time.monotonic() - begin
    ended = datetime.now()
    exit_code = normalize_exit_code(exit_code)

    entry = record_run(entries, exe, started, ended, seconds)
    save_entries(record, entries)

    print(f"程序已关闭：本次 {duration_text(seconds)}（退出码 {exit_code}）")
    print(f"该程序第 {entry['count']} 次，累计 {duration_text(entry['seconds'])}")
    print(f"已更新：{record}")

    if not no_open:
        try:
            subprocess.Popen(["notepad.exe", str(record)])
        except OSError:
            pass

    return 0