from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ShowEvent


class SourceAdapter(ABC):
    @abstractmethod
    def fetch_events(self) -> list[ShowEvent]:
        raise NotImplementedError
