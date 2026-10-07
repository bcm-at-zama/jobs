"""User-specific regression guards.

These tests encode this user's `data/user_config.py` choices — the
specific locations/titles they do not want to see, and the fact that
their SOURCES list is populated. They would fail in a stock
open-source clone (empty blacklists, empty SOURCES), so they live in
`data/tests/` (gitignored, excluded by `script/export-opensource.sh`)
rather than in `tests/`.

Framework-level behavior (regex shape, mixed-location semantics, slug
rules, parser integrity) stays in `tests/` so an OSS clone's
`make test` passes clean.

Run (part of the private `make test`):
    PYTHONPATH=src python3 -m unittest discover data/tests
"""
import unittest

import config
import jobs


class TestLocationBlacklistDecisions(unittest.TestCase):
    """Each entry here is a product decision — if a test fails,
    data/user_config.py was edited in a way that broke a previous
    decision, intentionally or not."""

    BLACKLIST_CASES = [
        ("Bangkok, Thailand",         True),   # Added 2026-10
        ("Thailand",                  True),
        ("Mumbai, India",             True),
        ("Tel Aviv, Israel",          True),
        ("Dublin, Ireland",           True),
        ("Tokyo, Japan",              True),
        ("Belgrade, Serbia",          True),
        ("Warsaw, Poland",            True),
        ("Ho Chi Minh City, Vietnam", True),
        ("Manila, Philippines",       True),

        ("Austin, USA",               False),
        ("San Francisco, USA",        False),
        ("Paris, France",             False),
        ("London, UK",                False),
        ("Berlin, Germany",           False),
        ("Remote",                    False),
    ]

    def test_all(self):
        for loc, expected in self.BLACKLIST_CASES:
            job = {"locations": [loc]}
            with self.subTest(location=loc):
                self.assertEqual(
                    jobs.is_location_blacklisted(job), expected,
                    f"{loc!r} blacklist decision wrong",
                )


class TestTitleBlacklistDecisions(unittest.TestCase):

    def test_junior_and_intern_blocked(self):
        for title in ["Junior Developer", "Software Engineering Intern",
                      "Associate Engineer"]:
            with self.subTest(title=title):
                self.assertTrue(
                    jobs.is_title_blacklisted({"title": title}),
                    f"{title!r} should be blacklisted",
                )


class TestSourcesPopulated(unittest.TestCase):

    def test_sources_list_non_empty(self):
        self.assertTrue(config.SOURCES, "config.SOURCES is empty")


if __name__ == "__main__":
    unittest.main()
