# 知识星球 API 参考

> 基于实测验证，Web 版 v2 API，Cookie 认证。

## 认证

请求头携带 Cookie 即可，不需要签名验证：
```
Cookie: zsxq_access_token=TOKEN; abtest_env=product
Origin: https://wx.zsxq.com
Referer: https://wx.zsxq.com/
```

## 接口列表

### GET /v2/groups
获取用户加入的所有星球。

返回: `resp_data.groups[]` — group_id, name, type, owner 等

### GET /v2/groups/{group_id}/topics
获取星球帖子列表。

参数:
- `scope`: all | digests | by_owner | questions | with_files | with_images
- `count`: 每页数量（建议 10）
- `end_time`: 分页游标（上一页最后一条的 create_time）

返回: `resp_data.topics[]`

### GET /v2/hashtags/{hashtag_id}/topics
获取指定标签下的帖子。

参数: count, end_time

### GET /v2/groups/{group_id}/menus
获取频道顶部筛选菜单。

返回: `resp_data.menus[]` — menu_id, title, preset/preset_type 或 hashtag.hashtag_id

### GET /v2/groups/{group_id}/hashtags
获取频道所有标签及帖子数。

返回: `resp_data.hashtags[]` — hashtag_id, title, topics_count

### GET /v2/files/{file_id}/download_url
获取文件/语音的临时下载链接。

返回: `resp_data.download_url`（带签名，有时效）

## Topic 数据结构

```json
{
  "topic_id": 55522284425488584,
  "type": "talk | q&a | article",
  "create_time": "2026-04-11T14:29:50.800+0800",
  "digested": true,
  "likes_count": 79,
  "comments_count": 12,
  "title": "自动摘要...",

  "talk": {
    "owner": { "name": "...", "user_id": ... },
    "text": "正文（含富文本标记）",
    "images": [{ "large": { "url": "..." }, "original": { "url": "..." } }],
    "files": [{ "file_id": ..., "name": "x.pdf", "size": ..., "duration": ... }]
  },

  "content_voice": {
    "file_id": ..., "name": "x.mp3", "duration": 114, "size": 457652
  },

  "question": { "owner": {...}, "text": "...", "questionee": {...} },
  "answer": { "owner": {...}, "text": "..." },

  "show_comments": [...]
}
```

## 富文本标记

正文中的特殊标记：
- `<e type="hashtag" hid="ID" title="%23标签名%23" />` → 标签
- `<e type="text_bold" title="文本" />` → 加粗
- `<e type="web" href="URL编码" title="标题" />` → 链接
- `<e type="mention" uid="ID" title="用户名" />` → @提及

## 频率限制

- 建议每次请求间隔 1.5 秒
- count 参数建议 ≤ 10
- Cookie 有效期约 1-3 个月
