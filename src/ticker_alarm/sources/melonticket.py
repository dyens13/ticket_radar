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
    LIST_AJAX_URL = "https://ticket.melon.com/csoon/ajax/listTicketOpen.htm"
    DATE_PREFIX_RE = re.compile(r"^\[오픈\]\s*\d{2}\.\d{2}\.\d{2}\([^)]*\)\s*")
    DATE_SUFFIX_RE = re.compile(r"\s*\[오픈\]\s*\d{2}\.\d{2}\.\d{2}\([^)]*\)\s*$")
    SCHEDULE_SUFFIX_RE = re.compile(r"\s*오픈일정\s*보기\s*>\s*$")

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
        max_pages = int(self.source_cfg.get("max_pages", 10))
        url = self.source_cfg.get("url", self.LIST_URL)

        form_params = self._load_form_params(url)

        events: list[ShowEvent] = []
        seen_links: set[str] = set()

        for page_no in range(1, max_pages + 1):
            page_index = self._to_page_index(page_no)
            html = self._fetch_list_fragment(url, form_params, page_index)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            page_added = 0
            for link in soup.select("a[href*='detail.htm?csoonId='], a[href*='csoon/detail.htm']"):
                raw_title = link.get_text(" ", strip=True)
                href = link.get("href", "").strip()
                if not raw_title or not href:
                    continue

                full_link = urljoin(url, href)
                if full_link in seen_links:
                    continue
                seen_links.add(full_link)

                detail_text = self._fetch_detail_text(full_link)
                open_at = parse_korean_datetime(detail_text or raw_title, self.timezone_name)
                title = self._normalize_title(raw_title)
                if not title:
                    continue

                events.append(
                    ShowEvent(
                        source_name="Melon Ticket",
                        title=title,
                        link=full_link,
                        booking_open_at=open_at,
                    )
                )
                page_added += 1

            if page_added == 0:
                break

        return events

    def _load_form_params(self, url: str) -> dict[str, str]:
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.select_one("form#sForm")
        if form is None:
            return {"orderType": "0", "pageIndex": "1", "schGcode": "GENRE_ALL", "schText": ""}

        params: dict[str, str] = {}
        for el in form.select("input[name], select[name], textarea[name]"):
            name = el.get("name", "").strip()
            if not name:
                continue

            value = el.get("value", "")
            if el.name == "select":
                selected = el.select_one("option[selected]") or el.select_one("option")
                value = selected.get("value", "") if selected else ""

            params[name] = str(value)

        params.setdefault("orderType", "0")
        params.setdefault("pageIndex", "1")
        params.setdefault("schText", "")
        params.setdefault("schGcode", "GENRE_ALL")
        return params

    def _fetch_list_fragment(self, url: str, form_params: dict[str, str], page_idx: int) -> str:
        data = dict(form_params)
        data["pageIndex"] = str(page_idx)

        resp = self.session.post(
            self.LIST_AJAX_URL,
            data=data,
            timeout=20,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": url,
                "Origin": "https://ticket.melon.com",
            },
        )
        if resp.status_code >= 400:
            return ""
        return resp.text

    def _fetch_detail_text(self, detail_url: str) -> str:
        try:
            resp = self.session.get(detail_url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            return soup.get_text(" ", strip=True)
        except Exception:
            return ""

    def _normalize_title(self, raw_title: str) -> str:
        title = self.DATE_PREFIX_RE.sub("", raw_title)
        title = self.DATE_SUFFIX_RE.sub("", title)
        title = self.SCHEDULE_SUFFIX_RE.sub("", title)
        return re.sub(r"\s+", " ", title).strip()

    @staticmethod
    def _to_page_index(page_no: int) -> int:
        # Melon pagination uses goPage("1"), goPage("11"), goPage("21")...
        return 1 + (page_no - 1) * 10
