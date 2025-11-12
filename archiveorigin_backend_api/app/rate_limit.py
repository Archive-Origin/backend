from __future__ import annotations

from cachetools import TTLCache
from threading import Lock
from time import time

class RateLimiter:
    """Simple in-memory rate limiter (best-effort, single process)."""

    def __init__(self, window_seconds: int = 60, max_entries: int = 10_000):
        self.window_seconds = window_seconds
        self.cache: TTLCache[str, tuple[int, float]] = TTLCache(maxsize=max_entries, ttl=window_seconds)
        self.lock = Lock()

    def hit(self, key: str, limit: int) -> bool:
        """Registers a hit. Returns True if allowed, False if over limit."""
        now = time()
        with self.lock:
            hits, window_start = self.cache.get(key, (0, now))
            if now - window_start >= self.window_seconds:
                hits = 0
                window_start = now
            if hits >= limit:
                self.cache[key] = (hits, window_start)
                return False
            hits += 1
            self.cache[key] = (hits, window_start)
            return True

global_rate_limiter = RateLimiter()
