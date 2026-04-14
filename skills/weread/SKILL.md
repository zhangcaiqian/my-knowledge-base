---
name: weread
description: >-
  管理微信读书的划线、笔记与读书总结：同步高亮内容、提取金句、生成读书总结模板。
  当用户提到微信读书、weread、读书笔记、书评、划线内容、读书总结、同步读书时使用。
---

# 微信读书知识库管理

本 Skill 位于 `skills/weread/`，知识库根目录为仓库根。

- 脚本目录: `skills/weread/scripts/`
- 配置模板: `skills/weread/config.example.json`
- API 参考: `skills/weread/reference/api-reference.md`
- 运行时配置: `config.json`（仓库根，不提交 Git）
- 数据目录: `books/`（仓库根）

## 前置条件

1. 安装依赖: `python3 -m pip install -r skills/weread/requirements.txt`
2. 在根目录 `config.json` 中添加 `weread_cookie` 字段（见下方）
3. Cookie 获取: 浏览器登录 weread.qq.com → F12 → Application → Cookies → 复制全部

### config.json 中添加微信读书配置

```json
{
  "weread_cookie": "wr_vid=xxx; wr_skey=xxx; wr_rt=xxx; wr_pf=xxx"
}
```

如果 `config.json` 已有知识星球配置，直接在 JSON 根对象中加入 `weread_cookie` 字段即可。

---

## ⚠️ 关键规则（必须遵守）

1. **每本书三件套**：`highlights.md`（划线+想法）、`highlights.quotes.md`（金句）、`summary.md`（读书总结）
2. **划线和想法必须关联**：想法（💭）紧跟在对应的划线（>）之后，不能分开
3. **按章节组织**：所有划线和想法按章节分组，保持原书结构
4. **金句从划线中提取**：不要编造金句，必须是书中原文或用户的精炼表达
5. **summary.md 是用户手写**：脚本生成模板，Agent 可辅助生成草稿，但标记 `status: draft`
6. **不要丢弃任何划线**：所有划线和想法都必须保留，不能遗漏

---

## 工作流

### 步骤 1：查看有笔记的书

```bash
python3 skills/weread/scripts/sync.py --list
```

输出每本书的书名、作者、bookId、划线数、想法数。

### 步骤 2：同步书籍

根据用户需求选择命令：

```bash
# 按书名关键词同步（模糊匹配）
python3 skills/weread/scripts/sync.py --book "穷查理"

# 按 bookId 同步
python3 skills/weread/scripts/sync.py --book-id 123456

# 同步全部有笔记的书
python3 skills/weread/scripts/sync.py --all

# 覆盖已有文件（重新同步）
python3 skills/weread/scripts/sync.py --book "穷查理" --refresh
```

**脚本自动完成的事情：**
- 获取书籍元数据（标题、作者、ISBN、分类、封面）
- 获取所有章节信息
- 获取所有划线（按章节排列，保留划线样式）
- 获取所有想法/笔记（关联到对应划线之后）
- 生成 `highlights.md`（含完整 frontmatter）
- 生成 `summary.md`（模板，状态为 draft）

**同步后检查：** 打开 `highlights.md`，确认划线和想法数量与 `--list` 显示一致。

### 步骤 3：内容富化（Agent 执行）

对每本新同步的书执行以下操作：

#### 3.1 读取 highlights.md

用 Read 工具读取完整内容。

#### 3.2 更新 frontmatter

找到以下 3 个空字段，用 StrReplace 一次性替换：

**替换前：**
```yaml
keywords: []
quotes_count: 0
summary: ""
```

**替换后：**
```yaml
keywords:
  - 关键词1
  - 关键词2
  - 关键词3
quotes_count: 3
summary: "一句话概括本书核心观点，≤50字"
```

#### 3.3 提取金句创建 quotes 文件

从划线内容中挑选最有价值的句子，创建 `highlights.quotes.md`：

**金句标准：**
- 有独立含义，脱离上下文也能理解
- 表达了深刻观点或独特洞见
- 不是纯事实性描述
- 优先选择用户加了"想法"的划线

