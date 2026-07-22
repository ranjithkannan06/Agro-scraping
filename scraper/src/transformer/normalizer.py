"""Transforms raw commodity records into canonical pipeline records."""

from datetime import datetime
from typing import Iterable, List

from models.commodity import CommodityRecord, RawCommodity
from transformer.cleaner import parse_date, parse_int_price, title_name


class CommodityTransformer:
    """Normalize dates, prices, and naming conventions."""

    def transform(self, records: Iterable[RawCommodity]) -> List[CommodityRecord]:
        transformed: List[CommodityRecord] = []
        for record in records:
            modal_price = parse_int_price(record.modal_price)
            normalized_date = parse_date(record.date)
            if modal_price is None or normalized_date is None:
                continue

            scraped_time = record.scraped_time
            if not isinstance(scraped_time, datetime):
                scraped_time = datetime.utcnow()

            transformed.append(
                CommodityRecord(
                    commodity=title_name(record.commodity),
                    category=title_name(record.category or "Other"),
                    district=title_name(record.district or "Tamilnadu"),
                    market=title_name(record.market),
                    variety=title_name(record.variety),
                    minimum_price=parse_int_price(record.minimum_price),
                    maximum_price=parse_int_price(record.maximum_price),
                    modal_price=modal_price,
                    date=normalized_date,
                    source_url=str(record.source_url or ""),
                    scraped_time=scraped_time,
                    unit=str(record.unit or "Kg").strip() or "Kg",
                )
            )
        return transformed
