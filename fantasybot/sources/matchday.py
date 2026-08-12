"""Date of the next matchday from futbolfantasy.

Used for two things:
  - Signing urgency: the fewer days left, the more room to overpay.
  - Knowing when the FINAL lineup must be set (before the first match).

The date is on each match's page as text
("15 de agosto del 2026 a las 19:30"). Cached 6h.
"""

import re
from datetime import datetime, timezone, timedelta

from .. import config, net, cache

CACHE_TTL = 21600  # 6h
try:
    from zoneinfo import ZoneInfo
    SPAIN_TZ = ZoneInfo("Europe/Madrid")   # respects summer/winter time (CET/CEST)
except Exception:                          # no tz database (Windows without 'tzdata'): fixed CEST
    SPAIN_TZ = timezone(timedelta(hours=2))
MATCH_URL = "https://www.futbolfantasy.com/partidos/{slug}"

MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
          "diciembre": 12}


def _parse_match_datetime(html):
    m = re.search(r"(\d{1,2}) de (\w+) del (\d{4}) a las (\d{1,2}):(\d{2})",
                  html, re.I)
    if not m:
        return None
    day, mon, year, hh, mm = m.groups()
    month = MONTHS.get(mon.lower())
    if not month:
        return None
    return datetime(int(year), month, int(day), int(hh), int(mm), tzinfo=SPAIN_TZ)


def _match_slugs(limit=10):
    """Slugs of upcoming matches (lowest id = nearest matchday)."""
    html = net.get(config.FF_LINEUPS_INDEX)
    slugs = re.findall(r"/partidos/(\d+-[a-z0-9-]+)", html)
    # sort by numeric id and keep the first ones (one matchday)
    uniq = sorted(set(slugs), key=lambda s: int(s.split("-")[0]))
    return uniq[:limit]


def _compute_next_kickoff():
    now = datetime.now(timezone.utc)
    times = []
    for slug in _match_slugs():
        try:
            dt = _parse_match_datetime(net.get(MATCH_URL.format(slug=slug)))
            if dt:
                times.append(dt)
        except Exception:
            continue
    if not times:
        return None
    future = [t for t in times if t > now]
    return (min(future) if future else min(times)).isoformat()


def next_kickoff():
    """datetime (ISO) of the first match of the next matchday, or None."""
    return cache.cached("next_kickoff", CACHE_TTL, _compute_next_kickoff)


def days_until_matchday():
    """Days (float) until the first match, or None if it couldn't be obtained."""
    iso = next_kickoff()
    if not iso:
        return None
    dt = datetime.fromisoformat(iso)
    return (dt - datetime.now(timezone.utc)).total_seconds() / 86400
