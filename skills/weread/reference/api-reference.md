# 微信读书 Web API 参考

## 概述

微信读书没有官方公开 API，但其 Web 版 (weread.qq.com) 内部使用了稳定的 REST API。
通过 Cookie 认证即可调用这些接口。

**Base URL:** `https://i.weread.qq.com`

## 认证

### Cookie 获取方式

1. 浏览器打开 [weread.qq.com](https://weread.qq.com)，微信扫码登录
2. F12 打开开发者工具
3. Application → Cookies → `weread.qq.com`
4. 复制所有 cookie，关键字段：`wr_vid`, `wr_skey`, `wr_rt`, `wr_pf`

### 请求头

```
Cookie: wr_vid=xxx; wr_skey=xxx; wr_rt=xxx; wr_pf=xxx
User-Agent: Mozilla/5.0 ...
```

## 主要接口

### 1. 书架 — GET /shelf/sync

```
GET /shelf/sync?synckey=0&teenmode=0
```

返回用户书架上的所有书籍。

### 2. 有笔记的书 — GET /user/notebooks

```
GET /user/notebooks
```

返回所有有划线或笔记的书籍列表。

**响应结构:**

```json
{
  "books": [
    {
      "bookId": "123456",
      "book": {
        "bookId": "123456",
        "title": "书名",
        "author": "作者",
        "cover": "封面URL",
        "category": "分类",
        "isbn": "ISBN"
      },
      "bookmarkCount": 25,
      "reviewCount": 3,
      "sort": 1712345678
    }
  ]
}
```

### 3. 书籍详情 — GET /book/info

```
GET /book/info?bookId=123456
```

返回书籍的详细元数据（标题、作者、出版社、简介等）。

### 4. 章节信息 — POST /book/chapterInfos

```
POST /book/chapterInfos
Content-Type: application/json

{"bookIds": ["123456"]}
```

**响应结构:**

```json
{
  "data": [
    {
      "bookId": "123456",
      "updated": [
        {
          "chapterUid": 1,
          "chapterIdx": 1,
          "title": "第一章 标题",
          "level": 1
        }
      ]
    }
  ]
}
```

### 5. 用户划线 — GET /book/bookmarklist

```
GET /book/bookmarklist?bookId=123456
```

**响应结构:**

```json
{
  "updated": [
    {
      "bookmarkId": "...",
      "bookId": "123456",
      "chapterUid": 1,
      "range": "...",
      "markText": "划线的文本内容",
      "createTime": 1712345678,
      "style": 0,
      "type": 1,
      "colorStyle": 0
    }
  ],
  "synckey": 0
}
```

**style 含义:**
- `0` — 直线下划线
- `1` — 波浪线
- `2` — 荧光笔高亮

### 6. 用户想法/笔记 — GET /review/list

```
GET /review/list?bookId=123456&listType=11&mine=1&synckey=0
```

**响应结构:**

```json
{
  "reviews": [
    {
      "review": {
        "reviewId": "...",
        "bookId": "123456",
        "chapterUid": 1,
        "content": "用户写的想法",
        "abstract": "所关联的划线文本",
        "createTime": 1712345678,
        "range": "...",
        "type": 1
      }
    }
  ]
}
```

### 7. 热门划线 — GET /book/bestbookmarks

```
GET /book/bestbookmarks?bookId=123456
```

返回全平台热门划线（被最多人标记的段落）。

### 8. 阅读进度 — GET /book/readinfo

```
GET /book/readinfo?bookId=123456&readingDetail=1
```

返回阅读进度和时长信息。

## 注意事项

- Cookie 有效期通常为数天到数周，过期后需重新获取
- 无官方限流文档，建议请求间隔 ≥ 1 秒
- 返回 HTTP 401 表示 Cookie 过期
- 返回 HTTP 429 表示请求过频，需等待
- bookId 类型可能是字符串或数字，建议统一为字符串处理
