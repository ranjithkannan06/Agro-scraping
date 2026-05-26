import os
import asyncio
import logging
import sys

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
from scrapers.vayal_scraper import scrape_vayal_flowers

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

async def scheduled_job():
    logger.info("=============================================================")
    logger.info("Starting scheduled scraping and synchronization job...")
    logger.info("=============================================================")
    try:
        # Run the full integrated scraper pipeline (Scrape -> DB Upsert -> Google Sheet Sync -> Backend alert)
        await scrape_vayal_flowers()
        logger.info("Scheduled job execution completed successfully.")
    except Exception as e:
        logger.error(f"Error executing scheduled scraper job: {e}")

async def main():
    logger.info("Starting Farmer's Hub Scraper Scheduler Service...")
    scheduler = AsyncIOScheduler()
    
    # Add job to run every 5 minutes as specified by current settings
    scheduler.add_job(scheduled_job, 'interval', minutes=5)
    scheduler.start()
    logger.info("Scraper scheduler initialized successfully. Interval set to every 5 minutes.")
    
    # Run immediately on startup to seed the database and spreadsheet
    await scheduled_job()
    
    # Keep the script running asynchronously
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        # Allow Windows event loop compatibility
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scraper Scheduler Service stopped cleanly.")
