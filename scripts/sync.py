#!/usr/bin/env python3
"""
从知识星球抓取内容并转为 Markdown 文件。

用法:
    python scripts/sync.py --channel qijunjie-fans
    python scripts/sync.py --channel all --count 5
    python scripts/sync.py --channel qijunjie-fans --scope all --count 20
    python scripts/sync.py --channel qijunjie-fans --hashtag 齐观晨会 --count 5
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from zsxq_api import ZsxqClient
from utils import (
    BASE_DIR,
    load_config,
    load_synced_ids,
    save_synced_id,
    parse_rich_text,
    extract_hashtags,
    safe_filename,
    infer_category,
    format_date_path,
    format_date,
)

CHANNELS_DIR = BASE_DIR / "channels"
DATA_DIR = BASE_DIR / "data"


def topic_to_markdown(topic: dict, channel_key: str, channel_name: str, config: dict) -> str:
    """将 topic JSON 转为 Markdown 字符串"""
    topic_id = str(topic["topic_id"])
    topic_type = topic.get("type", "talk")
    create_time = topic.get("create_time", "")
    date = format_date(create_time)
    is_digest = topic.get("digested", False)
    likes = topic.get("likes_count", 0)
    comments = topic.get("comments_count", 0)

    raw_text = ""
    author = ""
    images = []
    files = []
    voice = None

    if topic_type == "talk":
        talk = topic.get("talk", {}) or {}
        raw_text = talk.get("text", "")
        author = talk.get("owner", {}).get("name", "")
        images = talk.get("images", [])
        files = talk.get("files", [])
    elif topic_type == "q&a":
        q = topic.get("question", {}) or {}
        a = topic.get("answer", {}) or {}
        q_text = q.get("text", "")
        a_text = a.get("text", "")
        author = a.get("owner", {}).get("name", "") or q.get("owner", {}).get("name", "")
        q_owner = q.get("owner", {}).get("name", "")
        raw_text = f"Q_OWNER:{q_owner}\nQ:{q_text}\nA:{a_text}"
        images = q.get("images", []) + a.get("images", [])
        files = q.get("files", []) + a.get("files", [])
    elif topic_type == "article":
        article = topic.get("article", {}) or {}
        raw_text = article.get("content", "") or article.get("text", "")
        author = article.get("owner", {}).get("name", "")
        images = article.get("images", [])

    if "content_voice" in topic:
        cv = topic["content_voice"]
        voice = {
            "file_id": str(cv.get("file_id", "")),
            "name": cv.get("name", ""),
            "duration": cv.get("duration", 0),
            "size": cv.get("size", 0),
        }

    tags = extract_hashtags(raw_text)
    category = infer_category(tags, config)

    content_types = []
    if raw_text.strip():
        content_types.append("text")
    if voice:
        content_types.append("voice")
    if files:
        content_types.append("file")
    if images:
        content_types.append("image")
    content_type = "+".join(content_types) or "text"

    body_md = _build_body(topic_type, raw_text, images, files, voice)

    # YAML frontmatter
    fm_tags = "\n".join(f"  - {t}" for t in tags) if tags else ""
    fm_files = ""
    if files:
        fm_files_items = []
        for f in files:
            fm_files_items.append(
                f'  - file_id: "{f.get("file_id", "")}"\n'
                f'    name: "{f.get("name", "")}"\n'
                f'    size: {f.get("size", 0)}'
            )
        fm_files = "\n".join(fm_files_items)

    fm_voice = ""
    if voice:
        fm_voice = (
            f'  file_id: "{voice["file_id"]}"\n'
            f'  name: "{voice["name"]}"\n'
            f"  duration: {voice['duration']}\n"
            f"  size: {voice['size']}"
        )

    frontmatter = f"""---
