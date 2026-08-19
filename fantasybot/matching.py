"""Name normalization and matching across sources.

The LaLiga API uses nicknames ("Etta Eyong") and futbolfantasy uses full names
("karl etta eyong"). This module centralizes the matching, previously duplicated
in several places.
"""

import unicodedata

# API positions (positionId -> abbreviation). Shared by the strategies.
POS = {1: "POR", 2: "DEF", 3: "MED", 4: "DEL"}


def normalize(name: str) -> str:
    """lowercase + accent-stripped, to match names across sources."""
    n = unicodedata.normalize("NFKD", name or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    return n.lower().strip()


def index_by_name(items, key="nombre"):
    """Dict normalized_name -> item."""
    return {normalize(it[key]): it for it in items}


def match_name(nickname: str, full_name: str, index: dict):
    """Finds the `index` entry for a player from the LaLiga API.

    Tries an exact match by nickname and by full name; if that fails, by tokens
    (all the significant tokens of the nickname appear in the key).
    Returns the entry or None.
    """
    nick = normalize(nickname)
    full = normalize(full_name)
    if nick in index:
        return index[nick]
    if full in index:
        return index[full]
    tokens = [t for t in nick.split() if len(t) > 2]
    if tokens:
        # Only trust a token match if it's UNIQUE. A short/common nickname
        # ("Pedro", "Álvarez") is a subset of several names; returning an arbitrary
        # one is a false positive (what SANITY_MAX_DIFF in flip.py papers over).
        # Ambiguous -> no confident match. The ID crosswalk is the real fix.
        hits = [value for key, value in index.items()
                if all(t in key for t in tokens)]
        if len(hits) == 1:
            return hits[0]
    return None
