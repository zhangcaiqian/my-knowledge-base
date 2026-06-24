#!/usr/bin/env python3
"""
从知识星球抓取内容并转为 Markdown 文件。

用法:
    python scripts/sync.py --channel all --today
    python scripts/sync.py --channel qijunjie-fans --date 2026-04-11
    python scripts/sync.py --channel all --count 10
    python scripts/sync.py --channel qijunjie-fans --hashtag 齐观晨会 --count 5
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from zsxq_api import ZsxqClient
from utils import (
    BASE_DIR,
    ASSETS_DIR,
    load_config,
    load_synced_ids,
    save_synced_id,
    remove_synced_ids,
    parse_rich_text,
    extract_hashtags,
    safe_filename,
    infer_category,
    format_date_path,
    format_date,
    extract_docx_text,
    extract_docx_images,
    extract_pdf_text,
    extract_pdf_images,
    extract_article_text_from_html,
)

CHANNELS_DIR = BASE_DIR / "channels"
DATA_DIR = BASE_DIR / "data"


def download_and_extract_files(client: ZsxqClient, files: list, channel_key: str,
                                date_path: str) -> dict:
    """下载附件并提取文本/图片。返回 {filename: {local_path, extracted_text, extracted_images}}"""
    results = {}
    if not files:
        return results

    save_dir = ASSETS_DIR / channel_key / date_path
    save_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        fid = str(f.get("file_id", ""))
        name = f.get("name", f"file_{fid}")
        local_path = save_dir / name

        if local_path.exists():
            print(f"    📎 已存在: {name}")
        else:
            try:
                client.download_file(fid, str(local_path))
                print(f"    📥 下载: {name}")
            except Exception as e:
                print(f"    ❌ 下载失败 {name}: {e}")
                results[name] = {"local_path": "", "extracted_text": "", "extracted_images": []}
                continue

        extracted = ""
        extracted_images: list[str] = []
        suffix = local_path.suffix.lower()
        image_dir = save_dir / f"{local_path.stem}_images"
        if suffix == ".docx":
            extracted = extract_docx_text(str(local_path))
            extracted_images = extract_docx_images(str(local_path), str(image_dir))
        elif suffix == ".pdf":
            extracted = extract_pdf_text(str(local_path))
            extracted_images = extract_pdf_images(str(local_path), str(image_dir))

        results[name] = {
            "local_path": str(local_path.relative_to(BASE_DIR)),
            "extracted_text": extracted,
            "extracted_images": [
                str(Path(path).relative_to(BASE_DIR))
                for path in extracted_images
                if Path(path).exists()
            ],
        }

    return results


def prepare_markdown_images(file_results: dict, markdown_dir: Path, markdown_name: str) -> dict:
    """把附件提取出的图片复制到 Markdown 同目录，便于预览与版本管理。"""
    if not file_results:
        return file_results

    markdown_dir.mkdir(parents=True, exist_ok=True)

    for attachment_index, (attachment_name, info) in enumerate(file_results.items(), start=1):
        markdown_images: list[str] = []
        for idx, image_path in enumerate(info.get("extracted_images", []), start=1):
            src = BASE_DIR / image_path
            if not src.exists():
                continue
            suffix = src.suffix.lower() or ".png"
            target_name = f"embedded-{attachment_index:02d}-{idx:02d}{suffix}"
            target_path = markdown_dir / target_name
            shutil.copy2(src, target_path)
            markdown_images.append(target_name)
        info["markdown_images"] = markdown_images

    return file_results


def download_voice(client: ZsxqClient, voice: dict, channel_key: str,
                   date_path: str) -> str:
    """下载语音文件，返回本地相对路径"""
    if not voice:
        return ""
    fid = voice.get("file_id", "")
    name = voice.get("name", f"voice_{fid}.mp3")
    save_dir = ASSETS_DIR / channel_key / date_path
    save_dir.mkdir(parents=True, exist_ok=True)
    local_path = save_dir / name

    if local_path.exists():
        print(f"    🔊 已存在: {name}")
    else:
        try:
            client.download_file(str(fid), str(local_path))
            print(f"    🔊 下载: {name}")
        except Exception as e:
            print(f"    ❌ 语音下载失败 {name}: {e}")
            return ""

    return str(local_path.relative_to(BASE_DIR))


def topic_to_markdown(topic: dict, channel_key: str, channel_name: str,
                      config: dict, file_results: dict = None,
                      voice_path: str = "", article_text: str = "") -> str:
    """将 topic JSON 转为完整 Markdown，包含附件提取的正文"""
    topic_id = str(topic["topic_id"])
    topic_type = topic.get("type", "talk")
    create_time = topic.get("create_time", "")
    dt = format_date(create_time)
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
        raw_text = article_text or talk.get("text", "")
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

    body_md = _build_body(topic_type, raw_text, images, files, voice,
                          file_results, voice_path)

    fm_tags = "\n".join(f"  - {t}" for t in tags) if tags else ""
    fm_files = ""
    if files:
        fm_files_items = []
        for f in files:
            fname = f.get("name", "")
            local = ""
            if file_results and fname in file_results:
                local = file_results[fname].get("local_path", "")
            fm_files_items.append(
                f'  - file_id: "{f.get("file_id", "")}"\n'
                f'    name: "{fname}"\n'
                f'    size: {f.get("size", 0)}'
                + (f'\n    local_path: "{local}"' if local else "")
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
        if voice_path:
            fm_voice += f'\n  local_path: "{voice_path}"'

    frontmatter = f"""---
