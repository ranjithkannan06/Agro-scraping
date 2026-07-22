"""Playwright extraction helpers for Vayal Agro market pages."""

import asyncio
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from config.constants import DEFAULT_RETRY_ATTEMPTS, VAYAL_DISTRICT_MAPPING

logger = logging.getLogger("vayal_extractor")

def get_random_delay() -> float:
    return random.uniform(1.5, 3.5)


async def robust_action(page, action_type: str, target: str, *args, max_retries: int = DEFAULT_RETRY_ATTEMPTS, **kwargs):
    """Execute a Playwright action with retry and backoff."""
    url_context = page.url
    for attempt in range(1, max_retries + 1):
        try:
            await asyncio.sleep(get_random_delay())
            if action_type == "goto":
                return await page.goto(target, wait_until="domcontentloaded", timeout=45000)
            if action_type == "click":
                await page.click(target, timeout=15000, *args, **kwargs)
                return True
            if action_type == "fill":
                await page.fill(target, args[0] if args else kwargs.get("value", ""), timeout=15000)
                return True
            if action_type == "select":
                if kwargs.get("label"):
                    await page.select_option(target, label=kwargs["label"], timeout=15000)
                elif kwargs.get("value"):
                    await page.select_option(target, value=kwargs["value"], timeout=15000)
                return True
            raise ValueError(f"Unknown action type: {action_type}")
        except PlaywrightTimeoutError as exc:
            logger.warning("Timeout during %s on %s at %s: %s", action_type, target, url_context, exc)
        except Exception as exc:
            logger.warning("Error during %s on %s at %s: %s", action_type, target, url_context, exc)
        if attempt < max_retries:
            await asyncio.sleep((2**attempt) + random.uniform(0.5, 1.5))
    raise RuntimeError(f"Action {action_type!r} on {target!r} failed after {max_retries} attempts")


def parse_price(value_str: Any) -> int | None:
    if not value_str:
        return None
    clean_str = str(value_str).split("/")[0].split("Per")[0]
    digits = "".join(filter(str.isdigit, clean_str))
    return int(digits) if digits else None


def clean_date_string(date_str: Any) -> str | None:
    if not date_str:
        return None
    text = str(date_str).strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def get_standardized_district(city_or_district: str | None) -> str:
    if not city_or_district:
        return "Tamilnadu"
    val = city_or_district.strip().lower()
    return VAYAL_DISTRICT_MAPPING.get(val, city_or_district.strip())


def get_category_from_url(url: str | None) -> str:
    if not url:
        return "Other"
    url_lower = url.lower()
    category_markers = [
        ("flower", "Flowers"),
        ("vegetable", "Vegetables"),
        ("banana", "Banana"),
        ("groundnut", "Groundnut"),
        ("coconut", "Coconut Products"),
        ("cassava", "Cassava"),
        ("garlic", "Garlic"),
        ("turmeric", "Turmeric"),
        ("areca", "Areca Nut"),
        ("cotton", "Cotton"),
        ("maize", "Maize"),
        ("sesame", "Sesame"),
        ("sugar", "Brown sugar"),
    ]
    if any(marker in url_lower for marker in ("black-gram", "black_gram", "blackgram")):
        return "Black gram"
    for marker, category in category_markers:
        if marker in url_lower:
            return category
    return "Other"


async def extract_market_links(page) -> List[Dict[str, str]]:
    """Extract commodity detail links from visible market listing tables."""
    return await page.evaluate(
        """() => {
            const links = Array.from(document.querySelectorAll("table tbody tr td a, table tr td a"));
            return links.map(a => {
                const row = a.closest("tr");
                if (!row) return null;
                const cells = Array.from(row.cells).map(td => td.innerText.trim());
                if (cells.length >= 6) {
                    return {href: a.href, commodity: cells[0] || "", district: cells[1] || "", city: cells[2] || "", unit: cells[4] || "Kg"};
                }
                if (cells.length >= 2) {
                    const nameParts = (cells[0] || "").split(/\\s{2,}/);
                    return {href: a.href, commodity: nameParts[0] || cells[0], district: nameParts[1] || "Sathyamangalam", city: nameParts[1] || "Sathyamangalam", unit: "Kg"};
                }
                return null;
            }).filter(x => x !== null && x.href !== "");
        }"""
    )


