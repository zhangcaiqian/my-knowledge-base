import time
import requests


class WeReadClient:
    BASE_URL = "https://weread.qq.com"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://weread.qq.com",
        "Referer": "https://weread.qq.com/",
    }
    REQUEST_INTERVAL = 1.0

    def __init__(self, cookie: str):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.headers["Cookie"] = cookie
        self._last_request_time = 0

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _check_response(self, resp, path: str):
        if resp.status_code == 401:
            try:
                err = resp.json()
                msg = err.get("errmsg", "未知原因")
            except Exception:
                msg = "未知原因"
            raise RuntimeError(
                f"微信读书认证失败（{msg}）\n"
                f"  请重新获取 Cookie：浏览器登录 weread.qq.com → F12 → Network → 复制 Cookie\n"
                f"  然后更新 config.json 中的 weread_cookie 字段"
            )

    def _get(self, path: str, params: dict = None, _retries: int = 3) -> dict:
        self._throttle()
        url = f"{self.BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=15)
        self._check_response(resp, path)
        if resp.status_code == 429 and _retries > 0:
            time.sleep(5)
            return self._get(path, params, _retries - 1)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") and data["errcode"] != 0:
            raise RuntimeError(f"微信读书 API 错误: {data.get('errmsg', '?')} (code={data['errcode']})")
        return data

    def _post(self, path: str, json_data: dict = None, _retries: int = 3) -> dict:
        self._throttle()
        url = f"{self.BASE_URL}{path}"
        resp = self.session.post(url, json=json_data, timeout=15)
        self._check_response(resp, path)
        if resp.status_code == 429 and _retries > 0:
            time.sleep(5)
            return self._post(path, json_data, _retries - 1)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") and data["errcode"] != 0:
            raise RuntimeError(f"微信读书 API 错误: {data.get('errmsg', '?')} (code={data['errcode']})")
        return data

    def get_shelf(self) -> list[dict]:
        """获取书架（含书籍详细信息）"""
        data = self._get("/web/shelf/sync", params={"synckey": 0, "teenmode": 0})
        return data.get("books", [])

    def get_book_info(self, book_id: str) -> dict:
        """获取书籍详情"""
        return self._get("/web/book/info", params={"bookId": book_id})

    def get_chapter_infos(self, book_id: str) -> list[dict]:
        """获取章节信息"""
        data = self._post("/web/book/chapterInfos", json_data={"bookIds": [book_id]})
        items = data.get("data", [])
        if items:
            return items[0].get("updated", [])
        return []

    def get_bookmarks(self, book_id: str) -> list[dict]:
        """获取用户划线（高亮）"""
        data = self._get("/web/book/bookmarklist", params={"bookId": book_id})
        return data.get("updated", [])

    def get_reviews(self, book_id: str) -> list[dict]:
        """获取用户想法/笔记"""
        data = self._get(
            "/web/review/list",
            params={
                "bookId": book_id,
                "listType": 11,
                "mine": 1,
                "synckey": 0,
            },
        )
        reviews = data.get("reviews", [])
        return [r.get("review", r) for r in reviews]

    def get_best_bookmarks(self, book_id: str) -> list[dict]:
        """获取热门划线"""
        data = self._get("/web/book/bestbookmarks", params={"bookId": book_id})
        return data.get("items", [])

    def get_read_info(self, book_id: str) -> dict:
        """获取阅读进度信息"""
        return self._get("/web/book/readinfo", params={"bookId": book_id, "readingDetail": 1})

    def search_books(self, keyword: str) -> list[dict]:
        """在书架中搜索书籍（本地过滤）"""
        shelf = self.get_shelf()
        keyword_lower = keyword.lower()
        matched = []
        for book in shelf:
            title = book.get("title", "").lower()
            author = book.get("author", "").lower()
            if keyword_lower in title or keyword_lower in author:
                matched.append(book)
        return matched
