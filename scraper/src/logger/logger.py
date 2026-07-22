"""Structured daily-rotating logging setup for scraper pipeline runs."""

from logging.handlers import TimedRotatingFileHandler
import json
import logging
import sys
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            payload["extra"] = getattr(record, "extra_data")
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_root: Path) -> logging.Logger:
    log_root.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("harvesthub.scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    file_handler = TimedRotatingFileHandler(
        log_root / "pipeline.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger
