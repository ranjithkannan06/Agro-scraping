# HarvestHub Scraper ETL Architecture

## Rationale

The scraper is now organized as a pipeline of explicit stages. The Playwright collector is responsible only for collecting raw source records in memory. It does not validate, normalize, write to MongoDB, update Google Sheets, notify the backend, or generate exports. Those concerns are handled by downstream stages in `src/main.py`, which makes the collector replaceable without changing storage or reporting code.

The stage boundary is intentionally typed around `RawCommodity` and `CommodityRecord`. A second source can plug in by implementing a collector that returns `list[RawCommodity]`; validation, transformation, deduplication, analytics, exports, and loaders can remain unchanged. Storage is hidden behind `PriceRepository`, so MongoDB duplicate lookups can be replaced or tested with an in-memory repository.

The pipeline order is fixed: collect raw records, validate them, transform valid rows into canonical records, deduplicate against durable storage, generate analytics and export artifacts, then load only new records into MongoDB and Google Sheets. Dashboard datasets are generated from transformed pipeline output, so the scraper remains the single producer of downstream data files.

## Interfaces

```python
class Collector:
    async def collect(self, force: bool = False) -> list[RawCommodity]: ...

class Validator:
    def validate(self, records: list[RawCommodity]) -> tuple[list[RawCommodity], ValidationReport]: ...

class PriceRepository:
    async def existing_keys(self, records: list[CommodityRecord]) -> set[tuple[str, str, str, str]]: ...
    async def close(self) -> None: ...
```

## Module Responsibilities

`src/main.py`: Orchestrates stages 1 through 9 and owns pipeline-level error handling.

`src/config/constants.py`: Stores static source defaults, retry limits, folders, and Vayal-specific constants.

`src/config/settings.py`: Loads environment-backed runtime settings and optional allow-list config.

`src/logger/logger.py`: Configures structured daily-rotating scraper logs.

`src/models/commodity.py`: Defines raw and normalized commodity record contracts.

`src/models/statistics.py`: Defines validation and deduplication report contracts.

`src/parser/collector.py`: Adapts the Vayal scraper into a collection-only pipeline source.

`src/parser/extractor.py`: Owns Playwright page actions, DOM extraction, detail-table parsing, and failed-page capture.

`src/scrapers/vayal_scraper.py`: Coordinates Vayal Agro traversal and returns raw legacy-shaped records in memory.

`src/validator/validator.py`: Validates required fields, duplicates, prices, dates, and optional allow-lists.

`src/validator/deduplicator.py`: Filters transformed records against repository-backed composite keys.

`src/transformer/cleaner.py`: Provides shared text, price, and date cleaning helpers.

`src/transformer/normalizer.py`: Converts valid raw records into canonical `CommodityRecord` objects.

`src/database/repository.py`: Defines the repository abstraction used by deduplication.

`src/database/mongodb.py`: Ensures indexes, checks existing MongoDB keys, and bulk-upserts new records.

`src/sheets/google_sheets.py`: Incrementally appends or updates Google Sheets rows without clearing the sheet.

`src/analytics/analytics.py`: Builds totals, deltas, price stats, and most-active summaries.

`src/analytics/reports.py`: Writes JSON reports with datetime-safe serialization.

`src/exporters/csv_exporter.py`: Writes `scraped_data.csv`.

`src/exporters/excel_exporter.py`: Writes `scraped_data.xlsx`.

`src/exporters/json_exporter.py`: Writes `scraped_data.json`.

`src/dashboard/dashboard_generator.py`: Writes dashboard-only JSON datasets from transformed records.

`src/notifications/backend.py`: Publishes completed batches to existing backend notification hooks after pipeline output is ready.

`src/utils/retry.py`: Provides reusable async retry behavior.

`src/utils/helpers.py`: Provides small filesystem and JSON serialization helpers.

## Conflict Log

The old scraper inserted into MongoDB, rewrote Google Sheets, and notified the backend inside `scrape_vayal_flowers()`. That conflicted with the single-source ETL model, so the collector now returns records only; persistence occurs in `run_pipeline()`.

The previous Google Sheets implementation cleared and rewrote the whole sheet. The new synchronizer diffs existing rows, appends new records, updates changed records, and keeps formatting operations separate from data mutation.

The original `vayal_scraper.py` was over 700 lines and mixed extraction helpers, traversal, parsing, persistence, and notification. It has been reduced to a source adapter, with extraction and page-control helpers moved into `parser/extractor.py`.

The dashboard constraint says the web dashboard must read only `outputs/dashboard/*.json`, while the same task also says not to touch dashboard UI or FastAPI routes. The scraper now generates the required dashboard JSON files, but switching the dashboard fetch layer to consume those files requires a later non-scraper change or an approved static-file serving path.
