"""Generates dashboard-only JSON datasets from normalized records."""

from collections import defaultdict
from pathlib import Path
from typing import Iterable, List

from analytics.reports import write_report
from models.commodity import CommodityRecord


class DashboardDatasetGenerator:
    """Write all JSON files consumed by the web dashboard layer."""

    def generate(self, records: Iterable[CommodityRecord], analytics: dict, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        data = sorted(list(records), key=lambda r: (r.date, r.commodity), reverse=True)

        latest_by_key = {}
        history = defaultdict(list)
        commodity_summary = defaultdict(lambda: {"records": 0, "markets": set(), "districts": set()})
        district_summary = defaultdict(lambda: {"records": 0, "commodities": set(), "markets": set()})
        market_summary = defaultdict(lambda: {"records": 0, "commodities": set(), "district": ""})

        for record in data:
            latest_by_key.setdefault((record.commodity, record.district, record.market), record)
            history[record.commodity].append(record.to_dict())
            commodity_summary[record.commodity]["records"] += 1
            commodity_summary[record.commodity]["markets"].add(record.market)
            commodity_summary[record.commodity]["districts"].add(record.district)
            district_summary[record.district]["records"] += 1
            district_summary[record.district]["commodities"].add(record.commodity)
            district_summary[record.district]["markets"].add(record.market)
            market_summary[record.market]["records"] += 1
            market_summary[record.market]["commodities"].add(record.commodity)
            market_summary[record.market]["district"] = record.district

        write_report(output_dir / "latest_prices.json", [r.to_mongo_document() for r in latest_by_key.values()])
        write_report(output_dir / "history.json", history)
        write_report(output_dir / "commodity_summary.json", self._collapse_sets(commodity_summary))
        write_report(output_dir / "district_summary.json", self._collapse_sets(district_summary))
        write_report(output_dir / "market_summary.json", self._collapse_sets(market_summary))
        write_report(output_dir / "price_trends.json", self._price_trends(data))
        write_report(output_dir / "dashboard_stats.json", analytics)

    @staticmethod
    def _collapse_sets(summary: dict) -> dict:
        collapsed = {}
        for key, value in summary.items():
            collapsed[key] = {
                name: sorted(items) if isinstance(items, set) else items
                for name, items in value.items()
            }
        return collapsed

    @staticmethod
    def _price_trends(records: List[CommodityRecord]) -> dict:
        trends = defaultdict(list)
        for record in records:
            trends[f"{record.commodity}|{record.market}"].append(
                {"date": record.date, "price": record.modal_price}
            )
        return trends