id: "{topic_id}"
source: {channel_name}
channel: {channel_key}
author: {author}
date: {dt}
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


def _build_body(topic_type: str, raw_text: str, images: list, files: list,
                voice: dict | None, file_results: dict = None,
                voice_path: str = "") -> str:
    """生成 Markdown 正文，包含附件提取的全文"""
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
        parsed = parse_rich_text(raw_text)
        if parsed:
            parts.append(parsed)

    if images:
        img_lines = []
        for img in images:
            url = img.get("large", {}).get("url") or img.get("original", {}).get("url", "")
            if url:
                img_lines.append(f"![图片]({url})")
        if img_lines:
            parts.append("\n".join(img_lines))

    # 附件提取的正文内容（核心改进）
    if file_results:
        for fname, info in file_results.items():
            text = info.get("extracted_text", "")
            if text and not text.startswith("["):
                parts.append(f"---\n\n## 📄 {fname}\n\n{text}")
            images = info.get("markdown_images", [])
            if images:
                image_lines = [f"![{fname}]({img_path})" for img_path in images]
                parts.append(
                    f"---\n\n## 🖼️ {fname} 图片提取\n\n" + "\n\n".join(image_lines)
                )

    if voice:
        duration_min = voice['duration'] // 60
        duration_sec = voice['duration'] % 60
        voice_info = f"🎙️ **语音** ({duration_min}分{duration_sec}秒)"
        if voice_path:
            voice_info += f" → `{voice_path}`"
        else:
            voice_info += f" (file_id: {voice['file_id']})"
        voice_info += "\n\n> ⚠️ 语音内容需要 ASR 转文字后补充到此处"
        parts.append(voice_info)

    if files:
        file_lines = ["\n---\n\n**📎 附件列表**:"]
        for f in files:
            name = f.get("name", "未知文件")
            size_kb = f.get("size", 0) // 1024
            local = ""
            if file_results and name in file_results:
                local = file_results[name].get("local_path", "")
            status_parts = []
            if file_results and name in file_results and file_results[name].get("extracted_text"):
                status_parts.append("✅ 已提取正文")
            if file_results and name in file_results and file_results[name].get("extracted_images"):
                status_parts.append(f"🖼️ {len(file_results[name]['extracted_images'])} 张图")
            if name.lower().endswith((".mp3", ".m4a", ".wav")):
                status_parts = ["🎙️ 语音"]
            status = " ".join(status_parts)
            loc_str = f" → `{local}`" if local else ""
            file_lines.append(f"- {name} ({size_kb}KB{loc_str}) {status}")
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


