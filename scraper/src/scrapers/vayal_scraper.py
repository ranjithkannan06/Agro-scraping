import asyncio
import logging
import random
import os
import sys
import traceback
from datetime import datetime, timedelta
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Load environment variables from project root .env file
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    load_dotenv(dotenv_path)
except ImportError:
    pass

# Allow Windows event loop compatibility for async subprocesses immediately upon import
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure root-level logging for scraper.log as well as stdout
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("vayal_scraper")

# Ensure parent and scraper directories are on path to allow clean imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from database import Database
from google_sheets import GoogleSheetsService

# Anti-Detection User Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
]

def get_random_delay():
    return random.uniform(1.5, 3.5)

async def robust_action(page, action_type, target, *args, max_retries=3, **kwargs):
    """
    Executes a Playwright page action (goto, click, fill, select_option) 
    with exponential backoff retries and explicit error capturing.
    """
    url_context = page.url
    for attempt in range(1, max_retries + 1):
        try:
            delay = get_random_delay()
            await asyncio.sleep(delay)
            
            if action_type == "goto":
                logger.info(f"Navigating to {target} (Attempt {attempt}/{max_retries})...")
                # Wait until domcontentloaded to handle heavy JS pages gracefully
                response = await page.goto(target, wait_until="domcontentloaded", timeout=45000)
                return response
            elif action_type == "click":
                logger.info(f"Clicking element {target} (Attempt {attempt}/{max_retries})...")
                await page.click(target, timeout=15000, *args, **kwargs)
                return True
            elif action_type == "fill":
                value = args[0] if args else kwargs.get("value", "")
                logger.info(f"Filling input {target} with {value} (Attempt {attempt}/{max_retries})...")
                await page.fill(target, value, timeout=15000)
                return True
            elif action_type == "select":
                label = kwargs.get("label")
                value = kwargs.get("value")
                logger.info(f"Selecting option {target} with label={label}/value={value} (Attempt {attempt}/{max_retries})...")
                if label:
                    await page.select_option(target, label=label, timeout=15000)
                elif value:
                    await page.select_option(target, value=value, timeout=15000)
                return True
            else:
                raise ValueError(f"Unknown action type: {action_type}")
        except PlaywrightTimeoutError as te:
            logger.warning(f"Timeout occurred executing '{action_type}' on '{target}' at url {url_context}: {te}")
        except Exception as e:
            logger.warning(f"Error executing '{action_type}' on '{target}' at url {url_context}: {e}")
            
        if attempt < max_retries:
            backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
            logger.info(f"Retrying action in {backoff:.2f} seconds...")
            await asyncio.sleep(backoff)
            
    logger.error(f"Failed to execute '{action_type}' on '{target}' at url {url_context} after {max_retries} attempts.")
    raise Exception(f"Action '{action_type}' on '{target}' failed permanently.")

def parse_price(value_str):
    """Extracts integer price values from raw string formats (e.g. 'Rs. 250/Kg' -> 250)."""
    if not value_str:
        return None
    try:
        # Strip currency symbols and split on unit slash or spacing
        clean_str = value_str.split('/')[0].split('Per')[0]
        # Retain only digits
        digits = "".join(filter(str.isdigit, clean_str))
        return int(digits) if digits else None
    except Exception:
        return None

DISTRICT_MAPPING = {
    "sathyamangalam": "Erode",
    "namakkal city": "Namakkal",
    "namakkal": "Namakkal",
    "chetupattu": "Thiruvannamalai",
    "salem": "Salem",
    "coimbatore": "Coimbatore",
    "dindigul": "Dindigul",
    "theni": "Theni",
    "thenkaasi": "Thenkaasi",
}

def get_standardized_district(city_or_district):
    if not city_or_district:
        return "Tamilnadu"
    val = city_or_district.strip().lower()
    return DISTRICT_MAPPING.get(val, city_or_district.strip())

def clean_date_string(date_str):
    """Converts a parsed date string into YYYY-MM-DD format."""
    if not date_str:
        return None
    # Common formats: DD-MM-YYYY, YYYY-MM-DD
    date_str = date_str.strip()
    try:
        # Check DD-MM-YYYY
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_str
    except Exception:
        return date_str

