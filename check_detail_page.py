"""
Diagnostic: Inspect the history detail page table on vayalagro.com.

FIX: The page has 4 tables:
  - Table#0 / #2 : hidden (offsetParent=null), mobile layout, Date/Price cols
  - Table#1       : VISIBLE, 6-col desktop layout (Category, District, City, Date, Price, Units)
  - Table#3       : VISIBLE, cross-district history table (.history-table)
Using document.querySelector("table") always picks Table#0 (hidden) -> timeout.
We now poll for the first VISIBLE table with data rows.
"""

import asyncio
import sys
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

TARGET_URL = (
    "https://vayalagro.com/market-price/tamilnadu/"
    "flowers-history-price-dindigul/nilakkottai/arali-history-price"
)

async def main():
    print(f"Launching Chromium to inspect history detail page: {TARGET_URL}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(TARGET_URL, wait_until="domcontentloaded")

        print("Polling for a visible data table (up to 15 s)...")
        visible_table_found = False
        for _ in range(15):
            found = await page.evaluate('''() => {
                const tables = Array.from(document.querySelectorAll("table"));
                return tables.some(t => t.offsetParent !== null && t.rows.length > 1);
            }''')
            if found:
                visible_table_found = True
                break
            await asyncio.sleep(1.0)

        if not visible_table_found:
            print("ERROR: No visible data table found after 15 s.")
            await browser.close()
            return

        # Extract from the VISIBLE table with the most rows
        rows = await page.evaluate('''() => {
            const tables = Array.from(document.querySelectorAll("table"));
            const visible = tables.filter(t => t.offsetParent !== null && t.rows.length > 1);
            if (!visible.length) return [];
            const best = visible.reduce((a, b) => (a.rows.length >= b.rows.length ? a : b));
            return Array.from(best.rows).map(row =>
                Array.from(row.querySelectorAll("td, th")).map(cell => cell.innerText.trim())
            );
        }''')

        print(f"Successfully found visible history table! Total rows = {len(rows)}")
        if rows:
            print(f"Headers : {rows[0]}")
            print("First 5 data rows:")
            for r in rows[1:6]:
                print(" ", r)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
