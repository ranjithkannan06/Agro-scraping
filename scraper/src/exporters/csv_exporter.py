"""CSV export writer for normalized commodity records."""

import csv
from pathlib import Path
from typing import Iterable

from models.commodity import CommodityRecord


class CsvExporter:
    fields = [
        "date",
        "category",
        "commodity",
        "district",
        "market",
        "minimum_price",
        "maximum_price",
        "modal_price",
        "unit",
        "source_url",
        "scraped_time",
    ]

    def export(self, records: Iterable[CommodityRecord], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.fields)
            writer.writeheader()
            for record in records:
                row = record.to_dict()
                writer.writerow({field: row.get(field, "") for field in self.fields})
