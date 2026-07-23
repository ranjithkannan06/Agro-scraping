import os
import asyncio
import logging
import sys
import time

# Load environment variables from project root .env file
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(dotenv_path)
except ImportError:
    pass

# Allow Windows event loop compatibility immediately on import
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from analytics.analytics import AnalyticsEngine
from analytics.reports import write_report
from config.settings import PipelineSettings
from dashboard.dashboard_generator import DashboardDatasetGenerator
from database.mongodb import MongoPriceRepository
from exporters.csv_exporter import CsvExporter
from exporters.excel_exporter import ExcelExporter
from exporters.json_exporter import JsonExporter
from logger.logger import configure_logging
from notifications.backend import BackendNotifier
from parser.collector import VayalCollector
from sheets.google_sheets import GoogleSheetsSynchronizer
from transformer.normalizer import CommodityTransformer
from utils.resource_metrics import ResourceSampler
from validator.deduplicator import DeduplicationEngine
from validator.validator import CommodityValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scheduler.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("scheduler")


async def run_pipeline(force=False):
    settings = PipelineSettings.from_env()
    pipeline_logger = configure_logging(settings.log_root)
    resources = ResourceSampler()
    start_time = time.perf_counter()
    error_count = 0
    repository = MongoPriceRepository(settings.mongodb_url, settings.database_name, pipeline_logger)

    try:
        pipeline_logger.info("Pipeline started", extra={"extra_data": resources.delta()})
        await repository.ensure_indexes()

        raw_records = await VayalCollector(settings.source_url, settings.concurrent_tabs).collect(force=force)
        pipeline_logger.info(
            "Collector completed",
            extra={"extra_data": {"records": len(raw_records), **resources.delta()}},
        )

        validator = CommodityValidator(settings.valid_values)
        valid_raw, validation_report = validator.validate(raw_records)
        write_report(settings.output_root / "reports" / "validation_report.json", validation_report)
        pipeline_logger.info(
            "Validation completed",
            extra={"extra_data": {"valid": len(valid_raw), "invalid": validation_report.invalid, **resources.delta()}},
        )

        transformed = CommodityTransformer().transform(valid_raw)
        write_report(settings.output_root / "reports" / "failed_records.json", [
            issue.record for issue in validation_report.issues
        ])

        deduplicator = DeduplicationEngine(repository)
        new_records, duplicate_report = await deduplicator.filter_new(transformed)
        write_report(settings.output_root / "reports" / "duplicates.json", duplicate_report)
        pipeline_logger.info(
            "Deduplication completed",
            extra={"extra_data": {"new": len(new_records), "duplicate": duplicate_report.duplicate, **resources.delta()}},
        )

        deltas = {
            "new": len(new_records),
            "duplicate": duplicate_report.duplicate,
            "updated": 0,
            "invalid": validation_report.invalid,
        }
        analytics = AnalyticsEngine().generate(transformed, deltas)
        analytics["execution"] = {
            "duration_seconds": round(time.perf_counter() - start_time, 2),
            "error_count": error_count,
            **resources.delta(),
        }
        write_report(settings.output_root / "reports" / "analytics.json", analytics)

        CsvExporter().export(transformed, settings.output_root / "csv" / "scraped_data.csv")
        ExcelExporter().export(transformed, settings.output_root / "excel" / "scraped_data.xlsx")
        JsonExporter().export(transformed, settings.output_root / "json" / "scraped_data.json")
        pipeline_logger.info("Exports completed", extra={"extra_data": resources.delta()})

        DashboardDatasetGenerator().generate(
            transformed,
            analytics,
            settings.output_root / "dashboard",
        )
        pipeline_logger.info("Dashboard datasets completed", extra={"extra_data": resources.delta()})

        loaded_count = await repository.bulk_upsert(new_records, retries=settings.retry_attempts)
        sheets_result = GoogleSheetsSynchronizer(
            settings.google_sheet_id,
            settings.google_credentials_file,
            pipeline_logger,
        ).sync(new_records)

        await BackendNotifier(settings.backend_internal_url, pipeline_logger).publish(new_records)

        pipeline_logger.info(
            "Pipeline finished",
            extra={
                "extra_data": {
                    "raw": len(raw_records),
                    "valid": len(valid_raw),
                    "transformed": len(transformed),
                    "new": len(new_records),
                    "loaded": loaded_count,
                    "sheets": sheets_result,
                    "duration_seconds": round(time.perf_counter() - start_time, 2),
                    **resources.delta(),
                }
            },
        )
        return {
            "raw": len(raw_records),
            "valid": len(valid_raw),
            "new": len(new_records),
            "loaded": loaded_count,
            "sheets": sheets_result,
        }
    except Exception:
        error_count += 1
        pipeline_logger.exception("Pipeline failed")
        raise
    finally:
        await repository.close()


async def scheduled_job(force=False):
    logger.info("=============================================================")
    logger.info("Starting scheduled scraping and synchronization job...")
    logger.info("=============================================================")
    try:
        # Run the full ETL pipeline: collect -> validate -> transform -> dedupe -> analyze -> load/export.
        await run_pipeline(force=force)
        logger.info("Scheduled job execution completed successfully.")
    except Exception as e:
        logger.error(f"Error executing scheduled scraper job: {e}")

async def main(force=False):
    logger.info("Starting Farmer's Hub Scraper Scheduler Service...")
    scheduler = AsyncIOScheduler()
    
    # Add job to run every 30 minutes daily between 9 AM and 12 PM
    scheduler.add_job(scheduled_job, 'cron', hour='9-12', minute='*/30')
    scheduler.start()
    logger.info("Scraper scheduler initialized successfully. Set to run daily between 9 AM and 12 PM (every 30 mins).")
    
    # Run immediately on startup to seed the database and spreadsheet
    await scheduled_job(force=force)
    
    # Keep the script running asynchronously
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser(description="HarvestHub Scraper Scheduler")
        parser.add_argument("--force", action="store_true", help="Force scrape all records, bypassing dedup")
        args = parser.parse_args()
        
        # Allow Windows event loop compatibility
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(main(force=args.force))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scraper Scheduler Service stopped cleanly.")
