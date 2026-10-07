"""First-visit guard — a newly-added source must baseline all its URLs
instead of flagging every posting as NEW.

Regression context: a WTTJ bulk-add bumped SOURCES from 182 → 692 in one
commit. Many of those 510 new companies legitimately return 1-4 postings
each. The old guard required `len(source_urls) >= 5`, so those small
boards slipped past first-visit and flooded the NEW tab with ~1900+
one-time false positives. The guard now only requires that the source
have *any* URLs and that none of them overlap with the user's seen /
liked / rejected sets.

Run:  python3 -m unittest tests.test_is_new
"""
import unittest

import jobs


class TestIsFirstVisit(unittest.TestCase):

    def test_small_new_source_qualifies(self):
        """1-4 postings from a brand-new company → baseline, no NEW flood.
        This is the WTTJ-bulk-add scenario this change fixes."""
        urls = {"https://example.com/jobs/1", "https://example.com/jobs/2"}
        self.assertTrue(jobs._is_first_visit(urls, seen=set(), liked=set(), rejected=set()))

    def test_single_posting_qualifies(self):
        """A company with exactly one posting is still a first visit."""
        urls = {"https://example.com/jobs/1"}
        self.assertTrue(jobs._is_first_visit(urls, seen=set(), liked=set(), rejected=set()))

    def test_empty_source_does_not_qualify(self):
        """Zero fetched URLs cannot be a 'first visit' — there is nothing
        to baseline and tagging the empty set as first-visit would be a
        no-op anyway. Keeping it False avoids a misleading log line."""
        self.assertFalse(jobs._is_first_visit(set(), seen=set(), liked=set(), rejected=set()))

    def test_overlap_with_seen_disqualifies(self):
        """One URL already in seen means we've surfaced this source before,
        so the rest are legitimately NEW (not baseline)."""
        urls = {"https://example.com/jobs/1", "https://example.com/jobs/2"}
        seen = {"https://example.com/jobs/1"}
        self.assertFalse(jobs._is_first_visit(urls, seen=seen, liked=set(), rejected=set()))

    def test_overlap_with_liked_disqualifies(self):
        """A liked URL proves the user has interacted with this source
        before — treating fresh URLs as 'first visit' would silently
        suppress legitimate NEW markers."""
        urls = {"https://example.com/jobs/1", "https://example.com/jobs/2"}
        liked = {"https://example.com/jobs/1"}
        self.assertFalse(jobs._is_first_visit(urls, seen=set(), liked=liked, rejected=set()))

    def test_overlap_with_rejected_disqualifies(self):
        """Same as liked — a rejected URL is proof of prior interaction."""
        urls = {"https://example.com/jobs/1", "https://example.com/jobs/2"}
        rejected = {"https://example.com/jobs/1"}
        self.assertFalse(jobs._is_first_visit(urls, seen=set(), liked=set(), rejected=rejected))

    def test_large_new_source_qualifies(self):
        """The removed `>= 5` threshold must not have been replaced by a
        new lower bound — big new boards should still baseline."""
        urls = {f"https://example.com/jobs/{i}" for i in range(50)}
        self.assertTrue(jobs._is_first_visit(urls, seen=set(), liked=set(), rejected=set()))


if __name__ == "__main__":
    unittest.main()