def save_topic(topic: dict, channel_key: str, channel_name: str,
               config: dict, client: ZsxqClient) -> str | None:
    """保存单个 topic：下载附件、提取内容、生成完整 Markdown"""
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

    # 收集所有附件
    topic_type = topic.get("type", "talk")
    files = []
    if topic_type == "talk":
        files = (topic.get("talk", {}) or {}).get("files", [])
    elif topic_type == "q&a":
        files = ((topic.get("question", {}) or {}).get("files", [])
                 + (topic.get("answer", {}) or {}).get("files", []))

    voice_data = topic.get("content_voice")
    voice_info = None
    if voice_data:
        voice_info = {
            "file_id": str(voice_data.get("file_id", "")),
            "name": voice_data.get("name", ""),
            "duration": voice_data.get("duration", 0),
            "size": voice_data.get("size", 0),
        }

    article_text = ""
    talk_article = (topic.get("talk", {}) or {}).get("article", {}) or {}
    article_url = talk_article.get("inline_article_url") or talk_article.get("article_url") or ""
    if article_url:
        try:
            article_html = client.fetch_article_html(article_url)
            article_text = extract_article_text_from_html(article_html)
        except Exception as e:
            print(f"    ⚠️ 文章全文抓取失败: {e}")

    # 下载附件并提取文本
    file_results = download_and_extract_files(client, files, channel_key, date_path)
    file_results = prepare_markdown_images(file_results, target_dir, filepath.stem)
    voice_path = download_voice(client, voice_info, channel_key, date_path)

    md_content = topic_to_markdown(
        topic, channel_key, channel_name, config,
        file_results=file_results, voice_path=voice_path, article_text=article_text,
    )
    filepath.write_text(md_content, encoding="utf-8")
    save_synced_id(topic_id)

    raw_dir = DATA_DIR / "raw" / channel_key / date_path
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{topic_id}.json"
    raw_path.write_text(json.dumps(topic, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(filepath.relative_to(BASE_DIR))


def filter_by_date(topics: list[dict], target_date: str) -> list[dict]:
    """按日期过滤 topics，target_date 格式 YYYY-MM-DD"""
    return [t for t in topics if t.get("create_time", "")[:10] == target_date]


def collect_topic_ids_channel_month(channel_key: str, year_month: str) -> set[str]:
    """扫描 channels/{key}/YYYY/MM 下主文章的 topic id（不含 .quotes.md）"""
    parts = year_month.split("-")
    if len(parts) != 2:
        return set()
    year, month = parts[0], parts[1]
    base = CHANNELS_DIR / channel_key / year / month
    ids: set[str] = set()
    if not base.is_dir():
        return ids
    for md in sorted(base.rglob("*.md")):
        if md.name.endswith(".quotes.md"):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^id:\s*"(\d+)"', text, re.MULTILINE)
        if m:
            ids.add(m.group(1))
    return ids


def delete_channel_month_dirs(channel_key: str, year_month: str):
    """删除某频道某月的 channels / data/raw / assets 子目录"""
    parts = year_month.split("-")
    if len(parts) != 2:
        return
    year, month = parts[0], parts[1]
    rel = Path(year) / month
    for root in (
        CHANNELS_DIR / channel_key / rel,
        DATA_DIR / "raw" / channel_key / rel,
        ASSETS_DIR / channel_key / rel,
    ):
        if root.is_dir():
            shutil.rmtree(root)
            print(f"  🗑️ 已删除: {root.relative_to(BASE_DIR)}")


def fetch_topics_for_month(
    client: ZsxqClient,
    group_id: str,
    scope: str,
    year_month: str,
) -> list[dict]:
    """分页拉取指定年月的所有帖子（按 create_time 属于该月）"""
    collected: list[dict] = []
    end_time = None
    month_start = f"{year_month}-01"

    while True:
        topics, _ = client.get_topics(group_id, scope=scope, count=10, end_time=end_time)
        if not topics:
            break
        for t in topics:
            ct = (t.get("create_time") or "")[:10]
            if len(ct) >= 7 and ct[:7] == year_month:
                collected.append(t)
        oldest = (topics[-1].get("create_time") or "")[:10]
        if oldest < month_start:
            break
        end_time = topics[-1]["create_time"]

    # 去重（分页边界偶发重复）
    seen: set[str] = set()
    unique: list[dict] = []
    for t in collected:
        tid = str(t.get("topic_id", ""))
        if tid and tid not in seen:
            seen.add(tid)
            unique.append(t)
    unique.sort(key=lambda x: x.get("create_time") or "")
    return unique


def sync_channel_month(
    client: ZsxqClient,
    channel_key: str,
    channel_cfg: dict,
    config: dict,
    year_month: str,
    scope: str | None,
    refresh: bool,
) -> list[str]:
    """整月同步：分页拉取该月全部帖子并写入 md"""
    group_id = channel_cfg["group_id"]
    channel_name = channel_cfg["name"]
    scope = scope or channel_cfg.get("default_scope", "digests")

    print(f"\n📡 整月同步: {channel_name} ({year_month}, scope={scope}, refresh={refresh})")

    if refresh:
        ids = collect_topic_ids_channel_month(channel_key, year_month)
        if ids:
            remove_synced_ids(ids)
            print(f"  🔄 已从 .synced_ids 移除 {len(ids)} 个 topic_id")
        delete_channel_month_dirs(channel_key, year_month)

    topics = fetch_topics_for_month(client, group_id, scope, year_month)
    print(f"  📋 API 共 {len(topics)} 条属于 {year_month}")

    new_files: list[str] = []
    for topic in topics:
        path = save_topic(topic, channel_key, channel_name, config, client)
        if path:
            new_files.append(path)

    print(f"  ✅ 新增/写入 {len(new_files)} 个文件")
    return new_files


def sync_channel(client: ZsxqClient, channel_key: str, channel_cfg: dict, config: dict,
                 scope: str = None, count: int = 10, hashtag: str = None,
                 target_date: str = None):
    """同步单个频道"""
    group_id = channel_cfg["group_id"]
    channel_name = channel_cfg["name"]
    scope = scope or channel_cfg.get("default_scope", "digests")

    date_hint = f", date={target_date}" if target_date else ""
    print(f"\n📡 同步: {channel_name} (scope={scope}, count={count}{date_hint})")

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

    if target_date:
        topics = filter_by_date(topics, target_date)
        if not topics:
            print(f"  ℹ️ {target_date} 无新内容")
            return []

    new_files = []
    for topic in topics:
        path = save_topic(topic, channel_key, channel_name, config, client)
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
    parser.add_argument("--today", action="store_true", help="只同步今天的内容")
    parser.add_argument("--date", default=None, help="只同步指定日期 (YYYY-MM-DD)")
    parser.add_argument(
        "--month",
        default=None,
        help="整月同步 YYYY-MM（分页拉取该月全部帖子，需配合单频道或 all）",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="与 --month 合用：删除本地该月目录、从 .synced_ids 移除后再全量重写",
    )
    args = parser.parse_args()

    config = load_config()
    client = ZsxqClient(config["zsxq_cookie"])

    channels = config["channels"]
    if args.channel != "all":
        if args.channel not in channels:
            print(f"❌ 未知频道: {args.channel}")
            print(f"   可选: {', '.join(channels.keys())}")
            sys.exit(1)
        channels = {args.channel: channels[args.channel]}

    # 整月同步（分页）
    if args.month:
        m = args.month.strip()
        if len(m) != 7 or m[4] != "-":
            print("❌ --month 格式应为 YYYY-MM，例如 2026-04")
            sys.exit(1)
        if args.refresh and args.channel == "all":
            print("❌ --refresh 时建议指定单一 --channel，避免误删多频道同月数据")
            sys.exit(1)
        all_new_files = []
        for key, cfg in channels.items():
            new_files = sync_channel_month(
                client, key, cfg, config, m, args.scope, args.refresh,
            )
            all_new_files.extend(new_files)
        print(f"\n{'='*50}")
        print(f"整月同步完成，共写入 {len(all_new_files)} 个文件")
        if all_new_files:
            print("\n文件列表（需要 Agent 补充 enrichment）:")
            for f in all_new_files:
                print(f"  📄 {f}")
        print()
        return

    target_date = None
    if args.today:
        target_date = date.today().isoformat()
    elif args.date:
        target_date = args.date

    all_new_files = []
    for key, cfg in channels.items():
        new_files = sync_channel(
            client, key, cfg, config,
            scope=args.scope, count=args.count, hashtag=args.hashtag,
            target_date=target_date,
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
