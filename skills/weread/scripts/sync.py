#!/usr/bin/env python3
"""
微信读书 → 知识库同步

用法:
    # 列出书架上的书（按书名搜索）
    python3 skills/weread/scripts/sync.py --list
    python3 skills/weread/scripts/sync.py --list --book "金花"

    # 同步某本书
    python3 skills/weread/scripts/sync.py --book "金花的秘密"

    # 同步某 bookId
    python3 skills/weread/scripts/sync.py --book-id 24217632

    # 刷新（覆盖已有文件）
    python3 skills/weread/scripts/sync.py --book "金花" --refresh
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from weread_api import WeReadClient
from utils import (
    load_config,
    safe_book_dirname,
    format_reading_time,
    format_timestamp,
    format_timestamp_full,
    BOOKS_DIR,
)


def build_chapter_map(chapters: list[dict]) -> dict[int, str]:
    """chapterUid → 章节标题"""
    return {ch["chapterUid"]: ch.get("title", f"第{ch['chapterUid']}章") for ch in chapters}


def build_highlights_md(
    book_info: dict,
    chapters: list[dict],
    bookmarks: list[dict],
    reviews: list[dict],
    read_info: dict,
) -> str:
    """生成 highlights.md 内容"""
    chapter_map = build_chapter_map(chapters)

    title = book_info.get("title", "未知书名")
    author = book_info.get("author", "未知作者")
    isbn = book_info.get("isbn", "")
    category = book_info.get("category", "")
    publisher = book_info.get("publisher", "")
    cover = book_info.get("cover", "")
    intro = book_info.get("intro", "")
    book_id = book_info.get("bookId", "")
    rating = book_info.get("newRating", 0)

    reading_detail = read_info.get("readDetail", read_info.get("readingDetail", {}))
    total_time = reading_detail.get("totalReadTime", 0) if isinstance(reading_detail, dict) else 0
    finished = read_info.get("finishReading", 0)

    bookmark_dates = [b.get("createTime", 0) for b in bookmarks if b.get("createTime")]
    review_dates = [r.get("createTime", 0) for r in reviews if r.get("createTime")]
    all_dates = bookmark_dates + review_dates
    first_date = format_timestamp(min(all_dates)) if all_dates else ""
    last_date = format_timestamp(max(all_dates)) if all_dates else ""

    lines = [
        "---",
        f"title: \"{title}\"",
        f"author: \"{author}\"",
        f"book_id: \"{book_id}\"",
        f"isbn: \"{isbn}\"",
        f"category: \"{category}\"",
        f"publisher: \"{publisher}\"",
        f"cover: \"{cover}\"",
        f"rating: {rating}",
        f"total_read_time: \"{format_reading_time(total_time)}\"",
        f"finished: {'true' if finished else 'false'}",
        f"highlights_count: {len(bookmarks)}",
        f"thoughts_count: {len(reviews)}",
        f"first_mark_date: \"{first_date}\"",
        f"last_mark_date: \"{last_date}\"",
        "keywords: []",
        "quotes_count: 0",
        "summary: \"\"",
        "---",
        "",
        f"# {title}",
        "",
        f"**{author}**",
        "",
    ]

    if intro:
        lines.append(f"> {intro[:200]}{'...' if len(intro) > 200 else ''}")
        lines.append("")

    bm_by_chapter: dict[int, list[dict]] = {}
    for bm in sorted(bookmarks, key=lambda x: (x.get("chapterUid", 0), x.get("range", ""))):
        uid = bm.get("chapterUid", 0)
        bm_by_chapter.setdefault(uid, []).append(bm)

    rv_by_chapter: dict[int, list[dict]] = {}
    for rv in sorted(reviews, key=lambda x: (x.get("chapterUid", 0), x.get("createTime", 0))):
        uid = rv.get("chapterUid", 0)
        rv_by_chapter.setdefault(uid, []).append(rv)

    all_chapter_uids = sorted(set(list(bm_by_chapter.keys()) + list(rv_by_chapter.keys())))

    for uid in all_chapter_uids:
        ch_title = chapter_map.get(uid, f"第{uid}章")
        lines.append(f"## {ch_title}")
        lines.append("")

        chapter_bms = bm_by_chapter.get(uid, [])
        chapter_rvs = rv_by_chapter.get(uid, [])

        rv_by_abstract: dict[str, list[dict]] = {}
        for rv in chapter_rvs:
            abstract = rv.get("abstract", "").strip()
            rv_by_abstract.setdefault(abstract, []).append(rv)

        used_abstracts: set[str] = set()

        for bm in chapter_bms:
            text = bm.get("markText", "").strip()
            if not text:
                continue
            style = bm.get("style", 0)
            style_mark = "📏" if style == 0 else ("〰️" if style == 1 else "🖍️")
            lines.append(f"> {style_mark} {text}")
            lines.append("")

            if text in rv_by_abstract:
                for rv in rv_by_abstract[text]:
                    content = rv.get("content", "").strip()
                    if content:
                        ts = format_timestamp_full(rv["createTime"]) if rv.get("createTime") else ""
                        lines.append(f"💭 {content}")
                        if ts:
                            lines.append(f"<sub>{ts}</sub>")
                        lines.append("")
                used_abstracts.add(text)

        for abstract, rvs in rv_by_abstract.items():
            if abstract in used_abstracts:
                continue
            for rv in rvs:
                content = rv.get("content", "").strip()
                if not content:
                    continue
                ts = format_timestamp_full(rv["createTime"]) if rv.get("createTime") else ""
                if abstract:
                    lines.append(f"> {abstract}")
                    lines.append("")
                lines.append(f"💭 {content}")
                if ts:
                    lines.append(f"<sub>{ts}</sub>")
                lines.append("")

    return "\n".join(lines)


def sync_book(client: WeReadClient, book_id: str, refresh: bool = False) -> str | None:
    """同步单本书，返回生成的目录路径，如果跳过返回 None"""
    print(f"📖 获取书籍信息: {book_id}")
    book_info = client.get_book_info(book_id)
    title = book_info.get("title", "未知书名")
    author = book_info.get("author", "未知作者")

    dirname = safe_book_dirname(title)
    book_dir = BOOKS_DIR / dirname

    highlights_path = book_dir / "highlights.md"
    if highlights_path.exists() and not refresh:
        print(f"  ⏭️  已存在: {dirname}/highlights.md（使用 --refresh 覆盖）")
        return None

    print(f"  📚 {title} — {author}")

    chapters = client.get_chapter_infos(book_id)
    print(f"  📑 章节: {len(chapters)}")

    bookmarks = client.get_bookmarks(book_id)
    print(f"  📏 划线: {len(bookmarks)}")

    reviews = client.get_reviews(book_id)
    print(f"  💭 想法: {len(reviews)}")

    if not bookmarks and not reviews:
        print("  ⚠️  无划线和想法，跳过")
        return None

    read_info = {}
    try:
        read_info = client.get_read_info(book_id)
    except Exception:
        pass

    book_dir.mkdir(parents=True, exist_ok=True)

    md_content = build_highlights_md(book_info, chapters, bookmarks, reviews, read_info)
    highlights_path.write_text(md_content, encoding="utf-8")
    print(f"  ✅ {highlights_path.relative_to(BOOKS_DIR.parent)}")

    summary_path = book_dir / "summary.md"
    if not summary_path.exists():
        summary_content = build_summary_template(book_info)
        summary_path.write_text(summary_content, encoding="utf-8")
        print(f"  ✅ {summary_path.relative_to(BOOKS_DIR.parent)}")

    return str(book_dir)


def build_summary_template(book_info: dict) -> str:
    title = book_info.get("title", "")
    author = book_info.get("author", "")
    rating = book_info.get("newRating", 0)

    return f"""---
