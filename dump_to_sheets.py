import sys
import os
import asyncio
from dotenv import load_dotenv

# Allow Windows event loop compatibility
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Load environment variables
load_dotenv()

# Add scraper/src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "scraper", "src"))

from database import Database
from google_sheets import GoogleSheetsService

async def main():
    print("Connecting to MongoDB database...")
    db = Database()
    await db.connect()
    
    print("Reading all records from MongoDB...")
    collection = db.db["market_prices"]
    records = await collection.find({}).to_list(10000)
    print(f"Discovered {len(records)} total records in database.")
    
    if not records:
        print("No records found in database. Nothing to sync.")
        await db.close()
        return
        
    print("Connecting to Google Sheets...")
    sheets = GoogleSheetsService()
    
    print("Starting Google Sheets synchronization...")
    success = sheets.append_records(records)
    if success:
        print("Deduplicated database records successfully synced to Google Sheet!")
    else:
        print("Google Sheets synchronization failed.")
        
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
