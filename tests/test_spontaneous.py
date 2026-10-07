"""Spontaneous-application detection.

is_spontaneous(job) returns True for titles like "Introduce Yourself",
"General Application", "Don't see the right role" etc. These are
surfaced as a ✉ link at the top of each section, not in the main list.

Run:  python3 -m unittest tests.test_spontaneous
"""
import unittest

import jobs


class TestIsSpontaneous(unittest.TestCase):

    POSITIVES = [
        "Introduce Yourself!",             # Oct 2026 regression
        "introduce yourself",              # case-insensitive
        "General Application",
        "Spontaneous application",
        "Speculative Application",
        "Don't see the right role?",
        "Don't see a role that fits?",
        "Candidature Spontanee",           # FR singular
        "Candidatures Spontanees",         # FR plural — surfaced by Zama's hand-rolled board
    ]

    NEGATIVES = [
        "Software Engineer",
        "Senior Security Engineer",
        "VP of Engineering",
        "Director, Product Design",
        "Staff Software Engineer, Platform",
    ]

    def test_positives(self):
        for title in self.POSITIVES:
            with self.subTest(title=title):
                self.assertTrue(
                    jobs.is_spontaneous({"title": title}),
                    f"{title!r} should be detected as spontaneous",
                )

    def test_negatives(self):
        for title in self.NEGATIVES:
            with self.subTest(title=title):
                self.assertFalse(
                    jobs.is_spontaneous({"title": title}),
                    f"{title!r} should NOT be detected as spontaneous",
                )


if __name__ == "__main__":
    unittest.main()
