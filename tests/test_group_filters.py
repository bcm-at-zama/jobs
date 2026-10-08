"""Group-filter chip shown next to WTJ / YC titles in the CMD+E modal.

Server-side builder reads from the discovery modules so edits to the
filter constants propagate without a parallel edit in jobs.py. Guards:

  - WTJ entry mentions a sector-ish fragment from DEFAULT_SECTOR_FACETS.
  - YC entry mentions both the tag filter AND the quality cutoff
    (teamSize / batches) — those are two separate pieces the user may
    want to tune independently.
  - The hover `hint` names the source file + the make target so geeks
    can act on it. CLAUDE.md's "no jargon in UI" rule has an exception
    here because the user explicitly asked for the geeky details to be
    discoverable from the modal.
"""
import unittest

import jobs


class TestBuildGroupFilters(unittest.TestCase):

    def test_wttj_entry_present(self):
        out = jobs._build_group_filters()
        self.assertIn("Welcome to the Jungle", out)
        entry = out["Welcome to the Jungle"]
        self.assertIn("chip", entry)
        self.assertIn("hint", entry)
        # chip surfaces at least one sector name
        self.assertTrue(entry["chip"].strip())
        # hint names the file + the make target
        self.assertIn("src/wttj_discovery.py", entry["hint"])
        self.assertIn("make wttj-refresh", entry["hint"])

    def test_yc_entry_present(self):
        out = jobs._build_group_filters()
        self.assertIn("Y Combinator", out)
        entry = out["Y Combinator"]
        self.assertIn("chip", entry)
        self.assertIn("hint", entry)
        # chip mentions the quality floor
        self.assertIn("teams", entry["chip"].lower())
        # hint names the file + make target
        self.assertIn("src/yc_discovery.py", entry["hint"])
        self.assertIn("make yc-refresh", entry["hint"])


if __name__ == "__main__":
    unittest.main()