async def selectors_are_online(page) -> bool:
    return await page.evaluate(
        """() => {
            const selects = Array.from(document.querySelectorAll("select"));
            const hasCategory = selects.some(s => s.options[0]?.text.toLowerCase().includes("category"));
            const hasDistrict = selects.some(s => s.options[0]?.text.toLowerCase().includes("district"));
            return hasCategory && hasDistrict;
        }"""
    )


async def wait_for_dropdown_options(page, placeholder: str, minimum_count: int = 2) -> bool:
    for _ in range(20):
        options_len = await page.evaluate(
            """(label) => {
                const select = Array.from(document.querySelectorAll("select"))
                    .find(s => s.options[0]?.text.toLowerCase().includes(label));
                return select ? select.options.length : 0;
            }""",
            placeholder.lower(),
        )
        if options_len >= minimum_count:
            return True
        await page.wait_for_timeout(500)
    return False


async def select_dropdown_by_text(page, placeholder: str, value: str) -> bool:
    return await page.evaluate(
        """({placeholder, value}) => {
            const select = Array.from(document.querySelectorAll("select"))
                .find(s => s.options[0]?.text.toLowerCase().includes(placeholder));
            if (!select) return false;
            const opt = Array.from(select.options).find(o => o.text.trim().toLowerCase() === value.toLowerCase());
            if (!opt) return false;
            select.value = opt.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            return true;
        }""",
        {"placeholder": placeholder.lower(), "value": value},
    )


async def get_district_options(page) -> List[str]:
    return await page.evaluate(
        """() => {
            const select = Array.from(document.querySelectorAll("select"))
                .find(s => s.options[0]?.text.toLowerCase().includes("district"));
            if (!select) return [];
            return Array.from(select.options)
                .filter(o => o.value && o.value !== "0" && o.value !== "")
                .map(o => o.text.trim());
        }"""
    )


async def select_all_cities(page) -> bool:
    city_loaded = False
    for _ in range(20):
        city_len = await page.evaluate(_CITY_SELECT_LENGTH_JS)
        if city_len > 1:
            city_loaded = True
            break
        await page.wait_for_timeout(500)
    if not city_loaded:
        return False
    await page.evaluate(_SELECT_ALL_CITY_JS)
    return True


async def click_search_when_enabled(page) -> bool:
    for _ in range(10):
        is_disabled = await page.evaluate(
            """() => {
                const btn = Array.from(document.querySelectorAll("button"))
                    .find(b => b.innerText.toLowerCase().includes("search") || b.classList.contains("catgory-button"));
                return btn ? btn.hasAttribute("disabled") || btn.classList.contains("disabled-red") : true;
            }"""
        )
        if not is_disabled:
            await page.evaluate(
                """() => {
                    const btn = Array.from(document.querySelectorAll("button"))
                        .find(b => b.innerText.toLowerCase().includes("search") || b.classList.contains("catgory-button"));
                    if (btn) btn.click();
                }"""
            )
            return True
        await page.wait_for_timeout(500)
    return False


async def click_next_page(page) -> bool:
    next_btn_handle = await page.evaluate_handle(
        """() => {
            const els = Array.from(document.querySelectorAll("button, a, li, span.page-link"));
            return els.find(el => {
                const text = (el.innerText || el.textContent || "").trim();
                const parentDisabled = el.parentElement && el.parentElement.classList.contains("disabled");
                const isClickable = !el.classList.contains("disabled") && !el.hasAttribute("disabled") && !parentDisabled;
                return (text === ">" || text.toLowerCase() === "next" || text === "»") && isClickable;
            });
        }"""
    )
    next_btn = next_btn_handle.as_element()
    if not next_btn:
        return False
    first_link = await page.evaluate("() => document.querySelector('table td a')?.href || ''")
    await next_btn.click()
    try:
        await page.wait_for_function(
            "(url) => document.querySelector('table td a')?.href !== url",
            arg=first_link,
            timeout=8000,
        )
    except Exception:
        return False
    await asyncio.sleep(1.0)
    return True


