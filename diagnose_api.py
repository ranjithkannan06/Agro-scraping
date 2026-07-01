"""
STEP 1b — TARGETED API PROBE (unicode-safe)
"""
import asyncio
import sys
import json
import io

# Force UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

BASE_URL = "https://vayalagro.com/market-price"

def safe(s, limit=400):
    return str(s)[:limit].encode("utf-8", errors="replace").decode("utf-8")

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        heroku_calls = []

        async def on_response(response):
            url = response.url
            if "vaiyal-app.herokuapp.com" in url:
                try:
                    body = await response.text()
                    heroku_calls.append({"url": url, "status": response.status, "body": body[:600]})
                except Exception:
                    heroku_calls.append({"url": url, "status": response.status, "body": "(unreadable)"})

        page.on("response", on_response)

        # ── Initial load ──────────────────────────────────────────────────
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        print("[STEP 1] Initial page load API calls:")
        for c in heroku_calls:
            print(f"  {c['url']}  [{c['status']}]")
            print(f"    {safe(c['body'], 250)}")
        heroku_calls.clear()

        # ── Select Flowers ────────────────────────────────────────────────
        await page.evaluate("""() => {
            const sel = Array.from(document.querySelectorAll('select'))
                .find(s => s.options[0]?.text.toLowerCase().includes('category'));
            if (sel) {
                const opt = Array.from(sel.options).find(o => o.text.trim().toLowerCase() === 'flowers');
                if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
            }
        }""")
        await page.wait_for_timeout(2500)
        print("\n[STEP 2] After selecting 'Flowers':")
        for c in heroku_calls:
            print(f"  {c['url']}  [{c['status']}]")
            print(f"    {safe(c['body'], 250)}")
        heroku_calls.clear()

        # ── Select Erode ──────────────────────────────────────────────────
        await page.evaluate("""() => {
            const sel = Array.from(document.querySelectorAll('select'))
                .find(s => s.options[0]?.text.toLowerCase().includes('district'));
            if (sel) {
                const opt = Array.from(sel.options).find(o => o.text.trim().toLowerCase() === 'erode');
                if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
            }
        }""")
        await page.wait_for_timeout(2000)
        print("\n[STEP 3] After selecting 'Erode':")
        for c in heroku_calls:
            print(f"  {c['url']}  [{c['status']}]")
            print(f"    {safe(c['body'], 300)}")
        heroku_calls.clear()

        # ── City = All + click Search ─────────────────────────────────────
        await page.evaluate("""() => {
            const sel = Array.from(document.querySelectorAll('select'))
                .find(s => Array.from(s.options).some(o => o.value === '0'));
            if (sel) { sel.value = '0'; sel.dispatchEvent(new Event('change', {bubbles:true})); }
        }""")
        await page.wait_for_timeout(500)
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button'))
                .find(b => b.innerText.toLowerCase().includes('search') || b.classList.contains('catgory-button'));
            if (btn) btn.click();
        }""")
        await page.wait_for_timeout(7000)

        print("\n[STEP 4] After clicking Search (Flowers + Erode + All cities):")
        for c in heroku_calls:
            print(f"  {c['url']}  [{c['status']}]")
            print(f"    {safe(c['body'], 500)}")

        # Count links
        link_count = await page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('table td a'));
            return { count: links.length, samples: links.slice(0,5).map(a => a.href) };
        }""")
        print(f"\n[STEP 5] Visible result links: count={link_count['count']}")
        for s in link_count['samples']:
            print(f"  {s}")

        # ── Probe listing API directly with pagination params ─────────────
        listing_url = None
        for c in heroku_calls:
            u = c['url']
            if any(k in u for k in ["price", "list", "search", "market", "flower"]):
                if "maintenance" not in u and "meta" not in u and "recentlist" not in u:
                    listing_url = u
                    break

        if not listing_url:
            # pick any non-trivial one
            for c in heroku_calls:
                if "maintenance" not in c['url'] and "meta" not in c['url']:
                    listing_url = c['url']
                    break

        if listing_url:
            print(f"\n[STEP 6] Probing for pagination on: {listing_url}")
            import urllib.request
            sep = "&" if "?" in listing_url else "?"
            for suffix in ["page=2", "page=1&limit=50", "offset=10", "start=10"]:
                test_url = listing_url + sep + suffix
                try:
                    req = urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        body = resp.read().decode("utf-8", errors="replace")[:500]
                        print(f"  GET {test_url}")
                        print(f"    Response ({resp.status}): {safe(body, 300)}")
                except Exception as e:
                    print(f"  GET {test_url} -> ERROR: {e}")
        else:
            print("\n[STEP 6] No search-listing endpoint captured (all calls were init/meta).")
            print("  Listing: all heroku calls made during Search click:")
            for c in heroku_calls:
                print(f"    {c['url']}")

        # ── Also hit the recentlist to see its structure ───────────────────
        print("\n[STEP 7] Probing /get/recentlist structure:")
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://vaiyal-app.herokuapp.com/get/recentlist?type=market",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                data = json.loads(body)
                items = data.get("data", [])
                print(f"  Total items in recentlist: {len(items)}")
                if items:
                    print(f"  First item keys: {list(items[0].keys())}")
                    print(f"  First item: {safe(json.dumps(items[0]), 400)}")
        except Exception as e:
            print(f"  ERROR: {e}")

        await browser.close()
        print("\nAPI Diagnostic complete.")

if __name__ == "__main__":
    asyncio.run(main())
