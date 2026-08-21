"""Unit tests for rival budget calculation, clause tracking, and activity accounting.
No network calls — mock client and data.
"""

import unittest

from fantasybot.strategy.rivals import (
    parse_activity,
    analyze_squad_clauses,
    autocalibrate_initial_cash,
    analyze_rivals,
    TYPE_MARKET_BUY,
    TYPE_MARKET_SELL,
    TYPE_DIRECT_TRANSFER,
    TYPE_MATCHDAY_REWARD,
)
from fantasybot.state import snapshot_rivals, diff_rival_clauses


class TestRivalAccounting(unittest.TestCase):
    def test_parse_activity_accounting(self):
        activity = [
            # User 100 buys player from market for 10M
            {"activityTypeId": TYPE_MARKET_BUY, "user1Id": 100, "amount": 10_000_000},
            # User 100 sells player to market for 15M
            {"activityTypeId": TYPE_MARKET_SELL, "user1Id": 100, "amount": 15_000_000},
            # User 100 receives matchday reward of 2M
            {"activityTypeId": TYPE_MATCHDAY_REWARD, "user1Id": 100, "amount": 2_000_000},
            # User 200 buys player from User 100 for 8M
            {"activityTypeId": TYPE_DIRECT_TRANSFER, "user1Id": 200, "user2Id": 100, "amount": 8_000_000},
        ]
        flow = parse_activity(activity)

        u100 = flow[100]
        self.assertEqual(u100["purchases"], 10_000_000)
        self.assertEqual(u100["sales"], 15_000_000 + 8_000_000)  # 23M
        self.assertEqual(u100["prizes"], 2_000_000)
        self.assertEqual(u100["transactions_count"], 4)

        u200 = flow[200]
        self.assertEqual(u200["purchases"], 8_000_000)
        self.assertEqual(u200["sales"], 0)
        self.assertEqual(u200["prizes"], 0)
        self.assertEqual(u200["transactions_count"], 1)

    def test_parse_empty_activity(self):
        flow = parse_activity([])
        self.assertEqual(flow, {})

    def test_analyze_squad_clauses(self):
        players = [
            {
                "playerMaster": {"id": "1", "name": "Vinicius", "nickname": "Vini", "marketValue": 50_000_000, "positionId": 4},
                "buyoutClause": 70_000_000,
            },
            {
                "playerMaster": {"id": "2", "name": "Pedri", "marketValue": 30_000_000, "positionId": 3},
                "buyoutClause": 30_000_000,
            },
            {
                "playerMaster": {"id": "3", "name": "Kubo", "marketValue": 25_000_000, "positionId": 3},
                "buyoutClause": 85_000_000,  # Max clause
            },
        ]
        res = analyze_squad_clauses(players)
        self.assertIsNotNone(res["top_protected"])
        self.assertEqual(res["top_protected"]["name"], "Kubo")
        self.assertEqual(res["top_protected"]["invested"], 60_000_000)
        self.assertEqual(res["max_clause_player"]["buyout_clause"], 85_000_000)

    def test_autocalibrate_initial_cash(self):
        teams = [
            {"managerId": 100, "teamMoney": None},
            {"managerId": 200, "teamMoney": 10_000_000},
        ]
        flow = {
            200: {"purchases": 25_000_000, "sales": 15_000_000, "prizes": 2_000_000},
        }
        # Initial cash = 10M (current) - 15M (sales) - 2M (prizes) + 25M (purchases) = 18M
        init = autocalibrate_initial_cash(teams, flow)
        self.assertEqual(init, 18_000_000)

    def test_analyze_rivals(self):
        teams = [
            {
                "id": "1001",
                "managerId": 100,
                "position": 1,
                "teamPoints": 50,
                "teamValue": 100_000_000,
                "manager": {"id": 100, "managerName": "Leader"},
                "players": [
                    {
                        "playerMaster": {"id": "1", "name": "Star", "marketValue": 40_000_000, "positionId": 4},
                        "buyoutClause": 55_000_000,
                    }
                ],
                "teamMoney": None,  # rival -> money hidden
            },
            {
                "id": "1002",
                "managerId": 200,
                "position": 2,
                "teamPoints": 40,
                "teamValue": 80_000_000,
                "manager": {"id": 200, "managerName": "MyTeam"},
                "players": [],
                "teamMoney": 12_345_678,  # authenticated user
            },
        ]
        activity = [
            {"id": "a1", "activityTypeId": TYPE_MARKET_BUY, "user1Id": 100, "amount": 25_000_000},
            {"id": "a2", "activityTypeId": TYPE_MARKET_SELL, "user1Id": 100, "amount": 10_000_000},
            {"id": "a3", "activityTypeId": TYPE_MATCHDAY_REWARD, "user1Id": 100, "amount": 1_000_000},
            # User 200 activity:
            {"id": "a4", "activityTypeId": TYPE_MARKET_BUY, "user1Id": 200, "amount": 20_000_000},
            {"id": "a5", "activityTypeId": TYPE_MARKET_SELL, "user1Id": 200, "amount": 10_000_000},
        ]

        class MockClient:
            def league_teams(self, lid):
                return teams
            def league_activity(self, lid, fetch_all=True):
                return activity

        rivals = analyze_rivals(MockClient(), "017906460", initial_budget=50_000_000)
        self.assertEqual(len(rivals), 2)

        r1 = rivals[0]
        self.assertEqual(r1["manager_name"], "Leader")
        self.assertEqual(r1["purchases"], 25_000_000)
        self.assertEqual(r1["sales"], 10_000_000)
        self.assertEqual(r1["prizes"], 1_000_000)
        # Expected balance = 50M (initial) + 10M (sales) + 1M (prizes) - 25M (purchases) = 36M
        self.assertEqual(r1["estimated_balance"], 36_000_000)
        self.assertFalse(r1["is_me"])

        r2 = rivals[1]
        self.assertEqual(r2["manager_name"], "MyTeam")
        self.assertTrue(r2["is_me"])
        self.assertEqual(r2["known_balance"], 12_345_678)
        # Pure estimated balance = 50M (initial) + 10M (sales) - 20M (purchases) = 40M
        self.assertEqual(r2["estimated_balance"], 40_000_000)

    def test_diff_rival_clauses(self):
        prev = {
            "managers": {
                "Leader": {
                    "10": {"name": "Mbappe", "clause": 50_000_000},
                    "20": {"name": "Bellingham", "clause": 40_000_000},
                }
            }
        }
        curr = {
            "managers": {
                "Leader": {
                    "10": {"name": "Mbappe", "clause": 65_000_000},  # raised +15M
                    "20": {"name": "Bellingham", "clause": 40_000_000},
                }
            }
        }
        diffs = diff_rival_clauses(prev, curr)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["manager"], "Leader")
        self.assertEqual(diffs[0]["name"], "Mbappe")
        self.assertEqual(diffs[0]["delta"], 15_000_000)


if __name__ == "__main__":
    unittest.main()
