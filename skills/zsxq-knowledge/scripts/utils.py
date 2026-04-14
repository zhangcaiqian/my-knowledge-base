import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

SKILL_DIR = Path(__file__).resolve().parent.parent          # skills/zsxq-knowledge/
BASE_DIR = SKILL_DIR.parent.parent                          # 知识库根目录
CONFIG_PATH = BASE_DIR / "config.json"
SYNCED_IDS_PATH = BASE_DIR / ".synced_ids"
ASSETS_DIR = BASE_DIR / "assets"


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"未找到 {CONFIG_PATH}，请复制 config.example.json 为 config.json 并填入 cookie"
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_synced_ids() -> set:
    if not SYNCED_IDS_PATH.exists():
        return set()
    with open(SYNCED_IDS_PATH, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_synced_id(topic_id: str):
    with open(SYNCED_IDS_PATH, "a", encoding="utf-8") as f:
        f.write(f"{topic_id}\n")


def remove_synced_ids(ids_to_remove: set[str]):
    """从 .synced_ids 中删除指定 id（用于整月重同步）"""
    if not ids_to_remove or not SYNCED_IDS_PATH.exists():
        return
    lines = SYNCED_IDS_PATH.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if line.strip() and line.strip() not in ids_to_remove]
    SYNCED_IDS_PATH.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


def parse_rich_text(text: str) -> str:
    """将知识星球富文本标记转为 Markdown"""
    if not text:
        return ""

    def replace_tag(m):
        tag = m.group(0)
        etype = re.search(r'type="([^"]*)"', tag)
        if not etype:
            return ""
        etype = etype.group(1)

        if etype == "hashtag":
            title = re.search(r'title="([^"]*)"', tag)
            if title:
                decoded = unquote(title.group(1))
                return f" {decoded} "
            return ""
        elif etype == "text_bold":
            title = re.search(r'title="([^"]*)"', tag)
            return f"**{unquote(title.group(1))}**" if title else ""
        elif etype == "web":
            href = re.search(r'href="([^"]*)"', tag)
            title = re.search(r'title="([^"]*)"', tag)
            if href:
                url = unquote(href.group(1))
                label = unquote(title.group(1)) if title else url
                return f"[{label}]({url})"
            return ""
        elif etype == "mention":
            name = re.search(r'title="([^"]*)"', tag)
            return f"@{unquote(name.group(1))}" if name else ""
        return ""

    result = re.sub(r"<e\s[^>]*/>", replace_tag, text)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def extract_hashtags(text: str) -> list[str]:
    """从富文本中提取 hashtag 列表"""
    if not text:
        return []
    tags = []
    for m in re.finditer(r'<e\s[^>]*type="hashtag"[^>]*title="([^"]*)"[^>]*/>', text):
        decoded = unquote(m.group(1)).strip("#").strip()
        if decoded:
            tags.append(decoded)
    return list(dict.fromkeys(tags))


def safe_filename(text: str, max_length: int = 60) -> str:
    """从标题/文本生成安全文件名"""
    if not text:
        return "untitled"
    name = text.strip()
    name = re.sub(r"<e\s[^>]*/>", "", name)
    name = re.sub(r"[\\/:*?\"<>|]", "", name)
    name = re.sub(r"[\s\n\r]+", "-", name)
    name = re.sub(r"[#@\[\]()（）【】]", "", name)
    name = name.strip("-. ")
    if len(name) > max_length:
        name = name[:max_length].rstrip("-. ")
    return name or "untitled"


def infer_category(tags: list[str], config: dict) -> str | None:
    """根据标签推断分类"""
    mapping = config.get("tag_to_category", {})
    for tag in tags:
        if tag in mapping:
            return mapping[tag]
    return None


def format_date_path(date_str: str) -> str:
    """'2026-04-11T14:29:50.800+0800' → '2026/04/11'"""
    return date_str[:10].replace("-", "/")


def format_date(date_str: str) -> str:
    """'2026-04-11T14:29:50.800+0800' → '2026-04-11'"""
    return date_str[:10]


def extract_docx_text(filepath: str) -> str:
    """从 docx 文件提取全部文本"""
    try:
        from docx import Document
        doc = Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        return f"[docx 提取失败: {e}]"


def extract_pdf_text(filepath: str) -> str:
    """从 PDF 文件提取全部文本"""
    try:
        import fitz
        doc = fitz.open(filepath)
        pages = [page.get_text().strip() for page in doc]
        doc.close()
        return "\n\n".join(p for p in pages if p)
    except Exception as e:
        return f"[PDF 提取失败: {e}]"
