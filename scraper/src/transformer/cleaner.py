"""Low-level value cleaning helpers shared by validation and transformation."""

from datetime import datetime
import re
from typing import Any, Optional


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def title_name(value: Any) -> str:
    text = clean_text(value)
    return " ".join(part.capitalize() for part in text.split(" "))


def parse_int_price(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def parse_date(value: Any) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
