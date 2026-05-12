---
name: zsxq-knowledge
description: >-
  管理知识星球频道知识库：同步帖子与精华、转 Markdown、提取金句、构建索引、搜索内容、补全文字稿。
  当用户提到知识星球、zsxq、星球文章、精华帖、晨会内容、老齐读书圈、同步星球、搜索内容、按标签查找、语音转文字时使用。
---

# 知识星球知识库管理

本 Skill 位于 `skills/zsxq-knowledge/`，知识库根目录为仓库根。

- 脚本目录: `skills/zsxq-knowledge/scripts/`
- 配置模板: `skills/zsxq-knowledge/config.example.json`
- API 参考: `skills/zsxq-knowledge/reference/api-reference.md`
- 运行时配置: `config.json`（仓库根，不提交 Git）

## 前置条件

1. 安装依赖: `python3 -m pip install -r skills/zsxq-knowledge/requirements.txt`
2. 复制 `skills/zsxq-knowledge/config.example.json` 为根目录 `config.json`，填入知识星球 Cookie
3. Cookie 获取: 浏览器登录 wx.zsxq.com → F12 → Network → 复制 Cookie
4. 配置字段名为 `zsxq_cookie`（注意不是 `cookie`）

## 频道信息

| 频道 | key | group_id |
|------|-----|----------|
| 齐俊杰的粉丝群 | qijunjie-fans | 552521181154 |
| 老齐的读书圈 | qijunjie-reading | 454548818428 |
| 躬行客读毛选 | maoxuan | 51128845544444 |
| pure日月：认知普惠 | pure-sunmoon | 15555442414282 |

---

## ⚠️ 关键规则（必须遵守）

1. **用户说"今天"就只同步今天**：使用 `--today` 参数，不要拉历史数据
2. **每篇文章必须有完整正文**：如果 md 文件只有标题没有正文，说明附件内容没提取成功，必须检查
3. **附件文件必须下载到本地**：sync 脚本会自动下载 docx/pdf/mp3 到 `assets/` 目录
4. **docx/pdf 的文本必须写入 md**：sync 脚本会自动提取并写入，检查 md 中是否有 `## 📄 文件名` 段落
5. **金句必须从完整正文中提取**：不要从标题凑金句，必须读完全文后提取有价值的句子
6. **不要跳过短文章**：所有文章无论长短都需要做 enrichment
7. **生成卡片优先用生图模型**：不要调用 HTML/PPT 类 Skill 生成卡片，优先调用图像生成模型直接出图

---

## 工作流（按步骤执行）

### 步骤 1：同步内容（运行脚本）

根据用户需求选择正确的命令：

```bash
# 只同步今天的内容（用户说"同步今天"时用这个）
python3 skills/zsxq-knowledge/scripts/sync.py --channel all --today

# 同步指定日期
python3 skills/zsxq-knowledge/scripts/sync.py --channel all --date 2026-04-11

# 整月重拉某频道（删本地该月目录、分页拉取、重写 md 与附件）
python3 skills/zsxq-knowledge/scripts/sync.py --channel qijunjie-reading --month 2026-04 --refresh

# 同步最近 N 条（不限日期）
python3 skills/zsxq-knowledge/scripts/sync.py --channel all --count 10

# 同步单个频道
python3 skills/zsxq-knowledge/scripts/sync.py --channel qijunjie-fans --today

# 按标签筛选
python3 skills/zsxq-knowledge/scripts/sync.py --channel qijunjie-fans --hashtag 齐观晨会 --count 5
```

参数说明:
- `--channel`: 频道 key 或 `all`
- `--scope`: digests(默认) | all | by_owner | questions | with_files
- `--count`: 拉取数量（默认 10）
- `--today`: 只保留今天的帖子
- `--date YYYY-MM-DD`: 只保留指定日期的帖子
- `--month YYYY-MM`: 分页拉取该月全部帖子；与 `--refresh` 合用可删本地该月并重写
- `--refresh`: 仅与 `--month` 合用，且建议单频道（勿 `--channel all`）
- `--hashtag`: 按标签筛选

