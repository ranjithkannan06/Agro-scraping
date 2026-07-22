"""Build aggregate analytics from normalized pipeline output."""

from collections import Counter
from datetime import date
from statistics import mean
from typing import Iterable, List

from models.commodity import CommodityRecord


class AnalyticsEngine:
    """Generate totals, deltas, and price statistics for a pipeline run."""

    def generate(self, records: Iterable[CommodityRecord], deltas: dict) -> dict:
        data = list(records)
        prices = [record.modal_price for record in data]
        today = date.today().isoformat()
        commodity_counts = Counter(record.commodity for record in data)
        district_counts = Counter(record.district for record in data)

        return {
            "totals": {
                "commodities": len({record.commodity for record in data}),
                "districts": len({record.district for record in data}),
                "markets": len({record.market for record in data}),
                "records": len(data),
                "today_records": len([record for record in data if record.date == today]),
            },
            "pipeline_deltas": deltas,
            "price_stats": {
                "average": round(mean(prices), 2) if prices else 0,
                "high": max(prices) if prices else 0,
                "low": min(prices) if prices else 0,
            },
            "most_active": {
                "commodity": commodity_counts.most_common(1)[0][0] if commodity_counts else None,
                "district": district_counts.most_common(1)[0][0] if district_counts else None,
            },
        }
