"""Private positions — jobs received through back-channels (recruiter DM,
network intro, …) that the user wants to track alongside scraped ones.

Shape contract (data/private_positions.json): a JSON array of dicts, each
with at least `company` + `title` + `url`. The loader groups them by
company and the main pipeline merges them into the matching source's job
list right after the parallel fetch completes — downstream scoring / like
/ reject work unchanged because they only look at the dict shape.

Run:  python3 -m unittest tests.test_private_positions
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import jobs


class TestLoadPrivatePositions(unittest.TestCase):

    def test_returns_empty_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(jobs, "DATA_DIR", tmp):
                self.assertEqual(jobs._load_private_positions(), {})

    def test_returns_empty_on_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "private_positions.json"), "w") as f:
                f.write("{not json")
            with mock.patch.object(jobs, "DATA_DIR", tmp):
                self.assertEqual(jobs._load_private_positions(), {})

    def test_groups_by_company_and_normalizes_shape(self):
        entries = [
            {
                "company": "Ledger",
                "title": "Product Security Director (private conversation)",
                "locations": ["Paris"],
                "url": "private://ledger/psd",
                "description": "<p>Compensation: 200k€ + 30%</p>",
                "blob": "psd ledger",
                "salary": "200k€ + 30% variable",
            },
            {
                "company": "Ledger",
                "title": "Another role",
                "url": "private://ledger/other",
            },
            {
                # Missing company → silently skipped (not something a user
                # should hit, but guard against hand-edit mistakes).
                "title": "Orphan",
                "url": "private://orphan",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "private_positions.json"), "w") as f:
                json.dump(entries, f)
            with mock.patch.object(jobs, "DATA_DIR", tmp):
                out = jobs._load_private_positions()
        self.assertIn("Ledger", out)
        self.assertEqual(len(out["Ledger"]), 2)
        first = out["Ledger"][0]
        self.assertEqual(first["title"], "Product Security Director (private conversation)")
        self.assertEqual(first["locations"], ["Paris"])
        self.assertEqual(first["url"], "private://ledger/psd")
        self.assertEqual(first["salary"], "200k€ + 30% variable")
        # Missing-company entry is dropped, not raised.
        self.assertNotIn("", out)
        self.assertNotIn(None, out)

    def test_blob_falls_back_to_title(self):
        """blob is used by the per-source query filter — when the user
        hand-adds a private position without a blob, we must still have
        enough searchable text that `matches(j, queries)` can evaluate."""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "private_positions.json"), "w") as f:
                json.dump([{
                    "company": "X",
                    "title": "Head of Security",
                    "url": "private://x/hos",
                }], f)
            with mock.patch.object(jobs, "DATA_DIR", tmp):
                out = jobs._load_private_positions()
        self.assertEqual(out["X"][0]["blob"], "Head of Security")


class TestBatchPromptSplits(unittest.TestCase):
    """The ⌘I / ⌘U batch prompt handles public and private URLs
    differently: public = URL-only (Claude fetches), private = full
    inline block (Claude can't fetch private:// URLs). This test reads
    the JS source directly because the function is defined inside the
    HTML_TEMPLATE triple-quoted string."""

    def setUp(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            src = f.read()
        self.scoring_fn = (
            src.split("function _buildClaudeScoringPrompt")[1]
            .split("\n}")[0]
        )

    def test_private_scheme_dispatched_to_inline_block(self):
        """`u.startsWith('private://')` must route to _formatJobBlock —
        otherwise private jobs appear in the prompt as just an unfetchable
        URL and Claude has no way to score them."""
        self.assertIn("private://", self.scoring_fn)
        self.assertIn("_formatJobBlock", self.scoring_fn)

    def test_public_urls_stay_url_only(self):
        """Public URLs must be emitted as `[idx] <url>` — not inlined.
        Protects against a regression that would re-inline all jobs and
        blow up the prompt size for 100+-job batches."""
        # The marker '[' + idx + '] ' + u is the compact URL-only form.
        self.assertIn("'[' + idx + '] ' + u", self.scoring_fn)


class TestRealLedgerEntry(unittest.TestCase):
    """Smoke test on the actual data/private_positions.json shipped in the
    user's data dir — makes sure the on-disk file is loadable and the
    Ledger entry has the suffix the user asked for."""

    def test_ledger_entry_present(self):
        # Use the real DATA_DIR (jobs._cfg.DATA_DIR) — this test only
        # asserts if the user has a Ledger entry; it is tolerant on
        # fresh clones where private_positions.json is absent (file
        # is gitignored under data/).
        out = jobs._load_private_positions()
        if "Ledger" not in out:
            self.skipTest("no Ledger private position on disk")
        titles = [j["title"] for j in out["Ledger"]]
        self.assertTrue(
            any("(private conversation)" in t for t in titles),
            f"expected a title with '(private conversation)' suffix, got {titles}",
        )


if __name__ == "__main__":
    unittest.main()
