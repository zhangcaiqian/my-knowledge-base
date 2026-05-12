# 火山引擎官方文档摘录（TTS/播客）

以下链接用于该 Skill 的实现依据（均为火山引擎官方文档）：

1. 精品长文本语音合成 API 接口文档  
   https://www.volcengine.com/docs/6561/1096680?lang=zh
2. 精品长文本音色列表  
   https://www.volcengine.com/docs/6561/1108211?lang=zh
3. 音色列表新接口（ListSpeakers）  
   https://www.volcengine.com/docs/6561/2160690
4. 语音播客大模型-产品简介  
   https://www.volcengine.com/docs/6561/1631586?lang=zh
5. 语音播客大模型 WebSocket v3 协议（接入时参考）  
   https://www.volcengine.com/docs/6561/1668014?lang=zh

---

## 关键点摘要

### A. 精品长文本语音合成（异步）

- 创建任务（普通版）：`POST https://openspeech.bytedance.com/api/v1/tts_async/submit`
- 查询任务（普通版）：`GET https://openspeech.bytedance.com/api/v1/tts_async/query`
- 创建任务（情感预测版）：`POST https://openspeech.bytedance.com/api/v1/tts_async_with_emotion/submit`
- 查询任务（情感预测版）：`GET https://openspeech.bytedance.com/api/v1/tts_async_with_emotion/query`

请求头要求（官方文档说明）：
- `Resource-Id`
- `Authorization`

常用请求参数：
- `appid` / `reqid` / `text` / `format` / `voice_type`
- 可选：`sample_rate` / `volume` / `speed` / `pitch` / `enable_subtitle` / `callback_url`

限制与注意：
- 创建任务频率限制：10 QPS
- 单次最多支持 10 万字符（异步场景）
- 结果 `audio_url` 有有效期，需及时下载

### B. 常用推荐音色（情感预测版）

- 擎苍 `BV701_streaming`
- 阳光青年 `BV123_streaming`
- 反卷青年 `BV120_streaming`
- 通用赘婿 `BV119_streaming`
- 古风少御 `BV115_streaming`
- 霸气青叔 `BV107_streaming`
- 质朴青年 `BV100_streaming`
- 温柔淑女 `BV104_streaming`
- 开朗青年 `BV004_streaming`
- 甜宠少御 `BV113_streaming`
- 儒雅青年 `BV102_streaming`

### C. 语音播客大模型

**核心机制（非常重要）**：
- 输入：**原始文章文本**（不需要提前改写成对话格式）
- 输出：由模型端到端自动生成的**双人播客音频**（含自然附和、停顿、插话节奏）
- Agent **不需要**：① 把文章改写成 A/B 对话脚本 ② 分两个音色分别合成 ③ 手动拼接两路音频

接入方式：
- 与普通 TTS 同样使用 WebSocket V3 协议，但是**独立产品**，需在控制台单独开通权限
- 端点：`wss://openspeech.bytedance.com/api/v3/tts/bidirection`（Resource-Id 与普通 TTS 不同，见官方文档）
- 请求中通过 `speakers` 数组配置主播A / 主播B 的音色（具体字段名以 [官方文档 1668014](https://www.volcengine.com/docs/6561/1668014) 为准）
- 认证头同普通 TTS V3：`X-Api-App-Key` / `X-Api-Access-Key` / `X-Api-Resource-Id`

官方说明该模型特性：
- 融入真人播客的自然附和、口语停顿、"嗯"声及呼吸感
- 还原插话、附和、停顿等真实对话节奏
- 内容专业度与播客质感媲美人工录制

---

## 实施建议

1. 优先通过 `ListSpeakers` 动态拉取最新可用音色  
2. 如果运行时未接入动态音色查询，则使用 `SKILL.md` 内置音色表  
3. 每次合成前必须让用户确认音色（direct=1个，podcast=2个）

