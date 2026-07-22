"""Publishes completed pipeline batches to existing backend consumers."""

from datetime import datetime
import logging
from typing import Iterable

import aiohttp

from models.commodity import CommodityRecord


class BackendNotifier:
    """Notify backend push and WebSocket hooks after ETL output is complete."""

    def __init__(self, backend_url: str, logger: logging.Logger):
        self.backend_url = backend_url.rstrip("/")
        self.logger = logger

    async def publish(self, records: Iterable[CommodityRecord]) -> None:
        payload = {"items": [self._serialize(record) for record in records]}
        if not payload["items"]:
            return

        async with aiohttp.ClientSession() as session:
            for path in ("/api/internal/notify", "/api/internal/broadcast"):
                try:
                    async with session.post(f"{self.backend_url}{path}", json=payload, timeout=10) as response:
                        if response.status >= 400:
                            self.logger.warning("Backend notify hook failed: %s %s", path, response.status)
                except Exception as exc:
                    self.logger.warning("Backend notify hook failed: %s %s", path, exc)

    @staticmethod
    def _serialize(record: CommodityRecord) -> dict:
        data = record.to_mongo_document()
        for key, value in list(data.items()):
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
