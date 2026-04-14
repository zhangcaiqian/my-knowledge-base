---
name: zsxq-knowledge
description: >-
  管理知识星球订阅频道的知识库：同步内容、转 Markdown、提取金句、构建索引、搜索查找、生成海报。
  当用户提到知识星球、同步星球、zsxq、知识库同步、搜索知识、查找内容、生成海报、金句卡片时使用。
---

# 知识星球知识库管理

本 Skill 的工作目录即知识库根目录。所有脚本位于 `scripts/`，API 参考见 `reference/api-reference.md`。

## 前置条件

1. 安装依赖: `pip install -r requirements.txt`
2. 复制 `config.example.json` 为 `config.json`，填入知识星球 Cookie
3. Cookie 获取: 浏览器登录 wx.zsxq.com → F12 → Network → 复制 Cookie

## 频道信息

| 频道 | key | group_id |
|------|-----|----------|
| 齐俊杰的粉丝群 | qijunjie-fans | 552521181154 |
| 老齐的读书圈 | qijunjie-reading | 454548818428 |
| 躬行客读毛选 | maoxuan | 51128845544444 |
| pure日月：认知普惠 | pure-sunmoon | 15555442414282 |

## 工作流

### 1. 同步内容（脚本，零 Token）

```bash
python scripts/sync.py --channel all --count 10
python scripts/sync.py --channel qijunjie-fans --scope digests --count 10
python scripts/sync.py --channel qijunjie-fans --hashtag 齐观晨会 --count 5
python scripts/sync.py --channel qijunjie-fans --scope all --count 20
```

参数说明:
- `--channel`: 频道 key 或 `all`
- `--scope`: digests(默认) | all | by_owner | questions | with_files
- `--count`: 拉取数量
- `--hashtag`: 按标签筛选

脚本输出新增文件列表，这些文件需要下一步补充 enrichment。

### 2. 内容富化（Agent 执行，消耗 Token）

对 sync 输出的每个新文件，读取内容后更新 frontmatter 字段并创建金句文件。

**处理步骤:**
1. 读取文件内容
2. 分析正文，一次性提取以下信息并更新 frontmatter:
   - `summary`: 一句话摘要（≤50字）
   - `keywords`: 3-5 个关键词（YAML 列表格式）
   - `topic_category`: 主题分类（如 frontmatter 中已有则保留）
   - `quotes_count`: 提取的金句数量
3. 如有金句，创建同名 `.quotes.md` 文件

**frontmatter 更新示例:**
```yaml
keywords:
  - 高考
  - 专业选择
  - 就业
summary: "高考选专业应以就业为导向，理工优先，文科奔考公"
topic_category: 职业发展
quotes_count: 2
```

**金句文件格式** (`xxx.quotes.md`):
```markdown
> 就业一定要跟着风口走。

> 上学的目的是就业，不要为了上学而上学，更不要为了爹妈的脸面而上学。
```

**批量优化:** 多篇短文章可合并分析，一次性返回所有结果，减少调用次数。

### 3. 更新索引（脚本，零 Token）

```bash
python scripts/build_index.py
```

自动生成:
- `INDEX.md` — 主索引（概览 + 最近 30 条）
- `index/by-date/{year}/{month}.md` — 按月索引
- `index/by-tag/{tag}.md` — 按标签索引
- `index/by-topic/{topic}.md` — 按主题分类索引
- `index/by-channel/{channel}.md` — 按频道索引
- `index/quotes-index.md` — 金句索引
- `index/index.json` — 机器可读索引（供 search.py 使用）

### 4. 搜索内容

```bash
python scripts/search.py "降息"
python scripts/search.py --tag "宏观策略" --limit 20
python scripts/search.py --channel maoxuan
python scripts/search.py --category "投资理念与方法"
python scripts/search.py --date-from 2026-04-01
```

搜索脚本查 `index/index.json`，只返回匹配结果（控制输出量），避免读大文件。

### 5. 浏览内容

查找内容时的推荐路径（最小化 Token 消耗）:

1. **先读 `INDEX.md`**（轻量，<500行）→ 获取概览
2. **定向读分片索引** → 如 `index/by-tag/齐观晨会.md`
3. **或直接用 search.py** → 关键词/标签/日期过滤
4. **最后读具体文章** → 根据搜索结果中的文件路径

**不要**一次性读取整个 `index/index.json`，它可能很大。

### 6. 语音转文字

知识星球中的语音内容需要下载后调用火山引擎 ASR 转写:

1. 从文章 frontmatter 获取 `voice.file_id`
2. 下载: 用 zsxq_api 的 `download_file(file_id, save_path)` 方法
3. 调用火山引擎大模型录音文件极速版 API 转写
4. 将转写文本补充到文章正文中

火山 ASR 接口: `POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash`

### 7. 文件处理

PDF/Word 附件需要下载后提取文字:
1. 从 frontmatter 获取 `files[].file_id`
2. 下载文件
3. PDF: `import fitz; doc = fitz.open(path); text = "".join(p.get_text() for p in doc)`
4. Word: `from docx import Document; doc = Document(path); text = "\n".join(p.text for p in doc.paragraphs)`
5. 将提取文本追加到文章内容中

### 8. 生成海报

将金句生成海报图片，用于小红书/公众号发布:

1. 从金句文件中选择要生成的句子
2. 根据内容风格选择海报模板（极简文字 / 中国风 / 现代渐变）
3. 使用 HTML + CSS 生成海报卡片（1080×1440 竖版适配小红书）
4. 如需截图为 PNG，可用 playwright/puppeteer

**海报 HTML 规范:**
- 尺寸: 1080×1440px（3:4 竖版）
- 金句文字: 32-40px，居中
- 来源标注: 14-16px，底部
- 背景: 根据内容主题选择配色

### 9. 视频生成

通过火山引擎豆包视频生成 API 将金句制作为短视频:

```
POST https://ark.cn-beijing.volces.com/api/v3/contents/generations
模型: doubao-seedance-1-0-pro-250528
```

支持文生视频，时长 2-12 秒，适合社交媒体发布。

## Markdown 文件格式

每个文件的 frontmatter 包含:

| 字段 | 来源 | 说明 |
|------|------|------|
| id | API | topic_id，唯一标识 |
| source | API | 频道中文名 |
| channel | API | 频道 key |
| author | API | 作者 |
| date | API | 发布日期 |
| type | API | talk / q&a / article |
| content_type | API | text / voice / file 组合 |
| is_digest | API | 是否精华 |
| likes | API | 点赞数 |
| comments | API | 评论数 |
| tags | API解析 | 来自正文 hashtag 标记 |
| topic_category | 规则+Agent | 主题分类 |
| keywords | Agent | 关键词列表 |
| summary | Agent | 一句话摘要 |
| quotes_count | Agent | 金句数量 |
| voice | API | 语音信息(file_id, duration) |
| files | API | 附件信息(file_id, name, size) |

## 注意事项

- Cookie 过期后需要重新从浏览器获取，更新 `config.json`
- API 请求间隔 1.5 秒，避免限流
- 索引文件单个不超过 500 行，超过自动分片
- 搜索优先用 `search.py`，避免 Agent 直接读大索引文件
- API 详情见 [reference/api-reference.md](reference/api-reference.md)
