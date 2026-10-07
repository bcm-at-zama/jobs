"""WTJ discovery via Algolia — pin the request shape + cache round-trip.
No network: `urllib.request.urlopen` is mocked everywhere."""
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import wttj_discovery


class _FakeHTTPResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._body = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def _page(hits, nb_hits):
    return {"results": [{"hits": hits, "nbHits": nb_hits}]}


class TestFetchCandidates(unittest.TestCase):

    def test_single_page_result(self):
        hits = [
            {"slug": "zama", "name": "Zama",
             "short_description": "FHE",
             "sectors_name": {"Tech": ["Cybersécurité"]},
             "website_url": "https://zama.ai",
             "company_size": "100-249"},
            {"slug": "mistral", "name": "Mistral",
             "sectors_name": {"Tech": ["Intelligence artificielle / Machine Learning"]}},
        ]
        with mock.patch.object(
            wttj_discovery.urllib.request, "urlopen",
            return_value=_FakeHTTPResponse(_page(hits, 2)),
        ):
            out = wttj_discovery.fetch_candidates(max_pages=3)
        self.assertEqual([c["slug"] for c in out], ["zama", "mistral"])
        self.assertEqual(out[0]["description"], "FHE")
        self.assertIn("Cybersécurité", out[0]["sectors"])
        self.assertEqual(out[0]["website_url"], "https://zama.ai")

    def test_pagination_stops_at_nbhits(self):
        """We stop once the running total of unique slugs catches up
        to nbHits — Algolia doesn't tell us the last page is last."""
        calls = []

        def fake(req, timeout=15):
            calls.append(req.data.decode())
            # Three unique slugs across two 2-hit pages → nbHits=3 total.
            if len(calls) == 1:
                return _FakeHTTPResponse(_page([
                    {"slug": "a", "name": "A"},
                    {"slug": "b", "name": "B"},
                ], 3))
            if len(calls) == 2:
                return _FakeHTTPResponse(_page([
                    {"slug": "c", "name": "C"},
                ], 3))
            raise AssertionError("overpaginated")

        with mock.patch.object(
            wttj_discovery.urllib.request, "urlopen", side_effect=fake,
        ):
            out = wttj_discovery.fetch_candidates(max_pages=10)
        self.assertEqual([c["slug"] for c in out], ["a", "b", "c"])
        self.assertEqual(len(calls), 2, "should stop after reaching nbHits")

    def test_dedupes_across_pages(self):
        """Algolia occasionally repeats a hit across pages; we must
        not double-count."""
        with mock.patch.object(
            wttj_discovery.urllib.request, "urlopen",
            side_effect=[
                _FakeHTTPResponse(_page([{"slug": "a", "name": "A"}], 2)),
                _FakeHTTPResponse(_page([
                    {"slug": "a", "name": "A"},    # dupe, ignored
                    {"slug": "b", "name": "B"},
                ], 2)),
            ],
        ):
            out = wttj_discovery.fetch_candidates(max_pages=5)
        self.assertEqual([c["slug"] for c in out], ["a", "b"])

    def test_http_failure_stops_cleanly(self):
        """A 403 / timeout returns whatever we got so far, no crash."""
        with mock.patch.object(
            wttj_discovery.urllib.request, "urlopen",
            side_effect=Exception("blocked"),
        ):
            out = wttj_discovery.fetch_candidates(max_pages=3)
        self.assertEqual(out, [])

    def test_request_shape_is_what_browser_sends(self):
        """REGRESSION — key / app ID / endpoint / headers must match
        the shape captured from the real browser. If any of these
        drift, we'll silently 400 or 401 in prod."""
        captured = {}

        def fake(req, timeout=15):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["headers"] = dict(req.headers)
            captured["body"] = json.loads(req.data.decode())
            return _FakeHTTPResponse(_page([], 0))

        with mock.patch.object(
            wttj_discovery.urllib.request, "urlopen", side_effect=fake,
        ):
            wttj_discovery.fetch_candidates(max_pages=1)

        self.assertEqual(captured["method"], "POST")
        self.assertIn("csekhvms53-dsn.algolia.net", captured["url"])
        self.assertEqual(captured["headers"].get("X-algolia-api-key"),
                         "4bd8f6215d0cc52b26430765769e65a0")
        self.assertEqual(captured["headers"].get("X-algolia-application-id"),
                         "CSEKHVMS53")
        self.assertEqual(captured["body"]["requests"][0]["indexName"],
                         "wk_cms_organizations_production")
        self.assertIn("facetFilters", captured["body"]["requests"][0]["params"])


class TestCacheRoundtrip(unittest.TestCase):

    def test_write_then_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wttj_discovered.json")
            payload = [{"slug": "zama", "name": "Zama"}]
            wttj_discovery.cache_candidates(path, payload)
            self.assertTrue(os.path.isfile(path))
            got = wttj_discovery.load_candidates(path)
            self.assertEqual(got["candidates"], payload)
            self.assertIn("fetched_at", got)

    def test_load_missing_returns_empty(self):
        got = wttj_discovery.load_candidates("/nope/does/not/exist.json")
        self.assertEqual(got, {})

    def test_load_malformed_returns_empty(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("not-valid-json {{{")
            path = f.name
        try:
            self.assertEqual(wttj_discovery.load_candidates(path), {})
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
