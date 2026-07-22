"""MongoDB repository and batch loader for normalized commodity records."""

import asyncio
import logging
from typing import Iterable, List, Set

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, UpdateOne

from database.repository import PriceRepository, RecordKey
from models.commodity import CommodityRecord


class MongoPriceRepository(PriceRepository):
    """Checks existing records and loads new data using bulk writes."""

    def __init__(self, mongodb_url: str, database_name: str, logger: logging.Logger):
        self.client = AsyncIOMotorClient(mongodb_url)
        self.db = self.client[database_name]
        self.collection = self.db["market_prices"]
        self.logger = logger

    async def ensure_indexes(self) -> None:
        indexes = [
            IndexModel(
                [("commodity_name", 1), ("district", 1), ("market_name", 1), ("date_scraped", 1)],
                unique=True,
                name="etl_unique_crop_price_index",
            ),
            IndexModel([("date_scraped", -1)], name="etl_date_index"),
            IndexModel([("commodity_name", 1)], name="etl_commodity_index"),
            IndexModel([("district", 1), ("market_name", 1)], name="etl_market_lookup_index"),
        ]
        await self.collection.create_indexes(indexes)

    async def existing_keys(self, records: Iterable[CommodityRecord]) -> Set[RecordKey]:
        keys = {record.key for record in records}
        if not keys:
            return set()

        existing: Set[RecordKey] = set()
        for commodity, district, market, date in keys:
            doc = await self.collection.find_one(
                {
                    "commodity_name": commodity,
                    "district": district,
                    "market_name": market,
                    "date_scraped": date,
                },
                {"_id": 0, "commodity_name": 1, "district": 1, "market_name": 1, "date_scraped": 1},
            )
            if doc:
                existing.add((commodity, district, market, date))
        return existing

    async def bulk_upsert(self, records: Iterable[CommodityRecord], retries: int = 3) -> int:
        docs = [record.to_mongo_document() for record in records]
        if not docs:
            return 0

        operations: List[UpdateOne] = [
            UpdateOne(
                {
                    "commodity_name": doc["commodity_name"],
                    "district": doc["district"],
                    "market_name": doc["market_name"],
                    "date_scraped": doc["date_scraped"],
                },
                {"$set": doc},
                upsert=True,
            )
            for doc in docs
        ]

        for attempt in range(1, retries + 1):
            try:
                result = await self.collection.bulk_write(operations, ordered=False)
                return result.upserted_count + result.modified_count
            except Exception:
                if attempt == retries:
                    raise
                await asyncio.sleep(2**attempt)
        return 0

    async def close(self) -> None:
        self.client.close()
