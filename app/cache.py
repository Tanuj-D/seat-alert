"""A tiny time-based cache so repeated page searches don't all hit UNC's server."""

import threading
import time
from collections.abc import Callable, Hashable
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float, max_items: int = 1000):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, compute: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        value = compute()  # errors propagate and nothing is cached
        with self._lock:
            if len(self._data) >= self.max_items:
                self._data.clear()
            self._data[key] = (now, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
