"""Polite HTTP fetching: retries on 429 while honoring Retry-After.

Adds no artificial waits: it only waits if the server throttles us (429). This
way it doesn't get in the way of urgent actions but avoids bans from overload.
"""

import time
import urllib.error
import urllib.request

from . import config


def get(url: str, timeout: int = 20, retries: int = 3) -> str:
    """Fetches text. On 429, waits (Retry-After or backoff) and retries."""
    delay = 2
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                retry_after = e.headers.get("Retry-After") or ""
                wait = int(retry_after) if retry_after.isdigit() else delay
                time.sleep(min(wait, 30))
                delay *= 2
                continue
            raise
    raise RuntimeError(f"No response after {retries} retries: {url}")
