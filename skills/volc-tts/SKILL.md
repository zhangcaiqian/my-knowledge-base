---
name: volc-tts
description: >-
  使用火山引擎将文本转换为语音，支持“播客双人对话”与“文字稿直转语音”两种模式。
  当用户提到文本转语音、TTS、配音、朗读、播客音频、音色选择、语音合成时使用。
---

# 火山引擎文本转语音

本 Skill 位于 `skills/volc-tts/`，用于把文本转成可发布的语音内容。

支持两种输出形式：
- `podcast`：双人对话播客风格（更口语、更有互动感）
- `direct`：文字稿直接转语音（单音色旁白）

## 先决规则（必须遵守）

1. 生成前必须先确认模式：`podcast` 或 `direct`
2. 如果用户未指定音色，先列出可选音色并让用户选择：
   - `direct`：选 1 个音色
   - `podcast`：选 2 个音色（分别对应主播A / 主播B），播客大模型自动生成双人对话音频，**不需要 Agent 手动改写文本或拼接音频**
3. 用户已明确指定音色时，可直接进入合成
4. 用户未选音色，不得直接合成
5. 默认使用火山引擎官方 API，不自行发明参数名
6. `podcast` 模式调用「语音播客大模型」（与普通 TTS 不同的独立产品），需提前在控制台开通对应权限

---

## 官方文档依据

先读 `reference/official-docs.md`（文档链接与关键参数摘要）。

重点依据：
- 精品长文本语音合成 API（异步）：submit/query
- 音色列表（情感预测版推荐音色）
- 语音播客大模型（双人对话）

---

## 可选音色（每次都要展示给用户）

> 当前使用 **豆包语音合成模型2.0**（Resource-Id: `seed-tts-2.0`）。
> 音色必须使用 `_uranus_bigtts` 后缀，旧版 `_moon_bigtts` / `_jupiter_bigtts` / `BV*_streaming` 与此 Resource-Id 不兼容。

以下为推荐音色（均已验证可用）：

| 音色名 | speaker | 适合内容 |
|---|---|---|
| 霸气青叔 | `zh_male_baqiqingshu_uranus_bigtts` | 厚重男声，适合气势型朗读、人物传记、偏情绪化演讲稿 |
| 悬疑解说 | `zh_male_xuanyijieshuo_uranus_bigtts` | 低沉神秘，适合悬疑故事、案件解说、带氛围感的叙事内容 |
| 深夜播客 | `zh_male_shenyeboke_uranus_bigtts` | 磁性沉稳，适合夜谈播客、长篇随笔、纪录片旁白 |
| 渊博小叔 | `zh_male_yuanboxiaoshu_uranus_bigtts` | 知识感强，适合财经分析、科普讲解、方法论文章 |
| 高冷沉稳 | `zh_male_gaolengchenwen_uranus_bigtts` | 理性克制，适合课程讲解、概念拆解、偏严肃的知识内容 |
| 云舟 | `zh_male_m191_uranus_bigtts` | 自然中性，适合知识朗读、方法论文章、说明性文本、通用长文 |
| Vivi | `zh_female_vv_uranus_bigtts` | 知性优雅，适合温和陪伴型朗读、书摘、有声书 |
| 清新女声 | `zh_female_qingxinnvsheng_uranus_bigtts` | 清爽自然，适合生活方式内容、轻知识分享、轻旁白 |
| 爽快思思 | `zh_female_shuangkuaisisi_uranus_bigtts` | 节奏明快，适合资讯快报、短视频口播、轻快风格内容 |

说明：
- 完整音色列表见官方文档：https://www.volcengine.com/docs/6561/1257544
- 运行 `python skills/volc-tts/scripts/tts.py list-voices` 可本地查看推荐列表

---

## 工作流

### 步骤 1：确认生成需求

向用户确认：
- 模式：`podcast` / `direct`
- 目标平台：小红书、公众号、播客平台、视频配音
- 时长目标（如 1 分钟 / 3 分钟 / 8 分钟）
- 语速（慢/中/快）

### 步骤 2：展示音色并让用户选择

必须用如下格式询问：

