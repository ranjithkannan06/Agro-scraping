"""Vayal Agro source adapter for collecting market-price records."""

import asyncio
from datetime import datetime
import logging
import os
import random
import sys
import traceback

from playwright.async_api import async_playwright

try:
    from dotenv import load_dotenv

    dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    load_dotenv(dotenv_path)
except ImportError:
    pass

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("vayal_scraper")

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from config.constants import VAYAL_CATEGORIES, VAYAL_USER_AGENTS
from parser.extractor import (
    click_next_page,
    click_search_when_enabled,
    extract_market_links,
    get_category_from_url,
    get_district_options,
    get_random_delay,
    robust_action,
    scrape_detail_page,
    select_all_cities,
    select_dropdown_by_text,
    selectors_are_online,
    wait_for_dropdown_options,
)


async def scrape_vayal_flowers(force=False, persist=None):
    """
    Collect Vayal Agro price history records.

    This collector always returns in-memory records only. Persistence is owned by
    the ETL pipeline final stages in main.py.
    """
    if persist is not None:
        logger.warning("The persist argument is deprecated and ignored by the ETL collector.")

    start_time = datetime.now()
    logger.info("Scraper run started at %s", start_time.isoformat())

    scraped_today_keys = set()
    if force:
        logger.info("Force flag enabled for collection. Pipeline deduplication still runs later.")
    all_records = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context(
            user_agent=random.choice(VAYAL_USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            base_url = os.getenv("SCRAPER_SOURCE_URL", "https://vayalagro.com/market-price")
            seen_hrefs = set()

            await robust_action(page, "goto", base_url)
            await page.wait_for_timeout(4000)

            direct_records = await _collect_direct_links(page, seen_hrefs, scraped_today_keys, force)
            all_records.extend(direct_records)

            form_records = await _collect_form_results(page, base_url, seen_hrefs, scraped_today_keys, force)
            all_records.extend(form_records)
        except Exception as exc:
            logger.error("Global scraper run exception encountered: %s", exc)
            traceback.print_exc()
        finally:
            await browser.close()

    duration = datetime.now() - start_time
    logger.info(
        "Scraper run ended. Duration: %.2fs. Extracted records: %s",
        duration.total_seconds(),
        len(all_records),
    )

    logger.info("Collection-only mode complete. Persistence skipped for ETL pipeline.")
    return all_records


async def _collect_direct_links(page, seen_hrefs: set, scraped_today_keys: set, force: bool):
    logger.info("Starting direct link traversal mode.")
    records = []
    unique_links = []

    for link in await extract_market_links(page):
        if link["href"] not in seen_hrefs:
            seen_hrefs.add(link["href"])
            unique_links.append(link)

    logger.info("Discovered %s unique commodity links on the landing page.", len(unique_links))
    for link_meta in unique_links:
        detail_records = await _scrape_link_history(page, link_meta, get_category_from_url(link_meta["href"]), scraped_today_keys, force)
        records.extend(detail_records)
        await asyncio.sleep(get_random_delay())
    return records


async def _collect_form_results(page, base_url: str, seen_hrefs: set, scraped_today_keys: set, force: bool):
    logger.info("Starting dropdown form traversal mode.")
    records = []

    await robust_action(page, "goto", base_url)
    await page.wait_for_timeout(3000)
    if not await selectors_are_online(page):
        logger.info("Dynamic search form dropdowns are offline. Form traversal skipped.")
        return records

    for category in VAYAL_CATEGORIES:
        category_records = await _collect_category_results(
            page,
            base_url,
            category,
            seen_hrefs,
            scraped_today_keys,
            force,
        )
        records.extend(category_records)
    return records


async def _collect_category_results(page, base_url: str, category: str, seen_hrefs: set, scraped_today_keys: set, force: bool):
    logger.info("Scanning districts for category %s.", category)
    records = []

    await robust_action(page, "goto", base_url)
    await page.wait_for_timeout(3000)
    if not await wait_for_dropdown_options(page, "category"):
        logger.warning("Category options failed to load for %s.", category)
        return records
    if not await select_dropdown_by_text(page, "category", category):
        logger.warning("Category %s not found in dropdown.", category)
        return records
    if not await wait_for_dropdown_options(page, "district"):
        logger.warning("District options failed to load for category %s.", category)
        return records

    for district in await get_district_options(page):
        district_records = await _collect_district_results(
            page,
            base_url,
            category,
            district,
            seen_hrefs,
            scraped_today_keys,
            force,
        )
        records.extend(district_records)
    return records


async def _collect_district_results(page, base_url: str, category: str, district: str, seen_hrefs: set, scraped_today_keys: set, force: bool):
    logger.info("Scanning category=%s district=%s.", category, district)
    records = []

    try:
        await robust_action(page, "goto", base_url)
        await page.wait_for_timeout(3000)
        await select_dropdown_by_text(page, "category", category)
        await page.wait_for_timeout(2000)
        await select_dropdown_by_text(page, "district", district)
        if not await select_all_cities(page):
            logger.warning("City dropdown did not load for category=%s district=%s.", category, district)
            return records
        if not await click_search_when_enabled(page):
            logger.warning("Search button was not enabled for category=%s district=%s.", category, district)
            return records

        try:
            await page.wait_for_function("() => document.querySelectorAll('table td a').length > 0", timeout=10000)
        except Exception:
            pass
        await asyncio.sleep(1.5)

        page_num = 1
        last_fingerprint = ""
        while True:
            listing_links = await extract_market_links(page)
            fingerprint = "|".join(link["href"] for link in listing_links[:5])
            if not listing_links or fingerprint == last_fingerprint:
                break
            last_fingerprint = fingerprint

            for link_meta in listing_links:
                if link_meta["href"] in seen_hrefs:
                    continue
                seen_hrefs.add(link_meta["href"])
                detail_records = await _scrape_link_history(page, link_meta, category, scraped_today_keys, force, district)
                records.extend(detail_records)
                await asyncio.sleep(get_random_delay())

            if page_num >= 20 or not await click_next_page(page):
                break
            page_num += 1
    except Exception as exc:
        logger.error("Error scanning category=%s district=%s: %s", category, district, exc)
    return records


async def _scrape_link_history(page, link_meta: dict, category: str, scraped_today_keys: set, force: bool, district_override: str | None = None):
    commodity = link_meta.get("commodity") or "Unknown Commodity"
    market = link_meta.get("city") or link_meta.get("district") or district_override or "Unknown Market"
    district = district_override or link_meta.get("district", market)
    if not force and (commodity, market) in scraped_today_keys:
        logger.info("Skipping %s at %s because it was already scraped today.", commodity, market)
        return []
    return await scrape_detail_page(
        page,
        link_meta["href"],
        category,
        commodity,
        market,
        district,
        link_meta.get("unit", "Kg"),
    )


if __name__ == "__main__":
    try:
        import argparse

        parser = argparse.ArgumentParser(description="HarvestHub Vayal Agro collector")
        parser.add_argument("--force", action="store_true", help="Force scrape all records")
        args = parser.parse_args()
        asyncio.run(scrape_vayal_flowers(force=args.force))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Manual scraper execution terminated.")
