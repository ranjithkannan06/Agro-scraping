# 🌾 Athanur Agro - Market Price Scraper & Dashboard

Welcome to the **Athanur Agro** repository! This project is designed to scrape, store, and display daily agricultural market prices (specifically flowers, vegetables, and other commodities) in Tamilnadu, India.

---

> [!NOTE]
> ### 🎓 Learning Journey: Web Scraping
> **I am currently learning web scraping!** This project is a hands-on learning environment where I am exploring:
> - Automated data extraction using **Python** and **Playwright**.
> - Navigating dynamic single-page applications (SPAs).
> - Dealing with complex page elements, dynamic dropdown menus, dates, and paginated tables.
> - Storing extracted data into databases (MongoDB) and syncing them to Google Sheets.
> - Triggering automated notifications to backend and mobile services.

---

## 📁 Repository Structure

Here's an overview of the key components in this repository:

*   **`scraper/`**: The core web scraping service.
    *   `src/scrapers/vayal_scraper.py`: The main scraping script using Playwright to extract flower prices from VayalAgro.
    *   `src/main.py`: The scheduler (using APScheduler) that runs the scraping job periodically.
    *   `src/database.py` & `src/google_sheets.py`: Data persistence layers (MongoDB & Google Sheets).
*   **`backend/`**: Fast API backend service that serves scraped prices to clients and handles notifications.
*   **`web_dashboard/`**: Next.js / React-based web dashboard to view historical price trends.
*   **`mobile/`**: React Native mobile app for farmers and traders to receive live price updates.
*   **`test_scraper.py`**: A lightweight script to test/dump HTML from the target site.

---

## 🛠️ Web Scraping Concepts I am Learning Here

Building this scraper covers several crucial modern web scraping techniques:

1.  **Dynamic Rendering (Playwright vs BeautifulSoup)**:
    Since the target site (`vayalagro.com`) is a modern JavaScript application (Vue.js), standard HTML parsers like BeautifulSoup won't see the data. We use **Playwright** to spin up a headless browser, execute JavaScript, select options, and load the dynamic tables.
2.  **Robust Element Locators**:
    Locating select dropdowns and buttons that don't have unique `id` or `name` attributes by using custom Javascript evaluators and text-based matching (e.g. searching options for "Flowers" or matching button text like `Search` or `>` / `Next`).
3.  **State and Form Interactions**:
    Selecting category options, matching districts, entering target dates in date fields, and programmatically triggering change/input events so the page knows to fetch the corresponding records.
4.  **Pagination Handling**:
    Iterating through multiple result pages by detecting and clicking the "Next" (`>`) button, checking for disabled states, and fingerprinting the table rows to avoid infinite loops.
5.  **Anti-Bot & Verification Measures**:
    Configuring realistic desktop `User-Agent` strings and viewports to prevent blockages or CAPTCHAs.

---

## 🚀 How to Set Up & Run the Scraper Locally

Follow these steps to set up the scraper on your machine:

### 1. Create a Python Virtual Environment
Keep your dependencies clean and isolated:
```bash
python -m venv .venv
```

### 2. Activate the Virtual Environment
*   **Windows (PowerShell):**
    ```powershell
    .venv\Scripts\Activate.ps1
    ```
*   **Windows (Command Prompt):**
    ```cmd
    .venv\Scripts\activate.bat
    ```
*   **macOS / Linux:**
    ```bash
    source .venv/bin/activate
    ```

### 3. Install Dependencies
Install all required libraries including Playwright, motor (async MongoDB driver), APScheduler, and Google Sheets connectors:
```bash
pip install -r scraper/requirements.txt
```

### 4. Install Playwright Browsers
Download the Chromium browser binaries used by Playwright:
```bash
playwright install chromium
```

### 5. Run the Scraper manually
Run the scraper script to fetch the latest flower market data:
```bash
python scraper/src/scrapers/vayal_scraper.py
```

---

## 🔍 Pagination & Multi-Page Scraping

When a search returns many rows, the table splits across multiple pages. The scraper is configured to:
1.  Extract all records from the current page.
2.  Find the `Next` (`>`) navigation button.
3.  Verify the button is clickable (not disabled).
4.  Click the button, wait for the table to update, and repeat until no `Next` button is found or a page fingerprint matches the previous page (signaling we are at the end).
