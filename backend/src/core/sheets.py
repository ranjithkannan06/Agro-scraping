import gspread
import os
import json
import logging
import time

logger = logging.getLogger(__name__)

# Very simple global in-memory cache to prevent hitting Google API quotas
# Since this reads the whole sheet for the dashboard, caching is essential.
_sheets_cache = {
    "data": None,
    "last_fetched": 0
}

CACHE_TTL = 60  # Cache for 60 seconds

def get_google_sheet_data():
    """
    Fetches all records from the Google Sheet. Uses a 60-second in-memory cache.
    """
    global _sheets_cache
    
    current_time = time.time()
    if _sheets_cache["data"] is not None and (current_time - _sheets_cache["last_fetched"]) < CACHE_TTL:
        return _sheets_cache["data"]

    try:
        # Resolve credential path
        cred_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "firebase-service-account.json")
        paths_to_try = [
            os.path.abspath(cred_file) if os.path.isabs(cred_file) else None,
            os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), cred_file)),
            os.path.abspath(cred_file),
            'd:\\agri\\athanur-agro\\firebase-service-account.json'
        ]
        
        credentials_path = None
        for p in paths_to_try:
            if p and os.path.exists(p) and os.path.getsize(p) > 0:
                credentials_path = p
                break
                
        if not credentials_path:
            logger.error("Could not find Google Sheets credentials file.")
            return []

        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if not sheet_id:
            logger.error("GOOGLE_SHEET_ID not set in environment.")
            return []

        client = gspread.service_account(filename=credentials_path)
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(0)
        
        records = worksheet.get_all_records()
        
        # Clean keys and values
        cleaned_records = []
        for r in records:
            # Map standard keys matching MongoDB schema
            cleaned_records.append({
                "date_scraped": str(r.get("Date", "")),
                "category": str(r.get("Category", "Unknown")),
                "commodity_name": str(r.get("Commodity", "")),
                "market_name": str(r.get("Market/City", "")),
                "price_min": r.get("Min Price (₹)", ""),
                "price_max": r.get("Max Price (₹)", ""),
                "price": r.get("Modal/Average Price (₹)", ""),
                "unit": str(r.get("Unit", "Kg")),
                "source_url": str(r.get("Source URL", ""))
            })
            
        _sheets_cache["data"] = cleaned_records
        _sheets_cache["last_fetched"] = current_time
        
        return cleaned_records

    except Exception as e:
        logger.error(f"Error fetching from Google Sheets: {e}")
        # Return stale cache if available, else empty list
        if _sheets_cache["data"] is not None:
            return _sheets_cache["data"]
        return []