**脚本自动完成的事情：**
- 下载 docx/pdf 文件到 `assets/{channel}/{date}/`
- 从 docx/pdf 提取正文并写入 markdown
- 下载 mp3 语音到 `assets/{channel}/{date}/`
- 去重（已同步的 topic_id 不会重复处理）

**同步后必须检查：** 打开新生成的 md 文件，确认正文不是空的。如果正文为空但有附件，需要排查。

### 步骤 2：内容富化（Agent 逐篇执行）

对步骤 1 输出的**每一个新文件**，执行以下操作：

#### 2.1 读取文件完整内容

读取 md 文件全文。

#### 2.2 分析内容并更新 frontmatter

在 frontmatter 中找到以下 4 个空字段并一次性更新：

**替换前（原始模板）：**
```yaml
topic_category: 
keywords: []
summary: ""
quotes_count: 0
```

**替换后（填入分析结果）：**
```yaml
topic_category: 宏观经济
keywords:
  - 关键词1
  - 关键词2
  - 关键词3
summary: "一句话摘要，不超过50字"
quotes_count: 2
```

**各字段填写规则：**

| 字段 | 规则 |
|------|------|
| topic_category | 从内容判断主题。常见分类：宏观经济、市场分析、时事分析、投资理念与方法、书籍笔记、哲学与思维方法、历史分析、领导力与组织、房地产与金融、职业发展、人生感悟、社会观察 |
| keywords | 3-5 个关键词，YAML 列表格式 |
| summary | 一句话概括核心观点，≤50字，用双引号包裹 |
| quotes_count | 下面步骤 2.3 提取的金句数量 |

**注意：** 如果 frontmatter 中 `topic_category` 已经有值（不为空），则保留原值，只替换其余三个字段。此时替换前的文本不同，需要先读取文件确认实际内容。

#### 2.3 提取金句并创建 quotes 文件

从正文中找出有哲理、有洞见、值得反复品味的句子。

**金句标准：**
- 有独立含义，脱离上下文也能理解
- 表达了深刻观点或独特见解
- 不是事实性陈述（如"今天涨了3%"不算金句）
- 不是标题的简单重复

**创建文件：** 与主文件同目录，文件名为 `{主文件名}.quotes.md`（即 `.md` 前插入 `.quotes`）。

**文件格式：**
```markdown
> 金句内容第一条

> 金句内容第二条
```

如果没有值得提取的金句，不创建文件，`quotes_count` 设为 0。

#### 2.4 批量处理建议

为减少 Token 消耗：
- 可以一次读取 3-5 篇文章
- 批量更新 frontmatter 和 quotes 文件
- 对子 Agent 做任务委托时，一次给出所有文件路径

### 步骤 3：重建索引（运行脚本）

所有文件富化完成后，运行一次：

```bash
python3 skills/zsxq-knowledge/scripts/build_index.py
```

自动生成:
- `INDEX.md` — 主索引概览
- `index/by-date/{year}/{month}.md` — 按月索引
- `index/by-tag/{tag}.md` — 按标签索引
- `index/by-topic/{topic}.md` — 按主题分类索引
- `index/by-channel/{channel}.md` — 按频道索引
- `index/quotes-index.md` — 金句索引
- `index/index.json` — 机器可读索引

### 步骤 4：向用户汇报

汇报格式：
```
同步完成：
- 同步日期：YYYY-MM-DD
- 各频道新增文章数
- 金句数量
- 内容摘要（每频道 2-3 条标题和一句话摘要）
```

---

## 搜索与查找

