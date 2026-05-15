import os
import sys
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import gspread
from google.oauth2.service_account import Credentials

# Configuration — reads from .env
from dotenv import load_dotenv
load_dotenv()
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "firebase-service-account.json")

async def main():
    print("Starting Google Sheets sync...")
    
    # 1. Connect to MongoDB
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient("mongodb://mongodb:27017")
    db = client["athanur_agro"]
    collection = db["market_prices"]
    
    # Fetch all records, sorted by Date (oldest first)
    print("Fetching records from database...")
    records = await collection.find().sort("date", 1).to_list(1000)
    print(f"Found {len(records)} records in the database.")
    
    if not records:
        print("No records to sync.")
        return

    # 2. Authenticate with Google Sheets
    print(f"Authenticating with Google Sheets using {CREDENTIALS_FILE}...")
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        gc = gspread.authorize(credentials)
        
        print(f"Opening spreadsheet {SHEET_ID}...")
        spreadsheet = gc.open_by_key(SHEET_ID)
        worksheet = spreadsheet.sheet1
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("\nMake sure you shared the sheet with 'firebase-adminsdk-fbsvc@agro-app-5f139.iam.gserviceaccount.com' as an Editor!")
        return

    # 3. Format Data for Google Sheets
    print("Formatting data for Sheets...")
    
    # Define headers
    headers = ["Date", "Category", "Commodity", "District", "City", "Price", "Unit"]
    
    # Create the rows
    rows_to_insert = [headers]
    for r in records:
        row = [
            r.get("date", ""),
            r.get("category", ""),
            r.get("commodity", ""),
            r.get("district", ""),
            r.get("city", "All"),
            r.get("price", ""),
            r.get("unit", "")
        ]
        rows_to_insert.append(row)
        
    # 4. Clear existing sheet and write new data
    print("Clearing existing sheet...")
    try:
        worksheet.clear()
        
        print(f"Writing {len(rows_to_insert)} rows to Google Sheet...")
        # Update the entire sheet starting at A1
        worksheet.update('A1', rows_to_insert)
        
        # Format the header row (bold)
        worksheet.format("A1:G1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
        })
        
        print("✅ SUCCESS! All data synced to Google Sheets!")
    except Exception as e:
        print(f"ERROR writing to Google Sheets: {e}")

if __name__ == "__main__":
    asyncio.run(main())
