import os
import logging
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        self.sheet_id = os.getenv("GOOGLE_SHEET_ID")
        # Use env var or default to app root
        cred_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "firebase-service-account.json")
        
        # Resolve credential path in a robust way, checking multiple fallback locations
        PATHS_TO_TRY = [
            os.path.abspath(cred_file) if os.path.isabs(cred_file) else None,
            # Project root (2 levels up from scraper/src — the standard layout)
            os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), cred_file)),
            # Scraper root (1 level up from scraper/src)
            os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), cred_file)),
            # CWD-relative (when script is launched from project root directly)
            os.path.abspath(os.path.join(os.getcwd(), cred_file)),
            # CWD parent (when launched from scraper/ subdirectory)
            os.path.abspath(os.path.join(os.getcwd(), '..', cred_file)),
            # CWD grandparent (when launched from scraper/src/)
            os.path.abspath(os.path.join(os.getcwd(), '..', '..', cred_file)),
            # Absolute default locations
            os.path.abspath(cred_file),
            '/app/firebase-service-account.json'
        ]
        
        self.credentials_path = None
        for path in PATHS_TO_TRY:
            if path and os.path.exists(path) and os.path.getsize(path) > 0:
                self.credentials_path = path
                break
                
        if not self.credentials_path:
            # Fallback to default
            self.credentials_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), cred_file))
            
        self.client = None
        self.worksheet = None
        
        # New production headers matching the complete schema
        self.headers = [
            "Date Scraped", "Category", "Commodity Name", 
            "Market Name", "Min Price", "Max Price", 
            "Modal Price", "Unit", "Source URL"
        ]
        logger.info(f"Initializing Google Sheets Service with sheet: {self.sheet_id}")
        self._init_client()

    def _init_client(self):
        try:
            if not os.path.exists(self.credentials_path):
                logger.error(f"Google Sheets credentials not found at {self.credentials_path}. Check GOOGLE_CREDENTIALS_FILE env var.")
                return
                
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            credentials = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            self.client = gspread.authorize(credentials)
            
            spreadsheet = self.client.open_by_key(self.sheet_id)
            self.worksheet = spreadsheet.sheet1
            logger.info(f"Successfully connected to Google Sheet: {self.sheet_id}")
            
            # Ensure headers exist
            self._ensure_headers()
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")

    def _ensure_headers(self):
        if not self.worksheet:
            return
        
        try:
            first_row = self.worksheet.row_values(1)
            if not first_row or first_row[0] != "Date Scraped":
                # Sheet might be empty or missing headers
                self.worksheet.insert_row(self.headers, index=1)
                self.worksheet.format("A1:I1", {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                })
                logger.info("Inserted headers into Google Sheet")
        except Exception as e:
            logger.error(f"Error checking/inserting headers: {e}")

    def append_records(self, records):
        if not self.worksheet or not records:
            logger.warning("Google Sheet worksheet not loaded, or no records provided. Sync skipped.")
            return False
            
        # Sync all valid scraped records to the Google Sheet (expanded from flower-only filter)
        valid_records = [r for r in records if r.get("category")]
        if not valid_records:
            logger.info("No records to sync to Google Sheets. Skipping.")
            return True
            
        try:
            # 1. Fetch existing rows to prevent duplicates
            existing_rows = self.worksheet.get_all_values()
            if not existing_rows:
                existing_rows = [self.headers]
                
            headers = existing_rows[0]
            data_rows = existing_rows[1:]
            
            # 2. Build unique dictionary to easily overwrite duplicates
            # Composite Key: "DateScraped_MarketName_CommodityName"
            unique_records = {}
            for row in data_rows:
                if len(row) >= 4:
                    date_val, cat_val, comm_val, market_val = row[0:4]
                    key = f"{date_val}_{market_val}_{comm_val}"
                    unique_records[key] = row
                    
            # 3. Add or update with new records
            for r in valid_records:
                date_val = r.get("date_scraped", "")
                market_val = r.get("market_name", "All")
                comm_val = r.get("commodity_name", "")
                key = f"{date_val}_{market_val}_{comm_val}"
                
                new_row = [
                    date_val,
                    r.get("category", "Other"),
                    comm_val,
                    market_val,
                    r.get("price_min", ""),
                    r.get("price_max", ""),
                    r.get("price_modal", r.get("price", "")),
                    r.get("unit", "Kg"),
                    r.get("source_url", "")
                ]
                unique_records[key] = new_row
                
            # 4. Write perfectly deduplicated data back to the sheet
            final_rows = [headers] + list(unique_records.values())
            
            self.worksheet.clear()
            self.worksheet.update('A1', final_rows)
            logger.info(f"Successfully synced perfectly deduplicated {len(final_rows)-1} rows to Google Sheet")
            
            # Re-apply header formatting
            self.worksheet.format("A1:I1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to append to Google Sheets: {e}")
            return False
