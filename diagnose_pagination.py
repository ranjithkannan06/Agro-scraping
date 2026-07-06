r"""
STEP 1 — LIVE DIAGNOSTIC SCRIPT
Probes vayalagro.com to answer three questions:
  1. How does pagination actually work on the listing page?
  2. How many items exist for Flowers / Erode (a district known to have >10)?
  3. Why does check_detail_page.py time out — which table element holds the prices?

Run with:  .venv\Scripts\python.exe diagnose_pagination.py
"""

import asyncio
import sys
import json
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

BASE_URL = "https://vayalagro.com/market-price"
DETAIL_URL = (
    "https://vayalagro.com/market-price/tamilnadu/"
    "flowers-history-price-dindigul/nilakkottai/arali-history-price"
)

# ─────────────────────────────────────────────────────────────────────────────
async def probe_pagination(page):
    print("\n" + "="*70)
    print("PROBE 1 — PAGINATION STRUCTURE (Flowers / Erode)")
    print("="*70)

    # ── Navigate & select Flowers → Erode ─────────────────────────────────
    await page.goto(BASE_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)

    # Select "Flowers" category
    await page.evaluate('''() => {
        const sel = Array.from(document.querySelectorAll("select"))
            .find(s => s.options[0]?.text.toLowerCase().includes("category"));
        if (sel) {
            const opt = Array.from(sel.options)
                .find(o => o.text.trim().toLowerCase() === "flowers");
            if (opt) {
                sel.value = opt.value;
                sel.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }
    }''')
    await page.wait_for_timeout(2500)

    # Select "Erode" district
    await page.evaluate('''() => {
        const sel = Array.from(document.querySelectorAll("select"))
            .find(s => s.options[0]?.text.toLowerCase().includes("district"));
        if (sel) {
            const opt = Array.from(sel.options)
                .find(o => o.text.trim().toLowerCase() === "erode");
            if (opt) {
                sel.value = opt.value;
                sel.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }
    }''')
    await page.wait_for_timeout(2000)

    # City → "All"
    await page.evaluate('''() => {
        const sel = Array.from(document.querySelectorAll("select"))
            .find(s => Array.from(s.options).some(o => o.value === "0"));
        if (sel) { sel.value = "0"; sel.dispatchEvent(new Event("change", { bubbles: true })); }
    }''')
    await page.wait_for_timeout(1000)

    # Click Search
    await page.evaluate('''() => {
        const btn = Array.from(document.querySelectorAll("button"))
            .find(b => b.innerText.toLowerCase().includes("search") ||
                       b.classList.contains("catgory-button"));
        if (btn) btn.click();
    }''')
    await page.wait_for_timeout(4000)

    # ── Snapshot the page after search ───────────────────────────────────
    print("\n[A] Current URL after Search click:", page.url)

    # Count rows visible in the results table
    row_info = await page.evaluate('''() => {
        const tables = Array.from(document.querySelectorAll("table"));
        return tables.map((t, i) => ({
            tableIndex: i,
            rowCount: t.rows.length,
            isVisible: t.offsetParent !== null,
            firstRow: t.rows[0] ? Array.from(t.rows[0].cells).map(c=>c.innerText.trim()) : []
        }));
    }''')
    print("\n[B] Tables on page after search:")
    for t in row_info:
        print(f"    Table#{t['tableIndex']}: rows={t['rowCount']}, visible={t['isVisible']}, firstRow={t['firstRow'][:4]}")

    # ── Check for any kind of pagination widget ───────────────────────────
    pagination_info = await page.evaluate('''() => {
        const paginationSelectors = [
            "ul.pagination", ".pagination", "[class*=pagination]",
            "nav[aria-label*=pagination]", ".page-item", ".page-link",
            "button.page-link", "a.page-link",
            "[class*=pager]", ".pager"
        ];
        let found = [];
        for (const sel of paginationSelectors) {
            const els = document.querySelectorAll(sel);
            if (els.length) {
                found.push({
                    selector: sel,
                    count: els.length,
                    html: Array.from(els).slice(0,3).map(e=>e.outerHTML.slice(0,200))
                });
            }
        }
        return found;
    }''')
    print("\n[C] Pagination elements found:")
    if pagination_info:
        print(json.dumps(pagination_info, indent=2))
    else:
        print("    NO pagination elements detected with standard selectors!")

    # ── Look for any Next / > / >> buttons or links ────────────────────────
    next_buttons = await page.evaluate('''() => {
        const all = Array.from(document.querySelectorAll("button, a, li, span"));
        return all
            .filter(el => {
                const t = (el.innerText || el.textContent || "").trim();
                return t === ">" || t === ">>" || t === ">>" ||
                       t.toLowerCase() === "next" || t.toLowerCase() === "next page";
            })
            .map(el => ({
                tag: el.tagName,
                text: (el.innerText || el.textContent || "").trim(),
                disabled: el.hasAttribute("disabled") || el.classList.contains("disabled"),
                parentDisabled: el.parentElement ? el.parentElement.classList.contains("disabled") : false,
                classes: el.className,
                href: el.href || null,
                outerHTML: el.outerHTML.slice(0, 300)
            }));
    }''')
    print("\n[D] Next/> buttons & links:")
    if next_buttons:
        for b in next_buttons:
            print(json.dumps(b, indent=4))
    else:
        print("    No Next button found — may be infinite scroll or API-driven!")

    # ── Check for XHR/Fetch calls that returned JSON (API-driven?) ─────────
    print("\n[E] Capturing XHR calls during Search (re-running)...")
    api_calls = []

    def on_response(r):
        ct = r.headers.get("content-type", "")
        if "json" in ct or "/api/" in r.url:
            api_calls.append(r.url)

    page.on("response", on_response)

    await page.goto(BASE_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    await page.evaluate('''() => {
        const sel = Array.from(document.querySelectorAll("select"))
            .find(s => s.options[0]?.text.toLowerCase().includes("category"));
        if (sel) {
            const opt = Array.from(sel.options).find(o => o.text.trim().toLowerCase() === "flowers");
            if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event("change", { bubbles: true })); }
        }
    }''')
    await page.wait_for_timeout(1500)
    await page.evaluate('''() => {
        const sel = Array.from(document.querySelectorAll("select"))
            .find(s => s.options[0]?.text.toLowerCase().includes("district"));
        if (sel) {
            const opt = Array.from(sel.options).find(o => o.text.trim().toLowerCase() === "erode");
            if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event("change", { bubbles: true })); }
        }
    }''')
    await page.wait_for_timeout(1500)
    await page.evaluate('''() => {
        const sel = Array.from(document.querySelectorAll("select"))
            .find(s => Array.from(s.options).some(o => o.value === "0"));
        if (sel) { sel.value = "0"; sel.dispatchEvent(new Event("change", { bubbles: true })); }
    }''')
    await page.wait_for_timeout(500)
    await page.evaluate('''() => {
        const btn = Array.from(document.querySelectorAll("button"))
            .find(b => b.innerText.toLowerCase().includes("search") || b.classList.contains("catgory-button"));
        if (btn) btn.click();
    }''')
    await page.wait_for_timeout(5000)
    print("    API/JSON responses intercepted during this run:")
    for url in api_calls:
        print(f"      {url}")
    if not api_calls:
        print("      (none)")

    # ── Total item count (look for a "showing X of Y" text) ───────────────
    total_text = await page.evaluate('''() => {
        const body = document.body.innerText;
        const match = body.match(/(showing|total|of|results?)[^\\n]{0,60}/gi);
        return match ? match.slice(0, 5) : [];
    }''')
    print("\n[F] Total/Showing text snippets on page:")
    for t in total_text:
        print(f"    {t.strip()}")

    # ── Full pagination HTML dump ──────────────────────────────────────────
    pagination_html = await page.evaluate('''() => {
        const nav = document.querySelector("nav, .pagination, ul.pagination, [class*=pagination]");
        return nav ? nav.outerHTML : null;
    }''')
    print("\n[G] Raw pagination HTML (first 1000 chars):")
    print(pagination_html[:1000] if pagination_html else "    None found.")

    # ── Count total link items in visible result table ─────────────────────
    link_count = await page.evaluate('''() => {
        const links = Array.from(document.querySelectorAll("table td a"));
        return links.length;
    }''')
    print(f"\n[H] Total <a> links inside table cells (visible result count): {link_count}")


# ─────────────────────────────────────────────────────────────────────────────
async def probe_detail_page(page):
    print("\n\n" + "="*70)
    print("PROBE 2 — DETAIL PAGE TABLE STRUCTURE")
    print(f"URL: {DETAIL_URL}")
    print("="*70)

    await page.goto(DETAIL_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    # Enumerate ALL tables: size, visibility, first few cells
    tables_audit = await page.evaluate('''() => {
        return Array.from(document.querySelectorAll("table")).map((t, i) => ({
            index: i,
            rowCount: t.rows.length,
            isVisible: t.offsetParent !== null,
            computedDisplay: window.getComputedStyle(t).display,
            computedVisibility: window.getComputedStyle(t).visibility,
            classes: t.className,
            id: t.id,
            parentClasses: t.parentElement ? t.parentElement.className : "",
            sampleRows: Array.from(t.rows).slice(0,3).map(
                r => Array.from(r.cells).map(c => c.innerText.trim())
            )
        }));
    }''')
    print("\n[A] ALL table elements on detail page:")
    for t in tables_audit:
        print(f"\n  Table#{t['index']}: rows={t['rowCount']}, visible={t['isVisible']}, "
              f"display={t['computedDisplay']}, visibility={t['computedVisibility']}")
        print(f"    id='{t['id']}' classes='{t['classes']}'")
        print(f"    parent classes='{t['parentClasses']}'")
        print(f"    Sample rows: {t['sampleRows']}")

    # What selector actually works for the price table?
    selector_tests = await page.evaluate('''() => {
        const candidates = [
            "table",
            "table.table",
            ".history-table table",
            ".price-history table",
            "div[class*=history] table",
            "section table",
            "main table",
            "article table",
        ];
        return candidates.map(sel => {
            try {
                const el = document.querySelector(sel);
                return {
                    selector: sel,
                    found: !!el,
                    rowCount: el ? el.rows.length : 0,
                    visible: el ? el.offsetParent !== null : false
                };
            } catch(e) { return { selector: sel, error: e.message }; }
        });
    }''')
    print("\n[B] Selector tests for price history table:")
    for s in selector_tests:
        print(f"    {s}")

    # Check if content loads lazily (wait more and re-check)
    print("\n[C] Waiting 8 more seconds to detect lazy-loaded content...")
    await page.wait_for_timeout(8000)
    late_audit = await page.evaluate('''() => {
        return Array.from(document.querySelectorAll("table")).map((t, i) => ({
            index: i,
            rowCount: t.rows.length,
            isVisible: t.offsetParent !== null,
            sampleRows: Array.from(t.rows).slice(0,3).map(
                r => Array.from(r.cells).map(c => c.innerText.trim())
            )
        }));
    }''')
    print("    Tables after extra wait:")
    for t in late_audit:
        print(f"    Table#{t['index']}: rows={t['rowCount']}, visible={t['isVisible']}, sample={t['sampleRows'][:2]}")


# ─────────────────────────────────────────────────────────────────────────────
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        await probe_pagination(page)
        await probe_detail_page(page)

        await browser.close()
        print("\n\nDiagnostic complete.")

if __name__ == "__main__":
    asyncio.run(main())
