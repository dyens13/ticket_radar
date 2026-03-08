from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..models import ShowEvent
from .base import SourceAdapter
from .parsing import parse_korean_datetime


class MelonTicketAdapter(SourceAdapter):
    LIST_URL = "https://ticket.melon.com/csoon/index.htm"
    DATE_PREFIX_RE = re.compile(r"^\[오픈\]\s*\d{2}\.\d{2}\.\d{2}\([^)]*\)\s*")

    def __init__(self, timezone_name: str, source_cfg: dict | None = None):
        self.timezone_name = timezone_name
        self.source_cfg = source_cfg or {}
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def fetch_events(self) -> list[ShowEvent]:
        url = self.source_cfg.get("url", self.LIST_URL)
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        events: list[ShowEvent] = []

        for link in soup.select("a[href*='csoon/detail.htm']"):
            raw_title = link.get_text(" ", strip=True)
            href = link.get("href", "").strip()
            if not raw_title or not href:
                continue

            full_link = urljoin(url, href)
            detail_text = self._fetch_detail_text(full_link)
            open_at = parse_korean_datetime(detail_text or raw_title, self.timezone_name)
            title = self.DATE_PREFIX_RE.sub("", raw_title)

            events.append(
                ShowEvent(
                    source_name="Melon Ticket",
                    title=title,
                    link=full_link,
                    booking_open_at=open_at,
                )
            )

        return self._dedupe(events)

    def _fetch_detail_text(self, detail_url: str) -> str:
        try:
            resp = self.session.get(detail_url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            return soup.get_text(" ", strip=True)
        except Exception:
            return ""

    def _dedupe(self, events: list[ShowEvent]) -> list[ShowEvent]:
        seen: set[str] = set()
        result: list[ShowEvent] = []
        for event in events:
            if event.link in seen:
                continue
            seen.add(event.link)
            result.append(event)
        return result
