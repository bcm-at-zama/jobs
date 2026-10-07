"""Regression: `collect()` must re-apply the per-source `queries`
filter even on a cache hit.

Without this, if the user's `data/list_cache/<slug>.json` was ever
written when queries=[] (e.g. because of a buggy save flow — this
actually shipped once with the edit-companies modal), subsequent
`make run`s within the 6-hour TTL would return the full unfiltered
board (Salesforce = 1500+ jobs instead of ~50 that match
["security", "cryptography", ...]).

Pin the invariant so no future refactor can regress it.

Run:  python3 -m unittest tests.test_collect_cache_queries
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import jobs


class TestCollectReappliesQueries(unittest.TestCase):

    def _write_cache(self, data_dir, slug, jobs_list):
        cache_dir = os.path.join(data_dir, "list_cache")
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{slug}.json")
        with open(path, "w") as f:
            json.dump({"jobs": jobs_list, "spontaneous_url": None}, f)
        return path

    def test_cache_hit_still_filters_by_queries(self):
        """Seed a cache with 3 jobs; only 1 matches queries. collect()
        must return just that one, not all three."""
        with tempfile.TemporaryDirectory() as tmp:
            # Build a fake source with a tight queries filter.
            source = {
                "name": "FakeCorp", "kind": "greenhouse", "slug": "fakecorp",
                "queries": ["security"],
            }
            # 3 cached jobs: only the first matches "security".
            cached_jobs = [
                {"title": "Security Engineer", "locations": ["Paris"],
                 "url": "https://x.com/1", "description": "",
                 "blob": "Security Engineer"},
                {"title": "Marketing Manager", "locations": ["London"],
                 "url": "https://x.com/2", "description": "",
                 "blob": "Marketing Manager"},
                {"title": "Sales VP", "locations": ["NYC"],
                 "url": "https://x.com/3", "description": "",
                 "blob": "Sales VP"},
            ]
            self._write_cache(tmp, "fakecorp", cached_jobs)

            # Point LIST_CACHE_DIR at our sandbox + call collect().
            with mock.patch.object(jobs, "LIST_CACHE_DIR",
                                   os.path.join(tmp, "list_cache")):
                result = jobs.collect(source)

            titles = [j["title"] for j in result["jobs"]]
            self.assertEqual(
                titles, ["Security Engineer"],
                "collect() should re-filter cache hits through queries. "
                f"Got: {titles}",
            )

    def test_cache_hit_with_empty_queries_returns_everything(self):
        """When queries=[] the filter is a no-op, so collect() returns
        every cached job unchanged. This pins the semantics so a future
        over-eager filter can't accidentally drop legit sources."""
        with tempfile.TemporaryDirectory() as tmp:
            source = {
                "name": "FakeCorp", "kind": "greenhouse", "slug": "fakecorp",
                "queries": [],
            }
            cached_jobs = [
                {"title": f"Job {i}", "locations": [], "url": f"u{i}",
                 "description": "", "blob": f"Job {i}"}
                for i in range(5)
            ]
            self._write_cache(tmp, "fakecorp", cached_jobs)

            with mock.patch.object(jobs, "LIST_CACHE_DIR",
                                   os.path.join(tmp, "list_cache")):
                result = jobs.collect(source)

            self.assertEqual(len(result["jobs"]), 5)


class TestCollectRefusesToCacheEmpty(unittest.TestCase):
    """REGRESSION — a transient Playwright flake used to cache [] for 6 h,
    silently zero-ing out any affected source until the TTL expired
    (first spotted on Zama: raw HTML had 3 real jobs, cache said 0).
    `collect()` now skips the cache write when `len(raw_jobs) <
    CACHE_MIN_JOBS` (default 5) — covers both the empty-cache and the
    half-scrolled-partial-cache failure modes."""

    def _fake_fetcher(self, jobs_list):
        """Build a FETCHERS-style fetcher that returns a canned result."""
        return lambda src: {
            "jobs": list(jobs_list),
            "spontaneous_url": None,
            "total_board": None,
        }

    def _run_collect(self, tmp, jobs_list):
        source = {
            "name": "FlakeyCorp", "kind": "greenhouse", "slug": "flakeycorp",
            "queries": [],
        }
        cache_dir = os.path.join(tmp, "list_cache")
        with mock.patch.object(jobs, "LIST_CACHE_DIR", cache_dir), \
             mock.patch.dict(jobs.FETCHERS,
                             {"greenhouse": self._fake_fetcher(jobs_list)}):
            jobs.collect(source)
        return os.path.join(cache_dir, "flakeycorp.json")

    @staticmethod
    def _canned_jobs(n):
        return [
            {"title": f"Engineer {i}", "locations": ["Paris"],
             "url": f"https://x.com/{i}", "description": "",
             "blob": f"Engineer {i}"}
            for i in range(n)
        ]

    def test_empty_fetch_is_not_cached(self):
        """Fetcher returned 0 jobs → no cache file on disk → next run
        re-fetches instead of serving the stale zero."""
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = self._run_collect(tmp, [])
            self.assertFalse(
                os.path.isfile(cache_path),
                f"empty fetch should NOT create {cache_path}",
            )

    def test_below_threshold_fetch_is_not_cached(self):
        """Partial-fetch mode: scroll loaded 3 of 50 — don't cache that
        either, next run retries. 3 < CACHE_MIN_JOBS (5) → no cache."""
        with mock.patch.object(jobs, "CACHE_MIN_JOBS", 5), \
             tempfile.TemporaryDirectory() as tmp:
            cache_path = self._run_collect(tmp, self._canned_jobs(3))
            self.assertFalse(
                os.path.isfile(cache_path),
                "partial fetch (3 jobs < threshold 5) should NOT cache",
            )

    def test_at_threshold_fetch_is_cached(self):
        """Boundary: exactly CACHE_MIN_JOBS → cached."""
        with mock.patch.object(jobs, "CACHE_MIN_JOBS", 5), \
             tempfile.TemporaryDirectory() as tmp:
            cache_path = self._run_collect(tmp, self._canned_jobs(5))
            self.assertTrue(os.path.isfile(cache_path))
            with open(cache_path) as f:
                self.assertEqual(len(json.load(f)["jobs"]), 5)

    def test_above_threshold_fetch_is_cached(self):
        """Sanity check — healthy fetch (10 jobs) gets cached."""
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = self._run_collect(tmp, self._canned_jobs(10))
            self.assertTrue(os.path.isfile(cache_path))


if __name__ == "__main__":
    unittest.main()
