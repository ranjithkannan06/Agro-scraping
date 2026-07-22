"""Environment-backed configuration for the scraper ETL pipeline."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Set

from config.constants import (
    DEFAULT_BACKEND_URL,
    DEFAULT_CONCURRENT_TABS,
    DEFAULT_CONFIG_FILE,
    DEFAULT_DATABASE_NAME,
    DEFAULT_FAILED_PAGES_ROOT,
    DEFAULT_LOG_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_SOURCE_URL,
    OUTPUT_SUBDIRECTORIES,
)


@dataclass(frozen=True)
class ValidValueConfig:
    commodities: Set[str] = field(default_factory=set)
    districts: Set[str] = field(default_factory=set)
    markets: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class PipelineSettings:
    source_url: str
    mongodb_url: str
    database_name: str
    google_sheet_id: str | None
    google_credentials_file: str
    backend_internal_url: str
    output_root: Path
    log_root: Path
    failed_pages_root: Path
    retry_attempts: int
    concurrent_tabs: int
    valid_values: ValidValueConfig

    @classmethod
    def from_env(cls) -> "PipelineSettings":
        raw_mongo_url = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
        if not os.path.exists("/.dockerenv") and "mongodb://mongodb:" in raw_mongo_url:
            raw_mongo_url = raw_mongo_url.replace("mongodb://mongodb:", "mongodb://127.0.0.1:")

        output_root = Path(os.getenv("SCRAPER_OUTPUT_ROOT", str(DEFAULT_OUTPUT_ROOT)))
        for name in OUTPUT_SUBDIRECTORIES:
            (output_root / name).mkdir(parents=True, exist_ok=True)

        log_root = Path(os.getenv("SCRAPER_LOG_ROOT", str(DEFAULT_LOG_ROOT)))
        failed_root = Path(os.getenv("FAILED_PAGES_ROOT", str(DEFAULT_FAILED_PAGES_ROOT)))
        log_root.mkdir(parents=True, exist_ok=True)
        (failed_root / "screenshots").mkdir(parents=True, exist_ok=True)
        (failed_root / "html").mkdir(parents=True, exist_ok=True)

        return cls(
            source_url=os.getenv("SCRAPER_SOURCE_URL", DEFAULT_SOURCE_URL),
            mongodb_url=raw_mongo_url,
            database_name=os.getenv("DATABASE_NAME", DEFAULT_DATABASE_NAME),
            google_sheet_id=os.getenv("GOOGLE_SHEET_ID"),
            google_credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "firebase-service-account.json"),
            backend_internal_url=os.getenv("BACKEND_INTERNAL_URL", DEFAULT_BACKEND_URL),
            output_root=output_root,
            log_root=log_root,
            failed_pages_root=failed_root,
            retry_attempts=int(os.getenv("SCRAPER_RETRY_ATTEMPTS", str(DEFAULT_RETRY_ATTEMPTS))),
            concurrent_tabs=int(os.getenv("SCRAPER_CONCURRENT_TABS", str(DEFAULT_CONCURRENT_TABS))),
            valid_values=load_valid_values(Path(os.getenv("SCRAPER_VALID_VALUES_FILE", str(DEFAULT_CONFIG_FILE)))),
        )


def load_valid_values(path: Path) -> ValidValueConfig:
    """Load optional allow-lists; empty sets mean no allow-list validation is applied."""
    if not path.exists():
        return ValidValueConfig()
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return ValidValueConfig(
        commodities={str(v).strip().lower() for v in payload.get("commodities", []) if str(v).strip()},
        districts={str(v).strip().lower() for v in payload.get("districts", []) if str(v).strip()},
        markets={str(v).strip().lower() for v in payload.get("markets", []) if str(v).strip()},
    )
