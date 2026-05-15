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
        if os.path.isabs(cred_file):
            self.credentials_path = cred_file
        else:
            # Assume it's in the app root (one level up from src)
            self.credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), cred_file)
            
        self.client = None
        self.worksheet = None
        
        self.headers = ["Date", "Category", "Commodity", "District", "City", "Price", "Unit"]
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
            if not first_row or first_row[0] != "Date":
                # Sheet might be empty or missing headers
                self.worksheet.insert_row(self.headers, index=1)
                self.worksheet.format("A1:G1", {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                })
                logger.info("Inserted headers into Google Sheet")
        except Exception as e:
            logger.error(f"Error checking/inserting headers: {e}")

    def append_records(self, records):
        if not self.worksheet or not records:
            return False
            
        # Filter to ONLY sync Flowers to the Google Sheet
        flower_records = [r for r in records if "flower" in r.get("category", "").lower()]
        if not flower_records:
            logger.info("No flower records to sync to Google Sheets. Skipping.")
            return True
            
        try:
            # 1. Fetch existing rows to prevent duplicates
            existing_rows = self.worksheet.get_all_values()
            if not existing_rows:
                existing_rows = [self.headers]
                
            headers = existing_rows[0]
            data_rows = existing_rows[1:]
            
            # 2. Build unique dictionary to easily overwrite duplicates
            # Key: "Date_City_Commodity"
            unique_records = {}
            for row in data_rows:
                if len(row) >= 5:
                    date_val, cat_val, comm_val, dist_val, city_val = row[0:5]
                    key = f"{date_val}_{city_val}_{comm_val}"
                    unique_records[key] = row
                    
            # 3. Add or update with new records
            for r in flower_records:
                date_val = r.get("date", "")
                city_val = r.get("city", "All")
                comm_val = r.get("commodity", "")
                key = f"{date_val}_{city_val}_{comm_val}"
                
                new_row = [
                    date_val,
                    r.get("category", ""),
                    comm_val,
                    r.get("district", ""),
                    city_val,
                    r.get("price", ""),
                    r.get("unit", "")
                ]
                unique_records[key] = new_row
                
            # 4. Write perfectly deduplicated data back to the sheet
            final_rows = [headers] + list(unique_records.values())
            
            self.worksheet.clear()
            self.worksheet.update('A1', final_rows)
            logger.info(f"Successfully synced perfectly deduplicated {len(final_rows)-1} rows to Google Sheet")
            
            # Re-apply header formatting
            self.worksheet.format("A1:G1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to append to Google Sheets: {e}")
            return False
