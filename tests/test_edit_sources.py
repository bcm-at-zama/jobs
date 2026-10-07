"""Edit-companies endpoint — the board's /write-user-config POST that
backs the 🏢 modal. Mirrors the onboarding wizard's write path but
preserves the existing HIGHLIGHTS / TITLE_BLACKLIST / LOCATION_BLACKLIST
instead of resetting them.

Run:  python3 -m unittest tests.test_edit_sources
"""
import importlib.util
import json
import os
import tempfile
import unittest
from io import BytesIO
from unittest import mock

import jobs


class TestWriteUserConfigEndpoint(unittest.TestCase):
    """We exercise jobs.Handler._handle_write directly via a tiny shim
    that bypasses BaseHTTPRequestHandler's socket plumbing. Module-level
    globals (HIGHLIGHTS, TITLE_BLACKLIST, LOCATION_BLACKLIST) are
    patched for the test and restored on tearDown — never a permanent
    reload, so sibling test modules keep seeing the real config."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = self.tmp.name
        existing = os.path.join(self.data, "user_config.py")
        with open(existing, "w") as f:
            f.write(
                "HIGHLIGHTS = ['AI', 'Rust']\n"
                "TITLE_BLACKLIST = ['Intern']\n"
                "LOCATION_BLACKLIST = ['Dubai']\n"
                "SOURCES = [{'name': 'Anthropic', 'kind': 'greenhouse', "
                "'slug': 'anthropic', 'queries': []}]\n"
            )
        self.existing_path = existing
        # Patch the three lists + JOBS_DATA_DIR for the duration of this
        # test. The handler reads jobs.HIGHLIGHTS etc. at call time, so
        # patching the module attributes is enough — no reload needed.
        self._patches = [
            mock.patch.dict(os.environ, {"JOBS_DATA_DIR": self.data}),
            mock.patch.object(jobs, "HIGHLIGHTS", ["AI", "Rust"]),
            mock.patch.object(jobs, "TITLE_BLACKLIST", ["Intern"]),
            mock.patch.object(jobs, "LOCATION_BLACKLIST", ["Dubai"]),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self.tmp.cleanup()

    def _invoke(self, path, body_dict):
        """Call Handler.do_POST on a request-less shim; return (status, body)."""
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

            def send_header(self, k, v):
                pass

            def end_headers(self):
                pass

            def log_message(self, *a, **kw):
                pass

        shim = _Shim()
        shim.do_POST()
        return shim._status, shim.wfile.getvalue()

    def test_write_replaces_sources_keeps_filters(self):
        status, body = self._invoke(
            "/write-user-config", {"names": ["OpenAI", "Mistral"]},
        )
        self.assertEqual(status, 200, body)
        resp = json.loads(body)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["n"], 2)
        self.assertTrue(resp["backup"], "backup path must be returned")
        self.assertTrue(os.path.isfile(resp["backup"]))

        # New file replaces SOURCES but keeps HIGHLIGHTS / BLACKLISTS.
        spec = importlib.util.spec_from_file_location("_uc", self.existing_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        names = {s["name"] for s in mod.SOURCES}
        self.assertEqual(names, {"OpenAI", "Mistral"})
        self.assertEqual(mod.HIGHLIGHTS, ["AI", "Rust"])
        self.assertEqual(mod.TITLE_BLACKLIST, ["Intern"])
        self.assertEqual(mod.LOCATION_BLACKLIST, ["Dubai"])

        # Backup still contains the old Anthropic entry.
        with open(resp["backup"]) as f:
            self.assertIn("Anthropic", f.read())

    def test_write_rejects_empty_names(self):
        status, body = self._invoke("/write-user-config", {"names": []})
        self.assertEqual(status, 400)

    def test_write_preserves_existing_per_source_queries(self):
        """REGRESSION — the edit-companies modal must NOT reset the
        per-source `queries` filter. Before this test shipped, saving
        from the modal rewrote every source with queries=[], unleashing
        the full firehose of workday-sized boards (Salesforce = 1500+
        jobs instead of ~50 filtered). Pin the invariant."""
        # Seed a jobs.SOURCES in-memory that mimics a real user with
        # non-empty queries on Anthropic.
        with mock.patch.object(jobs, "SOURCES", [
            {"name": "Anthropic", "kind": "greenhouse", "slug": "anthropic",
             "queries": ["security", "cryptography", "CTO", "VP"]},
            {"name": "OpenAI", "kind": "ashby", "slug": "openai",
             "queries": ["security"]},
        ]):
            status, _ = self._invoke(
                "/write-user-config",
                {"names": ["Anthropic", "OpenAI"]},
            )
        self.assertEqual(status, 200)
        out = os.path.join(self.data, "user_config.py")
        spec = importlib.util.spec_from_file_location("_uc", out)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        by_name = {s["name"]: s for s in mod.SOURCES}
        self.assertEqual(by_name["Anthropic"]["queries"],
                         ["security", "cryptography", "CTO", "VP"])
        self.assertEqual(by_name["OpenAI"]["queries"], ["security"])


class TestUpdateQueriesEndpoint(unittest.TestCase):
    """`/update-queries` is the in-place pill editor on each company
    header. It mutates ONE source's `queries` list and preserves
    everything else (companies set, highlights, blacklists, other
    sources' queries)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = self.tmp.name
        existing = os.path.join(self.data, "user_config.py")
        with open(existing, "w") as f:
            f.write(
                "HIGHLIGHTS = ['AI']\n"
                "TITLE_BLACKLIST = ['Intern']\n"
                "LOCATION_BLACKLIST = ['Dubai']\n"
                "SOURCES = [\n"
                "  {'name': 'Anthropic', 'kind': 'greenhouse', "
                "'slug': 'anthropic', 'queries': ['security']},\n"
                "  {'name': 'OpenAI', 'kind': 'ashby', "
                "'slug': 'openai', 'queries': ['keep', 'me']},\n"
                "]\n"
            )
        self.existing_path = existing
        self._patches = [
            mock.patch.dict(os.environ, {"JOBS_DATA_DIR": self.data}),
            mock.patch.object(jobs, "HIGHLIGHTS", ["AI"]),
            mock.patch.object(jobs, "TITLE_BLACKLIST", ["Intern"]),
            mock.patch.object(jobs, "LOCATION_BLACKLIST", ["Dubai"]),
            mock.patch.object(jobs, "SOURCES", [
                {"name": "Anthropic", "kind": "greenhouse", "slug": "anthropic",
                 "queries": ["security"]},
                {"name": "OpenAI", "kind": "ashby", "slug": "openai",
                 "queries": ["keep", "me"]},
            ]),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
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

    def _reload(self):
        spec = importlib.util.spec_from_file_location("_uc", self.existing_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {s["name"]: s for s in mod.SOURCES}, mod

    def test_add_and_replace_queries(self):
        status, body = self._invoke(
            "/update-queries",
            {"name": "Anthropic", "queries": ["security", "cryptography", "CTO", "VP"]},
        )
        self.assertEqual(status, 200, body)
        resp = json.loads(body)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["queries"],
                         ["security", "cryptography", "CTO", "VP"])
        by_name, mod = self._reload()
        self.assertEqual(by_name["Anthropic"]["queries"],
                         ["security", "cryptography", "CTO", "VP"])
        # Other source untouched.
        self.assertEqual(by_name["OpenAI"]["queries"], ["keep", "me"])
        # Filter lists preserved.
        self.assertEqual(mod.HIGHLIGHTS, ["AI"])
        self.assertEqual(mod.TITLE_BLACKLIST, ["Intern"])
        self.assertEqual(mod.LOCATION_BLACKLIST, ["Dubai"])

    def test_empty_queries_clears_source(self):
        status, _ = self._invoke(
            "/update-queries", {"name": "Anthropic", "queries": []},
        )
        self.assertEqual(status, 200)
        by_name, _ = self._reload()
        self.assertEqual(by_name["Anthropic"]["queries"], [])

    def test_dedupes_case_insensitive_and_trims(self):
        status, body = self._invoke(
            "/update-queries",
            {"name": "Anthropic",
             "queries": ["  security  ", "Security", "  ", "SECURITY", "crypto"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["queries"], ["security", "crypto"])

    def test_rejects_unknown_source(self):
        status, _ = self._invoke(
            "/update-queries", {"name": "NotRealCo", "queries": ["x"]},
        )
        self.assertEqual(status, 400)

    def test_rejects_missing_fields(self):
        status, _ = self._invoke("/update-queries", {"queries": ["x"]})
        self.assertEqual(status, 400)
        status, _ = self._invoke("/update-queries", {"name": "Anthropic"})
        # Missing queries key → defaults to [] → cleared; this is valid.
        self.assertEqual(status, 200)

    def test_in_memory_sources_sync_with_file(self):
        """REGRESSION guard — if the running server's SOURCES isn't
        updated, clicking Refresh immediately after a pill edit would
        use stale queries until the subprocess reloads from disk. We
        mutate in-memory to avoid that window."""
        self._invoke(
            "/update-queries",
            {"name": "Anthropic", "queries": ["freshly-added"]},
        )
        by_name = {s["name"]: s for s in jobs.SOURCES}
        self.assertEqual(by_name["Anthropic"]["queries"], ["freshly-added"])


class TestNewCompaniesBadgeFallback(unittest.TestCase):
    """REGRESSION — the "new companies" red badge used to seed its
    first-load `effectiveSeen` from the user's current SOURCES only.
    Right after onboarding with (say) just Apple, that made the badge
    show `catalog_size - 1` (~164) even though the user had just
    reviewed and declined every other company in the wizard.

    The fix seeds `effectiveSeen` with the FULL catalog on first load
    and persists it, so the badge counts only companies added to
    catalog.py in a FUTURE release the user hasn't acknowledged.

    Testing client-side JS from Python is coarse; we pin the fix by
    asserting the shared helper exists in jobs.py and the old buggy
    fallback pattern (`new Set(SOURCES_NAMES)` inside a seen-size
    guard) is gone from both badge + modal paths."""

    def setUp(self):
        import pathlib
        self.src = pathlib.Path(jobs.__file__).read_text()

    def test_shared_helper_exists(self):
        self.assertIn("function _effectiveSeenCatalog(", self.src,
                      "Shared seen-catalog helper is missing — did the fix "
                      "get reverted?")

    def test_helper_seeds_from_full_catalog(self):
        # Spot-check the helper body: on empty seen, it must build from
        # CATALOG_FOR_EDIT (not SOURCES_NAMES) and persist.
        import re
        m = re.search(
            r"function _effectiveSeenCatalog\([^)]*\)\s*\{(.+?)\n\}",
            self.src, re.DOTALL)
        self.assertIsNotNone(m, "helper body not found")
        body = m.group(1)
        self.assertIn("CATALOG_FOR_EDIT.map", body,
                      "helper must seed from the catalog, not SOURCES")
        self.assertIn("_saveSeenCatalog", body,
                      "helper must persist so the seed is one-shot")

    def test_old_buggy_fallback_pattern_is_gone(self):
        # The pre-fix inlined pattern — must not reappear in either the
        # badge refresher or the modal opener.
        self.assertNotIn(
            "seen.size === 0 ? new Set(SOURCES_NAMES)", self.src,
            "Old buggy fallback has returned — use _effectiveSeenCatalog().",
        )


class TestRunawayPerQuery(unittest.TestCase):
    """REGRESSION — the runaway guard used to kill the entire source
    when ANY one query tripped the threshold. For a config like
    Apple's queries=['security', 'cryptography', ...], the common
    first term "security" would hit 100+ matches and silently skip
    every subsequent query — the user then wondered why
    "cryptography" / "Logic" postings never showed up.

    The fix: runaway stops THIS query's pagination, outer loop
    continues to the next query. These tests pin that intent by
    inspecting the fetcher sources."""

    def setUp(self):
        import pathlib
        self.src = pathlib.Path(jobs.__file__).read_text()

    def test_no_stop_source_flag_remains(self):
        """The `stop_source = True` propagation is gone from every
        fetcher — would re-introduce the per-source abort."""
        self.assertNotIn(
            "stop_source = True", self.src,
            "A fetcher still sets stop_source=True on runaway. Convert "
            "it to a plain break so the outer per-query loop continues.",
        )

    def test_check_runaway_callers_only_break(self):
        """Every call site must `break` (inner loop only), never set a
        flag that unwinds the outer per-query loop."""
        import re
        # Match `if check_runaway("<SourceName>", ...):` followed by its
        # body. We only want real call sites inside fetchers — the
        # function definition itself starts with `def check_runaway(`.
        # Any `if check_runaway(…):` line inside a fetcher (one or two
        # args, string literal OR source["name"] indexing — accept both).
        pattern = re.compile(
            r"if check_runaway\([^)]+\):\s*\n(\s+)([^\n]+)",
            re.MULTILINE,
        )
        hits = pattern.findall(self.src)
        self.assertGreaterEqual(len(hits), 4,
                                "expected ≥4 runaway call sites (Apple, "
                                "Microsoft, Phenom, WTTJ)")
        for indent, body in hits:
            with self.subTest(body=body):
                self.assertTrue(
                    body.startswith("break"),
                    f"runaway follow-up should be `break`, got {body!r}",
                )


class TestSetSettingsEndpoint(unittest.TestCase):
    """POST /set-settings persists the runaway threshold to
    data/user_config.py AND updates config.RUNAWAY_THRESHOLD in memory
    so the next fetch picks it up without a restart."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = self.tmp.name
        self._patches = [
            mock.patch.dict(os.environ, {"JOBS_DATA_DIR": self.data}),
            mock.patch.object(jobs._cfg, "DATA_DIR", self.data),
            mock.patch.object(jobs._cfg, "RUNAWAY_THRESHOLD", 300),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self.tmp.cleanup()

    def _invoke(self, body_dict):
        body = json.dumps(body_dict).encode()

        class _Shim(jobs.Handler):
            def __init__(self):
                self.rfile = BytesIO(body)
                self.wfile = BytesIO()
                self.headers = {"Content-Length": str(len(body))}
                self.path = "/set-settings"
                self.command = "POST"
                self._status = None

            def send_response(self, code, msg=None):
                self._status = code

            def send_header(self, k, v): pass
            def end_headers(self): pass
            def log_message(self, *a, **kw): pass

        shim = _Shim()
        shim.do_POST()
        return shim._status

    def test_updates_memory_and_file(self):
        status = self._invoke({"runaway_threshold": 500})
        self.assertEqual(status, 204)
        self.assertEqual(jobs._cfg.RUNAWAY_THRESHOLD, 500)
        out = os.path.join(self.data, "user_config.py")
        self.assertTrue(os.path.isfile(out))
        with open(out) as f:
            self.assertIn("RUNAWAY_THRESHOLD = 500", f.read())

    def test_replaces_existing_line(self):
        out = os.path.join(self.data, "user_config.py")
        with open(out, "w") as f:
            f.write("HIGHLIGHTS=[]\nRUNAWAY_THRESHOLD = 200\nSOURCES=[]\n")
        status = self._invoke({"runaway_threshold": 777})
        self.assertEqual(status, 204)
        with open(out) as f:
            txt = f.read()
        self.assertIn("RUNAWAY_THRESHOLD = 777", txt)
        self.assertNotIn("RUNAWAY_THRESHOLD = 200", txt)

    def test_rejects_out_of_range(self):
        for bad in (5, -1, 20000, "not-a-number"):
            with self.subTest(bad=bad):
                self.assertEqual(self._invoke({"runaway_threshold": bad}), 400)


class TestEmptySectionHideOnReject(unittest.TestCase):
    """REGRESSION — rejecting the last job in a section used to leave
    the h2 group heading visible until the next tab switch. The fix
    makes updateCounters() call refreshGroupHeadings() so hide-empty-
    sections responds immediately."""

    def setUp(self):
        import pathlib
        self.src = pathlib.Path(jobs.__file__).read_text()

    def test_update_counters_refreshes_group_headings(self):
        import re
        m = re.search(r"function updateCounters\(.*?\n\}", self.src, re.DOTALL)
        self.assertIsNotNone(m, "updateCounters not found")
        body = m.group(0)
        self.assertIn(
            "refreshGroupHeadings", body,
            "updateCounters must call refreshGroupHeadings() so the h2 "
            "heading hides as soon as its last section goes empty.",
        )


class TestKeyboardShortcuts(unittest.TestCase):
    """Cmd/Ctrl + letter shortcuts route to the top-bar buttons. Pin the
    mapping so a refactor doesn't silently break muscle memory."""

    def setUp(self):
        import pathlib
        self.src = pathlib.Path(jobs.__file__).read_text()

    def test_shortcut_map_present(self):
        # The exact routing table — pin each (key → element id) pair.
        # Cmd+, targets the Settings <a> (which navigates to /settings)
        # rather than a button; see settings-link in render_html_nav.
        for key, el_id in [
            ("'r'", "refresh-btn"),
            ("'i'", "claude-score-all"),
            ("'e'", "edit-sources-setup"),
            ("','", "settings-link"),
        ]:
            with self.subTest(key=key, el=el_id):
                self.assertRegex(
                    self.src,
                    rf"{key}:\s*'{el_id}'",
                    f"shortcut {key} → #{el_id} missing from the keydown map",
                )

    def test_handler_ignores_shift(self):
        """Cmd+Shift+R must still trigger hard-reload; Cmd+Shift+I devtools.
        The handler explicitly bails on e.shiftKey."""
        self.assertIn(
            "e.shiftKey || e.altKey || e.repeat",
            self.src,
            "Shortcut handler must bail when Shift / Alt is held, or on repeat.",
        )

    def test_target_buttons_exist(self):
        """Each shortcut points at an element rendered in the main HTML
        (buttons for refresh / AI / Edit; the Settings gear is an <a>
        navigating to /settings)."""
        for el_id in ("refresh-btn", "claude-score-all",
                      "edit-sources-setup", "settings-link"):
            with self.subTest(el=el_id):
                self.assertIn(f'id="{el_id}"', self.src,
                              f"shortcut target #{el_id} not rendered")


if __name__ == "__main__":
    unittest.main()
