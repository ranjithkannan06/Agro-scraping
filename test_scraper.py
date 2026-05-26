import asyncio
import sys
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("Launching headless Chromium...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to https://vayalagro.com/market-price ...")
        await page.goto("https://vayalagro.com/market-price", wait_until="domcontentloaded", timeout=45000)
        
        print("Waiting for page content to load...")
        await page.wait_for_timeout(5000)
        
        content = await page.content()
        with open("vayal_dump.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Successfully saved page HTML dump to vayal_dump.html!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
