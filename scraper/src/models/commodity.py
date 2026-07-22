"""Typed commodity records passed between scraper ETL stages."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RawCommodity:
    """Untrusted fields exactly as collected from the source page."""

    commodity: str
    category: str
    district: str
    market: str
    variety: str
    minimum_price: Any
    maximum_price: Any
    modal_price: Any
    date: Any
    source_url: str
    scraped_time: Any
    unit: str = "Kg"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommodityRecord:
    """Normalized record shape used by loaders, reports, and dashboard datasets."""

    commodity: str
    category: str
    district: str
    market: str
    variety: str
    minimum_price: Optional[int]
    maximum_price: Optional[int]
    modal_price: int
    date: str
    source_url: str
    scraped_time: datetime
    unit: str = "Kg"

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.commodity, self.district, self.market, self.date)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["scraped_time"] = self.scraped_time.isoformat()
        return data

    def to_mongo_document(self) -> Dict[str, Any]:
        """Map canonical ETL fields to the existing MongoDB/dashboard schema."""
        return {
            "commodity_name": self.commodity,
            "category": self.category,
            "district": self.district,
            "market_name": self.market,
            "variety": self.variety,
            "price_min": self.minimum_price,
            "price_max": self.maximum_price,
            "price": self.modal_price,
            "price_modal": self.modal_price,
            "unit": self.unit,
            "date_scraped": self.date,
            "source_url": self.source_url,
            "scraped_at": self.scraped_time,
        }
