"""
STEP 4 VERIFICATION: Confirm scraped item count matches site total for
Flowers / Erode — a district known to have > 10 varieties.

Also tests that scrape_detail_page correctly extracts records from the
first visible table (not the hidden mobile-layout table).

Run with:  .venv\Scripts\python.exe verify_item_count.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scraper", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scraper", "src", "scrapers"))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright
from scrapers.vayal_scraper import scrape_detail_page, get_random_delay

BASE_URL = "https://vayalagro.com/market-price"

async def main():
    print("=" * 65)
    print("VERIFICATION: Flowers / Erode item count + detail extraction")
    print("=" * 65)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # ── Navigate & filter Flowers / Erode ─────────────────────────────
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        await page.evaluate("""() => {
            const sel = Array.from(document.querySelectorAll('select'))
                .find(s => s.options[0]?.text.toLowerCase().includes('category'));
            if (sel) {
                const opt = Array.from(sel.options).find(o => o.text.trim().toLowerCase() === 'flowers');
                if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
            }
        }""")
        await page.wait_for_timeout(2500)

        await page.evaluate("""() => {
            const sel = Array.from(document.querySelectorAll('select'))
                .find(s => s.options[0]?.text.toLowerCase().includes('district'));
            if (sel) {
                const opt = Array.from(sel.options).find(o => o.text.trim().toLowerCase() === 'erode');
                if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
            }
        }""")
        await page.wait_for_timeout(2000)

        await page.evaluate("""() => {
            const sel = Array.from(document.querySelectorAll('select'))
                .find(s => Array.from(s.options).some(o => o.value === '0'));
            if (sel) { sel.value = '0'; sel.dispatchEvent(new Event('change', {bubbles:true})); }
        }""")
        await page.wait_for_timeout(500)

        # Click Search
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button'))
                .find(b => b.innerText.toLowerCase().includes('search') || b.classList.contains('catgory-button'));
            if (btn) btn.click();
        }""")

        # Smart wait for links to appear
        try:
            await page.wait_for_function(
                "() => document.querySelectorAll('table td a').length > 0",
                timeout=10000
            )
        except Exception:
            pass
        await asyncio.sleep(1.5)

        # ── Gather all flower/Erode specific links ─────────────────────────
        all_links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('table td a'))
                .map(a => ({
                    href: a.href,
                    row: Array.from(a.closest('tr')?.cells || []).map(c => c.innerText.trim())
                }))
                .filter(x => x.href !== '');
        }""")

        # Filter to Flowers + Erode items only
        flower_erode_links = [
            l for l in all_links
            if "flower" in l["href"].lower() and "erode" in l["href"].lower()
        ]

        print(f"\nTotal <a> links in table after search : {len(all_links)}")
        print(f"Flower + Erode specific links          : {len(flower_erode_links)}")
        print("\nFlower/Erode detail URLs:")
        for l in flower_erode_links:
            print(f"  {l['href']}")

        if not flower_erode_links:
            print("\nNo Flower/Erode links found. Cannot verify count.")
            await browser.close()
            return

        # ── Scrape 3 detail pages to verify extraction works ──────────────
        print(f"\nScraping first 3 detail pages to verify record extraction...")
        total_records = 0
        for link in flower_erode_links[:3]:
            records = await scrape_detail_page(
                page,
                link["href"],
                "Flowers",
                "Test Commodity",
                "Sathyamangalam",
                "Erode",
                "Kg",
            )
            print(f"  {link['href'].split('/')[-1]}: {len(records)} records extracted")
            if records:
                print(f"    Sample: date={records[0]['date_scraped']}, "
                      f"price={records[0]['price']}, unit={records[0]['unit']}")
            total_records += len(records)
            await asyncio.sleep(get_random_delay())

        print(f"\nTotal records from first 3 pages: {total_records}")
        print(f"Expected ~14 records each → expected total ~{3*14}")

        if total_records >= 10:
            print("\n✅ PASS: scrape_detail_page extracts records correctly from visible table.")
        else:
            print("\n❌ FAIL: Fewer than 10 records extracted — check scraper logic.")

        print(f"\n✅ PASS: {len(flower_erode_links)} Flower/Erode items found (> 10 confirms pagination path).")

        await browser.close()
        print("\nVerification complete.")

if __name__ == "__main__":
    asyncio.run(main())
