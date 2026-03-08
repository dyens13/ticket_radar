from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from dateutil import tz

from .config import AppConfig
from .repository import EventRepository
from .sources import MelonTicketAdapter, NolTicketAdapter
from .telegram_client import TelegramClient

logger = logging.getLogger(__name__)


class TicketAlarmService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.zone = tz.gettz(config.timezone)
        self.repo = EventRepository(config.state_path, config.retention_days)
        self.telegram = TelegramClient(config.telegram_token, config.telegram_chat_id)

    def run(self) -> None:
        schedules = self.config.raw.get("schedules", {})
        daily = schedules.get("daily_registration_check", {})
        daily_hour = int(daily.get("hour", 9))
        daily_minute = int(daily.get("minute", 0))
        poll_minutes = int(schedules.get("reminder_poll_interval_minutes", 10))

        scheduler = BlockingScheduler(timezone=self.config.timezone)
        scheduler.add_job(
            self.run_daily_registration_check,
            "cron",
            hour=daily_hour,
            minute=daily_minute,
            id="daily-registration-check",
            replace_existing=True,
        )
        scheduler.add_job(
            self.run_reminder_check,
            "interval",
            minutes=poll_minutes,
            id="booking-reminder-check",
            replace_existing=True,
        )

        logger.info("Scheduler started (daily=%02d:%02d, reminder interval=%dm)", daily_hour, daily_minute, poll_minutes)
        self.run_reminder_check()
        scheduler.start()

    def run_daily_registration_check(self) -> None:
        logger.info("Running daily registration check")
        now = datetime.now(tz=self.zone)
        self.repo.cleanup_expired(now)

        all_events = self._fetch_all_sources()
        matched = self._filter_by_keywords(all_events)

        new_items = self.repo.upsert_events(matched)
        if not new_items:
            logger.info("No new matched events found")
            return

        for item in new_items:
            message = self._format_new_event_message(item)
            self.telegram.send(message)

        logger.info("Sent %d new-event alerts", len(new_items))

    def run_reminder_check(self) -> None:
        logger.info("Running reminder check")
        now = datetime.now(tz=self.zone)
        self.repo.cleanup_expired(now)
        events = self.repo.list_events()

        reminders_cfg = self.config.raw.get("reminders", {})
        poll_minutes = int(self.config.raw.get("schedules", {}).get("reminder_poll_interval_minutes", 10))
        tolerance = timedelta(minutes=poll_minutes)

        sent_count = 0
        for event in events:
            booking_open_at_raw = event.get("booking_open_at")
            if not booking_open_at_raw:
                continue

            booking_open_at = datetime.fromisoformat(booking_open_at_raw)
            if booking_open_at.tzinfo is None:
                booking_open_at = booking_open_at.replace(tzinfo=self.zone)

            checks = self._build_reminder_schedule(event, booking_open_at, reminders_cfg)
            for reminder_key, remind_at, text in checks:
                if remind_at is None:
                    continue
                fingerprint = event["fingerprint"]
                if self.repo.is_reminder_sent(fingerprint, reminder_key):
                    continue
                if now < remind_at or now >= remind_at + tolerance:
                    continue

                self.telegram.send(text)
                self.repo.mark_reminder_sent(fingerprint, reminder_key)
                sent_count += 1

        if sent_count:
            logger.info("Sent %d reminder alerts", sent_count)

    def _fetch_all_sources(self):
        results = []
        for source_cfg in self.config.raw.get("sources", []):
            if not source_cfg.get("enabled", True):
                continue

            source_type = str(source_cfg.get("type", "")).strip().lower()
            adapter = self._build_adapter(source_type, source_cfg)
            if adapter is None:
                logger.warning("Unknown source type: %s", source_type)
                continue

            try:
                events = adapter.fetch_events()
                results.extend(events)
                logger.info("Fetched %d events from %s", len(events), source_type)
            except Exception as exc:
                logger.exception("Source fetch failed (%s): %s", source_type, exc)
        return results

    def _build_adapter(self, source_type: str, source_cfg: dict):
        if source_type == "nolticket":
            return NolTicketAdapter(self.config.timezone, source_cfg)
        if source_type == "melonticket":
            return MelonTicketAdapter(self.config.timezone, source_cfg)
        return None

    def _filter_by_keywords(self, events):
        keywords = [k.lower() for k in self.config.keywords]
        if not keywords:
            return events

        matched = []
        for event in events:
            hay = f"{event.title} {event.venue}".lower()
            if any(k in hay for k in keywords):
                matched.append(event)
        return matched

    def _format_new_event_message(self, row: dict) -> str:
        open_at = row.get("booking_open_at") or "미정"
        return (
            "[신규 공연 등록]\n"
            f"사이트: {row['source_name']}\n"
            f"제목: {row['title']}\n"
            f"장소: {row.get('venue') or '-'}\n"
            f"예매오픈: {open_at}\n"
            f"링크: {row['link']}"
        )

    def _build_reminder_schedule(self, event: dict, booking_open_at: datetime, reminders_cfg: dict):
        title = event["title"]
        source_name = event["source_name"]
        link = event["link"]

        checks = []

        one_day_cfg = reminders_cfg.get("one_day_before", {})
        if one_day_cfg.get("enabled", True):
            remind_at = (booking_open_at - timedelta(days=1)).replace(
                hour=int(one_day_cfg.get("send_at_hour", 20)),
                minute=int(one_day_cfg.get("send_at_minute", 0)),
                second=0,
                microsecond=0,
            )
            checks.append(
                (
                    "one_day_before",
                    remind_at,
                    (
                        "[예매 전날 알림]\n"
                        f"{title}\n"
                        f"사이트: {source_name}\n"
                        f"예매 오픈: {booking_open_at.strftime('%Y-%m-%d %H:%M')}\n"
                        f"링크: {link}"
                    ),
                )
            )

        morning_cfg = reminders_cfg.get("same_day_morning", {})
        if morning_cfg.get("enabled", True):
            remind_at = booking_open_at.replace(
                hour=int(morning_cfg.get("send_at_hour", 8)),
                minute=int(morning_cfg.get("send_at_minute", 0)),
                second=0,
                microsecond=0,
            )
            checks.append(
                (
                    "same_day_morning",
                    remind_at,
                    (
                        "[예매 당일 아침 알림]\n"
                        f"{title}\n"
                        f"사이트: {source_name}\n"
                        f"예매 오픈: {booking_open_at.strftime('%Y-%m-%d %H:%M')}\n"
                        f"링크: {link}"
                    ),
                )
            )

        one_hour_cfg = reminders_cfg.get("one_hour_before", {})
        if one_hour_cfg.get("enabled", True):
            remind_at = booking_open_at - timedelta(hours=1)
            checks.append(
                (
                    "one_hour_before",
                    remind_at,
                    (
                        "[예매 1시간 전 알림]\n"
                        f"{title}\n"
                        f"사이트: {source_name}\n"
                        f"예매 오픈: {booking_open_at.strftime('%Y-%m-%d %H:%M')}\n"
                        f"링크: {link}"
                    ),
                )
            )

        return checks