async def scrape_detail_page(page, detail_url, category, commodity_name, market_name, district, fallback_unit):
    """
    Loads an individual commodity history subpage and extracts the 14-day 
    historical prices table.
    """
    logger.info(f"Scraping historical details from {detail_url}")
    records = []
    
    try:
        await robust_action(page, "goto", detail_url)
        # Wait up to 10 seconds for the history table to render in the DOM
        await page.wait_for_selector("table", state="attached", timeout=10000)
        
        # Extract rows from the history table
        rows_data = await page.evaluate('''() => {
            const table = document.querySelector("table");
            if (!table) return [];
            return Array.from(table.rows).map(row => 
                Array.from(row.querySelectorAll("td, th")).map(cell => cell.innerText.trim())
            );
        }''')
        
        if not rows_data or len(rows_data) < 2:
            logger.warning(f"No history data found in table at {detail_url}")
            return records

        headers = [h.lower() for h in rows_data[0]]
        logger.info(f"Found history headers: {headers}")
        
        # Try to identify column indices based on headers
        date_idx = 0
        price_idx = None
        
        for idx, h in enumerate(headers):
            if "date" in h:
                date_idx = idx
            elif any(x in h for x in ["price", "rate", "modal", "average", "min", "max"]):
                price_idx = idx
                
        # Fill in defaults if column indices were not found
        if price_idx is None: 
            price_idx = 1 if len(headers) > 1 else 0

        for row in rows_data[1:]:
            if len(row) <= date_idx:
                continue
                
            raw_date = row[date_idx]
            # Skip header repeats or invalid dates
            if not raw_date or any(x in raw_date.lower() for x in ["date", "s.no"]):
                continue
                
            date_scraped = clean_date_string(raw_date)
            
            # Parse price safely
            raw_price = row[price_idx] if len(row) > price_idx else row[1]
            price = parse_price(raw_price)
            
            # If price is successfully extracted, construct standard record
            if price is not None:
                record = {
                    "commodity_name": commodity_name,
                    "market_name": market_name,
                    "district": get_standardized_district(district or market_name),
                    "price": price,
                    "unit": fallback_unit or "Kg",
                    "date_scraped": date_scraped,
                    "source_url": detail_url,
                    "category": category,
                }
                records.append(record)
                
        logger.info(f"Successfully extracted {len(records)} daily records from history page.")
    except Exception as e:
        logger.error(f"Error scraping detail page {detail_url}: {e}")
        
    return records

def get_category_from_url(url):
    if not url:
        return "Other"
    url_lower = url.lower()
    if "flower" in url_lower:
        return "Flowers"
    elif "vegetable" in url_lower:
        return "Vegetables"
    elif "banana" in url_lower:
        return "Banana"
    elif "groundnut" in url_lower:
        return "Groundnut"
    elif "coconut" in url_lower:
        return "Coconut Products"
    elif "cassava" in url_lower:
        return "Cassava"
    elif "garlic" in url_lower:
        return "Garlic"
    elif "turmeric" in url_lower:
        return "Turmeric"
    elif "areca" in url_lower:
        return "Areca Nut"
    elif "cotton" in url_lower:
        return "Cotton"
    elif "maize" in url_lower:
        return "Maize"
    elif "black-gram" in url_lower or "black_gram" in url_lower or "blackgram" in url_lower:
        return "Black gram"
    elif "sesame" in url_lower:
        return "Sesame"
    elif "sugar" in url_lower:
        return "Brown sugar"
    return "Other"

