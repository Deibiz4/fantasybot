"""Lineup optimizer.

Picks the best XI and the best formation among several valid ones, based on the
probability of each player starting (futbolfantasy) and their availability
(injury/suspension, from the API and from futbolfantasy). Returns the proposal and the
body ready for `FantasyClient.update_lineup`. It does NOT apply anything by itself.
"""

from ..matching import match_name
from ..sources.lineups import probable_lineups

POS = {1: "goalkeeper", 2: "defender", 3: "midfield", 4: "striker"}


def payload_ids(best) -> set:
    """Set of playerTeamIds of the XI in a lineup payload (`optimize`)."""
    p = best["payload"]
    return {p["goalkeeper"], *p["defender"], *p["midfield"], *p["striker"]}

# Valid formations as (defenders, midfielders, forwards). The goalkeeper is fixed (1).
FORMATIONS = [
    (3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2),
    (4, 5, 1), (5, 3, 2), (5, 4, 1),
]

def caliber_prior(market_value):
    """Prior for 'probability of starting' when futbolfantasy gives no data.

    Relies on market value: an expensive player is almost certainly a starter; a
    cheap one is a benchwarmer. Prevents an unmatched cast-off (Purić, 0.4M) from being
    worth the same as an unmatched starter (Etta, 25M). Scaled 0-100 like the probability.
    """
    v = market_value or 0
    if v >= 15_000_000:
        return 62
    if v >= 8_000_000:
        return 52
    if v >= 4_000_000:
        return 42
    if v >= 2_000_000:
        return 28
    return 12


NOT_IN_XI_SCORE = 5.0  # on his team but futbolfantasy doesn't list him as a starter → ~0%


def player_score(player, prob_index):
    """Scores a player for the XI. Returns (score, prob, disponible, tag).

    tag distinguishes the source of the score:
      - 'in_xi'     : futbolfantasy gives him a starting probability (strong signal).
      - 'not_in_xi' : on his team but NOT in the probable lineup → ~0% (real bench;
                      in transfers, a signal to watch).
      - 'unknown'   : doesn't appear on futbolfantasy → we estimate from his value.
      - 'out'       : injured/suspended/unavailable.
    """
    pm = player["playerMaster"]
    info = match_name(pm.get("nickname", ""), pm.get("name", ""), prob_index)
    prob = info.get("prob") if info else None

    disponible = pm.get("playerStatus", "ok") == "ok"
    if info and (info.get("lesionado") or not info.get("disponible", True)):
        disponible = False

    if not disponible:
        base, tag = 0.0, "out"
    elif info is None:
        base, tag = float(caliber_prior(pm.get("marketValue"))), "unknown"
    elif prob is not None:
        base, tag = float(prob), "in_xi"
    else:
        base, tag = NOT_IN_XI_SCORE, "not_in_xi"
    base += (pm.get("lastSeasonPoints") or 0) * 0.001  # tiebreaker
    return base, prob, disponible, tag


def _pid(player):
    return player.get("playerTeamId") or player["playerMaster"]["id"]


def _entry(player, score, prob, disponible, tag):
    pm = player["playerMaster"]
    return {
        "playerTeamId": _pid(player),
        "nombre": pm.get("nickname") or pm.get("name"),
        "score": round(score, 1),
        "prob": prob,
        "disponible": disponible,
        "tag": tag,
        "valor": pm.get("marketValue"),
    }


