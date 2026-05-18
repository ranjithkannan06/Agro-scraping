import os
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scrapers.vayal_scraper import scrape_vayal_flowers
from database import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def scheduled_job():
    logger.info("Starting scheduled scraping job for flower prices...")
    try:
        # We will use the database module to insert
        db = Database()
        await db.connect()
        
        # Run scraper
        data = await scrape_vayal_flowers()
        
        if data:
            logger.info(f"Successfully scraped {len(data)} items. Inserting into DB...")
            await db.insert_prices(data)
            
            # Sync to Google Sheets
            try:
                from google_sheets import GoogleSheetsService
                sheets = GoogleSheetsService()
                sheets.append_records(data)
            except Exception as e:
                logger.error(f"Failed to sync to Google Sheets: {e}")
            
            # Notify the backend to send push notifications + WebSocket broadcast
            import aiohttp
            try:
                # Assuming backend service is accessible as 'backend:8000' in docker-compose
                async with aiohttp.ClientSession() as session:
                    # Convert datetimes to string for JSON serialization
                    serializable_data = [
                        {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in item.items()}
                        for item in data
                    ]
                    # 1. Trigger FCM push notifications to mobile
                    await session.post(
                        'http://backend:8000/api/internal/notify',
                        json={'items': serializable_data}
                    )
                    # 2. Broadcast WebSocket event to all connected dashboard clients
                    await session.post(
                        'http://backend:8000/api/internal/broadcast',
                        json={'items': serializable_data}
                    )
            except Exception as e:
                logger.error(f"Failed to trigger notifications: {e}")
                
        else:
            logger.warning("No data scraped in this run.")
            
        await db.close()
    except Exception as e:
        logger.error(f"Error in scheduled job: {e}")

async def main():
    logger.info("Starting Scraper Service")
    scheduler = AsyncIOScheduler()
    
    # Add job to run every 5 minutes
    scheduler.add_job(scheduled_job, 'interval', minutes=5)
    scheduler.start()
    
    # Run immediately on startup
    await scheduled_job()
    
    # Keep the script running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scraper Service stopped.")
