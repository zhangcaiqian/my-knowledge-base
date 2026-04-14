#!/usr/bin/env python3
"""
搜索知识库。

用法:
    python scripts/search.py "降息"
    python scripts/search.py --tag "宏观策略"
    python scripts/search.py --channel qijunjie-fans --limit 20
    python scripts/search.py --category "投资理念与方法"
    python scripts/search.py --date-from 2026-04-01 --date-to 2026-04-11
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import BASE_DIR

INDEX_PATH = BASE_DIR / "index" / "index.json"


def load_index() -> dict:
    if not INDEX_PATH.exists():
        print("❌ 索引不存在，请先运行: python scripts/build_index.py")
        sys.exit(1)
    with open(INDEX_PATH, encoding="utf-8") as f:
        return json.load(f)


def search(query: str = None, tag: str = None, channel: str = None,
           category: str = None, date_from: str = None, date_to: str = None,
           limit: int = 20) -> list[dict]:
    index = load_index()
    results = index["articles"]

    if channel:
        results = [a for a in results if a["channel"] == channel]

    if tag:
        tag_ids = set(index.get("tag_index", {}).get(tag, []))
        if tag_ids:
            results = [a for a in results if a["id"] in tag_ids]
        else:
            results = [a for a in results if tag in a.get("tags", [])]

    if category:
        results = [a for a in results if a.get("topic_category", "") == category]

    if date_from:
        results = [a for a in results if a.get("date", "") >= date_from]

    if date_to:
        results = [a for a in results if a.get("date", "") <= date_to]

    if query:
        q = query.lower()
        scored = []
        for a in results:
            score = 0
            summary = (a.get("summary") or "").lower()
            keywords = [k.lower() for k in a.get("keywords", [])]
            tags = [t.lower() for t in a.get("tags", [])]
            path = a.get("path", "").lower()

            if q in summary:
                score += 10
            if any(q in k for k in keywords):
                score += 8
            if any(q in t for t in tags):
                score += 5
            if q in path:
                score += 3
            if score > 0:
                scored.append((score, a))

        scored.sort(key=lambda x: (-x[0], x[1].get("date", "")), reverse=False)
        scored.sort(key=lambda x: -x[0])
        results = [a for _, a in scored]

    return results[:limit]


def format_results(results: list[dict], query: str = None) -> str:
    if not results:
        return "未找到匹配内容。"

    lines = [f"找到 {len(results)} 条结果:\n"]
    for i, a in enumerate(results, 1):
        title = a.get("summary") or Path(a["path"]).stem
        tags = ", ".join(a.get("tags", [])[:3])
        kw = ", ".join(a.get("keywords", [])[:4])
        lines.append(f"{i}. [{a.get('date', '')}] {title}")
        lines.append(f"   频道: {a.get('source', '')} | 类型: {a.get('content_type', '')}")
        if tags:
            lines.append(f"   标签: {tags}")
        if kw:
            lines.append(f"   关键词: {kw}")
        if a.get("topic_category"):
            lines.append(f"   分类: {a['topic_category']}")
        lines.append(f"   文件: {a.get('path', '')}")
        if a.get("quotes_path"):
            lines.append(f"   金句: {a['quotes_path']}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="搜索知识库")
    parser.add_argument("query", nargs="?", default=None, help="搜索关键词")
    parser.add_argument("--tag", default=None, help="按标签筛选")
    parser.add_argument("--channel", default=None, help="按频道筛选")
    parser.add_argument("--category", default=None, help="按主题分类筛选")
    parser.add_argument("--date-from", default=None, help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--date-to", default=None, help="截止日期 (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=20, help="最大结果数")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    results = search(
        query=args.query, tag=args.tag, channel=args.channel,
        category=args.category, date_from=args.date_from, date_to=args.date_to,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_results(results, args.query))


if __name__ == "__main__":
    main()
