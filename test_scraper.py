import asyncio
from playwright.async_api import async_playwright

async def dump_html():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        print("Navigating...")
        await page.goto('https://vayalagro.com/market-price', wait_until="domcontentloaded", timeout=60000)
        print("Waiting 10s...")
        await page.wait_for_timeout(10000)
        print("Getting content...")
        html = await page.content()
        with open("vayal_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Dumped to vayal_dump.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(dump_html())