async def scrape_detail_page(page, detail_url, category, commodity_name, market_name, district, fallback_unit):
    """Load a commodity history page and extract records from its visible data table."""
    records = []
    try:
        await robust_action(page, "goto", detail_url)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        if not await _wait_for_visible_table(page):
            logger.warning("No visible data table found at %s after 15 seconds", detail_url)
            return records
        rows_data = await _extract_best_visible_table(page)
        if not rows_data or len(rows_data) < 2:
            return records

        date_idx, price_idx, unit_idx = _detect_columns(rows_data[0])
        for row in rows_data[1:]:
            if len(row) <= date_idx:
                continue
            raw_date = row[date_idx]
            if not raw_date or any(x in raw_date.lower() for x in ["date", "s.no", "category", "district", "city"]):
                continue
            price = parse_price(row[price_idx] if len(row) > price_idx else "")
            if price is None:
                continue
            extracted_unit = row[unit_idx].strip() if unit_idx is not None and len(row) > unit_idx else None
            records.append(
                {
                    "commodity_name": commodity_name,
                    "market_name": market_name,
                    "district": get_standardized_district(district or market_name),
                    "price": price,
                    "unit": extracted_unit or fallback_unit or "Kg",
                    "date_scraped": clean_date_string(raw_date),
                    "source_url": detail_url,
                    "category": category,
                }
            )
        logger.info("Extracted %s history records from %s", len(records), detail_url)
    except Exception as exc:
        logger.error("Error scraping detail page %s: %s", detail_url, exc)
        await capture_failed_page(page, detail_url)
    return records


async def capture_failed_page(page, url: str, root: Path | None = None) -> None:
    root = root or Path("failed_pages")
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in url)[-120:]
    (root / "screenshots").mkdir(parents=True, exist_ok=True)
    (root / "html").mkdir(parents=True, exist_ok=True)
    try:
        await page.screenshot(path=str(root / "screenshots" / f"{safe_name}.png"), full_page=True)
        (root / "html" / f"{safe_name}.html").write_text(await page.content(), encoding="utf-8")
        with (root / "failed_urls.txt").open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.utcnow().isoformat()} {url}\n")
    except Exception as exc:
        logger.warning("Failed to capture failed page artifacts for %s: %s", url, exc)


async def _wait_for_visible_table(page) -> bool:
    for _ in range(15):
        found = await page.evaluate(
            """() => Array.from(document.querySelectorAll("table"))
                .some(t => t.offsetParent !== null && t.rows.length > 1)"""
        )
        if found:
            return True
        await asyncio.sleep(1.0)
    return False


async def _extract_best_visible_table(page):
    return await page.evaluate(
        """() => {
            const visible = Array.from(document.querySelectorAll("table"))
                .filter(t => t.offsetParent !== null && t.rows.length > 1);
            if (!visible.length) return [];
            const best = visible.reduce((a, b) => (a.rows.length >= b.rows.length ? a : b));
            return Array.from(best.rows).map(row =>
                Array.from(row.querySelectorAll("td, th")).map(cell => cell.innerText.trim())
            );
        }"""
    )


def _detect_columns(headers_raw):
    headers = [h.lower() for h in headers_raw]
    date_idx = 0
    price_idx = None
    unit_idx = None
    for idx, header in enumerate(headers):
        if header == "date":
            date_idx = idx
        elif header in ("price", "price/units") or "price" in header:
            price_idx = price_idx if price_idx is not None else idx
        elif header in ("units", "unit") or "quantity" in header:
            unit_idx = idx
        elif any(marker in header for marker in ["rate", "modal", "average", "min", "max"]):
            price_idx = price_idx if price_idx is not None else idx
    return date_idx, price_idx if price_idx is not None else min(1, len(headers) - 1), unit_idx


_CITY_SELECT_LENGTH_JS = """() => {
    const select = Array.from(document.querySelectorAll("select")).find(s => {
        const firstOptText = s.options[0]?.text.toLowerCase() || "";
        return !firstOptText.includes("category") &&
               !firstOptText.includes("district") &&
               firstOptText !== "en" &&
               firstOptText !== "tn" &&
               (firstOptText.includes("all") || firstOptText.includes("city") ||
                firstOptText.includes("market") || Array.from(s.options).some(o => o.value === "0"));
    });
    return select ? select.options.length : 0;
}"""

_SELECT_ALL_CITY_JS = """() => {
    const select = Array.from(document.querySelectorAll("select")).find(s => {
        const firstOptText = s.options[0]?.text.toLowerCase() || "";
        return !firstOptText.includes("category") &&
               !firstOptText.includes("district") &&
               firstOptText !== "en" &&
               firstOptText !== "tn" &&
               (firstOptText.includes("all") || firstOptText.includes("city") ||
                firstOptText.includes("market") || Array.from(s.options).some(o => o.value === "0"));
    });
    if (select) {
        select.value = "0";
        select.dispatchEvent(new Event("change", { bubbles: true }));
    }
}"""
