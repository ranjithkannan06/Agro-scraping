"""Async retry helper for transient scraper and loader failures."""

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def retry_async(operation: Callable[[], Awaitable[T]], attempts: int, base_delay: float = 1.0) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_error or RuntimeError("retry operation failed")
