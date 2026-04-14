# 知识星球知识库

将知识星球订阅内容整理为结构化的 Markdown 知识库，支持多维索引、全文搜索、金句提取和海报生成。

## 支持的频道

- 齐俊杰的粉丝群（投资、宏观经济、实事分析）
- 老齐的读书圈（财经书籍解读）
- 躬行客读毛选（毛选、唯物辩证法）
- pure日月：认知普惠（房地产、金融）

## 安装

```bash
git clone https://github.com/YOUR_USERNAME/my-knowledge-base.git
cd my-knowledge-base
pip install -r requirements.txt
cp config.example.json config.json
# 编辑 config.json，填入知识星球 Cookie
```

### 获取 Cookie

1. 浏览器打开 [wx.zsxq.com](https://wx.zsxq.com)，扫码登录
2. F12 打开开发者工具 → Network 面板
3. 刷新页面，找到 `api.zsxq.com` 的请求
4. 复制请求头中的 Cookie 值到 `config.json`

## 使用

### 作为 Cursor/Codex Skill

本仓库包含 `SKILL.md`，可直接作为 Agent Skill 使用：

**Cursor:** 将本目录链接到 `~/.cursor/skills/zsxq-knowledge/`
```bash
ln -s /path/to/my-knowledge-base ~/.cursor/skills/zsxq-knowledge
```

**Codex/其他 Agent:** 在项目中引用 `SKILL.md` 即可。

### 手动使用脚本

```bash
# 同步今天的精华内容
python scripts/sync.py --channel all --count 10

# 同步特定频道
python scripts/sync.py --channel qijunjie-fans --scope digests

# 按标签同步
python scripts/sync.py --channel qijunjie-fans --hashtag 齐观晨会

# 重建索引
python scripts/build_index.py

# 搜索
python scripts/search.py "降息"
python scripts/search.py --tag "宏观策略"
python scripts/search.py --channel maoxuan --limit 20
```

## 目录结构

```
├── SKILL.md                  # Agent Skill 定义
├── config.json               # 配置（gitignore）
├── scripts/                  # 工具脚本
│   ├── zsxq_api.py           # API 客户端
│   ├── sync.py               # 同步数据
│   ├── build_index.py        # 构建索引
│   └── search.py             # 搜索
├── reference/                # 参考文档
├── INDEX.md                  # 主索引（自动生成）
├── index/                    # 分片索引（自动生成）
├── channels/                 # 同步的文章内容
│   ├── qijunjie-fans/
│   ├── qijunjie-reading/
│   ├── maoxuan/
│   └── pure-sunmoon/
└── quotes/                   # 金句汇总
```

## 工作流概述

1. **同步** → `sync.py` 从 API 拉取内容，转为 Markdown（零 Token）
2. **富化** → Agent 读取新文件，补充摘要/关键词/金句（消耗 Token）
3. **索引** → `build_index.py` 自动构建多维索引（零 Token）
4. **查找** → `search.py` 或 Agent 读索引文件
5. **创作** → 生成海报/视频用于社交媒体发布
