from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import yaml

from .models import ShowEvent


class EventRepository:
    def __init__(self, state_path: Path, retention_days: int = 3):
        self.state_path = state_path
        self.retention_days = retention_days
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {"events": {}, "sent_reminders": {}}

        with open(self.state_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            return {"events": {}, "sent_reminders": {}}

        return {
            "events": data.get("events", {}) or {},
            "sent_reminders": data.get("sent_reminders", {}) or {},
        }

    def _save_state(self) -> None:
        with open(self.state_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._state, f, allow_unicode=True, sort_keys=True)

    def upsert_events(self, events: Iterable[ShowEvent]) -> list[dict]:
        now_iso = datetime.utcnow().isoformat()
        new_items: list[dict] = []

        for event in events:
            key = event.fingerprint
            payload = {
                "fingerprint": key,
                "source_name": event.source_name,
                "title": event.title,
                "link": event.link,
                "venue": event.venue,
                "booking_open_at": event.booking_open_at.isoformat() if event.booking_open_at else None,
                "last_seen_at": now_iso,
            }
            if key not in self._state["events"]:
                self._state["events"][key] = payload
                new_items.append(payload)
            else:
                self._state["events"][key]["last_seen_at"] = now_iso

        self._save_state()
        return new_items

    def list_events(self) -> list[dict]:
        return list(self._state["events"].values())

    def is_reminder_sent(self, fingerprint: str, reminder_key: str) -> bool:
        token = self._reminder_token(fingerprint, reminder_key)
        return token in self._state["sent_reminders"]

    def mark_reminder_sent(self, fingerprint: str, reminder_key: str) -> None:
        token = self._reminder_token(fingerprint, reminder_key)
        self._state["sent_reminders"][token] = datetime.utcnow().isoformat()
        self._save_state()

    def cleanup_expired(self, now: datetime) -> None:
        threshold = now - timedelta(days=self.retention_days)

        active_events: dict[str, dict] = {}
        for key, event in self._state["events"].items():
            raw_open = event.get("booking_open_at")
            raw_seen = event.get("last_seen_at")

            open_at = self._parse_iso(raw_open, now)
            seen_at = self._parse_iso(raw_seen, now)

            if open_at is not None:
                if open_at >= threshold:
                    active_events[key] = event
                continue

            if seen_at is not None and seen_at >= threshold:
                active_events[key] = event

        self._state["events"] = active_events

        valid_tokens = {
            self._reminder_token(k, rk)
            for k in active_events
            for rk in ("one_day_before", "same_day_morning", "one_hour_before")
        }
        self._state["sent_reminders"] = {
            token: sent_at
            for token, sent_at in self._state["sent_reminders"].items()
            if token in valid_tokens
        }
        self._save_state()

    @staticmethod
    def _parse_iso(raw: str | None, now: datetime) -> datetime | None:
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if dt.tzinfo is None and now.tzinfo is not None:
            dt = dt.replace(tzinfo=now.tzinfo)
        return dt

    @staticmethod
    def _reminder_token(fingerprint: str, reminder_key: str) -> str:
        return f"{fingerprint}::{reminder_key}"