async def scrape_vayal_flowers():
    """
    Main Scraping Function.
    1. Operates headlessly via Playwright.
    2. Implements Direct Link Traversal to bypass dynamic search form outages (supports all categories).
    3. Implements Dropdown Selector Exhaustion (Category -> District -> City) and Pagination as robust pipelines.
    4. Performs database updates and triggers Google Sheets sync inline.
    """
    start_time = datetime.now()
    logger.info(f"Scraper Run Started at {start_time.isoformat()}")
    
    all_scraped_records = []
    
    async with async_playwright() as p:
        # Launch browser in headful mode so the user can visually monitor execution
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        
        # Use random User-Agent
        selected_ua = random.choice(USER_AGENTS)
        context = await browser.new_context(
            user_agent=selected_ua,
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            base_url = "https://vayalagro.com/market-price"
            await robust_action(page, "goto", base_url)
            
            # Pause to let React/Vue application load dynamic components
            await page.wait_for_timeout(4000)
            
            seen_hrefs = set()
            
            # -------------------------------------------------------------
            # MODE A: Direct Link Traversal (Primary Bypass of Outage)
            # -------------------------------------------------------------
            logger.info("Starting Primary Bypass Mode (Direct Link Traversal)...")
            
            # Find all anchor links inside the market price tables on the landing page
            commodity_links = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll("table td a"));
                return links.map(a => {
                    const row = a.closest("tr");
                    if (!row) return null;
                    const cells = Array.from(row.cells).map(td => td.innerText.trim());
                    // Check if it's Table 1 (desktop layout with 6 columns)
                    if (cells.length >= 6) {
                        return {
                            href: a.href,
                            commodity: cells[0] || "",
                            district: cells[1] || "",
                            city: cells[2] || "",
                            unit: cells[4] || "Kg"
                        };
                    } else if (cells.length >= 2) {
                        // Table 0 (mobile responsive layout with 2 columns)
                        // Cell 0: 'Sendumalli Sathyamangalam', Cell 1: 'Rs. 80/Kg View'
                        // Split by multiple spaces to separate commodity and city
                        const nameParts = (cells[0] || "").split(/\\s{2,}/);
                        const commName = nameParts[0] || cells[0];
                        const cityName = nameParts[1] || "Sathyamangalam";
                        return {
                            href: a.href,
                            commodity: commName,
                            district: cityName,
                            city: cityName,
                            unit: "Kg"
                        };
                    }
                    return null;
                }).filter(x => x !== null && x.href !== "");
            }''')
            
            # Direct link traversal for all discovered links
            unique_links = []
            for link in commodity_links:
                if link["href"] not in seen_hrefs:
                    seen_hrefs.add(link["href"])
                    unique_links.append(link)
            
            logger.info(f"Discovered {len(unique_links)} unique commodity links on the landing page.")
            
            # Follow detail subpages and extract history tables
            for idx, link_meta in enumerate(unique_links):
                detail_url = link_meta["href"]
                commodity = link_meta["commodity"] or "Unknown Commodity"
                market = link_meta["city"] or link_meta["district"] or "Unknown Market"
                unit = link_meta["unit"] or "Kg"
                category = get_category_from_url(detail_url)
                
                # Scrape history detail table
                history_records = await scrape_detail_page(
                    page, detail_url, category, commodity, market, link_meta.get("district", market), unit
                )
                all_scraped_records.extend(history_records)
                
                # Rest delay to prevent hitting target rate limiters
                await asyncio.sleep(get_random_delay())
            
            # -------------------------------------------------------------
            # MODE B: Dropdown Selector Exhaustion & Pagination (Fallback Pipeline)
            # -------------------------------------------------------------
            logger.info(f"Returning to {base_url} for Form Execution Mode...")
            await robust_action(page, "goto", base_url)
            await page.wait_for_timeout(3000)

            logger.info("Checking if interactive search selectors are online...")
            
            selectors_found = await page.evaluate('''() => {
                const selects = Array.from(document.querySelectorAll("select"));
                const hasCategory = selects.some(s => s.options[0]?.text.toLowerCase().includes("category"));
                const hasDistrict = selects.some(s => s.options[0]?.text.toLowerCase().includes("district"));
                return hasCategory && hasDistrict;
            }''')
            
            if selectors_found:
                logger.info("Dynamic search form selectors are online. Initializing dropdown options scan...")
                
                categories_to_run = [
                    "Flowers", "Vegetables", "Banana", "Groundnut", "Coconut Products", "Cassava", 
                    "Garlic", "Turmeric", "Areca Nut", "Cotton", "Maize", "Black gram", "Sesame", "Brown sugar"
                ]
                
                for cat in categories_to_run:
                    logger.info(f"Selecting '{cat}' category in dropdown...")
                    
                    # Select Category option
                    cat_selected = await page.evaluate('''(c) => {
                        const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("category"));
                        if (select) {
                            const opt = Array.from(select.options).find(o => o.text.trim().toLowerCase() === c.toLowerCase());
                            if (opt) {
                                select.value = opt.value;
                                select.dispatchEvent(new Event("change", { bubbles: true }));
                                return true;
                            }
                        }
                        return false;
                    }''', cat)
                    
                    if not cat_selected:
                        logger.warning(f"Category '{cat}' not found in dropdown. Skipping.")
                        continue
                    
                    # Wait 3 seconds for the district dropdown to be enabled and loaded
                    await page.wait_for_timeout(3000)
                    
                    # Fetch districts loaded for this category
                    districts = await page.evaluate('''() => {
                        const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("district"));
                        if (!select) return [];
                        return Array.from(select.options).filter(o => o.value && o.value !== "0" && o.value !== "").map(o => o.text.trim());
                    }''')
                    
                    logger.info(f"Discovered districts enabled for {cat}: {districts}")
                    
                    for dist in districts:
                        try:
                            logger.info(f"Form execution: Category={cat}, District={dist}")
                            
                            # Select District
                            await page.evaluate('''(d) => {
                                const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("district"));
                                if (select) {
                                    const opt = Array.from(select.options).find(o => o.text.trim() === d);
                                    if (opt) {
                                        select.value = opt.value;
                                        select.dispatchEvent(new Event("change", { bubbles: true }));
                                    }
                                }
                            }''', dist)
                            
                            # Wait for City dropdown to load/enable
                            logger.info("Waiting for City dropdown to populate...")
                            await page.wait_for_timeout(2000)
                            
                            await page.evaluate('''() => {
                                const select = Array.from(document.querySelectorAll("select")).find(s => {
                                    const firstOptText = s.options[0]?.text.toLowerCase() || "";
                                    return !firstOptText.includes("category") && 
                                           !firstOptText.includes("district") && 
                                           firstOptText !== "en" && 
                                           firstOptText !== "tn" && 
                                           (firstOptText.includes("all") || firstOptText.includes("city") || firstOptText.includes("market") || Array.from(s.options).some(o => o.value === "0"));
                                });
                                if (select) {
                                    select.value = "0"; // Select "All"
                                    select.dispatchEvent(new Event("change", { bubbles: true }));
                                }
                            }''')
                            
                            # Wait up to 5 seconds for Search button to be enabled
                            logger.info("Verifying search button activation...")
                            search_btn_selector = 'button.catgory-button, button:has-text("Search")'
                            search_btn_enabled = False
                            
                            for _ in range(10): # Poll every 500ms
                                is_disabled = await page.evaluate('''(sel) => {
                                    const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.toLowerCase().includes("search") || b.classList.contains("catgory-button"));
                                    return btn ? btn.hasAttribute("disabled") || btn.classList.contains("disabled-red") : true;
                                }''', search_btn_selector)
                                if not is_disabled:
                                    search_btn_enabled = True
                                    break
                                await page.wait_for_timeout(500)
                            
                            if search_btn_enabled:
                                logger.info(f"Search button enabled for District={dist}. Clicking...")
                                await page.evaluate('''() => {
                                    const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.toLowerCase().includes("search") || b.classList.contains("catgory-button"));
                                    if (btn) btn.click();
                                }''')
                                await page.wait_for_timeout(4000)
                                
                                # Loop through listing pagination
                                page_num = 1
                                last_fingerprint = ""
                                
                                while True:
                                    logger.info(f"Scraping dynamic listing page {page_num} for district {dist}...")
                                    
                                    # Gather detail links from listing page
                                    listing_links = await page.evaluate('''() => {
                                        const links = Array.from(document.querySelectorAll("table tbody tr td a, table tr td a"));
                                        return links.map(a => {
                                            const row = a.closest("tr");
                                            if (!row) return null;
                                            const cells = Array.from(row.cells).map(td => td.innerText.trim());
                                            
                                            let commodity = "";
                                            let city = "";
                                            let unit = "Kg";
                                            
                                            if (cells.length >= 6) {
                                                commodity = cells[0] || "";
                                                city = cells[2] || "";
                                                unit = cells[4] || "Kg";
                                            } else if (cells.length >= 2) {
                                                const nameParts = (cells[0] || "").split(/\\s{2,}/);
                                                commodity = nameParts[0] || cells[0];
                                                city = nameParts[1] || "Sathyamangalam";
                                            }
                                            
                                            return {
                                                href: a.href,
                                                commodity: commodity,
                                                city: city,
                                                unit: unit
                                            };
                                        }).filter(x => x !== null && x.href !== "");
                                    }''')
                                    
                                    if not listing_links:
                                        break
                                        
                                    # Check fingerprint to avoid infinite pagination loops
                                    fingerprint = "|".join([l["href"] for l in listing_links[:5]])
                                    if fingerprint == last_fingerprint:
                                        logger.info("Fingerprint match. End of pagination reached.")
                                        break
                                    last_fingerprint = fingerprint
                                    
                                    for l_meta in listing_links:
                                        if l_meta["href"] not in seen_hrefs:
                                            seen_hrefs.add(l_meta["href"])
                                            # Traverse detail subpage
                                            l_records = await scrape_detail_page(
                                                page, l_meta["href"], cat, l_meta["commodity"], 
                                                l_meta["city"], dist, l_meta["unit"]
                                            )
                                            all_scraped_records.extend(l_records)
                                            await asyncio.sleep(get_random_delay())
                                                
                                    # Pagination: click Next button
                                    next_btn_handle = await page.evaluate_handle('''() => {
                                        const els = Array.from(document.querySelectorAll("button, a, li, span.page-link"));
                                        return els.find(el => {
                                            const text = (el.innerText || el.textContent || "").trim();
                                            const isClickable = !el.classList.contains("disabled") && !el.hasAttribute("disabled") && !el.parentElement.classList.contains("disabled");
                                            return (text === ">" || text.toLowerCase() === "next" || text === "»") && isClickable;
                                        });
                                    }''')
                                    
                                    next_btn = next_btn_handle.as_element()
                                    if next_btn:
                                        logger.info(f"Clicking pagination Next button (page {page_num} -> {page_num+1})")
                                        await next_btn.click()
                                        await page.wait_for_timeout(3000)
                                        page_num += 1
                                        if page_num > 10:
                                            break
                                    else:
                                        logger.info("Pagination Next button not found or is disabled.")
                                        break
                            else:
                                logger.warning(f"Search button not enabled for District={dist} in Category={cat}. Skipping.")
                        except Exception as comb_err:
                            logger.error(f"Error scanning option comb for {cat} in district {dist}: {comb_err}")
            else:
                logger.info("Dynamic search form dropdowns are currently offline/disabled. Standard Form Fallback skipped.")
        except Exception as e:
            logger.error(f"Global scraper run exception encountered: {e}")
            traceback.print_exc()
        finally:
            await browser.close()
            
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(
        f"Scraper Run Ended at {end_time.isoformat()}. "
        f"Duration: {duration.total_seconds():.2f} seconds. "
        f"Extracted Records Count: {len(all_scraped_records)}"
    )
    
    # -------------------------------------------------------------
    # Step 5: Save to Database & Google Sheets Inline
    # -------------------------------------------------------------
    if all_scraped_records:
        try:
            logger.info("Connecting to Database inline to save scraped records...")
            db = Database()
            await db.connect()
            await db.insert_prices(all_scraped_records)
            await db.close()
            logger.info("Database storage complete.")
        except Exception as db_err:
            logger.error(f"Failed to persist scraped data in database: {db_err}")
            
        try:
            logger.info("Syncing flowers/commodities data directly to Google Sheets inline...")
            sheets = GoogleSheetsService()
            sync_success = sheets.append_records(all_scraped_records)
            if sync_success:
                logger.info("Google Sheets synchronization completed successfully.")
            else:
                logger.warning("Google Sheets sync completed with errors or was skipped.")
        except Exception as sheets_err:
            logger.error(f"Failed to sync scraped data to Google Sheets: {sheets_err}")
            
        # Notify backend so it triggers live WebSocket and push alerts
        try:
            logger.info("Triggering backend notification alerts...")
            import aiohttp
            async with aiohttp.ClientSession() as session:
                serializable_data = []
                for item in all_scraped_records:
                    serializable_item = {}
                    for k, v in item.items():
                        if isinstance(v, datetime):
                            serializable_item[k] = v.isoformat()
                        else:
                            serializable_item[k] = v
                    serializable_data.append(serializable_item)
                
                # Check backend endpoint and resolve local vs Docker address
                raw_backend_url = os.getenv("BACKEND_INTERNAL_URL", "http://127.0.0.1:8000")
                if not os.path.exists('/.dockerenv') and "http://backend:" in raw_backend_url:
                    backend_url = raw_backend_url.replace("http://backend:", "http://127.0.0.1:")
                    logger.info(f"Local host environment detected. Resolving Docker backend alias to: {backend_url}")
                else:
                    backend_url = raw_backend_url
                await session.post(
                    f"{backend_url}/api/internal/notify",
                    json={"items": serializable_data},
                    timeout=10
                )
                await session.post(
                    f"{backend_url}/api/internal/broadcast",
                    json={"items": serializable_data},
                    timeout=10
                )
                logger.info("Backend notifications dispatched successfully.")
        except Exception as notify_err:
            logger.error(f"Failed to dispatch backend notifications: {notify_err}")
    else:
        logger.warning("No records were scraped in this run. Sync skipped.")
        
    return all_scraped_records

if __name__ == "__main__":
    try:
        # Allow Windows event loop compatibility for async subprocesses
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(scrape_vayal_flowers())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Manual scraper execution terminated.")