**文件格式：**
```markdown
> 金句第一条 —— 《书名》

> 金句第二条 —— 《书名》
```

#### 3.4 辅助生成读书总结（用户要求时）

当用户要求写总结时，读取 `highlights.md` 全文，根据 `summary.md` 模板生成草稿：

1. 读取所有划线和想法
2. 提炼核心观点（3-5 个）
3. 总结关键收获
4. 找出与其他知识（知识星球内容、其他书籍）的关联
5. 将 frontmatter 中 `status` 从 `draft` 改为 `review`

**注意：** 总结是辅助草稿，需要用户确认后改为 `status: final`。

### 步骤 4：向用户汇报

```
同步完成：
- 书名：《xxx》
- 作者：xxx
- 划线数：xx 条
- 想法数：xx 条
- 金句数：xx 条
- 章节覆盖：xx 章
```

---

## 搜索与查找

微信读书内容的搜索通过直接读取文件实现：

```bash
# 搜索所有书中的关键词
grep -r "关键词" books/ --include="*.md" -l

# 查看某本书的划线
cat books/穷查理宝典/highlights.md

# 查看所有金句
cat books/*/highlights.quotes.md
```

Agent 也可以直接用 Grep / Read 工具在 `books/` 目录下搜索。

---

## 与知识星球的关联

微信读书的书籍内容可以与知识星球的文章互相关联：

- **老齐的读书圈** 解读的书 → 在该书的 `summary.md` 中添加"关联内容"链接
- 知识星球文章中引用的书籍 → 在 `summary.md` 的"与其他知识的关联"部分记录

Agent 在做 enrichment 时，可主动检查 `channels/qijunjie-reading/` 和 `index/` 寻找关联。

---

## 目录结构

```
my-knowledge-base/
├── skills/
│   ├── zsxq-knowledge/             # 知识星球 Skill
│   └── weread/                     # 本 Skill
│       ├── SKILL.md                # Skill 定义（本文件）
│       ├── config.example.json     # 配置模板
│       ├── requirements.txt        # Python 依赖
│       ├── scripts/                # 自动化脚本
│       │   ├── sync.py
│       │   ├── weread_api.py
│       │   └── utils.py
│       └── reference/
│           └── api-reference.md
├── config.json                     # 运行时配置（不提交 Git）
├── books/                          # 读书数据
│   ├── 穷查理宝典/
│   │   ├── highlights.md           # 划线 + 想法
│   │   ├── highlights.quotes.md    # 金句
│   │   └── summary.md              # 读书总结
│   └── 纳瓦尔宝典/
│       ├── highlights.md
│       ├── highlights.quotes.md
│       └── summary.md
├── channels/                       # 知识星球内容
├── index/                          # 索引
└── README.md
```

## highlights.md frontmatter 字段

| 字段 | 来源 | 说明 |
|------|------|------|
| title | 脚本 | 书名 |
| author | 脚本 | 作者 |
| book_id | 脚本 | 微信读书 bookId |
| isbn | 脚本 | ISBN |
| category | 脚本 | 分类 |
| publisher | 脚本 | 出版社 |
| cover | 脚本 | 封面 URL |
| rating | 脚本 | 微信读书评分 |
| total_read_time | 脚本 | 累计阅读时长 |
| finished | 脚本 | 是否读完 |
| highlights_count | 脚本 | 划线数 |
| thoughts_count | 脚本 | 想法数 |
| first_mark_date | 脚本 | 最早标注日期 |
| last_mark_date | 脚本 | 最近标注日期 |
| keywords | Agent | 关键词列表 |
| quotes_count | Agent | 金句数量 |
| summary | Agent | 一句话概括 |

## 注意事项

- Cookie 过期后重新从浏览器获取，更新 `config.json` 中的 `weread_cookie`
- API 请求间隔 1 秒，脚本已内置限流
- 划线样式保留：📏 直线、〰️ 波浪线、🖍️ 荧光笔
- API 详情见 `skills/weread/reference/api-reference.md`
