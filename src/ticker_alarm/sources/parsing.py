from __future__ import annotations

import re
from datetime import datetime

from dateutil import tz

DATE_RE = re.compile(
    r"(?P<year>\d{2,4})[./-]\s*(?P<month>\d{1,2})[./-]\s*(?P<day>\d{1,2})"
    r"(?:\([^)]*\))?"
    r"(?:\s*(?P<hour>\d{1,2})[:시]\s*(?P<minute>\d{1,2})?)?"
)


def parse_korean_datetime(text: str, timezone_name: str, default_hour: int = 10, default_minute: int = 0) -> datetime | None:
    match = DATE_RE.search(text)
    if not match:
        return None

    year = int(match.group("year"))
    if year < 100:
        year += 2000
    month = int(match.group("month"))
    day = int(match.group("day"))

    if match.group("hour") is None:
        hour = default_hour
        minute = default_minute
    else:
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)

    zone = tz.gettz(timezone_name)
    return datetime(year, month, day, hour, minute, tzinfo=zone)
