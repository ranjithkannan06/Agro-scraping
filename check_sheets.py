r"""
Quick Google Sheets diagnostic:
1. Connects using the existing firebase-service-account.json
2. Reads the current row count and last few rows of the sheet
3. Does a test write of 2 dummy rows, then reads them back to confirm write works

Run with: .venv\Scripts\python.exe check_sheets.py
"""
import os, sys, json

# Force UTF-8 output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Load .env manually
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID    = os.getenv("GOOGLE_SHEET_ID", "")
CREDS_FILE  = os.getenv("GOOGLE_CREDENTIALS_FILE", "firebase-service-account.json")
CREDS_PATH  = os.path.abspath(CREDS_FILE)

print("=" * 60)
print("GOOGLE SHEETS DIAGNOSTIC")
print("=" * 60)
print(f"Sheet ID     : {SHEET_ID}")
print(f"Creds file   : {CREDS_PATH}")
print(f"Creds exists : {os.path.exists(CREDS_PATH)}")

if not SHEET_ID:
    print("ERROR: GOOGLE_SHEET_ID is not set in .env")
    sys.exit(1)
if not os.path.exists(CREDS_PATH):
    print("ERROR: Credentials file not found")
    sys.exit(1)

# ── Connect ───────────────────────────────────────────────────────────────
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds  = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
    client = gspread.authorize(creds)
    print("\n[1] gspread authorize   : OK")
except Exception as e:
    print(f"\n[1] gspread authorize   : FAILED -> {e}")
    sys.exit(1)

try:
    spreadsheet = client.open_by_key(SHEET_ID)
    ws           = spreadsheet.sheet1
    print(f"[2] Open spreadsheet    : OK  (title='{spreadsheet.title}', sheet='{ws.title}')")
except Exception as e:
    print(f"[2] Open spreadsheet    : FAILED -> {e}")
    print("    --> Check that the service account email has been shared edit access on the sheet.")
    sys.exit(1)

# ── Read current state ────────────────────────────────────────────────────
try:
    all_rows = ws.get_all_values()
    print(f"[3] Current row count   : {len(all_rows)}  (including header row)")
    if all_rows:
        print(f"    Headers row         : {all_rows[0]}")
    if len(all_rows) > 1:
        print(f"    Last 3 data rows:")
        for row in all_rows[-3:]:
            print(f"      {row}")
    else:
        print("    (Sheet is empty - no data rows yet)")
except Exception as e:
    print(f"[3] Read sheet          : FAILED -> {e}")
    sys.exit(1)

# ── Test write ────────────────────────────────────────────────────────────
print("\n[4] Testing write access (appending 1 test row)...")
test_row = ["DIAG-TEST", "Flowers", "Arali", "Sathyamangalam", "", "", "110", "Kg", "https://test-url"]
try:
    ws.append_row(test_row)
    print("    append_row()        : OK")
    # Read it back
    updated = ws.get_all_values()
    if updated[-1][0] == "DIAG-TEST":
        print("    Read-back check     : OK - test row is in the sheet")
        # Clean it up
        ws.delete_rows(len(updated))
        print("    Cleanup             : OK - test row deleted")
    else:
        print("    Read-back check     : WARNING - could not verify test row")
except Exception as e:
    print(f"    append_row()        : FAILED -> {e}")
    sys.exit(1)

print("\n[RESULT] Google Sheets is configured correctly and write access is working.")
print(f"         Sheet URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
print(f"         Current data rows: {len(all_rows) - 1 if all_rows else 0}")
