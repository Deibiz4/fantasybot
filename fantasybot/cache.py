"""On-disk cache with TTL for slow-changing reads (scrapes).

Avoids re-downloading the same pages on every command (and the 429s that come
with it). Never used for write actions or for data that must be fresh.
"""

import json
import os
import time

from . import config

CACHE_DIR = os.path.join(config.ROOT, ".cache")


def _path(key: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
    return os.path.join(CACHE_DIR, safe + ".json")


def cached(key: str, ttl_seconds: int, producer):
    """Returns the cached value if fresh; otherwise calls producer and stores it.

    producer must return something JSON-serializable.
    """
    path = _path(key)
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age < ttl_seconds:
            with open(path, encoding="utf-8") as f:
                return json.load(f)

    value = producer()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
    return value


def clear():
    """Clears the entire cache."""
    if os.path.isdir(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            os.remove(os.path.join(CACHE_DIR, f))
