from __future__ import annotations
import time
from .cache_manager import CacheManager

def poll_watch(cache: CacheManager, interval: float = 2.0):
    """Simple polling watcher. Replace with watchdog if needed."""
    while True:
        cache.refresh()
        time.sleep(interval)
