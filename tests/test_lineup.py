"""Lineup optimizer: it must never field an UNAVAILABLE player, and it must never
leave a formation slot empty (it backfills from the available bench instead).

Regression for the reported bug: the agent removed an injured striker from the XI
and left the slot empty (LaLiga drops an unavailable player from the lineup).

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
    def test_forced_defender_crisis_backfills_available(self):
        """Only 1 available defender but the squad has plenty of available midfielders.

        Old behaviour: the only count-feasible formations need 3 defenders, so the
        optimizer fills the two missing defender slots with INJURED defenders -> those
        slots come back empty when the lineup is sent. The optimizer must instead
        backfill from the available bench so every fielded player is available.
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

        # and nobody fielded is unavailable
        fielded = payload_ids(best)
        self.assertEqual(len(fielded), 11)
        injured = {"d2", "d3"}
        self.assertFalse(fielded & injured,
                         f"unavailable players fielded: {fielded & injured}")
        self.assertEqual(fielded, _available_ids(best),
                         "every fielded player must be available")

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