title: "{title}"
author: "{author}"
type: summary
status: draft
---

# {title} — 读书总结

## 基本信息

- **书名**：{title}
- **作者**：{author}
- **评分**：{rating}/100

## 一句话总结



## 核心观点

1. 
2. 
3. 

## 关键收获

### 认知升级



### 行动启发



## 与其他知识的关联



## 个人思考

"""


def find_book_by_keyword(shelf: list[dict], keyword: str) -> list[dict]:
    """在书架中模糊匹配书名/作者"""
    keyword_lower = keyword.lower()
    matched = []
    for book in shelf:
        title = book.get("title", "").lower()
        author = book.get("author", "").lower()
        if keyword_lower in title or keyword_lower in author:
            matched.append(book)
    return matched


def list_shelf(client: WeReadClient, keyword: str = None):
    """列出书架上的书"""
    shelf = client.get_shelf()
    if keyword:
        shelf = find_book_by_keyword(shelf, keyword)

    if not shelf:
        if keyword:
            print(f"📭 书架上没有匹配「{keyword}」的书")
        else:
            print("📭 书架为空")
        return

    print(f"📚 共 {len(shelf)} 本书:\n")
    for i, book in enumerate(shelf, 1):
        title = book.get("title", "?")
        author = book.get("author", "?")
        book_id = book.get("bookId", "?")
        category = book.get("category", "")
        print(f"  {i:3d}. 《{title}》 — {author}")
        print(f"       ID: {book_id}  分类: {category}")


def main():
    parser = argparse.ArgumentParser(description="同步微信读书划线与笔记")
    parser.add_argument("--list", action="store_true", help="列出书架上的书")
    parser.add_argument("--book", default=None, help="按书名关键词搜索/同步")
    parser.add_argument("--book-id", default=None, help="按 bookId 同步")
    parser.add_argument("--refresh", action="store_true", help="覆盖已有文件")
    args = parser.parse_args()

    config = load_config()
    cookie = config.get("weread_cookie", "")
    if not cookie or cookie.startswith("wr_vid=xxx"):
        print("❌ 请在 config.json 中填入微信读书 Cookie (weread_cookie)")
        print("   获取方式: 浏览器登录 weread.qq.com → F12 → Network → 复制 Cookie")
        sys.exit(1)

    client = WeReadClient(cookie)

    if args.list:
        list_shelf(client, keyword=args.book)
        return

    if args.book:
        shelf = client.get_shelf()
        matched = find_book_by_keyword(shelf, args.book)
        if not matched:
            print(f"❌ 书架上未找到匹配「{args.book}」的书")
            print("   使用 --list 查看书架")
            sys.exit(1)
        if len(matched) > 1:
            print(f"🔍 找到 {len(matched)} 本匹配的书:")
            for book in matched:
                print(f"  • 《{book.get('title', '?')}》(ID: {book.get('bookId', '?')})")
            print("\n请用 --book-id 指定，或使用更精确的书名")
            return

        result = sync_book(client, matched[0]["bookId"], refresh=args.refresh)
        if result:
            print(f"\n✅ 同步完成: {result}")
        return

    if args.book_id:
        result = sync_book(client, args.book_id, refresh=args.refresh)
        if result:
            print(f"\n✅ 同步完成: {result}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
