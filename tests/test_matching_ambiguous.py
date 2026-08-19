"""Regression: match_name must not silently pick one of several ambiguous matches.

The token fallback accepted the FIRST index entry whose key contained all the
nickname tokens. With a short/common nickname ("Pedro", "Álvarez") several players
match and it returned an arbitrary one — a false positive that SANITY_MAX_DIFF in
flip.py then has to paper over. An ambiguous token match must resolve to None; the
real fix (an ID crosswalk) builds on top of a matcher that no longer lies.
"""

import unittest

from fantasybot.matching import index_by_name, match_name


class TestAmbiguousMatch(unittest.TestCase):
    def test_ambiguous_token_match_is_rejected(self):
        index = index_by_name([{"nombre": "pedro porro", "v": 1},
                               {"nombre": "pedro leon", "v": 2}])
        # "Pedro" alone matches BOTH keys -> must not pick one at random
        self.assertIsNone(match_name("Pedro", "", index))

    def test_unique_token_match_still_works(self):
        index = index_by_name([{"nombre": "karl etta eyong", "v": 1},
                               {"nombre": "pedro porro", "v": 2}])
        # "Etta Eyong" matches exactly one key -> still resolved
        self.assertEqual(match_name("Etta Eyong", "", index)["v"], 1)


if __name__ == "__main__":
    unittest.main()
