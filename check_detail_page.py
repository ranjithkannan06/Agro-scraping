import asyncio
import sys
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    target_url = "https://vayalagro.com/market-price/tamilnadu/flowers-history-price-dindigul/nilakkottai/arali-history-price"
    print(f"Launching Chromium to inspect history detail page: {target_url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(target_url, wait_until="domcontentloaded")
        
        print("Waiting for history table to render...")
        try:
            await page.wait_for_selector("table", timeout=10000)
            rows = await page.evaluate('''() => {
                const table = document.querySelector("table");
                if (!table) return [];
                return Array.from(table.rows).map(row => 
                    Array.from(row.querySelectorAll("td, th")).map(cell => cell.innerText.trim())
                );
            }''')
            
            print(f"Successfully discovered history table! Total rows = {len(rows)}")
            if rows:
                print(f"Headers: {rows[0]}")
                print("First 5 data rows:")
                for r in rows[1:6]:
                    print(r)
        except Exception as e:
            print(f"Failed to find or parse history table: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
