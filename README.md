# 个人知识库

将多平台订阅内容整理为结构化的 Markdown 知识库，通过 Agent Skill 自动化管理。

## Skills

| Skill | 目录 | 说明 |
|-------|------|------|
| [知识星球](skills/zsxq-knowledge/SKILL.md) | `skills/zsxq-knowledge/` | 同步知识星球频道内容、提取金句、构建索引 |
| [微信读书](skills/weread/SKILL.md) | `skills/weread/` | 同步微信读书划线与笔记、提取金句、生成读书总结 |

## 安装

```bash
git clone https://github.com/YOUR_USERNAME/my-knowledge-base.git
cd my-knowledge-base

# 知识星球
pip install -r skills/zsxq-knowledge/requirements.txt

# 微信读书
pip install -r skills/weread/requirements.txt

# 复制配置模板
cp skills/zsxq-knowledge/config.example.json config.json
# 编辑 config.json，填入知识星球 Cookie 和微信读书 Cookie
```

### 获取 Cookie

**知识星球：**
1. 浏览器打开 [wx.zsxq.com](https://wx.zsxq.com)，扫码登录
2. F12 打开开发者工具 → Network 面板
3. 刷新页面，找到 `api.zsxq.com` 的请求
4. 复制请求头中的 Cookie 值到 `config.json`

**微信读书：**
1. 浏览器打开 [weread.qq.com](https://weread.qq.com)，微信扫码登录
2. F12 → Application → Cookies → `weread.qq.com`
3. 复制所有 Cookie 值到 `config.json` 的 `weread_cookie` 字段

## 使用

### 作为 Agent Skill

本仓库的 `skills/` 目录包含可复用的 Agent Skill：

**Cursor:** 在 Skill 配置中指向对应 Skill 的 `SKILL.md`

**Codex/其他 Agent:** 在项目中引用对应的 `SKILL.md` 即可

### 手动使用脚本

**知识星球：**
```bash
# 同步今天的精华内容
python3 skills/zsxq-knowledge/scripts/sync.py --channel all --today

# 同步最近 N 条
python3 skills/zsxq-knowledge/scripts/sync.py --channel all --count 10

# 整月重拉某频道
python3 skills/zsxq-knowledge/scripts/sync.py --channel qijunjie-reading --month 2026-04 --refresh

# 重建索引
python3 skills/zsxq-knowledge/scripts/build_index.py

# 搜索
python3 skills/zsxq-knowledge/scripts/search.py "降息"
python3 skills/zsxq-knowledge/scripts/search.py --tag "宏观策略"
```

**微信读书：**
```bash
# 列出有笔记的书
python3 skills/weread/scripts/sync.py --list

# 同步某本书
python3 skills/weread/scripts/sync.py --book "穷查理"

# 同步全部有笔记的书
python3 skills/weread/scripts/sync.py --all

# 重新同步（覆盖）
python3 skills/weread/scripts/sync.py --book "穷查理" --refresh
```

## 目录结构

```
├── skills/                          # Agent Skills
│   ├── zsxq-knowledge/              # 知识星球 Skill
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   ├── config.example.json
│   │   ├── requirements.txt
│   │   └── reference/
│   └── weread/                      # 微信读书 Skill
│       ├── SKILL.md
│       ├── scripts/
│       ├── config.example.json
│       ├── requirements.txt
│       └── reference/
├── config.json                      # 运行时配置（gitignore）
├── channels/                        # 知识星球文章
│   ├── qijunjie-fans/
│   ├── qijunjie-reading/
│   ├── maoxuan/
│   └── pure-sunmoon/
├── books/                           # 微信读书数据
│   └── {书名}/
│       ├── highlights.md            # 划线 + 想法
│       ├── highlights.quotes.md     # 金句
│       └── summary.md              # 读书总结
├── assets/                          # 下载的附件（gitignore）
├── INDEX.md                         # 主索引（自动生成）
├── index/                           # 分片索引（自动生成）
└── data/                            # 原始 API 数据（gitignore）
```

## 工作流概述

**知识星球：**
1. **同步** → `sync.py` 从 API 拉取内容，下载附件，提取正文，转为 Markdown
2. **富化** → Agent 读取新文件，补充摘要/关键词/金句
3. **索引** → `build_index.py` 自动构建多维索引
4. **查找** → `search.py` 或 Agent 读索引文件
5. **创作** → 生成海报/视频用于社交媒体发布

**微信读书：**
1. **同步** → `sync.py` 从 API 拉取划线和想法，按章节组织为 Markdown
2. **富化** → Agent 提取金句、补充关键词
3. **总结** → Agent 辅助生成读书总结草稿
4. **关联** → 与知识星球内容交叉引用
