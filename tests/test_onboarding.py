"""Onboarding wizard — drives the per-group dialog with scripted stdin
and asserts the generated user_config.py is a valid Python module that
`src/config.py`'s loader can consume.

Run:  python3 -m unittest tests.test_onboarding
"""
import importlib.util
import io
import os
import tempfile
import unittest
from unittest import mock

import onboarding


def _run_with_stdin(script_lines, data_dir):
    """Feed the wizard a list of input lines, return the generated path."""
    stream = io.StringIO("\n".join(script_lines) + "\n")
    with mock.patch("sys.stdin", stream):
        with mock.patch("builtins.input", side_effect=script_lines):
            rc = onboarding.run_wizard(data_dir)
    return rc


class TestWizardFlow(unittest.TestCase):

    def test_catalog_is_grouped_and_non_empty(self):
        """Sanity check: the catalog has multiple groups and every entry
        carries a kind + slug (the plumbing the wizard needs)."""
        groups = onboarding._group_catalog()
        self.assertGreater(len(groups), 1, "catalog should have multiple groups")
        for name, entries in groups:
            self.assertTrue(name, "group name must not be empty")
            self.assertGreater(len(entries), 0, f"group {name!r} is empty")
            for e in entries:
                self.assertIn("name", e)
                self.assertIn("kind", e)
                self.assertIn("slug", e)

    def test_build_user_config_is_valid_python(self):
        """The emitted file must import cleanly and expose SOURCES as a
        list of dicts, each with the fields jobs.py expects."""
        content = onboarding._build_user_config({"Anthropic", "OpenAI"})
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            spec = importlib.util.spec_from_file_location("_test_uc", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertEqual(len(mod.SOURCES), 2)
            names = {s["name"] for s in mod.SOURCES}
            self.assertEqual(names, {"Anthropic", "OpenAI"})
            for s in mod.SOURCES:
                self.assertIn("kind", s)
                self.assertIn("slug", s)
                self.assertEqual(s["queries"], [])
            # Empty stubs for the three future wizard steps.
            self.assertEqual(mod.HIGHLIGHTS, [])
            self.assertEqual(mod.TITLE_BLACKLIST, [])
            self.assertEqual(mod.LOCATION_BLACKLIST, [])
        finally:
            os.unlink(path)

    def test_build_user_config_strips_group_field(self):
        """`group` is catalog metadata — it must NOT bleed into the
        emitted SOURCES entries (jobs.py doesn't expect it)."""
        content = onboarding._build_user_config({"Anthropic"})
        self.assertNotIn("'group'", content)
        self.assertNotIn('"group"', content)

    def test_wizard_cancels_on_overwrite_decline(self):
        """When an existing user_config.py is present and the user says
        no to the overwrite prompt, the wizard must leave the file
        untouched and return 0."""
        with tempfile.TemporaryDirectory() as tmp:
            existing = os.path.join(tmp, "user_config.py")
            with open(existing, "w") as f:
                f.write("SOURCES = [{'name': 'Keep me', 'kind': 'greenhouse', 'slug': 'keepme'}]\n")
            orig_mtime = os.path.getmtime(existing)
            # Feed: "n" to the overwrite prompt → wizard exits before
            # ever asking about groups.
            with mock.patch("builtins.input", side_effect=["n"]):
                rc = onboarding.run_wizard(tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(os.path.getmtime(existing), orig_mtime)
            with open(existing) as f:
                self.assertIn("Keep me", f.read())

    def test_wizard_skips_every_group_writes_empty_sources(self):
        """Feed 'd' (done) for every group and 'y' to the final write.
        End state: user_config.py written with SOURCES = []."""
        with tempfile.TemporaryDirectory() as tmp:
            n_groups = len(onboarding._group_catalog())
            # One "d" per group + "y" to confirm the write.
            script = ["d"] * n_groups + ["y"]
            with mock.patch("builtins.input", side_effect=script):
                rc = onboarding.run_wizard(tmp)
            self.assertEqual(rc, 0)
            out = os.path.join(tmp, "user_config.py")
            self.assertTrue(os.path.isfile(out))
            spec = importlib.util.spec_from_file_location("_tst", out)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertEqual(mod.SOURCES, [])


if __name__ == "__main__":
    unittest.main()
