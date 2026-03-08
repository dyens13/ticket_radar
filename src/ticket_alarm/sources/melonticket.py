from __future__ import annotations

import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..models import ShowEvent
from .base import SourceAdapter
from .parsing import parse_korean_datetime

logger = logging.getLogger(__name__)


class MelonTicketAdapter(SourceAdapter):
    LIST_URL = "https://ticket.melon.com/csoon/index.htm"
    LIST_AJAX_URL = "https://ticket.melon.com/csoon/ajax/listTicketOpen.htm"
    PERFORMANCE_URL = "https://ticket.melon.com/performance/index.htm?prodId={prod_id}"

    DATE_PREFIX_RE = re.compile(r"^\[오픈\]\s*\d{2}\.\d{2}\.\d{2}\([^)]*\)\s*")
    DATE_SUFFIX_RE = re.compile(r"\s*\[오픈\]\s*\d{2}\.\d{2}\.\d{2}\([^)]*\)\s*$")
    SCHEDULE_SUFFIX_RE = re.compile(r"\s*오픈일정\s*보기\s*>\s*$")
    PROD_ID_RE = re.compile(r"bannerLanding\(\s*['\"]TD['\"]\s*,\s*['\"](\d+)['\"]\s*\)")
    BLOCKED_STATUSES = {423, 429, 500, 502, 503, 504}

    def __init__(self, timezone_name: str, source_cfg: dict | None = None):
        self.timezone_name = timezone_name
        self.source_cfg = source_cfg or {}
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
            }
        )
        self._venue_cache: dict[str, str] = {}
        self.request_retries = int(self.source_cfg.get("request_retries", 4))
        self.retry_backoff_seconds = float(self.source_cfg.get("retry_backoff_seconds", 1.2))

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

                detail_text, prod_id = self._fetch_detail_text_and_prod_id(full_link)
                open_at = parse_korean_datetime(detail_text or raw_title, self.timezone_name)
                title = self._normalize_title(raw_title)
                venue = self._fetch_venue_by_prod_id(prod_id) if prod_id else ""
                if not title:
                    continue

                events.append(
                    ShowEvent(
                        source_name="Melon Ticket",
                        title=title,
                        link=full_link,
                        booking_open_at=open_at,
                        venue=venue,
                    )
                )
                page_added += 1

            if page_added == 0:
                break

        return events

    def _load_form_params(self, url: str) -> dict[str, str]:
        default_params = {"orderType": "0", "pageIndex": "1", "schGcode": "GENRE_ALL", "schText": ""}

        # Warm up cookie/session first; this sometimes reduces 423 responses.
        try:
            self._request_with_retries("GET", "https://ticket.melon.com/", timeout=20)
        except Exception:
            pass

        resp = self._request_with_retries("GET", url, timeout=20)
        if resp is None or resp.status_code >= 400:
            code = resp.status_code if resp is not None else "N/A"
            logger.warning("Melon index fetch unavailable (status=%s). Fallback to default form params.", code)
            return default_params

        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.select_one("form#sForm")
        if form is None:
            logger.warning("Melon index loaded but form#sForm not found. Using default form params.")
            return default_params

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

        resp = self._request_with_retries(
            "POST",
            self.LIST_AJAX_URL,
            data=data,
            timeout=20,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": url,
                "Origin": "https://ticket.melon.com",
                "Accept": "*/*",
            },
        )

        if resp is None or resp.status_code >= 400:
            code = resp.status_code if resp is not None else "N/A"
            logger.warning("Melon list fragment unavailable (pageIndex=%s, status=%s)", page_idx, code)
            return ""
        return resp.text

    def _fetch_detail_text_and_prod_id(self, detail_url: str) -> tuple[str, str | None]:
        try:
            resp = self._request_with_retries("GET", detail_url, timeout=20)
            if resp is None or resp.status_code >= 400:
                return "", None

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)

            m = self.PROD_ID_RE.search(html)
            prod_id = m.group(1) if m else None
            return text, prod_id
        except Exception:
            return "", None

    def _fetch_venue_by_prod_id(self, prod_id: str) -> str:
        if prod_id in self._venue_cache:
            return self._venue_cache[prod_id]

        venue = ""
        try:
            url = self.PERFORMANCE_URL.format(prod_id=prod_id)
            resp = self._request_with_retries("GET", url, timeout=20)
            if resp is None or resp.status_code >= 400:
                self._venue_cache[prod_id] = ""
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")

            place = self._clean_text(self._first_text(soup, ["span.place", "p.place", "li.place"]))
            location = self._clean_text(self._first_text(soup, ["span.location", "p.location", "li.location"]))

            if place and location and location not in place:
                venue = f"{place} ({location})"
            else:
                venue = place or location
        except Exception:
            venue = ""

        self._venue_cache[prod_id] = venue
        return venue

    def _request_with_retries(self, method: str, url: str, **kwargs) -> requests.Response | None:
        last_resp: requests.Response | None = None

        for attempt in range(1, self.request_retries + 1):
            try:
                resp = self.session.request(method, url, **kwargs)
                last_resp = resp

                if resp.status_code not in self.BLOCKED_STATUSES:
                    return resp

                logger.warning(
                    "Melon request blocked (status=%s, attempt=%s/%s): %s",
                    resp.status_code,
                    attempt,
                    self.request_retries,
                    url,
                )
            except requests.RequestException as exc:
                logger.warning(
                    "Melon request error (attempt=%s/%s): %s (%s)",
                    attempt,
                    self.request_retries,
                    url,
                    exc,
                )

            if attempt < self.request_retries:
                sleep_seconds = self.retry_backoff_seconds * attempt
                time.sleep(sleep_seconds)

        return last_resp

    @staticmethod
    def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(" ", strip=True)
                if txt:
                    return txt
        return ""

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()

    def _normalize_title(self, raw_title: str) -> str:
        title = self.DATE_PREFIX_RE.sub("", raw_title)
        title = self.DATE_SUFFIX_RE.sub("", title)
        title = self.SCHEDULE_SUFFIX_RE.sub("", title)
        return re.sub(r"\s+", " ", title).strip()

    @staticmethod
    def _to_page_index(page_no: int) -> int:
        # Melon pagination uses goPage("1"), goPage("11"), goPage("21")...
        return 1 + (page_no - 1) * 10