```bash
python3 skills/zsxq-knowledge/scripts/search.py "降息"
python3 skills/zsxq-knowledge/scripts/search.py --tag "宏观策略" --limit 20
python3 skills/zsxq-knowledge/scripts/search.py --channel maoxuan
python3 skills/zsxq-knowledge/scripts/search.py --category "投资理念与方法"
python3 skills/zsxq-knowledge/scripts/search.py --date-from 2026-04-01
```

**查找顺序（最小化 Token）：**
1. 先用 `search.py` 按关键词/标签/日期查找
2. 读取 `INDEX.md` 获取概览
3. 读取分片索引（如 `index/by-tag/齐观晨会.md`）
4. 最后读具体文章

---

## 语音转文字（ASR）

md 文件中的语音标记为 `> ⚠️ 语音内容需要 ASR 转文字后补充到此处`。

处理步骤：
1. 从 frontmatter 获取 `voice.local_path`（已下载的本地 mp3 路径）
2. 调用火山引擎大模型 ASR API 转写
3. 将转写文本替换 md 中的语音占位符

火山 ASR: `POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash`

---

## 生成海报

将金句生成海报图片（默认使用生图模型）：
1. 从 `.quotes.md` 文件选择金句
2. 根据来源频道和内容风格给出生图提示词（主题、风格、配色、排版、字体氛围）
3. 调用图像生成模型直接生成 1080×1440px 竖版卡片

**强制要求：**
- 不使用 HTML/PPT 的 slide 技能来生成卡片
- 优先使用图像生成模型（如通用文生图能力）
- 每次至少给出 2-3 个风格方向供用户选择（如极简、国风、金融杂志风）

---

## 目录结构

```
my-knowledge-base/                   # 知识库根目录
├── skills/                          # 个人 Skills 目录
│   └── zsxq-knowledge/              # 本 Skill
│       ├── SKILL.md                 # Skill 定义（本文件）
│       ├── config.example.json      # 配置模板
│       ├── requirements.txt         # Python 依赖
│       ├── scripts/                 # 自动化脚本
│       │   ├── sync.py
│       │   ├── build_index.py
│       │   ├── search.py
│       │   ├── zsxq_api.py
│       │   └── utils.py
│       └── reference/               # API 参考文档
│           └── api-reference.md
├── config.json                      # 运行时配置（不提交 Git）
├── .synced_ids                      # 同步状态（不提交 Git）
├── channels/                        # Markdown 文章
│   ├── qijunjie-fans/
│   ├── qijunjie-reading/
│   ├── maoxuan/
│   └── pure-sunmoon/
├── assets/                          # 下载的附件（docx/pdf/mp3）
├── index/                           # 索引文件
├── INDEX.md                         # 主索引
├── data/raw/                        # 原始 JSON（不提交 Git）
└── README.md
```

## Markdown 文件 frontmatter 字段

| 字段 | 来源 | 说明 |
|------|------|------|
| id | 脚本 | topic_id 唯一标识 |
| source | 脚本 | 频道中文名 |
| channel | 脚本 | 频道 key |
| author | 脚本 | 作者 |
| date | 脚本 | 发布日期 |
| type | 脚本 | talk / q&a / article |
| content_type | 脚本 | text / voice / file 组合 |
| is_digest | 脚本 | 是否精华 |
| likes | 脚本 | 点赞数 |
| comments | 脚本 | 评论数 |
| tags | 脚本 | 正文中的 hashtag |
| topic_category | Agent | 主题分类 |
| keywords | Agent | 关键词列表 |
| summary | Agent | 一句话摘要 |
| quotes_count | Agent | 金句数量 |
| voice | 脚本 | 语音信息含 local_path |
| files | 脚本 | 附件信息含 local_path |

## 注意事项

- Cookie 过期后重新从浏览器获取，更新根目录 `config.json` 中的 `zsxq_cookie`
- API 请求间隔 1.5 秒，脚本已内置限流
- `assets/` 目录可能较大，按需 gitignore
- API 详情见 `skills/zsxq-knowledge/reference/api-reference.md`
