"""Resource usage snapshots for scraper pipeline logging."""

from dataclasses import dataclass
import os
import time
import tracemalloc


@dataclass(frozen=True)
class ResourceSnapshot:
    wall_time: float
    process_time: float
    memory_current_mb: float
    memory_peak_mb: float


class ResourceSampler:
    """Measure wall time, CPU process time, and Python memory usage."""

    def __init__(self):
        tracemalloc.start()
        self.start = self.snapshot()

    def snapshot(self) -> ResourceSnapshot:
        current, peak = tracemalloc.get_traced_memory()
        return ResourceSnapshot(
            wall_time=time.perf_counter(),
            process_time=time.process_time(),
            memory_current_mb=round(current / 1024 / 1024, 2),
            memory_peak_mb=round(peak / 1024 / 1024, 2),
        )

    def delta(self) -> dict:
        now = self.snapshot()
        return {
            "pid": os.getpid(),
            "duration_seconds": round(now.wall_time - self.start.wall_time, 2),
            "cpu_process_seconds": round(now.process_time - self.start.process_time, 2),
            "memory_current_mb": now.memory_current_mb,
            "memory_peak_mb": now.memory_peak_mb,
        }
