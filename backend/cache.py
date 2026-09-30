from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= monotonic():
                del self._entries[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> Any:
        with self._lock:
            self._entries[key] = CacheEntry(value, monotonic() + ttl_seconds)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


cache = TTLCache()
