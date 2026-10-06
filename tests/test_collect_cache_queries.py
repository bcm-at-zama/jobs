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


if __name__ == "__main__":
    unittest.main()
