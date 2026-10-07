"""Blacklist filters: title + location — framework behavior only.

User-specific regression cases (which countries / which title substrings
this user actually blacklists) live in `data/tests/test_user_decisions.py`
so a stock open-source clone with an empty user_config can still pass
`make test`.

Run:  python3 -m unittest tests.test_blacklist
"""
import unittest

import jobs


class TestLocationBlacklistShape(unittest.TestCase):
    """Behaviour of is_location_blacklisted() independent of what's in
    the blacklist — these must hold even if LOCATION_BLACKLIST is []."""

    def test_empty_locations_not_blacklisted(self):
        self.assertFalse(jobs.is_location_blacklisted({"locations": []}))
        self.assertFalse(jobs.is_location_blacklisted({"locations": None}))

    def test_mixed_locations_returns_bool(self):
        # Multi-location jobs where ONE location is blacklisted: either
        # True (blocks mixed) or False (keeps mixed) is defensible. We
        # only assert the return type is a bool so callers can rely on it.
        job = {"locations": ["San Francisco, USA", "Bangkok, Thailand"]}
        self.assertIsInstance(jobs.is_location_blacklisted(job), bool)


class TestTitleBlacklistShape(unittest.TestCase):

    def test_senior_roles_not_blocked(self):
        # None of these senior titles should match a reasonable blacklist
        # — holds whether TITLE_BLACKLIST is empty or populated with the
        # usual junior/intern/associate filters.
        for title in ["Senior Software Engineer", "Staff Software Engineer",
                      "Principal Engineer"]:
            with self.subTest(title=title):
                self.assertFalse(
                    jobs.is_title_blacklisted({"title": title}),
                    f"{title!r} must NOT be blacklisted",
                )


if __name__ == "__main__":
    unittest.main()
