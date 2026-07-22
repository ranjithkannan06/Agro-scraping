"""Static defaults for source URLs, folders, and pipeline thresholds."""

from pathlib import Path

SCRAPER_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SCRAPER_ROOT.parent

DEFAULT_SOURCE_URL = "https://vayalagro.com/market-price"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_DATABASE_NAME = "harvesthub"

DEFAULT_OUTPUT_ROOT = SCRAPER_ROOT / "outputs"
DEFAULT_LOG_ROOT = SCRAPER_ROOT / "logs"
DEFAULT_FAILED_PAGES_ROOT = SCRAPER_ROOT / "failed_pages"
DEFAULT_CONFIG_FILE = SCRAPER_ROOT / "config" / "valid_values.json"

DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_CONCURRENT_TABS = 3

VAYAL_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

VAYAL_CATEGORIES = [
    "Flowers",
    "Vegetables",
    "Banana",
    "Groundnut",
    "Coconut Products",
    "Cassava",
    "Garlic",
    "Turmeric",
    "Areca Nut",
    "Cotton",
    "Maize",
    "Black gram",
    "Sesame",
    "Brown sugar",
]

VAYAL_DISTRICT_MAPPING = {
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

OUTPUT_SUBDIRECTORIES = (
    "csv",
    "excel",
    "json",
    "reports",
    "dashboard",
)
