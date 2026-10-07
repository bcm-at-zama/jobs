"""Runaway guard — stops a per-query paginated scraper when a single
query (e.g. "engineer" at Apple) is pulling in hundreds of jobs.

Two modes:
  - Non-interactive (default; initial `make run`): hard-stop at threshold.
  - Interactive (`--interactive-runaway`, used by /refresh): write a
    pending signal, poll for a decision file, honour stop/continue, and
    default to stop on timeout.

Also exercises the two HTTP endpoints that back the live modal:
  - POST /refresh-decision  → writes decision.json
  - POST /refresh-status    → surfaces pending.json entries in `runaway`

Run:  python3 -m unittest tests.test_runaway
"""
import importlib.util  # noqa: F401 — kept for symmetry with sibling tests
import json
import os
import tempfile
import threading
import time
import unittest
from io import BytesIO
from unittest import mock

import jobs


class TestCheckRunaway(unittest.TestCase):
    """Pure-function behaviour of check_runaway()."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Point DATA_DIR at a scratch dir so signal files don't collide
        # with the real data/.runaway/ (if any).
        self._patch_data = mock.patch.object(jobs, "DATA_DIR", self.tmp.name)
        self._patch_data.start()
        # Shorter timeout so timeout-case tests don't take a full minute.
        self._patch_timeout = mock.patch.object(jobs, "RUNAWAY_TIMEOUT_S", 1)
        self._patch_timeout.start()
        # Pin the threshold so these tests don't need to track the
        # user-tunable default (which lives in config.RUNAWAY_THRESHOLD
        # and may change over time / from settings).
        self._patch_threshold = mock.patch.object(jobs._cfg, "RUNAWAY_THRESHOLD", 100)
        self._patch_threshold.start()

    def tearDown(self):
        self._patch_threshold.stop()
        self._patch_timeout.stop()
        self._patch_data.stop()
        self.tmp.cleanup()

    def test_below_threshold_returns_false(self):
        """A healthy scraper never hits the guard."""
        self.assertFalse(jobs.check_runaway("Apple", "cryptography", 2, 15))

    def test_non_interactive_hard_stops(self):
        """Without --interactive-runaway, >threshold hard-stops the source
        with no file I/O (so a plain `make run` doesn't block)."""
        with mock.patch.object(jobs, "_interactive_runaway_enabled", False):
            self.assertTrue(
                jobs.check_runaway("Apple", "engineer", 5, 150),
            )
        # No signal files should have been created.
        d = os.path.join(self.tmp.name, ".runaway")
        if os.path.isdir(d):
            self.assertEqual(os.listdir(d), [])

    def test_interactive_honours_stop_decision(self):
        """A decision file with action=stop → check_runaway returns True."""
        with mock.patch.object(jobs, "_interactive_runaway_enabled", True):
            # Write the decision file BEFORE calling so the poll finds it
            # immediately — no race.
            d = jobs._runaway_dir()
            with open(os.path.join(d, f"{jobs.slug('Apple')}.decision.json"), "w") as f:
                json.dump({"action": "stop"}, f)
            self.assertTrue(
                jobs.check_runaway("Apple", "engineer", 5, 150),
            )
            # Both pending + decision cleaned up afterwards.
            self.assertEqual(
                [n for n in os.listdir(d)
                 if n.endswith(".json")], [],
            )

    def test_interactive_honours_continue_decision(self):
        """action=continue → return False (keep going)."""
        with mock.patch.object(jobs, "_interactive_runaway_enabled", True):
            d = jobs._runaway_dir()
            with open(os.path.join(d, f"{jobs.slug('Apple')}.decision.json"), "w") as f:
                json.dump({"action": "continue"}, f)
            self.assertFalse(
                jobs.check_runaway("Apple", "engineer", 5, 150),
            )

    def test_interactive_timeout_defaults_to_stop(self):
        """No decision within RUNAWAY_TIMEOUT_S → stop (safe default so
        a forgotten tab doesn't pin Playwright for an hour)."""
        with mock.patch.object(jobs, "_interactive_runaway_enabled", True):
            t0 = time.time()
            result = jobs.check_runaway("Apple", "engineer", 5, 150)
            elapsed = time.time() - t0
        self.assertTrue(result, "timeout should default to stop")
        # Should have respected the (patched) 1s timeout, not blocked forever.
        self.assertGreaterEqual(elapsed, 0.8)
        self.assertLess(elapsed, 3.0)

    def test_clear_runaway_signals_removes_stale_files(self):
        """At the top of main() we wipe stale .pending/.decision from a
        prior refresh. Otherwise the browser pops yesterday's prompt."""
        d = jobs._runaway_dir()
        for name in ("apple.pending.json", "apple.decision.json",
                     "microsoft.pending.json"):
            with open(os.path.join(d, name), "w") as f:
                f.write("{}")
        jobs._clear_runaway_signals()
        self.assertEqual(
            [n for n in os.listdir(d) if n.endswith(".json")], [],
        )


class TestInteractiveRunawayCliFlag(unittest.TestCase):
    """--interactive-runaway is the one that /refresh passes in. Must be
    parsed as a bool and default to False."""

    def _parse(self, argv):
        import sys
        orig = sys.argv
        try:
            sys.argv = ["jobs.py"] + argv
            return jobs._parse_cli()
        finally:
            sys.argv = orig

    def test_default_is_false(self):
        self.assertFalse(self._parse([]).interactive_runaway)

    def test_flag_sets_true(self):
        self.assertTrue(
            self._parse(["--interactive-runaway"]).interactive_runaway,
        )


class TestRefreshDecisionEndpoint(unittest.TestCase):
    """`/refresh-decision` writes the decision file the fetcher polls for."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(jobs, "DATA_DIR", self.tmp.name)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.cleanup()

    def _invoke(self, path, body_dict):
        body = json.dumps(body_dict).encode()

        class _Shim(jobs.Handler):
            def __init__(self):
                self.rfile = BytesIO(body)
                self.wfile = BytesIO()
                self.headers = {"Content-Length": str(len(body))}
                self.path = path
                self.command = "POST"
                self._status = None

            def send_response(self, code, msg=None):
                self._status = code

            def send_header(self, k, v): pass
            def end_headers(self): pass
            def log_message(self, *a, **kw): pass

        shim = _Shim()
        shim.do_POST()
        return shim._status, shim.wfile.getvalue()

    def test_stop_writes_decision_file(self):
        status, body = self._invoke(
            "/refresh-decision", {"source": "Apple", "action": "stop"},
        )
        self.assertEqual(status, 200, body)
        path = os.path.join(self.tmp.name, ".runaway", "apple.decision.json")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["action"], "stop")

    def test_continue_writes_decision_file(self):
        status, _ = self._invoke(
            "/refresh-decision", {"source": "Apple", "action": "continue"},
        )
        self.assertEqual(status, 200)
        path = os.path.join(self.tmp.name, ".runaway", "apple.decision.json")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["action"], "continue")

    def test_rejects_invalid_action(self):
        status, _ = self._invoke(
            "/refresh-decision", {"source": "Apple", "action": "yolo"},
        )
        self.assertEqual(status, 400)

    def test_rejects_missing_source(self):
        status, _ = self._invoke(
            "/refresh-decision", {"action": "stop"},
        )
        self.assertEqual(status, 400)

    def test_slugifies_source_name(self):
        """Source names with spaces/punct must round-trip through slug()
        so the fetcher's _runaway_file() finds the same path."""
        status, _ = self._invoke(
            "/refresh-decision",
            {"source": "Scale AI", "action": "stop"},
        )
        self.assertEqual(status, 200)
        expected = os.path.join(
            self.tmp.name, ".runaway",
            f"{jobs.slug('Scale AI')}.decision.json",
        )
        self.assertTrue(os.path.isfile(expected))


class TestRefreshStatusRunawayList(unittest.TestCase):
    """`/refresh-status` must surface pending runaway prompts so the
    modal can pop. Without this the browser never knows the fetcher is
    waiting."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(jobs, "DATA_DIR", self.tmp.name)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.cleanup()

    def _invoke_status(self):
        body = b"{}"

        class _Shim(jobs.Handler):
            def __init__(self):
                self.rfile = BytesIO(body)
                self.wfile = BytesIO()
                self.headers = {"Content-Length": str(len(body))}
                self.path = "/refresh-status"
                self.command = "POST"
                self._status = None

            def send_response(self, code, msg=None):
                self._status = code

            def send_header(self, k, v): pass
            def end_headers(self): pass
            def log_message(self, *a, **kw): pass

        shim = _Shim()
        shim.do_POST()
        return shim._status, json.loads(shim.wfile.getvalue() or b"{}")

    def test_empty_when_no_pending_files(self):
        status, data = self._invoke_status()
        self.assertEqual(status, 200)
        self.assertEqual(data.get("runaway"), [])

    def test_surfaces_pending_files(self):
        d = os.path.join(self.tmp.name, ".runaway")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "apple.pending.json"), "w") as f:
            json.dump({
                "source": "Apple", "query": "engineer",
                "pages": 3, "jobs": 150, "at": 1.0,
            }, f)
        status, data = self._invoke_status()
        self.assertEqual(status, 200)
        self.assertEqual(len(data["runaway"]), 1)
        self.assertEqual(data["runaway"][0]["source"], "Apple")
        self.assertEqual(data["runaway"][0]["query"], "engineer")
        self.assertEqual(data["runaway"][0]["jobs"], 150)


class TestRefreshStatusProgress(unittest.TestCase):
    """`/refresh-status` must also surface per-source progress so the
    floater shows "N/M fetched · latest: X · working on: Y" instead of
    just an elapsed-seconds counter. Progress is derived from
    LIST_CACHE_DIR/*.json entries written since the refresh started."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = os.path.join(self.tmp.name, "list_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._patches = [
            mock.patch.object(jobs, "DATA_DIR", self.tmp.name),
            mock.patch.object(jobs, "LIST_CACHE_DIR", self.cache_dir),
            mock.patch.object(jobs, "SOURCES", [
                {"name": "Apple"}, {"name": "Microsoft"}, {"name": "Meta"},
            ]),
        ]
        for p in self._patches:
            p.start()
        # Pretend a refresh kicked off 10s ago.
        self._prev_state = dict(jobs._refresh_state)
        jobs._refresh_state["status"] = "running"
        jobs._refresh_state["started_at"] = time.time() - 10

    def tearDown(self):
        jobs._refresh_state.clear()
        jobs._refresh_state.update(self._prev_state)
        for p in self._patches:
            p.stop()
        self.tmp.cleanup()

    def _invoke_status(self):
        body = b"{}"

        class _Shim(jobs.Handler):
            def __init__(self):
                self.rfile = BytesIO(body)
                self.wfile = BytesIO()
                self.headers = {"Content-Length": str(len(body))}
                self.path = "/refresh-status"
                self.command = "POST"
                self._status = None

            def send_response(self, code, msg=None):
                self._status = code

            def send_header(self, k, v): pass
            def end_headers(self): pass
            def log_message(self, *a, **kw): pass

        shim = _Shim()
        shim.do_POST()
        return shim._status, json.loads(shim.wfile.getvalue() or b"{}")

    def _touch_cache(self, name):
        """Mimic a successful fetch landing a list_cache/<slug>.json."""
        with open(os.path.join(self.cache_dir, f"{jobs.slug(name)}.json"), "w") as f:
            json.dump({"jobs": []}, f)

    def test_progress_block_present(self):
        _, data = self._invoke_status()
        self.assertIn("progress", data)
        p = data["progress"]
        self.assertEqual(p["total"], 3)
        self.assertEqual(p["done_count"], 0)
        self.assertIsNone(p["last_done"])
        # First not-yet-done source is "working on".
        self.assertEqual(p["currently_working"], "Apple")

    def test_progress_counts_completed_sources(self):
        self._touch_cache("Apple")
        self._touch_cache("Microsoft")
        # Pin mtimes so last_done is deterministic (back-to-back writes
        # otherwise share mtime at filesystem resolution).
        now = time.time()
        os.utime(os.path.join(self.cache_dir, f"{jobs.slug('Apple')}.json"),
                 (now - 2, now - 2))
        os.utime(os.path.join(self.cache_dir, f"{jobs.slug('Microsoft')}.json"),
                 (now - 1, now - 1))
        _, data = self._invoke_status()
        p = data["progress"]
        self.assertEqual(p["done_count"], 2)
        self.assertEqual(p["total"], 3)
        # last_done is the most-recently-written cache file.
        self.assertEqual(p["last_done"], "Microsoft")
        # Only Meta is left.
        self.assertEqual(p["currently_working"], "Meta")

    def test_progress_ignores_stale_pre_refresh_caches(self):
        """A JSON file whose mtime predates the refresh start must NOT
        count — otherwise a cold start would read "3/3 done" instantly."""
        self._touch_cache("Apple")
        stale = os.path.join(self.cache_dir, f"{jobs.slug('Apple')}.json")
        old = time.time() - 1000  # well before started_at
        os.utime(stale, (old, old))
        _, data = self._invoke_status()
        self.assertEqual(data["progress"]["done_count"], 0)


class TestFetcherIntegration(unittest.TestCase):
    """End-to-end: a fetcher thread calls check_runaway, the test writes
    a decision file that mimics the browser modal, and the thread wakes
    up with the right return value within the (patched) timeout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._patch_data = mock.patch.object(jobs, "DATA_DIR", self.tmp.name)
        self._patch_data.start()
        self._patch_timeout = mock.patch.object(jobs, "RUNAWAY_TIMEOUT_S", 3)
        self._patch_timeout.start()
        self._patch_mode = mock.patch.object(
            jobs, "_interactive_runaway_enabled", True,
        )
        self._patch_mode.start()
        self._patch_threshold = mock.patch.object(jobs._cfg, "RUNAWAY_THRESHOLD", 100)
        self._patch_threshold.start()

    def tearDown(self):
        self._patch_threshold.stop()
        self._patch_mode.stop()
        self._patch_timeout.stop()
        self._patch_data.stop()
        self.tmp.cleanup()

    def test_browser_decision_unblocks_fetcher(self):
        result = {}

        def _runner():
            result["stop"] = jobs.check_runaway("Apple", "engineer", 3, 150)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        # Give the fetcher thread a moment to write the pending file and
        # enter its polling loop, then write the decision (as the modal
        # would via /refresh-decision).
        time.sleep(0.4)
        d = jobs._runaway_dir()
        with open(os.path.join(d, f"{jobs.slug('Apple')}.decision.json"), "w") as f:
            json.dump({"action": "continue"}, f)
        t.join(timeout=2.0)
        self.assertFalse(t.is_alive(), "fetcher didn't wake up on decision")
        self.assertFalse(result["stop"], "continue should let fetcher keep going")


if __name__ == "__main__":
    unittest.main()
