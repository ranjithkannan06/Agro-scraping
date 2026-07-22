"""Deduplicates transformed records against the configured repository."""

from typing import Iterable, List, Tuple

from database.repository import PriceRepository
from models.commodity import CommodityRecord
from models.statistics import DeduplicationReport


class DeduplicationEngine:
    """Separate new records from records already present in durable storage."""

    def __init__(self, repository: PriceRepository):
        self.repository = repository

    async def filter_new(
        self,
        records: Iterable[CommodityRecord],
    ) -> Tuple[List[CommodityRecord], DeduplicationReport]:
        data = list(records)
        existing = await self.repository.existing_keys(data)
        new_records: List[CommodityRecord] = []
        duplicate_records = []

        for record in data:
            if record.key in existing:
                duplicate_records.append(record.to_dict())
            else:
                new_records.append(record)

        return new_records, DeduplicationReport(
            total=len(data),
            new=len(new_records),
            duplicate=len(duplicate_records),
            duplicates=duplicate_records,
        )
