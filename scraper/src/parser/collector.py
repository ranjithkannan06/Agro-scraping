"""Playwright collection adapter that returns raw records without persistence."""

from datetime import datetime
from typing import List

from models.commodity import RawCommodity
from scrapers.vayal_scraper import scrape_vayal_flowers


class VayalCollector:
    """Collect raw commodity rows from Vayal Agro using the legacy Playwright traversal."""

    def __init__(self, source_url: str, concurrent_tabs: int):
        self.source_url = source_url
        self.concurrent_tabs = concurrent_tabs

    async def collect(self, force: bool = False) -> List[RawCommodity]:
        legacy_records = await scrape_vayal_flowers(
            force=force,
            source_url=self.source_url,
            concurrent_tabs=self.concurrent_tabs,
        )
        return [self._from_legacy(record) for record in legacy_records]

    @staticmethod
    def _from_legacy(record: dict) -> RawCommodity:
        return RawCommodity(
            commodity=record.get("commodity_name", ""),
            category=record.get("category", ""),
            district=record.get("district", ""),
            market=record.get("market_name", ""),
            variety=record.get("variety", ""),
            minimum_price=record.get("price_min"),
            maximum_price=record.get("price_max"),
            modal_price=record.get("price_modal", record.get("price")),
            date=record.get("date_scraped", ""),
            source_url=record.get("source_url", ""),
            scraped_time=record.get("scraped_at", datetime.utcnow()),
            unit=record.get("unit", "Kg"),
        )
