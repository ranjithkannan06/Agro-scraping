"""Validates raw commodity records and emits validation reports."""

from datetime import datetime
from typing import Iterable, List, Tuple

from config.settings import ValidValueConfig
from models.commodity import RawCommodity
from models.statistics import ValidationIssue, ValidationReport
from transformer.cleaner import clean_text, parse_date, parse_int_price


class CommodityValidator:
    """Validate required fields, duplicates, allow-lists, prices, and dates."""

    def __init__(self, valid_values: ValidValueConfig):
        self.valid_values = valid_values

    def validate(self, records: Iterable[RawCommodity]) -> Tuple[List[RawCommodity], ValidationReport]:
        valid: List[RawCommodity] = []
        issues: List[ValidationIssue] = []
        seen_keys: set[tuple[str, str, str, str]] = set()
        duplicate_count = 0
        all_records = list(records)

        for index, record in enumerate(all_records):
            row_issues = self._validate_row(record)
            date_value = parse_date(record.date) or clean_text(record.date)
            key = (
                clean_text(record.commodity).lower(),
                clean_text(record.district).lower(),
                clean_text(record.market).lower(),
                date_value,
            )
            if key in seen_keys:
                duplicate_count += 1
                row_issues.append("duplicate row in raw batch")
            seen_keys.add(key)

            if row_issues:
                issues.append(ValidationIssue(index, "; ".join(row_issues), record.to_dict()))
            else:
                valid.append(record)

        invalid = len(issues)
        total = len(all_records)
        report = ValidationReport(
            total=total,
            valid=len(valid),
            duplicate=duplicate_count,
            invalid=invalid,
            validity_percentage=round((len(valid) / total) * 100, 2) if total else 0,
            issues=issues,
        )
        return valid, report

    def _validate_row(self, record: RawCommodity) -> List[str]:
        issues: List[str] = []
        for field in ("commodity", "category", "district", "market", "date", "source_url"):
            if not clean_text(getattr(record, field)):
                issues.append(f"missing {field}")

        modal_price = parse_int_price(record.modal_price)
        if modal_price is None:
            issues.append("missing or non-numeric modal_price")
        elif modal_price < 0:
            issues.append("negative modal_price")

        for price_field in ("minimum_price", "maximum_price"):
            parsed = parse_int_price(getattr(record, price_field))
            if parsed is not None and parsed < 0:
                issues.append(f"negative {price_field}")

        if parse_date(record.date) is None:
            issues.append("malformed date")

        if record.scraped_time and not isinstance(record.scraped_time, datetime):
            issues.append("malformed scraped_time")

        self._validate_allow_list("commodity", record.commodity, self.valid_values.commodities, issues)
        self._validate_allow_list("district", record.district, self.valid_values.districts, issues)
        self._validate_allow_list("market", record.market, self.valid_values.markets, issues)
        return issues

    @staticmethod
    def _validate_allow_list(field: str, value: str, allowed: set[str], issues: List[str]) -> None:
        if allowed and clean_text(value).lower() not in allowed:
            issues.append(f"invalid {field}")
