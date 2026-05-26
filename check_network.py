import asyncio
import sys
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("Launching Chromium to audit network traffic...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Intercept and print request/response logs
        page.on("request", lambda request: print(f">> Request: {request.method} {request.url}"))
        page.on("response", lambda response: print(f"<< Response: {response.status} {response.url}"))
        
        print("Navigating to https://vayalagro.com/market-price ...")
        await page.goto("https://vayalagro.com/market-price", wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        
        print("Network traffic scan finished successfully.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
