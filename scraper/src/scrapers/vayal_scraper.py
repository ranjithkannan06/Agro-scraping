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

    The page renders MULTIPLE <table> elements:
      - Table#0 / #2 : hidden mobile-layout tables (offsetParent=null) with 2 cols (Date, Price/Units)
      - Table#1      : visible desktop table with 6 cols (Category, District, City, Date, Price, Units)
    document.querySelector("table") always returns Table#0 which is invisible, causing
    wait_for_selector to time out. We instead poll for the first VISIBLE table.
    """
    logger.info(f"Scraping historical details from {detail_url}")
    records = []

    try:
        await robust_action(page, "goto", detail_url)

        # Rate-limit: small extra pause after navigation
        await asyncio.sleep(random.uniform(1.0, 2.0))

        # Poll up to 15 s for a visible table with actual data rows to appear.
        # (Do NOT use wait_for_selector("table") — it picks the hidden Table#0.)
        visible_table_found = False
        for _ in range(15):
            found = await page.evaluate('''() => {
                const tables = Array.from(document.querySelectorAll("table"));
                return tables.some(t => t.offsetParent !== null && t.rows.length > 1);
            }''')
            if found:
                visible_table_found = True
                break
            await asyncio.sleep(1.0)

        if not visible_table_found:
            logger.warning(f"No visible data table found at {detail_url} after 15 s — skipping.")
            return records

        # Extract rows from the FIRST VISIBLE table that has the most data rows.
        # For the 6-column desktop layout the headers are:
        #   Category | District | City | Date | Price | Units
        rows_data = await page.evaluate('''() => {
            const tables = Array.from(document.querySelectorAll("table"));
            const visible = tables.filter(t => t.offsetParent !== null && t.rows.length > 1);
            if (!visible.length) return [];
            // Prefer the table with the most rows (the detailed history table)
            const best = visible.reduce((a, b) => (a.rows.length >= b.rows.length ? a : b));
            return Array.from(best.rows).map(row =>
                Array.from(row.querySelectorAll("td, th")).map(cell => cell.innerText.trim())
            );
        }''')

        if not rows_data or len(rows_data) < 2:
            logger.warning(f"No history data found in visible table at {detail_url}")
            return records

        headers = [h.lower() for h in rows_data[0]]
        logger.info(f"Found history headers: {headers}")

        # Detect column indices from header names (handles both 2-col and 6-col layouts)
        date_idx = 0
        price_idx = None
        unit_idx = None

        for idx, h in enumerate(headers):
            if h == "date":
                date_idx = idx
            elif h in ("price", "price/units") or "price" in h:
                if price_idx is None:
                    price_idx = idx
            elif h in ("units", "unit") or "quantity" in h:
                unit_idx = idx
            elif any(x in h for x in ["rate", "modal", "average", "min", "max"]):
                if price_idx is None:
                    price_idx = idx

        # Fallback if price column not detected by name
        if price_idx is None:
            price_idx = 1 if len(headers) > 1 else 0

        for row in rows_data[1:]:
            if len(row) <= date_idx:
                continue

            raw_date = row[date_idx]
            # Skip repeated header rows or non-date values
            if not raw_date or any(
                x in raw_date.lower() for x in ["date", "s.no", "category", "district", "city"]
            ):
                continue

            date_scraped = clean_date_string(raw_date)

            raw_price = row[price_idx] if len(row) > price_idx else ""
            price = parse_price(raw_price)

            # Prefer unit from a dedicated column; fall back to passed-in unit
            extracted_unit = None
            if unit_idx is not None and len(row) > unit_idx:
                extracted_unit = row[unit_idx].strip() or None

            if price is not None:
                record = {
                    "commodity_name": commodity_name,
                    "market_name": market_name,
                    "district": get_standardized_district(district or market_name),
                    "price": price,
                    "unit": extracted_unit or fallback_unit or "Kg",
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
                    logger.info(f"Navigating to clean base page to scan districts for category '{cat}'...")
                    await robust_action(page, "goto", base_url)
                    await page.wait_for_timeout(3000)
                    
                    # Wait for Category dropdown options to populate dynamically
                    category_loaded = False
                    for _ in range(20):
                        options_len = await page.evaluate('''() => {
                            const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("category"));
                            return select ? select.options.length : 0;
                        }''')
                        if options_len > 1:
                            category_loaded = True
                            break
                        await page.wait_for_timeout(500)
                    
                    if not category_loaded:
                        logger.warning(f"Category options failed to load for '{cat}'. Skipping.")
                        continue
                        
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
                    
                    # Wait for district options to load (more than 1 option in District dropdown)
                    logger.info(f"Waiting for District dropdown to populate for category '{cat}'...")
                    district_loaded = False
                    for _ in range(20):
                        dist_len = await page.evaluate('''() => {
                            const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("district"));
                            return select ? select.options.length : 0;
                        }''')
                        if dist_len > 1:
                            district_loaded = True
                            break
                        await page.wait_for_timeout(500)
                    
                    if not district_loaded:
                        logger.warning(f"District options failed to load for Category '{cat}'. Skipping.")
                        continue
                    
                    # Fetch districts loaded for this category
                    districts = await page.evaluate('''() => {
                        const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("district"));
                        if (!select) return [];
                        return Array.from(select.options).filter(o => o.value && o.value !== "0" && o.value !== "").map(o => o.text.trim());
                    }''')
                    
                    logger.info(f"Discovered districts enabled for {cat}: {districts}")
                    
                    for dist in districts:
                        try:
                            # Return to clean base_url for each district form execution to avoid results page component state issues
                            logger.info(f"Form execution: Category={cat}, District={dist}. Navigating to base page...")
                            await robust_action(page, "goto", base_url)
                            await page.wait_for_timeout(3000)
                            
                            # Select Category again on clean page
                            await page.evaluate('''(c) => {
                                const select = Array.from(document.querySelectorAll("select")).find(s => s.options[0]?.text.toLowerCase().includes("category"));
                                if (select) {
                                    const opt = Array.from(select.options).find(o => o.text.trim().toLowerCase() === c.toLowerCase());
                                    if (opt) {
                                        select.value = opt.value;
                                        select.dispatchEvent(new Event("change", { bubbles: true }));
                                    }
                                }
                            }''', cat)
                            
                            # Wait for district options to load
                            await page.wait_for_timeout(2000)
                            
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
                            city_loaded = False
                            for _ in range(20): # Poll up to 10 seconds
                                city_len = await page.evaluate('''() => {
                                    const select = Array.from(document.querySelectorAll("select")).find(s => {
                                        const firstOptText = s.options[0]?.text.toLowerCase() || "";
                                        return !firstOptText.includes("category") && 
                                               !firstOptText.includes("district") && 
                                               firstOptText !== "en" && 
                                               firstOptText !== "tn" && 
                                               (firstOptText.includes("all") || firstOptText.includes("city") || firstOptText.includes("market") || Array.from(s.options).some(o => o.value === "0"));
                                    });
                                    return select ? select.options.length : 0;
                                }''')
                                if city_len > 1:
                                    city_loaded = True
                                    break
                                await page.wait_for_timeout(500)
                            
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
                                # Smart wait: poll until at least one result link appears in the
                                # listing table, rather than sleeping a fixed 4 s.
                                try:
                                    await page.wait_for_function(
                                        "() => document.querySelectorAll('table td a').length > 0",
                                        timeout=10000
                                    )
                                except Exception:
                                    pass
                                await asyncio.sleep(1.5)  # small extra buffer for full render
                                
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
                                        # Capture the current first link URL so we can detect
                                        # when the DOM actually updates after the click.
                                        pre_click_first = await page.evaluate(
                                            "() => document.querySelector('table td a')?.href || ''"
                                        )
                                        await next_btn.click()
                                        # Wait for the first visible link to change URL (real DOM
                                        # update), rather than sleeping a fixed 3 s.
                                        try:
                                            await page.wait_for_function(
                                                "(url) => document.querySelector('table td a')?.href !== url",
                                                arg=pre_click_first,
                                                timeout=8000
                                            )
                                        except Exception:
                                            # Timeout means content did not change — end of pages
                                            logger.info("Content unchanged after Next click — treating as last page.")
                                            break
                                        await asyncio.sleep(1.0)  # settle render
                                        page_num += 1
                                        if page_num > 20:
                                            logger.warning("Pagination safety cap (20 pages) reached.")
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