```text
可选音色如下（豆包语音合成模型2.0，均已验证可用）：
1) 霸气青叔  zh_male_baqiqingshu_uranus_bigtts   — 厚重男声，适合气势型朗读/人物传记
2) 悬疑解说  zh_male_xuanyijieshuo_uranus_bigtts  — 低沉神秘，适合悬疑叙事/案件解说
3) 深夜播客  zh_male_shenyeboke_uranus_bigtts     — 磁性沉稳，适合播客/纪录片/长篇随笔
4) 渊博小叔  zh_male_yuanboxiaoshu_uranus_bigtts  — 知识感强，适合财经/科普/方法论讲解
5) 云舟      zh_male_m191_uranus_bigtts            — 自然中性，适合知识朗读/方法论文章/说明性长文
6) Vivi      zh_female_vv_uranus_bigtts             — 知性优雅，适合温和朗读/书摘/有声书
7) 清新女声  zh_female_qingxinnvsheng_uranus_bigtts — 清爽自然，适合轻知识/生活方式内容
8) 爽快思思  zh_female_shuangkuaisisi_uranus_bigtts — 明快活泼，适合资讯快报/短视频口播
请选择：
- direct 模式：1 个音色
- podcast 模式：2 个音色（主播A / 主播B；模型自动生成双人对话，无需手动改写文本）
```

### 步骤 3：文本预处理

- `direct`：保留原文结构，清理无效符号，必要时分段（单次建议 ≤1000 字，超长请分段）
- `podcast`：**直接传入原始文章文本即可**，无需人工改写成对话格式。
  火山引擎「语音播客大模型」会端到端自动完成：
  - 文章内容 → 双人对话脚本（LLM 侧）
  - 双人脚本 → 带附和/停顿/插话的真实播客音频（TTS 侧）
  整个过程在一次 API 调用内完成，**不需要 Agent 介入改写或拼接**。

### 步骤 4：执行脚本合成音频

统一使用 `skills/volc-tts/scripts/tts.py`，无需手动拼装请求。

#### 安装依赖（首次）

```bash
pip install websockets aiofiles
# 或
pip install -r skills/volc-tts/requirements.txt
```

#### 凭证配置（任选其一）

```bash
# 方式 A：环境变量
export VOLC_TTS_APP_ID="your_app_id"
export VOLC_TTS_TOKEN="your_token"

# 方式 B：config.json（添加以下字段）
# "volcengine": { "tts_app_id": "...", "tts_token": "..." }
```

凭证获取：https://console.volcengine.com/speech/app → 语音合成大模型 → Token

#### `direct` 模式

```bash
python skills/volc-tts/scripts/tts.py direct \
  --text "你好，今天来聊一聊投资中的..." \
  --speaker zh_male_baqiqingshu_uranus_bigtts \
  --output assets/tts/2026-04-14/article-direct.mp3
```

或从文件读取：

```bash
python skills/volc-tts/scripts/tts.py direct \
  --file channels/qijunjie/2026/04/14/some-article.md \
  --speaker zh_male_yuanboxiaoshu_uranus_bigtts \
  --speed 1.05 \
  --output assets/tts/2026-04-14/article-direct.mp3
```

#### `podcast` 模式（语音播客大模型）

直接传入原始文章，模型自动生成双人对话音频：

```bash
python skills/volc-tts/scripts/tts.py podcast \
  --file channels/qijunjie/2026/04/14/some-article.md \
  --speaker-a zh_male_shenyeboke_uranus_bigtts \
  --speaker-b zh_female_vv_uranus_bigtts \
  --output assets/tts/2026-04-14/article-podcast.mp3
```

> ⚠️ `podcast` 模式需在控制台开通「语音播客大模型」权限。
> 若遇到 Resource-Id 错误，请查阅 [官方文档 1668014](https://www.volcengine.com/docs/6561/1668014)，
> 将脚本顶部的 `RESOURCE_ID_PODCAST` 更新为正确值。

### 步骤 5：交付结果

返回给用户：
- 生成模式
- 使用音色（含 voice_type）
- 音频文件路径
- 如有失败，返回接口报错与修复建议

---

## 输出模板

```text
语音生成完成：
- 模式：podcast
- 主播A：深夜播客（zh_male_shenyeboke_uranus_bigtts）
- 主播B：Vivi（zh_female_vv_uranus_bigtts）
- 参数：mp3 / 24k / speed=1.0
- 文件：assets/tts/2026-04-14/topic-podcast.mp3
```
