from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ShowEvent:
    source_name: str
    title: str
    link: str
    booking_open_at: Optional[datetime]
    venue: str = ""

    @property
    def fingerprint(self) -> str:
        open_at = self.booking_open_at.isoformat() if self.booking_open_at else "none"
        return f"{self.source_name}|{self.title.strip()}|{self.link.strip()}|{open_at}"
