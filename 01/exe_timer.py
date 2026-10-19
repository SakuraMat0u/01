#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""程序运行计时器 —— 记录每个 .exe 从启动到关闭的时长，历次结果汇总到同一份 txt。

它会做什么
    1. 你给出一个 .exe 路径；
    2. 脚本立即启动它，并开始计时；
    3. 该进程退出（你关掉程序）时停表；
    4. 把本次用时更新到 运行计时记录.txt（同一个程序只占一条记录）；
    5. 默认用记事本打开记录文件。

交互提示符参数用法
    > "F:\gal\game.exe" --no-open
          写完后不自动用记事本打开
    > "F:\gal\game.exe" --check
          只检查这一个，不启动
    > -d "F:\gal"
          只换记录位置，然后继续提示输入路径
    > "F:\gal\game.exe" -d F:\gal --no-open
          三个参数同时使用

参数
    exe                 要计时的 .exe 路径；省略则进入交互输入
    -d, --out-dir DIR   记录文件所在目录，默认与脚本同目录
    --check             只检查路径与已有记录，不启动程序
    --no-open           写完后不自动用记事本打开
    -h, --help          显示帮助

记录文件
    文件名固定为 运行计时记录.txt，按程序汇总：同一个 .exe 只有一条，每次运行更新它。
        程序 / 路径 / 次数 / 累计时长 / 首次 / 最近 / 最近的单次用时
    多个程序按累计时长从多到少排列；换 -d 等于换一本账，删掉等于清空历史。

退出码
    0 正常结束   1 启动失败   2 路径无效 / 没有读到输入   130 手动中断
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RECORD_FILENAME = "运行计时记录.txt"
SEPARATOR = "=" * 60


def _force_utf8_when_redirected() -> None:
    """输出被重定向到管道或文件时统一用 UTF-8，避免中文在日志里变成乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


# ---------------------------------------------------------------- 路径与格式

def parse_exe(raw: str) -> Path:
    """把用户给的路径整理成绝对路径，并检查它确实是个存在的 .exe。"""
    text = raw.strip().strip('"').strip("'").strip()
    if not text:
        raise ValueError("路径不能为空")

    path = Path(text).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()

    if path.suffix.lower() != ".exe":
        raise ValueError(f"这不是 .exe 文件：{path.name}")
    if not path.is_file():
        raise FileNotFoundError(f"找不到文件：{path}")
    return path


def duration_text(seconds: float) -> str:
    """把秒数写成“X 小时 Y 分 Z 秒”。"""
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


# ---------------------------------------------------------------- 记录的读写

def load_entries(record: Path) -> dict[str, dict]:
    """读回“按程序汇总”的记录；读不懂的行直接跳过，不影响其它条目。"""
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


def parse_time(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def last_used(entries: dict[str, dict]) -> Path | None:
    """最近一次计时过的程序，用于“直接回车复用”。"""
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


# ---------------------------------------------------------------- 交互输入

INTERACTIVE_FLAGS = {"--check", "--no-open"}
INTERACTIVE_DIR_FLAGS = {"-d", "--out-dir"}


def tokenize(text: str) -> list[str]:
    """按空白切词并去掉引号；引号闭合后紧跟的内容（如 "a.exe"--check）另算一个词。"""
    tokens: list[str] = []
    buffer: list[str] = []
    quote = ""

    def flush() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for char in text:
        if quote:
            if char == quote:
                quote = ""
                flush()
            else:
                buffer.append(char)
        elif char in "\"'":
            flush()
            quote = char
        elif char.isspace():
            flush()
        else:
            buffer.append(char)

    flush()
    return tokens


def split_interactive_line(raw: str) -> tuple[str, set[str], Path | None, list[str]]:
    """把交互输入拆成 (路径, 选项, 记录目录, 不认识的词)。

    这些写法都支持（引号可有可无，引号后有没有空格都行）：
        "F:\\gal\\game.exe" --check
        "F:\\gal\\game.exe"--check
        -d "F:\\gal" "F:\\gal\\game.exe"
        F:\\gal\\game.exe
    """
    flags: set[str] = set()
    unknown: list[str] = []
    out_dir: Path | None = None
    path_parts: list[str] = []

    tokens = tokenize(raw.strip())
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None

        if token in INTERACTIVE_DIR_FLAGS and following and not following.startswith("-"):
            out_dir = Path(following).expanduser().resolve()
            index += 2
            continue
        if token in INTERACTIVE_FLAGS:
            flags.add(token)
        elif token.startswith("-") and len(token) > 1:
            unknown.append(token)
        else:
            path_parts.append(token)
        index += 1

    return " ".join(path_parts).strip(), flags, out_dir, unknown


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


# ---------------------------------------------------------------- 主流程

def main() -> int:
    _force_utf8_when_redirected()

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


if __name__ == "__main__":
    sys.exit(main())
