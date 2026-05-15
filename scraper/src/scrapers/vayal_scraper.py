import logging
import asyncio
from playwright.async_api import async_playwright
from datetime import datetime

logger = logging.getLogger(__name__)

async def scrape_vayal_flowers(max_retries=3):
    url = "https://vayalagro.com/market-price"
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}: Navigating to {url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                # Setting a realistic user agent
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                # Navigate to the page
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for the category dropdown to be visible
                await page.wait_for_timeout(5000)
                
                data = []
                
                # Dynamically get all category options from the dropdown
                categories = await page.evaluate('''() => {
                    const select = document.querySelector('select.selec');
                    if (!select) return [];
                    return Array.from(select.options)
                        .filter(opt => opt.value && opt.value !== "")
                        .map(opt => ({ value: opt.value, text: opt.text.trim() }));
                }''')
                
                if not categories:
                    logger.warning("Could not find any categories in the dropdown.")
                
                for cat in categories:
                    try:
                        logger.info(f"Scraping category: {cat['text']} (value: {cat['value']})")
                        # Select the category
                        await page.evaluate(f'''() => {{
                            const select = document.querySelector('select.selec');
                            if (select) {{
                                select.value = "{cat['value']}";
                                select.dispatchEvent(new Event('change'));
                            }}
                        }}''')
                        
                        await page.wait_for_timeout(4000) # Wait for table to update
                        
                        # Extract the table data
                        await page.wait_for_selector('.table-1-web table', state='attached', timeout=15000)
                        rows = await page.locator('.table-1-web table tr').all()
                        
                        for row in rows:
                            cells = await row.locator('td').all_inner_texts()
                            if len(cells) >= 5:
                                commodity_name = cells[0].strip() if len(cells) > 0 else "Unknown"
                                
                                item = {
                                    "raw_data": cells,
                                    "category": cat['text'],
                                    "commodity": commodity_name,
                                    "district": cells[1].strip() if len(cells) > 1 else "Unknown",
                                    "city": cells[2].strip() if len(cells) > 2 else "Unknown",
                                    "price": cells[3].strip().replace('Rs.', '').strip() if len(cells) > 3 else "0",
                                    "unit": cells[4].strip() if len(cells) > 4 else "Kg",
                                    "date": datetime.now().strftime("%Y-%m-%d"),
                                    "scraped_at": datetime.utcnow()
                                }
                                data.append(item)
                    except Exception as e:
                        logger.warning(f"Error scraping category {cat['text']}: {e}")
                
                await browser.close()
                logger.info(f"Successfully scraped {len(data)} total records across all categories.")
                return data
                
        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {e}")
            await asyncio.sleep(5)
            
    logger.error("Max retries reached. Scraping failed.")
    return []

if __name__ == "__main__":
    # Test run
    data = asyncio.run(scrape_vayal_flowers())
    print(data)
