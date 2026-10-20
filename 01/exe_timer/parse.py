"""用户输入与文件路径的解析。"""

from __future__ import annotations

from pathlib import Path

INTERACTIVE_FLAGS = {"--check", "--no-open"}
INTERACTIVE_DIR_FLAGS = {"-d", "--out-dir"}


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


# ---------------------------------------------------------------- 交互输入拆词

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