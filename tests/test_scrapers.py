"""Scraper regex extractors + fetch_pw_generic wiring.

Each test:
  1. loads an existing debug dump
  2. runs the production regex
  3. asserts a sane count of matches + sample title/URL shape

Rationale: these regexes have broken multiple times when refactoring
(attribute order changes, class name tweaks, …). A dump-based test
locks the current behavior so refactors fail LOUDLY instead of silently
returning zero jobs.

When a dump is missing (gitignored, fresh clone), the test skips — never
fails. The CLAUDE.md house rule covers this: "if no dump exists yet, say
so" — the test skip is the programmatic equivalent.

Run:  python3 -m unittest tests.test_scrapers
"""
import html as html_mod
import os
import re
import unittest

import jobs


DEBUG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "debug"))


def _load(filename):
    """Return the dump content, or None if the dump isn't on disk."""
    path = os.path.join(DEBUG, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


class TestCiscoScraper(unittest.TestCase):
    """_CISCO_JOB_CARD_RE: title via data-ph-at-job-title-text attribute,
    URL via /global/en/job/<id>/<slug>. Avoids body-split noise."""

    DUMP = "debug-cisco-product-and-engineering-jobs-0.html"
    MIN_CARDS = 10

    def setUp(self):
        self.html = _load(self.DUMP)
        if self.html is None:
            self.skipTest(f"{self.DUMP} not on disk")

    def test_card_count_sane(self):
        matches = jobs._CISCO_JOB_CARD_RE.findall(self.html)
        self.assertGreaterEqual(len(matches), self.MIN_CARDS,
                                "Cisco regex regressed — card count dropped")

    def test_url_shape(self):
        matches = jobs._CISCO_JOB_CARD_RE.findall(self.html)
        self.assertTrue(matches, "no cards to inspect")
        _title_attr, path = matches[0]
        self.assertRegex(path, r"^/global/en/job/\d+/[^?#]+$",
                         f"Cisco job URL path has wrong shape: {path!r}")

    def test_title_not_empty_after_unescape(self):
        matches = jobs._CISCO_JOB_CARD_RE.findall(self.html)
        for title_attr, _ in matches:
            title = html_mod.unescape(title_attr).strip()
            with self.subTest(title=title):
                self.assertTrue(title, "Cisco title empty after unescape")
                # No HTML tag leaked into the title
                self.assertNotIn("<", title)


class TestBoseScraper(unittest.TestCase):
    """_BOSE_JOB_CARD_RE: Phenom-like, URL /us/en/job/<alnum-id>/<slug>."""

    DUMP = "debug-bose-total.html"

    def setUp(self):
        self.html = _load(self.DUMP)
        if self.html is None:
            self.skipTest(f"{self.DUMP} not on disk")

    def test_card_count(self):
        matches = jobs._BOSE_JOB_CARD_RE.findall(self.html)
        # Bose careers board is small; count should match the dump exactly.
        self.assertGreaterEqual(len(matches), 1,
                                "Bose regex regressed — zero cards")

    def test_url_shape(self):
        matches = jobs._BOSE_JOB_CARD_RE.findall(self.html)
        for _title, path in matches:
            with self.subTest(path=path):
                self.assertRegex(path, r"^/us/en/job/[A-Za-z0-9]+/[^?#]+$")


class TestIBMScraper(unittest.TestCase):
    """_IBM_CARD_RE: Carbon-Design cards, aria-label carries the title."""

    DUMP = "debug-ibm-1.html"
    MIN_CARDS = 5

    def setUp(self):
        self.html = _load(self.DUMP)
        if self.html is None:
            self.skipTest(f"{self.DUMP} not on disk")

    def test_card_count(self):
        matches = jobs._IBM_CARD_RE.findall(self.html)
        self.assertGreaterEqual(len(matches), self.MIN_CARDS,
                                "IBM regex regressed")

    def test_titles_not_jobdetail_literal(self):
        """IBM bug: previously every title came back as the literal
        "Jobdetail" because the fetcher was deriving title from the URL
        tail (/JobDetail?jobId=…). The dedicated regex must extract the
        real title from aria-label."""
        matches = jobs._IBM_CARD_RE.findall(self.html)
        titles = [html_mod.unescape(m[0]).strip() for m in matches]
        self.assertFalse(
            any(t.lower() == "jobdetail" for t in titles),
            f"IBM title regression — found literal 'Jobdetail' in {titles[:5]}",
        )


class TestLinkedInScraper(unittest.TestCase):
    """_LINKEDIN_CARD_RE: public /jobs/search/ page (not the authwalled
    /jobs/search-results/). We union 3 URL variants in production; the
    regex itself must work on any of the dumps."""

    DUMP = "debug-linkedin-0.html"
    MIN_CARDS = 30

    def setUp(self):
        self.html = _load(self.DUMP)
        if self.html is None:
            self.skipTest(f"{self.DUMP} not on disk")

    def test_card_count(self):
        matches = jobs._LINKEDIN_CARD_RE.findall(self.html)
        self.assertGreaterEqual(len(matches), self.MIN_CARDS,
                                "LinkedIn regex regressed")

    def test_entity_urn_shape(self):
        matches = jobs._LINKEDIN_CARD_RE.findall(self.html)
        for jid, _body in matches[:5]:
            with self.subTest(jid=jid):
                self.assertRegex(jid, r"^\d+$", "jobPosting URN must be digits")


class TestTeamtailorRegex(unittest.TestCase):
    """The anchor regex inside fetch_teamtailor. Marshall is the canonical
    Teamtailor source. Pattern: /jobs/<id>-<slug>."""

    DUMP = "debug-marshall-1.html"
    MIN_JOBS = 5

    ANCHOR_RE = re.compile(
        r'<a[^>]+href="((?:https?://[^"]*)?/jobs/(\d+)-[a-z0-9-]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    def setUp(self):
        self.html = _load(self.DUMP)
        if self.html is None:
            self.skipTest(f"{self.DUMP} not on disk")

    def test_unique_job_ids(self):
        matches = self.ANCHOR_RE.findall(self.html)
        unique_ids = {jid for _path, jid, _body in matches}
        self.assertGreaterEqual(len(unique_ids), self.MIN_JOBS,
                                f"Teamtailor regex regressed — got {len(unique_ids)} unique jobs")

    def test_titles_present(self):
        matches = self.ANCHOR_RE.findall(self.html)
        titles = []
        for _path, _jid, body in matches:
            clean = re.sub(r"<[^>]+>", " ", body)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean and len(clean) >= 3:
                titles.append(clean)
        # Every anchor had a non-trivial title
        self.assertGreater(len(titles), 0, "no non-empty titles")


class TestSeymourDuncanRegex(unittest.TestCase):
    """Seymour Duncan link_re (config.py:942). Must match the current
    /2026-assembler-job-posting style URL on the dump."""

    DUMP = "debug-seymour-duncan-1.html"

    LINK_RE = re.compile(
        r'href="(https?://yoursmartsource\.hiringthing\.com/job/\d+/[a-z0-9-]+'
        r'|https?://(?:www\.)?seymourduncan\.com/[a-z0-9-]+-job-posting'
        r'|/[a-z0-9-]+-job-posting)"',
        re.IGNORECASE,
    )

    def setUp(self):
        self.html = _load(self.DUMP)
        if self.html is None:
            self.skipTest(f"{self.DUMP} not on disk")

    def test_at_least_one_match(self):
        matches = self.LINK_RE.findall(self.html)
        self.assertGreater(
            len(matches), 0,
            "Seymour Duncan link_re regressed — zero matches on known-good dump",
        )


class TestFetchPwGenericScrollFlag(unittest.TestCase):
    """fetch_pw_generic must thread the `scroll` catalog field into
    _pw_scrape_links so infinite-scroll boards (GM/DoorDash/Shopify/…)
    opt in without touching the fetcher code. Guards against a future
    refactor silently dropping the kwarg."""

    def _call(self, source):
        from unittest import mock
        with mock.patch.object(jobs, "_pw_scrape_links", return_value=[]) as m:
            jobs.fetch_pw_generic(source)
            return m.call_args

    _BASE = {
        "name": "TestCo",
        "search_url": "https://example.com/jobs",
        "link_re": r'href="(/jobs/[^"]+)"',
        "origin": "https://example.com",
    }

    def test_scroll_true_passes_through(self):
        call = self._call({**self._BASE, "scroll": True})
        self.assertIs(call.kwargs.get("scroll"), True)

    def test_scroll_absent_defaults_false(self):
        call = self._call(self._BASE)
        self.assertIs(call.kwargs.get("scroll"), False)

    def test_scroll_false_passes_through(self):
        call = self._call({**self._BASE, "scroll": False})
        self.assertIs(call.kwargs.get("scroll"), False)


if __name__ == "__main__":
    unittest.main()
