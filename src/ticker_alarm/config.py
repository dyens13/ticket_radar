from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    raw: dict[str, Any]

    @property
    def telegram_token(self) -> str:
        return self.raw["telegram"]["bot_token"]

    @property
    def telegram_chat_id(self) -> str:
        return str(self.raw["telegram"]["chat_id"])

    @property
    def timezone(self) -> str:
        return self.raw.get("app", {}).get("timezone", "Asia/Seoul")

    @property
    def state_path(self) -> Path:
        return Path(self.raw.get("app", {}).get("state_path", "./data/state.yaml"))

    @property
    def retention_days(self) -> int:
        return int(self.raw.get("app", {}).get("retention_days", 3))

    @property
    def keywords(self) -> list[str]:
        return [k.strip() for k in self.raw.get("keywords", []) if k and k.strip()]


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("config root must be a mapping")
    return AppConfig(raw=data)
