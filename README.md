# 🌾 Farmer's Hub — Agro Price Tracker

> **⚠️ Heads up:** This is a personal learning project, not a product. We built this to understand real-world web scraping, backend pipelines, and dashboarding — not to ship anything to users. If something's broken, that's kind of the point 😄

---

## 🎓 What is this?

This is a **hands-on study project** built by students learning full-stack development and data engineering. The idea was simple: pick a real problem (farmers in Tamilnadu don't have easy access to commodity price trends), build a solution end-to-end, and learn as much as possible along the way.

We are **not** affiliated with VayalAgro or any agricultural organization. This is purely for **learning purposes**.

Things we were figuring out while building this:

- How does web scraping actually work on modern JS-heavy sites?
- How do you store and query time-series data in MongoDB?
- How does a FastAPI backend serve data to a frontend?
- How do you sync data to Google Sheets via a service account?
- How do you schedule background jobs that run automatically?
- How do you containerize a multi-service app with Docker?

---

## 📚 What We Learned (The Real README)

### 1. Scraping SPAs is hard
The target site (`vayalagro.com`) is a Vue.js app — `requests` + `BeautifulSoup` sees nothing. You need a real browser. We used **Playwright** to launch headless Chromium, interact with dropdowns, trigger JS events, and wait for dynamic content to render.

**Key gotcha we hit:** The page has multiple hidden `<table>` elements (mobile layout vs desktop layout). `document.querySelector("table")` always picks the hidden one. You have to check `offsetParent !== null` to find the actually-visible table.

### 2. Pagination isn't always a "Next" button
We assumed pagination = click a Next button. Turned out the site uses client-side rendering — all results render at once from a Heroku API (`vaiyal-app.herokuapp.com`). No pagination widget exists. We diagnosed this by intercepting all network responses with Playwright's `page.on("response", ...)`.

### 3. Fixed `sleep()` is a bad wait strategy
Early versions of the scraper had `await page.wait_for_timeout(4000)` everywhere. Sometimes 4s is too short (slow network), sometimes it's wasteful. We replaced fixed delays with `wait_for_function()` — polling the DOM until actual content appeared.

### 4. MongoDB URL issues in Docker vs local
Our `.env` has `MONGODB_URL=mongodb://mongodb:27017` (Docker hostname). Running scripts outside Docker caused connection failures. The fix: detect `/.dockerenv` at runtime and rewrite the hostname to `127.0.0.1`.

### 5. Google Sheets API needs the right scopes
Service account JSON from Firebase Console doesn't automatically have Sheets access. You need to explicitly pass `spreadsheets` + `drive` scopes when building credentials, AND share the spreadsheet with the service account email as an editor.

---

## 🗂️ Project Structure

```
├── scraper/
│   └── src/
│       ├── scrapers/vayal_scraper.py   ← Main Playwright scraper
│       ├── main.py                     ← APScheduler job (runs every 5 min)
│       ├── database.py                 ← MongoDB async writes (motor)
│       └── google_sheets.py            ← gspread sync to Google Sheets
├── backend/                            ← FastAPI REST API + WebSocket
├── web_dashboard/                      ← Web UI (HTML/CSS/JS)
├── mobile/                             ← React Native app (WIP)
├── run.bat                             ← One-click launcher (local mode)
├── docker-compose.yml                  ← Full stack containerized
│
│   ── Diagnostic scripts (our debug toolkit) ──
├── check_network.py        ← Verify site is reachable + log all network calls
├── check_elements.py       ← Audit dropdowns and buttons on the live page
├── check_page_structure.py ← Test dropdown reactivity (select → wait → verify)
├── check_detail_page.py    ← Verify detail page table extraction works
└── check_sheets.py         ← Test Google Sheets connection + write access
```

---

## 🚀 Running It Locally

### Prerequisites
- Python 3.10+
- MongoDB running on port 27017
- A Google service account JSON with Sheets + Drive scopes

### Setup
```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt
pip install -r scraper/requirements.txt

# 3. Install Playwright browsers
playwright install chromium

# 4. Copy and fill in your credentials
cp .env.example .env
# → Set GOOGLE_SHEET_ID, MONGODB_URL, etc.
```

### Run everything
```bash
# Windows one-click launcher (starts backend + scraper + opens dashboard)
.\run.bat

# Or run just the scraper manually
python scraper/src/scrapers/vayal_scraper.py
```

### Docker (full stack)
```bash
docker-compose up --build
```

---

## 🔬 Diagnostic Scripts

We built a bunch of standalone scripts to debug specific parts of the pipeline. Run these when something breaks:

| Script | What it checks |
|---|---|
| `check_network.py` | Can we reach `vayalagro.com`? Logs all HTTP calls |
| `check_elements.py` | Are all dropdowns and buttons present and correct? |
| `check_page_structure.py` | Does selecting a category→district actually enable Search? |
| `check_detail_page.py` | Does the price history table extract correctly? |
| `check_sheets.py` | Is Google Sheets connected? Does write access work? |
| `check_mongodb.py` | How many records are in MongoDB? Breakdown by category? |

---

## 📊 Data Flow

```
vayalagro.com  →  Playwright scraper  →  MongoDB (primary store)
                                      →  Google Sheets (sync copy)
                                      →  FastAPI backend  →  Web Dashboard
                                                         →  Mobile app
```

---

## ⚠️ Disclaimer

- This project scrapes a public website for **personal educational use only**
- We do not store or redistribute any proprietary data
- We have rate limiting in place to avoid hammering the site
- This is not affiliated with VayalAgro, Athanur Agro, or any farmer organization
- **Do not use this in production** — it's a study project and will definitely break

---

*Built with curiosity, broken many times, and slowly fixed 🛠️*
