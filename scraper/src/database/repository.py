"""Repository interface and MongoDB-backed duplicate lookup."""

from abc import ABC, abstractmethod
from typing import Iterable, Set, Tuple

from models.commodity import CommodityRecord

RecordKey = Tuple[str, str, str, str]


class PriceRepository(ABC):
    @abstractmethod
    async def existing_keys(self, records: Iterable[CommodityRecord]) -> Set[RecordKey]:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
