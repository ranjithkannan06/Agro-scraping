"""JSON export writer for normalized commodity records."""

import json
from pathlib import Path
from typing import Iterable

from models.commodity import CommodityRecord


class JsonExporter:
    def export(self, records: Iterable[CommodityRecord], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.to_dict() for record in records]
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
