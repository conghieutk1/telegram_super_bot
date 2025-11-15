import logging
from typing import Any, Dict, List, Optional, Tuple

from util import http_get_json


class NewsService:
    """
    Lấy tin tức tổng hợp (NewsAPI), lọc chỉ tin mới nếu cấu hình only_new=true.
    """

    def __init__(self, config: Dict[str, Any], secrets: Dict[str, Any]) -> None:
        self.config = config
        self.api_key = secrets.get("news_api_key")
        self.logger = logging.getLogger(self.__class__.__name__)

        self.enabled = config.get("enabled", True)
        self.api_base = config.get("api_base", "https://newsapi.org/v2")
        self.country = config.get("country", "vn")
        self.category = config.get("category", "general")
        self.page_size = int(config.get("page_size", 5))
        self.only_new = bool(config.get("only_new", True))

    def is_configured(self) -> bool:
        return self.enabled and self.api_key is not None

    def fetch_latest(self) -> Optional[Dict[str, Any]]:
        url = f"{self.api_base}/top-headlines"
        params = {
            "country": self.country,
            "category": self.category,
            "pageSize": self.page_size,
            "apiKey": self.api_key,
        }
        return http_get_json(url, params=params)

    @staticmethod
    def _filter_new_articles(
        articles: List[Dict[str, Any]], last_published_at: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Lọc ra những bài có publishedAt > last_published_at.
        Vì publishedAt là ISO 8601 nên so sánh string được (lexico ~ time).
        """
        if not articles:
            return [], last_published_at

        if not last_published_at:
            # lần đầu: gửi hết và lấy timestamp tối đa
            new_last = max(
                (a.get("publishedAt") for a in articles if a.get("publishedAt")),
                default=None,
            )
            return articles, new_last

        filtered: List[Dict[str, Any]] = []
        new_last = last_published_at

        for a in articles:
            ts = a.get("publishedAt")
            if not ts:
                continue
            if ts > last_published_at:
                filtered.append(a)
                if ts > new_last:
                    new_last = ts

        return filtered, new_last

    def build_summary(self, state: Dict[str, Any]) -> str:
        if not self.is_configured():
            self.logger.warning("NewsService is not properly configured.")
            return ""

        data = self.fetch_latest()
        if not data:
            return "📰 *Tin tức*: không lấy được dữ liệu."

        status = data.get("status")
        if status != "ok":
            self.logger.warning("NewsAPI status not ok: %s", status)
            return "📰 *Tin tức*: lỗi từ NewsAPI."

        articles = data.get("articles", [])
        if not articles:
            return "📰 *Tin tức*: hiện không có bài mới."

        last_published_at = state.get("news_last_published_at")

        if self.only_new:
            articles, new_last = self._filter_new_articles(articles, last_published_at)
            if not articles:
                # Không có tin mới hơn lần trước -> không gửi gì
                return ""
            if new_last:
                state["news_last_published_at"] = new_last

        lines = ["📰 *Tin tức mới*"]
        for a in articles[: self.page_size]:
            title = a.get("title") or "(Không tiêu đề)"
            url = a.get("url") or ""
            source_name = (a.get("source") or {}).get("name") or ""
            line = f"- [{title}]({url})" if url else f"- {title}"
            if source_name:
                line += f" _({source_name})_"
            lines.append(line)

        return "\n".join(lines)