id: "{topic_id}"
source: {channel_name}
channel: {channel_key}
author: {author}
date: {date}
type: {topic_type}
content_type: {content_type}
is_digest: {str(is_digest).lower()}
likes: {likes}
comments: {comments}"""

    if fm_tags:
        frontmatter += f"\ntags:\n{fm_tags}"
    if category:
        frontmatter += f"\ntopic_category: {category}"
    else:
        frontmatter += "\ntopic_category: "
    frontmatter += "\nkeywords: []"
    frontmatter += '\nsummary: ""'
    frontmatter += "\nquotes_count: 0"
    if fm_voice:
        frontmatter += f"\nvoice:\n{fm_voice}"
    if fm_files:
        frontmatter += f"\nfiles:\n{fm_files}"
    frontmatter += "\n---"

    return f"{frontmatter}\n\n{body_md}\n"


def _build_body(topic_type: str, raw_text: str, images: list, files: list, voice: dict | None) -> str:
    """生成 Markdown 正文"""
    parts = []

    if topic_type == "q&a" and raw_text.startswith("Q_OWNER:"):
        lines = raw_text.split("\n", 3)
        q_owner = lines[0].replace("Q_OWNER:", "").strip() if len(lines) > 0 else ""
        q_text = lines[1].replace("Q:", "").strip() if len(lines) > 1 else ""
        a_text = lines[2].replace("A:", "").strip() if len(lines) > 2 else ""
        q_md = parse_rich_text(q_text)
        a_md = parse_rich_text(a_text)
        if q_owner:
            parts.append(f"## 提问（{q_owner}）\n\n{q_md}")
        else:
            parts.append(f"## 提问\n\n{q_md}")
        parts.append(f"## 回答\n\n{a_md}")
    else:
        parts.append(parse_rich_text(raw_text))

    if voice:
        parts.append(
            f"\n---\n\n**语音**: {voice['name']} "
            f"({voice['duration']}秒, file_id: {voice['file_id']})"
        )

    if images:
        img_lines = ["\n---\n"]
        for img in images:
            url = img.get("large", {}).get("url") or img.get("original", {}).get("url", "")
            if url:
                img_lines.append(f"![图片]({url})")
        if len(img_lines) > 1:
            parts.append("\n".join(img_lines))

    if files:
        file_lines = ["\n---\n\n**附件**:"]
        for f in files:
            name = f.get("name", "未知文件")
            fid = f.get("file_id", "")
            size_kb = f.get("size", 0) // 1024
            duration = f.get("duration")
            extra = f", {duration}秒" if duration else ""
            file_lines.append(f"- {name} ({size_kb}KB{extra}, file_id: {fid})")
        parts.append("\n".join(file_lines))

    return "\n\n".join(parts)


def determine_filename(topic: dict) -> str:
    """从 topic 数据生成文件名"""
    title = topic.get("title", "")
    if title:
        return safe_filename(title)

    topic_type = topic.get("type", "talk")
    if topic_type == "talk":
        text = (topic.get("talk", {}) or {}).get("text", "")
    elif topic_type == "q&a":
        text = (topic.get("answer", {}) or {}).get("text", "") or (
            topic.get("question", {}) or {}
        ).get("text", "")
    elif topic_type == "article":
        text = (topic.get("article", {}) or {}).get("title", "") or (
            topic.get("article", {}) or {}
        ).get("content", "")
    else:
        text = ""

    text = parse_rich_text(text)
    return safe_filename(text[:80]) if text else f"topic-{topic.get('topic_id', 'unknown')}"


def save_topic(topic: dict, channel_key: str, channel_name: str, config: dict) -> str | None:
    """保存单个 topic 为 Markdown 文件，返回文件路径（如已存在返回 None）"""
    topic_id = str(topic["topic_id"])
    synced_ids = load_synced_ids()
    if topic_id in synced_ids:
        return None

    create_time = topic.get("create_time", "")
    date_path = format_date_path(create_time)
    filename = determine_filename(topic)

    target_dir = CHANNELS_DIR / channel_key / date_path
    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / f"{filename}.md"

    counter = 1
    while filepath.exists():
        filepath = target_dir / f"{filename}-{counter}.md"
        counter += 1

    md_content = topic_to_markdown(topic, channel_key, channel_name, config)
    filepath.write_text(md_content, encoding="utf-8")
    save_synced_id(topic_id)

    # 保存原始 JSON
    raw_dir = DATA_DIR / "raw" / channel_key / date_path
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{topic_id}.json"
    raw_path.write_text(json.dumps(topic, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(filepath.relative_to(BASE_DIR))


def sync_channel(client: ZsxqClient, channel_key: str, channel_cfg: dict, config: dict,
                 scope: str = None, count: int = 10, hashtag: str = None):
    """同步单个频道"""
    group_id = channel_cfg["group_id"]
    channel_name = channel_cfg["name"]
    scope = scope or channel_cfg.get("default_scope", "digests")

    print(f"\n📡 同步: {channel_name} (scope={scope}, count={count})")

    if hashtag:
        menus = client.get_menus(group_id)
        hashtag_id = None
        for menu in menus:
            menu_title = menu.get("title", "").strip("#")
            if menu_title == hashtag and "hashtag" in menu:
                hashtag_id = str(menu["hashtag"]["hashtag_id"])
                break
        if not hashtag_id:
            hashtags = client.get_hashtags(group_id)
            for h in hashtags:
                if h.get("title", "").strip("#") == hashtag:
                    hashtag_id = str(h["hashtag_id"])
                    break
        if not hashtag_id:
            print(f"  ⚠️ 未找到标签: #{hashtag}#")
            return []
        topics, _ = client.get_hashtag_topics(hashtag_id, count=count)
    else:
        topics, _ = client.get_topics(group_id, scope=scope, count=count)

    new_files = []
    for topic in topics:
        path = save_topic(topic, channel_key, channel_name, config)
        if path:
            new_files.append(path)

    print(f"  ✅ 获取 {len(topics)} 条，新增 {len(new_files)} 条")
    return new_files


def main():
    parser = argparse.ArgumentParser(description="同步知识星球内容")
    parser.add_argument("--channel", default="all", help="频道 key 或 'all'")
    parser.add_argument("--scope", default=None, help="筛选范围: digests, all, by_owner, questions")
    parser.add_argument("--count", type=int, default=10, help="每个频道拉取数量")
    parser.add_argument("--hashtag", default=None, help="按标签筛选")
    args = parser.parse_args()

    config = load_config()
    client = ZsxqClient(config["cookie"])

    channels = config["channels"]
    if args.channel != "all":
        if args.channel not in channels:
            print(f"❌ 未知频道: {args.channel}")
            print(f"   可选: {', '.join(channels.keys())}")
            sys.exit(1)
        channels = {args.channel: channels[args.channel]}

    all_new_files = []
    for key, cfg in channels.items():
        new_files = sync_channel(
            client, key, cfg, config,
            scope=args.scope, count=args.count, hashtag=args.hashtag,
        )
        all_new_files.extend(new_files)

    print(f"\n{'='*50}")
    print(f"同步完成，共新增 {len(all_new_files)} 个文件")
    if all_new_files:
        print("\n新增文件列表（需要 Agent 补充 enrichment）:")
        for f in all_new_files:
            print(f"  📄 {f}")
    print()


if __name__ == "__main__":
    main()
