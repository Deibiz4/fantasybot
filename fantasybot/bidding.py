"""Last-minute bidding: bid right at the close, not before.

Idea: don't reveal your bid early. A cron job launches this ~5 min before market
close and decides the amount based on the competition, at two checkpoints:

  - If there are bids from others → bid a competitive amount (value + margin),
    without exceeding your cap (`max_bid`). Don't wait: competition forces a move.
  - If there are NO bids with ~15s left → bid value + a touch (cushion) and done.

The timing is deterministic: it spends no LLM tokens. The agent only picks which
players and with what cap; this runs the finish.
"""

import threading
import time
from datetime import datetime, timezone

from .api import FantasyClient
from . import events, state

CONTESTED_MARGIN_PCT = 0.03   # how far above value to bid if there's competition
UNCONTESTED_CUSHION = 10      # minimum cushion if nobody else bids
DEFAULT_FINAL = 15           # seconds before close for the finish
DEFAULT_POLL = 3             # how often, in seconds, to poll in the final minute


def decide(value, other_bids, seconds_left, max_bid, final=DEFAULT_FINAL):
    """How much to bid NOW, or None to wait.

    - other_bids > 0  → competition: value + margin, capped at max_bid.
    - no competition and <= final s left → value + minimum cushion.
    - otherwise, wait.
    """
    if other_bids > 0:
        competitive = value + max(UNCONTESTED_CUSHION, round(value * CONTESTED_MARGIN_PCT))
        return min(max_bid, competitive)
    if seconds_left <= final:
        return min(max_bid, value + UNCONTESTED_CUSHION)
    return None


def _seconds_left(close_iso):
    close = datetime.fromisoformat(close_iso)
    return (close - datetime.now(timezone.utc)).total_seconds()


def _find(market, market_id):
    for e in market:
        if e.get("id") == market_id:
            return e
    return None


def last_minute_bid(league_id, market_id, max_bid, value=None, final=DEFAULT_FINAL,
                    poll=DEFAULT_POLL, dry_run=False, log=print):
    """Watches until close and places the bid at the optimal moment."""
    fc = FantasyClient()
    el = _find(fc.market(league_id), market_id)
    if not el:
        log(f"[bid] marketId {market_id} is not in the market (already closed?).")
        return None
    if value is None:
        value = el.get("salePrice") or el["playerMaster"].get("marketValue")
    close_iso = el.get("expirationDate")
    nombre = el["playerMaster"].get("nickname", market_id)
    if not close_iso:
        log(f"[bid] {nombre}: no close date; can't time it. Done.")
        return None
    log(f"[bid] {nombre}: value={value:,} cap={max_bid:,} close={close_iso}")

    while True:
        el = _find(fc.market(league_id), market_id)
        if not el:
            log(f"[bid] {nombre}: no longer in the market. Done.")
            return None
        left = _seconds_left(close_iso)
        other_bids = el.get("numberOfBids", 0)
        amount = decide(value, other_bids, left, max_bid, final)
        if amount is not None:
            if dry_run:
                log(f"[bid] {nombre}: WOULD BID {amount:,} "
                    f"(other_bids={other_bids}, {int(left)}s left)")
                return {"dry_run": True, "amount": amount, "other_bids": other_bids}
            resp = fc.make_bid(league_id, market_id, amount)
            log(f"[bid] {nombre}: BID {amount:,} placed "
                f"(other_bids={other_bids}, {int(left)}s left)")
            events.emit("bid", f"Last-minute bid: {amount:,} for {nombre}",
                        detail={"rival_bids": other_bids, "time_left": f"{int(left)}s"})
            return resp
        if left <= 0:
            log(f"[bid] {nombre}: market closed without bidding.")
            return None
        # adaptive polling: long wait far from close, short in the final minute
        if left > 60:
            wait = min(30, left - 60)
        else:
            wait = min(poll, max(1, left - final))
        time.sleep(wait)


def run_bid_plan(league_id, dry_run=False, log=print):
    """Runs the saved bid plan: one thread per target (simultaneous closes)."""
    plan = state.load_bid_plan()
    if not plan:
        return  # nothing to do; silent for the cron job
    log(f"[bid] running plan: {len(plan)} targets")
    threads = []
    for t in plan:
        th = threading.Thread(target=last_minute_bid, kwargs=dict(
            league_id=league_id, market_id=t["market_id"], max_bid=t["max_bid"],
            dry_run=dry_run, log=log))
        th.start()
        threads.append(th)
    for th in threads:
        th.join()
    if not dry_run:
        state.clear_bid_plan()  # plan consumed
