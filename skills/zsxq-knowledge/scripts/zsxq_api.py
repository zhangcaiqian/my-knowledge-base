import time
import requests


class ZsxqClient:
    BASE_URL = "https://api.zsxq.com"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Origin": "https://wx.zsxq.com",
        "Referer": "https://wx.zsxq.com/",
    }
    REQUEST_INTERVAL = 1.5  # 请求间隔（秒），避免触发限流

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

    def _get(self, path: str, params: dict = None, _retries: int = 3) -> dict:
        self._throttle()
        url = f"{self.BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("succeeded"):
            code = data.get("code", "?")
            if code == 1059 and _retries > 0:
                time.sleep(3)
                return self._get(path, params, _retries - 1)
            raise RuntimeError(f"API 错误 (code={code}): {path}")
        return data["resp_data"]

    def get_groups(self) -> list[dict]:
        return self._get("/v2/groups").get("groups", [])

    def get_topics(
        self,
        group_id: str,
        scope: str = "digests",
        count: int = 10,
        end_time: str = None,
    ) -> tuple[list[dict], str | None]:
        """返回 (topics, next_end_time)"""
        params = {"scope": scope, "count": count}
        if end_time:
            params["end_time"] = end_time
        data = self._get(f"/v2/groups/{group_id}/topics", params)
        topics = data.get("topics", [])
        next_time = topics[-1]["create_time"] if topics else None
        return topics, next_time

    def get_hashtag_topics(
        self, hashtag_id: str, count: int = 10, end_time: str = None
    ) -> tuple[list[dict], str | None]:
        params = {"count": count}
        if end_time:
            params["end_time"] = end_time
        data = self._get(f"/v2/hashtags/{hashtag_id}/topics", params)
        topics = data.get("topics", [])
        next_time = topics[-1]["create_time"] if topics else None
        return topics, next_time

    def get_menus(self, group_id: str) -> list[dict]:
        return self._get(f"/v2/groups/{group_id}/menus").get("menus", [])

    def get_hashtags(self, group_id: str) -> list[dict]:
        return self._get(f"/v2/groups/{group_id}/hashtags").get("hashtags", [])

    def get_file_download_url(self, file_id: str) -> str:
        data = self._get(f"/v2/files/{file_id}/download_url")
        return data.get("download_url", "")

    def download_file(self, file_id: str, save_path: str) -> str:
        """下载文件到指定路径，返回实际保存路径"""
        url = self.get_file_download_url(file_id)
        if not url:
            raise RuntimeError(f"无法获取文件下载链接: {file_id}")
        self._throttle()
        resp = self.session.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        from pathlib import Path

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return save_path
