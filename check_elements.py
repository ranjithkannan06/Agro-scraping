import asyncio
import sys
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("Launching Chromium browser to audit elements...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://vayalagro.com/market-price", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        
        elements_data = await page.evaluate('''() => {
            const selects = Array.from(document.querySelectorAll("select"));
            const selectAudits = selects.map((s, idx) => {
                return {
                    index: idx,
                    placeholder: s.options[0]?.text || "None",
                    optionCount: s.options.length,
                    options: Array.from(s.options).map(o => o.text.trim())
                };
            });
            
            const buttons = Array.from(document.querySelectorAll("button"));
            const buttonAudits = buttons.map(b => {
                return {
                    text: b.innerText || b.textContent || "",
                    disabled: b.hasAttribute("disabled") || b.classList.contains("disabled-red")
                };
            });
            
            return { selects: selectAudits, buttons: buttonAudits };
        }''')
        
        print("\n--- SELECT DROPDOWN AUDIT ---")
        for sel in elements_data["selects"]:
            print(f"Dropdown #{sel['index']}: Placeholder text = '{sel['placeholder']}', Total Options = {sel['optionCount']}")
            print(f"Options list: {sel['options'][:10]} ...")
            
        print("\n--- BUTTON AUDIT ---")
        for btn in elements_data["buttons"]:
            print(f"Button: text = '{btn['text'].strip()}', Disabled state = {btn['disabled']}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
