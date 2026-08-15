"""Lineup optimizer: it must always send a COMPLETE, POSITION-VALID XI.

LaLiga's rule (confirmed live): a player fielded OUT of position is silently dropped
(a midfielder sent as a defender comes off the lineup, leaving the slot empty), but a
player who is injured/suspended yet IN position is KEPT — he just scores 0. So the
optimizer must fill each line from its OWN players, using a line's injured players to
backfill that same line rather than borrowing a healthy player from another line.

Regression for the reported bug: a thin, injury-hit defence made the optimizer plug
defender slots with midfielders; LaLiga dropped them and the '11' it applied reached
the pitch as 9. The fix keeps every slot position-valid.

Run with:  python -m unittest discover -s tests
"""

import unittest

from fantasybot.strategy.lineup import optimize, payload_ids


def _player(pid, position_id, value, status="ok", last=0, name=None):
    """A squad member in the shape `optimize` expects (team['players'][i])."""
    return {
        "playerTeamId": pid,
        "playerMaster": {
            "id": f"m{pid}",
            "nickname": name or pid,
            "name": name or pid,
            "positionId": position_id,   # 1 GK, 2 DEF, 3 MED, 4 DEL
            "marketValue": value,
            "playerStatus": status,      # anything != "ok" => unavailable
            "lastSeasonPoints": last,
        },
    }


def _available_ids(best):
    """playerTeamIds that ended up in the XI and are marked available."""
    ok = set()
    for slot in ("goalkeeper", "defender", "midfield", "striker"):
        entries = best[slot]
        entries = entries if isinstance(entries, list) else [entries]
        for e in entries:
            if e["disponible"]:
                ok.add(e["playerTeamId"])
    return ok


def _slot_counts(best):
    d, m, f = best["formation"]
    p = best["payload"]
    return {
        "goalkeeper": 1 if p["goalkeeper"] else 0,
        "defender": len(p["defender"]),
        "midfield": len(p["midfield"]),
        "striker": len(p["striker"]),
    }, (1, d, m, f)


class TestLineupNeverEmptyNeverUnavailable(unittest.TestCase):
    def test_forced_defender_crisis_stays_position_valid(self):
        """Only 1 available defender, plenty of available midfielders.

        Every legal formation needs >= 3 defenders. The squad owns exactly 3 defenders,
        two of them injured. The optimizer must field those injured defenders in the
        defender slots (LaLiga keeps them, they score 0) and NOT plug the holes with
        healthy midfielders — a midfielder sent as a defender is dropped by LaLiga, so
        that 'trick' would reach the pitch as a 9-player XI. The extra midfielders stay
        on the bench.
        """
        players = [
            _player("gk1", 1, 5_000_000),
            _player("d1", 2, 8_000_000),
            _player("d2", 2, 8_000_000, status="injured"),
            _player("d3", 2, 8_000_000, status="injured"),
            _player("m1", 3, 8_000_000),
            _player("m2", 3, 8_000_000),
            _player("m3", 3, 8_000_000),
            _player("m4", 3, 8_000_000),
            _player("m5", 3, 8_000_000),
            _player("m6", 3, 8_000_000),
            _player("s1", 4, 20_000_000),
            _player("s2", 4, 15_000_000),
            _player("s3", 4, 10_000_000),
        ]
        best = optimize({"players": players}, prob_index={})

        counts, (g, d, m, f) = _slot_counts(best)
        # every slot in the chosen formation is filled (never empty)
        self.assertEqual(counts["goalkeeper"], g)
        self.assertEqual(counts["defender"], d)
        self.assertEqual(counts["midfield"], m)
        self.assertEqual(counts["striker"], f)

        # 11 fielded, and EVERY slot is position-valid (this is what LaLiga accepts)
        p = best["payload"]
        self.assertEqual(len(payload_ids(best)), 11)
        defenders, mids, strikers = {"d1", "d2", "d3"}, \
            {"m1", "m2", "m3", "m4", "m5", "m6"}, {"s1", "s2", "s3"}
        self.assertTrue(set(p["defender"]) <= defenders,
                        f"non-defenders in the defender line: "
                        f"{set(p['defender']) - defenders}")
        self.assertTrue(set(p["midfield"]) <= mids)
        self.assertTrue(set(p["striker"]) <= strikers)
        # the injured defenders ARE fielded (kept in position), not swapped for mids
        self.assertEqual(set(p["defender"]), {"d1", "d2", "d3"})

    def test_healthy_squad_unchanged(self):
        """A healthy squad still gets a full, all-available XI (no regression)."""
        players = [_player("gk1", 1, 5_000_000)]
        players += [_player(f"d{i}", 2, 8_000_000) for i in range(1, 6)]
        players += [_player(f"m{i}", 3, 8_000_000) for i in range(1, 6)]
        players += [_player(f"s{i}", 4, 10_000_000) for i in range(1, 4)]
        best = optimize({"players": players}, prob_index={})
        self.assertEqual(len(payload_ids(best)), 11)
        self.assertEqual(payload_ids(best), _available_ids(best))


if __name__ == "__main__":
    unittest.main()
