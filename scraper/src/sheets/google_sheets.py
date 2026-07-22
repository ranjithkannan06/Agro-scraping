"""Incremental Google Sheets synchronization for new and changed records."""

import logging
import os
from pathlib import Path
from typing import Iterable, List

import gspread
from google.oauth2.service_account import Credentials

from models.commodity import CommodityRecord


class GoogleSheetsSynchronizer:
    """Append new rows and update changed rows without clearing the sheet."""

    headers = [
        "Date Scraped",
        "Category",
        "Commodity Name",
        "Market Name",
        "Min Price",
        "Max Price",
        "Modal Price",
        "Unit",
        "Source URL",
        "District",
    ]

    def __init__(self, sheet_id: str | None, credentials_file: str, logger: logging.Logger):
        self.sheet_id = sheet_id
        self.credentials_file = credentials_file
        self.logger = logger
        self.worksheet = None

    def connect(self) -> None:
        if not self.sheet_id:
            self.logger.warning("GOOGLE_SHEET_ID is not set; Sheets sync skipped.")
            return

        credentials_path = self._resolve_credentials()
        if not credentials_path:
            self.logger.warning("Google credentials file was not found; Sheets sync skipped.")
            return

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
        client = gspread.authorize(credentials)
        self.worksheet = client.open_by_key(self.sheet_id).sheet1
        if not self.worksheet.row_values(1):
            self.worksheet.append_row(self.headers)

    def sync(self, records: Iterable[CommodityRecord]) -> dict:
        batch = list(records)
        if not batch:
            return {"appended": 0, "updated": 0}
        if self.worksheet is None:
            self.connect()
        if self.worksheet is None:
            return {"appended": 0, "updated": 0}

        existing_rows = self.worksheet.get_all_values()
        if not existing_rows:
            self.worksheet.append_row(self.headers)
            existing_rows = [self.headers]

        row_by_key = {}
        for row_number, row in enumerate(existing_rows[1:], start=2):
            if len(row) >= 4:
                district = row[9] if len(row) > 9 else ""
                key = (row[2], district, row[3], row[0])
                row_by_key[key] = (row_number, row)

        appends: List[List[str]] = []
        updates = 0
        for record in sorted(batch, key=lambda r: (r.date, r.commodity, r.district), reverse=True):
            row = self._to_row(record)
            current = row_by_key.get(record.key)
            if current is None:
                appends.append(row)
            elif current[1] != row:
                self.worksheet.update(f"A{current[0]}:J{current[0]}", [row])
                updates += 1

        if appends:
            self.worksheet.append_rows(appends, value_input_option="USER_ENTERED")

        self._format_sheet()
        return {"appended": len(appends), "updated": updates}

    def _resolve_credentials(self) -> Path | None:
        candidates = [
            Path(self.credentials_file),
            Path.cwd() / self.credentials_file,
            Path.cwd().parent / self.credentials_file,
            Path("/app/firebase-service-account.json"),
        ]
        for path in candidates:
            if path.exists() and path.stat().st_size > 0:
                return path
        return None

    def _format_sheet(self) -> None:
        try:
            self.worksheet.freeze(rows=1)
            self.worksheet.format("A1:J1", {"textFormat": {"bold": True}})
            self.worksheet.sort((1, "des"), (3, "asc"), (10, "asc"))
        except Exception as exc:
            self.logger.warning("Unable to apply Google Sheets formatting: %s", exc)

    @classmethod
    def _to_row(cls, record: CommodityRecord) -> List[str]:
        return [
            record.date,
            record.category,
            record.commodity,
            record.market,
            record.minimum_price or "",
            record.maximum_price or "",
            record.modal_price,
            record.unit,
            record.source_url,
            record.district,
        ]
