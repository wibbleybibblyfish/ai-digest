from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime

from ai_digest.models import RawItem

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, since: datetime) -> list[RawItem]:
        ...

    async def safe_collect(self, since: datetime) -> list[RawItem]:
        try:
            items = await self.collect(since)
            logger.info(f"{self.__class__.__name__}: collected {len(items)} items")
            return items
        except Exception as e:
            logger.warning(f"{self.__class__.__name__} failed: {e}")
            return []
