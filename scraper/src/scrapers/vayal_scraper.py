import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def scrape_vayal_flowers(max_retries=3):
    """
    Dynamically discover all flower districts and scrape all pages of data for each.
    Uses a single, robust logic to handle multiple table layouts and pagination.
    """
    data = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a real browser user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            # STEP 1: Discover all available districts for "Flowers"
            logger.info("Discovering all available flower districts...")
            await page.goto("https://vayalagro.com/market-price", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            
            # Robust dropdown detection (find by first option text since IDs/Names are missing)
            cat_select_handle = await page.evaluate_handle('''() => {
                const selects = Array.from(document.querySelectorAll('select'));
                return selects.find(s => s.options[0]?.text.toLowerCase().includes('category'));
            }''')
            cat_select = cat_select_handle.as_element()
            
            if cat_select:
                await cat_select.select_option(label="Flowers")
                logger.info("Category 'Flowers' selected.")
                await page.wait_for_timeout(4000)
            else:
                logger.error("Could not find category dropdown")
                return []
            
            dist_select_handle = await page.evaluate_handle('''() => {
                const selects = Array.from(document.querySelectorAll('select'));
                return selects.find(s => s.options[0]?.text.toLowerCase().includes('district'));
            }''')
            dist_select = dist_select_handle.as_element()

                
            if not dist_select:
                logger.error("Could not find district dropdown")
                return []
                
            available_districts = await dist_select.evaluate('''select => {
                return Array.from(select.options)
                    .filter(opt => opt.value && opt.value !== "" && !opt.text.includes("Select"))
                    .map(opt => opt.text.trim().toLowerCase());
            }''')
            
            # STEP 2: Iterate through each district and scrape the last 7 days
            from datetime import timedelta
            
            for region in available_districts:
                logger.info(f"Starting historical scrape for {region.capitalize()} (Last 7 days)...")
                
                for day_offset in range(7):
                    target_date = (datetime.now() - timedelta(days=day_offset))
                    date_str = target_date.strftime("%Y-%m-%d")
                    
                    for attempt in range(max_retries):
                        try:
                            logger.info(f"Scraping {region.capitalize()} for {date_str} (Attempt {attempt+1})...")
                            await page.goto("https://vayalagro.com/market-price", wait_until="domcontentloaded", timeout=60000)
                            await page.wait_for_timeout(3000)
                            
                            # 1. Select Flowers with extra verification
                            cat_select_handle = await page.evaluate_handle('''() => {
                                const select = Array.from(document.querySelectorAll('select')).find(s => s.options[0]?.text.toLowerCase().includes('category'));
                                if (!select) return null;
                                const flowerOpt = Array.from(select.options).find(o => o.text.toLowerCase() === 'flowers');
                                if (flowerOpt) select.value = flowerOpt.value;
                                select.dispatchEvent(new Event('change', { bubbles: true }));
                                return select;
                            }''')
                            if not cat_select_handle: 
                                logger.error("Category dropdown not found")
                                break
                                
                            await page.wait_for_timeout(3000)
                            
                            # 2. Select District
                            dist_select_handle = await page.evaluate_handle('''(region) => {
                                const select = Array.from(document.querySelectorAll('select')).find(s => s.options[0]?.text.toLowerCase().includes('district'));
                                if (!select) return null;
                                const targetOpt = Array.from(select.options).find(o => o.text.toLowerCase().includes(region.toLowerCase()));
                                if (targetOpt) select.value = targetOpt.value;
                                select.dispatchEvent(new Event('change', { bubbles: true }));
                                return select;
                            }''', region)

                            if not dist_select_handle: break
                            await page.wait_for_timeout(2000)
                            
                            # 3. Set Date
                            await page.fill('input[type="date"]', date_str)
                            
                            # 4. Click Search
                            search_btn = await page.query_selector('button:has-text("Search")')
                            if search_btn:
                                await search_btn.click()
                                await page.wait_for_timeout(5000)
                            
                            page_num = 1
                            last_page_fingerprint = ""
                            
                            while True:
                                # Robust table extraction
                                extract_result = await page.evaluate('''() => {
                                    const tables = Array.from(document.querySelectorAll('table'));
                                    const dataTables = tables.filter(t => t.rows.length >= 2 && t.rows[0].cells.length >= 4);
                                    if (dataTables.length === 0) return { rows: [] };
                                    const bestTable = dataTables.sort((a, b) => b.rows.length - a.rows.length)[0];
                                    return {
                                        rows: Array.from(bestTable.rows).map(tr => {
                                            return Array.from(tr.querySelectorAll('td, th')).map(td => td.innerText.trim());
                                        })
                                    };
                                }''')
                                
                                rows = extract_result['rows']
                                if not rows: break
                                
                                # Safeguard: If we see vegetables, we failed to select "Flowers" correctly
                                veg_keywords = ['tomato', 'ladies finger', 'onion', 'potato', 'carrot', 'beans', 'gourd']
                                sample_text = " ".join([r[0].lower() for r in rows[:10] if len(r) > 0])
                                if any(vk in sample_text for vk in veg_keywords):
                                    logger.warning(f"Vegetable detected in Flower search for {region}. Retrying category selection...")
                                    raise Exception("Incorrect category detected (Vegetables found)")
                                
                                current_fingerprint = "|".join([r[0] for r in rows[:5] if len(r) > 0])
                                if current_fingerprint == last_page_fingerprint: break
                                last_page_fingerprint = current_fingerprint
                                
                                page_items = 0
                                for cells in rows:
                                    if len(cells) < 4: continue
                                    if any(h in cells[0].lower() for h in ['category', 'product', 's.no', 'commodity']): continue
                                    
                                    commodity = cells[0]
                                    city = cells[2] if len(cells) > 2 else region.capitalize()
                                    price = cells[3] if len(cells) > 3 else "0"
                                    unit = cells[4] if len(cells) > 4 else "Kg"
                                    
                                    if "nandhi" in commodity.lower():
                                        logger.info(f"FOUND: {commodity} in {city} on {date_str} at Rs.{price}")
                                    
                                    clean_price = "".join(filter(str.isdigit, price.split('/')[0]))
                                    if not clean_price: clean_price = "0"
                                    
                                    item = {
                                        "category": "Flowers",
                                        "commodity": commodity,
                                        "district": region.capitalize(),
                                        "city": city,
                                        "price": clean_price,
                                        "unit": unit,
                                        "date": date_str,
                                        "scraped_at": datetime.utcnow()
                                    }
                                    data.append(item)
                                    page_items += 1
                                
                                # Pagination - go through all "sides"
                                next_btn_handle = await page.evaluate_handle('''() => {
                                    const els = Array.from(document.querySelectorAll('button, a, li, span.page-link'));
                                    return els.find(el => {
                                        const text = (el.innerText || el.textContent || "").trim();
                                        const isClickable = !el.classList.contains('disabled') && !el.hasAttribute('disabled') && !el.parentElement.classList.contains('disabled');
                                        return (text === '>' || text.toLowerCase() === 'next' || text === '»') && isClickable;
                                    });
                                }''')
                                
                                next_btn = next_btn_handle.as_element()
                                if next_btn:
                                    try:
                                        await next_btn.click(timeout=10000)
                                        await page.wait_for_timeout(4000)
                                        page_num += 1
                                        if page_num > 15: break # Extended limit for "all sides"
                                    except: break
                                else: break
                                
                            break # Success for this date
                        except Exception as e:
                            logger.warning(f"Error on {region} / {date_str}: {e}")
                            if attempt == max_retries - 1: break
                            await page.wait_for_timeout(5000)

                            
            logger.info(f"Total flower items scraped: {len(data)}")
            return data
            
        except Exception as e:
            logger.error(f"Global scraper error: {e}")
            return data
        finally:
            await browser.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scrape_vayal_flowers())
