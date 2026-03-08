from __future__ import annotations

from urllib.parse import urljoin

import requests

from ..models import ShowEvent
from .base import SourceAdapter
from .parsing import parse_korean_datetime


class NolTicketAdapter(SourceAdapter):
    LIST_URL = "https://tickets.interpark.com/contents/notice"
    LIST_API_URL = "https://tickets.interpark.com/api/open-notice/notice-list"

    def __init__(self, timezone_name: str, source_cfg: dict | None = None):
        self.timezone_name = timezone_name
        self.source_cfg = source_cfg or {}
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
            }
        )

    def fetch_events(self) -> list[ShowEvent]:
        page_size = int(self.source_cfg.get("page_size", 25))
        max_pages = int(self.source_cfg.get("max_pages", 20))

        events: list[ShowEvent] = []
        for page_idx in range(max_pages):
            offset = page_idx * page_size
            rows = self._fetch_notice_page(page_size=page_size, offset=offset)
            if not rows:
                break

            for row in rows:
                notice_id = row.get("noticeId")
                title = str(row.get("title", "")).strip()
                if not title or notice_id is None:
                    continue

                detail_link = urljoin(self.LIST_URL, f"/contents/notice/detail/{notice_id}")
                venue = str(row.get("venueName", "")).strip()

                open_at = None
                if not row.get("isGeneralLater", False):
                    open_at = parse_korean_datetime(str(row.get("openDateStr", "")), self.timezone_name)

                events.append(
                    ShowEvent(
                        source_name="NOL Ticket",
                        title=title,
                        link=detail_link,
                        booking_open_at=open_at,
                        venue=venue,
                    )
                )

            if len(rows) < page_size:
                break

        return self._dedupe(events)

    def _fetch_notice_page(self, page_size: int, offset: int) -> list[dict]:
        params = {
            "sorting": "OPEN_ASC",
            "goodsGenre": "ALL",
            "goodsRegion": "ALL",
            "pageSize": page_size,
            "offset": offset,
        }
        resp = self.session.get(self.LIST_API_URL, params=params, timeout=20)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def _dedupe(self, events: list[ShowEvent]) -> list[ShowEvent]:
        seen: set[str] = set()
        result: list[ShowEvent] = []
        for event in events:
            if event.link in seen:
                continue
            seen.add(event.link)
            result.append(event)
        return result