def _fill(need, by_pos, gk, pool):
    """Fill a formation, position by position, preferring a player OF THAT POSITION.

    LaLiga silently drops a player fielded OUT of position (a midfielder sent as a
    defender comes back off the lineup), so borrowing from another line to plug a hole
    leaves the slot empty anyway. But LaLiga KEEPS an injured/suspended player who is
    in the right position — he just scores 0. So each line is filled from ITS OWN
    players: available ones first, then that line's injured players (a legal slot that
    scores 0) rather than a healthy player from another line. Only when a position
    hasn't enough players of its own to fill the formation at all do we borrow from the
    global bench (`pool`) as a last resort — an emergency where no legal XI exists and a
    dropped slot is unavoidable. Returns (picks, unavailable_in_xi) or None if the
    squad can't field 11 even after borrowing.
    """
    used = {gk["playerTeamId"]}
    picks = {}
    for pos, n in need.items():
        # own players of this line, available first then injured (all position-valid)
        own = [e for e in by_pos[pos] if e["playerTeamId"] not in used]
        own.sort(key=lambda e: (not e["disponible"], -e["score"]))
        take = own[:n]
        for e in take:
            used.add(e["playerTeamId"])
        picks[pos] = take
    # last resort ONLY: a line with fewer players than slots borrows cross-position
    # (LaLiga may drop it, but an emergency XI beats an empty payload)
    bench = [e for e in pool if e["playerTeamId"] not in used]
    bi = 0
    for pos, n in need.items():
        while len(picks[pos]) < n and bi < len(bench):
            e = bench[bi]
            bi += 1
            picks[pos].append(e)
            used.add(e["playerTeamId"])
    if any(len(picks[pos]) < n for pos, n in need.items()):
        return None  # not even 11 players in the squad
    unavailable = sum(1 for pos in picks for e in picks[pos] if not e["disponible"])
    return picks, unavailable


def optimize(team, prob_index=None):
    """Computes the best XI + formation. Returns a dict with the proposal and the body.

    Guarantees a COMPLETE, LEGAL XI: every slot of the chosen formation is filled by a
    player OF THAT POSITION, preferring available players and using a line's own injured
    players only to backfill that same line (see `_fill`). LaLiga drops a player fielded
    out of position but keeps an injured one who is in position (he scores 0), so a
    position-valid XI is what actually reaches the pitch — a healthy player borrowed into
    the wrong line would be silently dropped and leave the slot empty.
    """
    if prob_index is None:
        prob_index = probable_lineups()

    # group and score the squad by position
    by_pos = {"goalkeeper": [], "defender": [], "midfield": [], "striker": []}
    watch = []  # signals to watch (expensive players outside the probable lineup)
    for p in team["players"]:
        pos = POS.get(p["playerMaster"]["positionId"])
        if not pos:
            continue
        score, prob, disp, tag = player_score(p, prob_index)
        entry = _entry(p, score, prob, disp, tag)
        by_pos[pos].append(entry)
        if tag == "not_in_xi" and (entry["valor"] or 0) >= 8_000_000:
            watch.append(entry)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda e: -e["score"])

    if not by_pos["goalkeeper"]:
        raise ValueError("No goalkeeper in the squad.")
    # only AVAILABLE players are candidates for a slot; injured/suspended never fielded
    avail = {pos: [e for e in by_pos[pos] if e["disponible"]] for pos in by_pos}
    gk = (avail["goalkeeper"] or by_pos["goalkeeper"])[0]

    # global bench for backfilling short positions: available players first (by score),
    # unavailable players only as an absolute last resort (so a slot is never empty).
    ordered = [e for pos in by_pos for e in by_pos[pos]]
    pool = sorted(ordered, key=lambda e: (not e["disponible"], -e["score"]))

    best = None
    for d, m, f in FORMATIONS:
        need = {"defender": d, "midfield": m, "striker": f}
        # prefer formations we can fill entirely from AVAILABLE players of each position
        full_available = (len(avail["defender"]) >= d and len(avail["midfield"]) >= m
                          and len(avail["striker"]) >= f)
        filled = _fill(need, by_pos, gk, pool)
        if filled is None:
            continue  # can't field 11 in this shape
        picks, unavailable = filled
        total = gk["score"] + sum(e["score"] for pos in picks for e in picks[pos])
        cand = {
            "formation": (d, m, f),
            "goalkeeper": gk,
            "defender": picks["defender"],
            "midfield": picks["midfield"],
            "striker": picks["striker"],
            "total": round(total, 1),
            # rank: fewest injured fielded, then prefer a clean shape, then score
            "_rank": (-unavailable, 1 if full_available else 0, round(total, 1)),
        }
        if best is None or cand["_rank"] > best["_rank"]:
            best = cand

    if best is None:
        raise ValueError("Not enough players for any valid formation.")
    best.pop("_rank", None)

    best["payload"] = {
        "goalkeeper": best["goalkeeper"]["playerTeamId"],
        "defender": [e["playerTeamId"] for e in best["defender"]],
        "midfield": [e["playerTeamId"] for e in best["midfield"]],
        "striker": [e["playerTeamId"] for e in best["striker"]],
        "tactical_formation": list(best["formation"]),
    }
    best["watch"] = watch
    return best
