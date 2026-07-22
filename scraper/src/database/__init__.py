"""Database abstractions and compatibility exports for scraper ETL."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_legacy_path = Path(__file__).resolve().parent.parent / "database.py"
_legacy_spec = spec_from_file_location("_legacy_scraper_database", _legacy_path)
if _legacy_spec and _legacy_spec.loader:
    _legacy_module = module_from_spec(_legacy_spec)
    _legacy_spec.loader.exec_module(_legacy_module)
    Database = _legacy_module.Database

__all__ = ["Database"]
