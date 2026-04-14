#!/usr/bin/env python3
"""
扫描所有 Markdown 文件，构建多维索引。

用法:
    python scripts/build_index.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import BASE_DIR

CHANNELS_DIR = BASE_DIR / "channels"
INDEX_DIR = BASE_DIR / "index"
QUOTES_DIR = BASE_DIR / "quotes"
MAX_LINES_PER_FILE = 500


def parse_frontmatter(filepath: Path) -> dict | None:
    """解析 Markdown 文件的 YAML frontmatter"""
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    fm_text = text[3:end].strip()
    meta = {}
    current_key = None
    current_list = None

    for line in fm_text.split("\n"):
        if line.startswith("  - ") and current_key:
            if current_list is None:
                current_list = []
            val = line.strip().lstrip("- ").strip().strip('"')
            current_list.append(val)
            meta[current_key] = current_list
            continue
        elif line.startswith("  ") and current_key and ":" not in line.split("#")[0]:
            continue

        if current_list is not None:
            current_list = None

        m = re.match(r'^(\w[\w_]*)\s*:\s*(.*)', line)
        if m:
            current_key = m.group(1)
            val = m.group(2).strip().strip('"')
            if val == "[]":
                meta[current_key] = []
            elif val == "true":
                meta[current_key] = True
            elif val == "false":
                meta[current_key] = False
            elif val.isdigit():
                meta[current_key] = int(val)
            elif val == "":
                meta[current_key] = ""
            else:
                meta[current_key] = val
            current_list = None if not isinstance(meta.get(current_key), list) else None

    if isinstance(meta.get("tags"), str):
        meta["tags"] = [meta["tags"]] if meta["tags"] else []
    if isinstance(meta.get("keywords"), str):
        kw = meta["keywords"].strip("[]")
        meta["keywords"] = [k.strip().strip('"') for k in kw.split(",") if k.strip()] if kw else []

    return meta


def scan_articles() -> list[dict]:
    """扫描所有频道下的 Markdown 文件"""
    articles = []
    if not CHANNELS_DIR.exists():
        return articles

    for md_file in sorted(CHANNELS_DIR.rglob("*.md"), reverse=True):
        if md_file.name.endswith(".quotes.md"):
            continue
        meta = parse_frontmatter(md_file)
        if not meta or "id" not in meta:
            continue
        meta["_path"] = str(md_file.relative_to(BASE_DIR))
        quotes_path = md_file.with_suffix("").with_suffix(".quotes.md")
        if quotes_path.exists():
            meta["_quotes_path"] = str(quotes_path.relative_to(BASE_DIR))
        articles.append(meta)

    return articles


def scan_quotes() -> list[dict]:
    """扫描所有金句文件"""
    quotes = []
    for qf in CHANNELS_DIR.rglob("*.quotes.md"):
        text = qf.read_text(encoding="utf-8")
        source_file = str(qf.with_name(qf.name.replace(".quotes.md", ".md")).relative_to(BASE_DIR))
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("> ") and not line.startswith("> —"):
                quotes.append({
                    "text": line[2:].strip(),
                    "source_file": source_file,
                    "quotes_file": str(qf.relative_to(BASE_DIR)),
                })
    for qf in (QUOTES_DIR).rglob("*.md") if QUOTES_DIR.exists() else []:
        text = qf.read_text(encoding="utf-8")
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("> ") and not line.startswith("> —"):
                quotes.append({
                    "text": line[2:].strip(),
                    "source_file": "",
                    "quotes_file": str(qf.relative_to(BASE_DIR)),
                })
    return quotes


def build_main_index(articles: list[dict], quotes: list[dict]):
    """构建 INDEX.md"""
    channels_stats = defaultdict(lambda: {"count": 0, "latest": "", "tags": set()})
    for a in articles:
        ch = a.get("channel", "unknown")
        channels_stats[ch]["count"] += 1
        d = a.get("date", "")
        if d > channels_stats[ch]["latest"]:
            channels_stats[ch]["latest"] = d
        for t in a.get("tags", []):
            channels_stats[ch]["tags"].add(t)

    all_tags = set()
    all_categories = set()
    for a in articles:
        all_tags.update(a.get("tags", []))
        cat = a.get("topic_category", "")
        if cat:
            all_categories.add(cat)

    recent = articles[:30]

    lines = [
        "# 知识星球知识库\n",
        f"> 最后构建: {_now()} | 总文章: {len(articles)} | 总金句: {len(quotes)}\n",
        "## 最近更新\n",
        "| 日期 | 频道 | 标题 | 标签 | 类型 |",
        "|------|------|------|------|------|",
    ]
    for a in recent:
        title = a.get("summary") or Path(a["_path"]).stem
        tags_str = ", ".join(a.get("tags", [])[:3]) or "-"
        link = f"[{_trunc(title, 30)}]({a['_path']})"
        lines.append(
            f"| {a.get('date', '')} | {a.get('source', '')} | {link} | {tags_str} | {a.get('content_type', '')} |"
        )

    lines.append("\n## 频道概览\n")
    lines.append("| 频道 | 文章数 | 最近更新 | 主要标签 |")
    lines.append("|------|--------|---------|---------|")
    for ch, stats in sorted(channels_stats.items()):
        tags_str = ", ".join(sorted(stats["tags"])[:5]) or "-"
        lines.append(f"| {ch} | {stats['count']} | {stats['latest']} | {tags_str} |")

    lines.append("\n## 可用标签\n")
    lines.append(", ".join(sorted(all_tags)) if all_tags else "暂无标签")

    lines.append("\n## 主题分类\n")
    if all_categories:
        cat_counts = defaultdict(int)
        for a in articles:
            cat = a.get("topic_category", "")
            if cat:
                cat_counts[cat] += 1
        for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {cat} ({cnt}篇)")
    else:
        lines.append("暂无分类（需要 Agent 补充 enrichment）")

    lines.append("\n## 查找指南\n")
    lines.append("- 按日期: `index/by-date/{year}/{month}.md`")
    lines.append("- 按标签: `index/by-tag/{tag}.md`")
    lines.append("- 按主题: `index/by-topic/{topic}.md`")
    lines.append("- 按频道: `index/by-channel/{channel}.md`")
    lines.append("- 金句索引: `index/quotes-index.md`")
    lines.append("- 全文搜索: `python scripts/search.py \"关键词\"`")

    (BASE_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✅ INDEX.md ({len(articles)} 篇文章, {len(quotes)} 条金句)")


def build_date_index(articles: list[dict]):
    """按年月构建日期索引"""
    date_dir = INDEX_DIR / "by-date"
    date_dir.mkdir(parents=True, exist_ok=True)

    by_year_month = defaultdict(list)
    for a in articles:
        d = a.get("date", "")
        if len(d) >= 7:
            ym = d[:7]
            by_year_month[ym].append(a)

    for ym, items in sorted(by_year_month.items(), reverse=True):
        year, month = ym.split("-")
        target_dir = date_dir / year
        target_dir.mkdir(parents=True, exist_ok=True)

        lines = [f"# {year}年{month}月\n"]
        lines.append(f"> 共 {len(items)} 篇\n")
        lines.append("| 日期 | 频道 | 标题 | 标签 |")
        lines.append("|------|------|------|------|")
        for a in items:
            title = a.get("summary") or Path(a["_path"]).stem
            tags_str = ", ".join(a.get("tags", [])[:3]) or "-"
            lines.append(
                f"| {a.get('date', '')} | {a.get('source', '')} | "
                f"[{_trunc(title, 30)}]({_rel(a['_path'], target_dir)}) | {tags_str} |"
            )
        (target_dir / f"{month}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  ✅ by-date/ ({len(by_year_month)} 个月份)")


def build_tag_index(articles: list[dict]):
    """按标签构建索引"""
    tag_dir = INDEX_DIR / "by-tag"
    tag_dir.mkdir(parents=True, exist_ok=True)

    by_tag = defaultdict(list)
    for a in articles:
        for tag in a.get("tags", []):
            by_tag[tag].append(a)

    for tag, items in sorted(by_tag.items()):
        fname = _safe_index_name(tag)
        lines = [f"# {tag}\n"]
        lines.append(f"> 共 {len(items)} 篇\n")

        ch_counts = defaultdict(int)
        for a in items:
            ch_counts[a.get("source", "")] += 1
        lines.append("频道分布: " + " | ".join(f"{ch}({cnt})" for ch, cnt in ch_counts.items()))
        lines.append("")

        lines.append("| 日期 | 频道 | 标题 | 关键词 |")
        lines.append("|------|------|------|--------|")
        for a in items[:MAX_LINES_PER_FILE]:
            title = a.get("summary") or Path(a["_path"]).stem
            kw = ", ".join(a.get("keywords", [])[:4]) or "-"
            lines.append(
                f"| {a.get('date', '')} | {a.get('source', '')} | "
                f"[{_trunc(title, 30)}]({_rel(a['_path'], tag_dir)}) | {kw} |"
            )
        if len(items) > MAX_LINES_PER_FILE:
            lines.append(f"\n> 仅显示前 {MAX_LINES_PER_FILE} 条，共 {len(items)} 条")

        (tag_dir / f"{fname}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  ✅ by-tag/ ({len(by_tag)} 个标签)")


def build_topic_index(articles: list[dict]):
    """按主题分类构建索引"""
    topic_dir = INDEX_DIR / "by-topic"
    topic_dir.mkdir(parents=True, exist_ok=True)

    by_topic = defaultdict(list)
    for a in articles:
        cat = a.get("topic_category", "")
        if cat:
            by_topic[cat].append(a)

    for topic, items in sorted(by_topic.items()):
        fname = _safe_index_name(topic)
        lines = [f"# {topic}\n"]
        lines.append(f"> 共 {len(items)} 篇\n")
        lines.append("| 日期 | 频道 | 标题 | 关键词 |")
        lines.append("|------|------|------|--------|")
        for a in items[:MAX_LINES_PER_FILE]:
            title = a.get("summary") or Path(a["_path"]).stem
            kw = ", ".join(a.get("keywords", [])[:4]) or "-"
            lines.append(
                f"| {a.get('date', '')} | {a.get('source', '')} | "
                f"[{_trunc(title, 30)}]({_rel(a['_path'], topic_dir)}) | {kw} |"
            )

        (topic_dir / f"{fname}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  ✅ by-topic/ ({len(by_topic)} 个分类)")


def build_channel_index(articles: list[dict]):
    """按频道构建索引"""
    ch_dir = INDEX_DIR / "by-channel"
    ch_dir.mkdir(parents=True, exist_ok=True)

    by_channel = defaultdict(list)
    for a in articles:
        by_channel[a.get("channel", "unknown")].append(a)

    for ch, items in sorted(by_channel.items()):
        lines = [f"# {items[0].get('source', ch)}\n"]
        lines.append(f"> 共 {len(items)} 篇\n")

        lines.append("| 日期 | 标题 | 标签 | 类型 |")
        lines.append("|------|------|------|------|")
        for a in items[:MAX_LINES_PER_FILE]:
            title = a.get("summary") or Path(a["_path"]).stem
            tags_str = ", ".join(a.get("tags", [])[:3]) or "-"
            lines.append(
                f"| {a.get('date', '')} | "
                f"[{_trunc(title, 30)}]({_rel(a['_path'], ch_dir)}) | {tags_str} | {a.get('content_type', '')} |"
            )
        if len(items) > MAX_LINES_PER_FILE:
            lines.append(f"\n> 仅显示前 {MAX_LINES_PER_FILE} 条，共 {len(items)} 条")

        (ch_dir / f"{ch}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  ✅ by-channel/ ({len(by_channel)} 个频道)")


def build_quotes_index(quotes: list[dict]):
    """构建金句索引"""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    if not quotes:
        lines = ["# 金句索引\n", "> 暂无金句，需要 Agent 补充 enrichment\n"]
    else:
        lines = [
            "# 金句索引\n",
            f"> 共 {len(quotes)} 条金句\n",
        ]
        for q in quotes[:300]:
            lines.append(f"> {q['text']}")
            if q.get("source_file"):
                lines.append(f"> — [原文]({q['source_file']})\n")
            else:
                lines.append("")

    (INDEX_DIR / "quotes-index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✅ quotes-index.md ({len(quotes)} 条)")


def build_json_index(articles: list[dict], quotes: list[dict]):
    """构建机器可读的 JSON 索引"""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index = {
        "total_articles": len(articles),
        "total_quotes": len(quotes),
        "articles": [],
        "tag_index": defaultdict(list),
        "topic_index": defaultdict(list),
    }

    for a in articles:
        aid = a.get("id", "")
        entry = {
            "id": aid,
            "path": a.get("_path", ""),
            "channel": a.get("channel", ""),
            "source": a.get("source", ""),
            "author": a.get("author", ""),
            "date": a.get("date", ""),
            "type": a.get("type", ""),
            "content_type": a.get("content_type", ""),
            "is_digest": a.get("is_digest", False),
            "tags": a.get("tags", []),
            "topic_category": a.get("topic_category", ""),
            "keywords": a.get("keywords", []),
            "summary": a.get("summary", ""),
            "quotes_count": a.get("quotes_count", 0),
        }
        if "_quotes_path" in a:
            entry["quotes_path"] = a["_quotes_path"]
        index["articles"].append(entry)

        for tag in a.get("tags", []):
            index["tag_index"][tag].append(aid)
        cat = a.get("topic_category", "")
        if cat:
            index["topic_index"][cat].append(aid)

    (INDEX_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✅ index.json")


# --- helpers ---

def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _trunc(s: str, n: int) -> str:
    s = s.replace("|", "\\|").replace("\n", " ")
    return s[:n] + "..." if len(s) > n else s


def _safe_index_name(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|#]', "", name)
    return name.strip() or "other"


def _rel(path: str, from_dir: Path) -> str:
    """计算从 from_dir 到 path 的相对路径"""
    try:
        return str(Path("../../") / path)
    except Exception:
        return path


def main():
    print("🔨 构建索引...\n")
    articles = scan_articles()
    quotes = scan_quotes()
    print(f"扫描到 {len(articles)} 篇文章, {len(quotes)} 条金句\n")

    build_main_index(articles, quotes)
    build_date_index(articles)
    build_tag_index(articles)
    build_topic_index(articles)
    build_channel_index(articles)
    build_quotes_index(quotes)
    build_json_index(articles, quotes)

    print(f"\n✅ 索引构建完成")


if __name__ == "__main__":
    main()
