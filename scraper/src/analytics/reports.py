"""Report serialization helpers for validation, duplicates, and analytics."""

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any


def write_report(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = payload.to_dict() if hasattr(payload, "to_dict") else payload
    path.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(value)
    return str(value)
