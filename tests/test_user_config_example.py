"""Lock the user_config.example.py contract.

A new user copies user_config.example.py → config.py and runs the engine.
If this template drifts (wrong field names, invalid kind, missing list),
onboarding breaks silently. These tests catch that at CI time.

Run:  python3 -m unittest tests.test_user_config_example
"""
import importlib.util
import os
import unittest

import jobs


REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXAMPLE = os.path.join(REPO, "src", "user_config.example.py")


def _load_example_module():
    """Load user_config.example.py as a standalone module. We can't just
    `import user_config.example` because the dot in the filename isn't
    valid in Python module names."""
    spec = importlib.util.spec_from_file_location("user_config_example", EXAMPLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestUserConfigExample(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(EXAMPLE):
            self.skipTest(f"{EXAMPLE} missing — generate it first")
        self.mod = _load_example_module()

    def test_has_required_lists(self):
        for name in ("SOURCES", "TITLE_BLACKLIST", "LOCATION_BLACKLIST",
                     "HIGHLIGHT_WORDS"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(self.mod, name),
                                f"{name} missing from example config")
                self.assertIsInstance(getattr(self.mod, name), list,
                                      f"{name} must be a list")

    def test_sources_shape(self):
        for src in self.mod.SOURCES:
            with self.subTest(name=src.get("name", "<unnamed>")):
                self.assertIn("name", src)
                self.assertIn("kind", src)
                self.assertIn("slug", src)
                self.assertIn("queries", src)
                self.assertIsInstance(src["queries"], list)

    def test_sources_kind_registered(self):
        """Every example source uses a kind that jobs.FETCHERS knows about —
        otherwise a copy-paste onboarding would crash at the first fetch."""
        for src in self.mod.SOURCES:
            with self.subTest(name=src["name"], kind=src["kind"]):
                self.assertIn(src["kind"], jobs.FETCHERS,
                              f"kind {src['kind']!r} not registered")

    def test_sources_queries_empty_by_default(self):
        """House rule (CLAUDE.md): new sources start with queries=[] so the
        user sees everything first and tightens later."""
        for src in self.mod.SOURCES:
            with self.subTest(name=src["name"]):
                self.assertEqual(
                    src["queries"], [],
                    f"example source {src['name']} should start with queries=[]",
                )

    def test_blacklist_entries_are_non_empty_strings(self):
        for name in ("TITLE_BLACKLIST", "LOCATION_BLACKLIST", "HIGHLIGHT_WORDS"):
            entries = getattr(self.mod, name)
            for entry in entries:
                with self.subTest(name=name, entry=entry):
                    self.assertIsInstance(entry, str)
                    self.assertTrue(entry.strip())


if __name__ == "__main__":
    unittest.main()
