"""Location parsing / normalization / grouping.

Every entry here was a regression at some point. When a new location shape
slips through to the "Other" bucket in production, add it here.

Note on layers: `_clean_loc` and `_flatten_locations` are the GENERIC
pipeline run on every job's locations field. Source-specific junk is
dropped INSIDE each fetcher (fetch_workday handles "Virtual, USA" →
"Remote (USA)", fetch_ibm drops "Multiple Cities", fetch_meta drops
department tokens via _is_meta_location). The tests here cover the
generic pipeline + the Workday virtual-remote rewrite that runs on the
fetcher side.

Run:  python3 -m unittest tests.test_locations
"""
import re
import unittest

import jobs


class TestCleanLoc(unittest.TestCase):
    """_clean_loc — low-level cleanup. Strip addresses, trailing office
    tokens, flip region-dash-city, etc. Pure function."""

    CASES = [
        # Reversed region-dash-city (Salesforce Workday, Snyk Ashby)
        ("California - San Francisco",             "San Francisco, California"),
        ("United States - Boston",                 "Boston, United States"),
        ("United States - Boston Local",           "Boston, United States"),
        ("California - San Francisco Office",      "San Francisco, California"),
        ("France - Paris",                         "Paris, France"),
        ("Virginia - Mclean",                      "Mclean, Virginia"),

        # Workday multi-dash state-city-street (Cisco)
        ("California- San Jose - 1730 Fox Drive",  "San Jose"),

        # Hyphenated city names must NOT be flipped by region-dash
        ("Winston-Salem",                          "Winston-Salem"),

        # Remote-prefix stripping
        ("Remote - United States",                 "United States"),

        # Pass-through: already clean
        ("Austin, TX",                             "Austin, TX"),
        ("San Francisco",                          "San Francisco"),

        # Trailing dangling comma / parenthesis
        ("Canada)",                                "Canada"),
        ("Austria (Remote)",                       "Austria"),

        # Anywhere-in
        ("Anywhere in France",                     "France"),
    ]

    def test_all(self):
        for raw, expected in self.CASES:
            with self.subTest(raw=raw):
                self.assertEqual(jobs._clean_loc(raw), expected)


class TestParseLoc(unittest.TestCase):
    """_parse_loc returns (city, country, display)."""

    CASES = [
        # Country only
        ("USA",     ("USA", "USA", "USA")),
        ("France",  ("France", "France", "France")),

        # US-state only → state, USA
        ("Delaware", ("Delaware", "USA", "Delaware, USA")),
        ("Texas",    ("Texas", "USA", "Texas, USA")),

        # Reversed region-dash → flipped, then recognized
        ("California - San Francisco",
         ("San Francisco", "USA", "San Francisco, USA")),
        ("United States - Boston",
         ("Boston", "USA", "Boston, USA")),

        # Known city auto-pins country
        ("San Francisco",
         ("San Francisco", "USA", "San Francisco, USA")),
        ("Paris",
         ("Paris", "France", "Paris, France")),
    ]

    def test_all(self):
        for raw, expected in self.CASES:
            with self.subTest(raw=raw):
                self.assertEqual(jobs._parse_loc(raw), expected)


class TestFlattenLocations(unittest.TestCase):
    """_flatten_locations is the end-to-end flattener used by every fetcher.
    Input: list of raw strings. Output: deduped, normalized list."""

    def test_region_dash_variants_dedup(self):
        raw = [
            "California - San Francisco",
            "United States - Boston",
            "United States - Boston Local",
            "Austin, TX",
        ]
        out = jobs._flatten_locations(raw)
        self.assertIn("San Francisco, USA", out)
        self.assertIn("Boston, USA", out)
        self.assertIn("Austin, USA", out)
        # Boston + Boston Local must dedupe to one entry
        self.assertEqual(out.count("Boston, USA"), 1)

    def test_empty_input(self):
        self.assertEqual(jobs._flatten_locations([]), [])
        self.assertEqual(jobs._flatten_locations(None), [])

    def test_html_entities_decoded(self):
        # Meta leaked HTML-encoded tokens into locations; flattener must decode.
        out = jobs._flatten_locations(["Austin&nbsp;,&nbsp;TX"])
        for x in out:
            self.assertNotIn("&nbsp;", x)
            self.assertNotIn("&amp;", x)


class TestGroupLocations(unittest.TestCase):
    """_group_locations buckets flattened locs by country for the report."""

    def test_region_dash_shapes_not_in_other(self):
        """The 3 shapes that landed in "Other" repeatedly in Oct 2026 must
        resolve to USA. If this breaks, Salesforce/Snyk feed regressed."""
        flat = jobs._flatten_locations([
            "California - San Francisco",
            "United States - Boston",
            "United States - Boston Local",
        ])
        groups = dict(jobs._group_locations(flat))
        self.assertNotIn("Other", groups,
                         f"regression — Other bucket not empty: {groups.get('Other')}")
        self.assertIn("USA", groups)

    def test_other_bucket_sorts_last(self):
        """Even when Other exists (unknown shapes), it must sort LAST so the
        known countries are listed first."""
        flat = ["Antarctica", "Paris, France", "San Francisco, USA"]
        out = jobs._group_locations(flat)
        # If Other is present, it must be at the end.
        for name, _ in out[:-1]:
            self.assertNotEqual(name, "Other",
                                f"Other must be last, got {[n for n,_ in out]}")

    def test_remote_bucket(self):
        flat = ["Remote", "Remote Friendly", "Remote - Europe"]
        groups = dict(jobs._group_locations(flat))
        self.assertIn("Remote", groups)


class TestWorkdayVirtualRewrite(unittest.TestCase):
    """fetch_workday normalizes "Virtual, <X>" → "Remote (<X>)" so Intel's
    remote jobs don't look like a city called "Virtual". This replicates
    the exact code path in fetch_workday without hitting the network."""

    @staticmethod
    def _rewrite(loc):
        """Mirror of the inline rewrite in fetch_workday (jobs.py:2274-2280)."""
        m_virt = re.match(r'^\s*Virtual\s*,\s*(.+?)\s*$', loc, re.IGNORECASE)
        if m_virt:
            return f"Remote ({m_virt.group(1)})"
        if loc.strip().lower() == "virtual":
            return "Remote"
        return loc

    def test_virtual_country(self):
        self.assertEqual(self._rewrite("Virtual, USA"), "Remote (USA)")
        self.assertEqual(self._rewrite("virtual , Canada"), "Remote (Canada)")

    def test_virtual_alone(self):
        self.assertEqual(self._rewrite("Virtual"), "Remote")
        self.assertEqual(self._rewrite("  virtual  "), "Remote")

    def test_real_city_untouched(self):
        self.assertEqual(self._rewrite("Austin, TX"), "Austin, TX")
        self.assertEqual(self._rewrite("San Francisco"), "San Francisco")


if __name__ == "__main__":
    unittest.main()
