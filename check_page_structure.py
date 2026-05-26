import asyncio
import sys
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("Launching Chromium to test dropdown page reactivity...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://vayalagro.com/market-price", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        
        # 1. Select category "Flowers"
        print("Selecting 'Flowers' category option...")
        await page.evaluate('''() => {
            const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("category"));
            if (select) {
                const opt = Array.from(select.options).find(o => o.text.trim().toLowerCase() === "flowers");
                if (opt) {
                    select.value = opt.value;
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }
        }''')
        
        await page.wait_for_timeout(3000)
        
        # 2. Get loaded districts
        districts = await page.evaluate('''() => {
            const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("district"));
            if (!select) return [];
            return Array.from(select.options).map(o => o.text.trim());
        }''')
        print(f"Districts loaded for Flowers: {districts}")
        
        if len(districts) > 1:
            test_dist = districts[1]
            print(f"Selecting test district '{test_dist}'...")
            await page.evaluate('''(d) => {
                const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("district"));
                if (select) {
                    const opt = Array.from(select.options).find(o => o.text.trim() === d);
                    if (opt) {
                        select.value = opt.value;
                        select.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                }
            }''', test_dist)
            
            await page.wait_for_timeout(2000)
            
            # Select "All" city
            await page.evaluate('''() => {
                const select = Array.from(document.querySelectorAll("select"))[4];
                if (select) {
                    select.value = "0";
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }''')
            
            await page.wait_for_timeout(1000)
            
            # Check button state
            btn_state = await page.evaluate('''() => {
                const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.toLowerCase().includes("search") || b.classList.contains("catgory-button"));
                return btn ? { text: btn.innerText.trim(), disabled: btn.hasAttribute("disabled") } : null;
            }''')
            print(f"Reactivity check - Search button state: {btn_state}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
