"""A small in-memory sliding-window rate limiter.

This works for a single server process. If the app ever runs on several
servers, swap the storage for Redis so the limits are shared.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def dependency(self, request: Request) -> None:
        """Use as a FastAPI dependency to limit an endpoint per client IP."""
        key = request.client.host if request.client else "unknown"
        if not self.allow(key):
            raise HTTPException(429, "Too many requests, slow down and try again in a minute")
