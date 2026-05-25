from __future__ import annotations

import time
from collections import OrderedDict


class TranslationCache:
    """In-memory LRU + TTL cache for (src, dst, normalised_text) → translation."""

    def __init__(self, *, ttl_seconds: float = 3600.0, max_entries: int = 5000) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        # key -> (expires_at_monotonic, value)
        self._store: OrderedDict[tuple[str, str, str], tuple[float, str]] = OrderedDict()

    def _now(self) -> float:
        return time.monotonic()

    def get(self, key: tuple[str, str, str]) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._now() > expires_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: tuple[str, str, str], value: str) -> None:
        self._store[key] = (self._now() + self._ttl, value)
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)

    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
