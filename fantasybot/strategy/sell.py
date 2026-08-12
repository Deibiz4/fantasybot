"""SELL advisor: who to offload and at what price.

Safe rule: only proposes selling players NOT in your optimal XI (so it doesn't
break your lineup) and only for a clear reason:
  1) Transfer risk: valuable but outside the probable lineup (the ⚠ Etta types) →
     sell him before he leaves LaLiga and his value collapses.
  2) Falling value: his trend is clearly negative → cash in before losing more.

It does NOT touch a cheap backup whose value is rising or stable (an appreciating
asset or useful rotation).
"""

from ..matching import match_name, POS
from .lineup import payload_ids

FALLING_THRESHOLD = -20  # trend (from futbolfantasy) below which it's "falling"


def sell_candidates(team, best, trends_index, falling_threshold=FALLING_THRESHOLD):
    """Players recommended to sell, with reason, priority and suggested price."""
    xi_ids = payload_ids(best)
    watch_ids = {w["playerTeamId"] for w in best.get("watch", [])}

    out = []
    for p in team["players"]:
        pm = p["playerMaster"]
        ptid = p.get("playerTeamId") or pm["id"]
        if ptid in xi_ids:
            continue  # he's a starter → don't sell

        valor = pm.get("marketValue") or 0
        trend = match_name(pm.get("nickname", ""), pm.get("name", ""), trends_index)
        tendencia = trend.get("tendencia") if trend else None

        if ptid in watch_ids:
            reason, prio = "transfer risk (out of the lineup, valuable)", 1
        elif tendencia is not None and tendencia <= falling_threshold:
            reason, prio = f"falling value (trend {tendencia})", 2
        else:
            continue  # stable/rising backup → keep

        out.append({
            "nombre": pm.get("nickname") or pm.get("name"),
            "player_id": pm.get("id"),
            "pos": POS.get(pm.get("positionId"), "?"),
            "valor": valor,
            "sale_price": round(valor),  # fair price for a quick sale
            "tendencia": tendencia,
            "reason": reason,
            "priority": prio,
        })
    out.sort(key=lambda c: (c["priority"], -c["valor"]))
    return out
