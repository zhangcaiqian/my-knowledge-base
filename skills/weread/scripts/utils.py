import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent  # skills/weread/
BASE_DIR = SKILL_DIR.parent.parent                  # 知识库根目录
CONFIG_PATH = BASE_DIR / "config.json"
BOOKS_DIR = BASE_DIR / "books"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"未找到 {CONFIG_PATH}，请复制 config.example.json 合并到 config.json 并填入微信读书 Cookie"
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def safe_book_dirname(title: str, max_length: int = 60) -> str:
    """从书名生成安全的目录名"""
    if not title:
        return "untitled"
    name = title.strip()
    name = re.sub(r"[\\/:*?\"<>|]", "", name)
    name = re.sub(r"[\s\n\r]+", " ", name)
    name = name.strip(". ")
    if len(name) > max_length:
        name = name[:max_length].rstrip(". ")
    return name or "untitled"


def format_reading_time(seconds: int) -> str:
    """秒数转可读时长"""
    if seconds < 60:
        return f"{seconds}秒"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}分钟"
    hours = minutes // 60
    remaining_min = minutes % 60
    if remaining_min:
        return f"{hours}小时{remaining_min}分钟"
    return f"{hours}小时"


def format_timestamp(ts: int) -> str:
    """Unix 时间戳 → YYYY-MM-DD"""
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def format_timestamp_full(ts: int) -> str:
    """Unix 时间戳 → YYYY-MM-DD HH:MM"""
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
