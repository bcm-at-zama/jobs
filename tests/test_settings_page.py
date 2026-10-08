"""Settings page — GET /settings serves src/settings.html with the two
template placeholders (__SERVER_URL__, __RUNAWAY_THRESHOLD__) inlined.

The page replaces the former Ctrl+, modal. These tests guard the
contract the browser depends on:

  - the route is reachable (200 OK, HTML content-type);
  - no raw placeholders leak through to the browser;
  - the runaway threshold reflects the current `_cfg.RUNAWAY_THRESHOLD`
    (so a /set-settings POST in the same session shows the new value
    when the user reopens /settings);
  - the markup contains the four section headings so a drive-by rename
    doesn't silently empty the page.

Run:  python3 -m unittest tests.test_settings_page
"""
import os
import unittest
from io import BytesIO
from unittest import mock

import jobs


class TestRenderSettingsHtml(unittest.TestCase):
    """Direct test of the renderer that reads settings.html and inlines
    the two placeholders. No HTTP plumbing — just the function."""

    def test_placeholders_replaced(self):
        with mock.patch.object(jobs._cfg, "RUNAWAY_THRESHOLD", 420):
            data = jobs._render_settings_html()
        self.assertIsInstance(data, bytes)
        text = data.decode("utf-8")
        self.assertNotIn("__SERVER_URL__", text)
        self.assertNotIn("__RUNAWAY_THRESHOLD__", text)
        # The current threshold shows up as the pre-filled value for the
        # number input (JSON-encoded int → bare "420").
        self.assertIn("420", text)

    def test_contains_all_section_headings(self):
        """A rename of settings.html that drops a section would silently
        strand user-visible toggles. Keep the heading-level contract."""
        data = jobs._render_settings_html()
        text = data.decode("utf-8")
        for heading in (
            ">Row display<",
            ">Section summaries<",
            ">AI assistant<",
            ">Scraping<",
            ">Highlight keywords<",
        ):
            self.assertIn(heading, text, f"missing heading: {heading}")

    def test_highlights_placeholder_replaced(self):
        """__HIGHLIGHTS__ must be substituted with a JSON array literal
        the chip editor can read. Raw placeholder = page JS breaks."""
        with mock.patch.object(jobs, "HIGHLIGHTS", ["crypto", "security"]):
            text = jobs._render_settings_html().decode("utf-8")
        self.assertNotIn("__HIGHLIGHTS__", text)
        self.assertIn('["crypto", "security"]', text)

    def test_back_link_points_to_root(self):
        """The Back link is the only navigation off the page; if it rot
        the user has to hand-type / to get back."""
        text = jobs._render_settings_html().decode("utf-8")
        self.assertIn('href="/"', text)


class TestSettingsGetRoute(unittest.TestCase):
    """GET /settings must serve the page with HTML content-type. We
    shim BaseHTTPRequestHandler the same way the other handler tests do
    (test_edit_sources, test_runaway)."""

    def _invoke(self, path):
        class _Shim(jobs.Handler):
            def __init__(self):
                self.rfile = BytesIO(b"")
                self.wfile = BytesIO()
                self.headers = {}
                self.path = path
                self.command = "GET"
                self._status = None
                self._headers = {}

            def send_response(self, code, msg=None):
                self._status = code

            def send_header(self, k, v):
                self._headers[k] = v

            def end_headers(self): pass
            def log_message(self, *a, **kw): pass

        shim = _Shim()
        shim.do_GET()
        return shim._status, shim._headers, shim.wfile.getvalue()

    def test_route_returns_200_html(self):
        status, headers, body = self._invoke("/settings")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertTrue(body)
        self.assertIn(b"<title>Settings", body)

    def test_route_alias(self):
        """/settings and /settings.html both serve the page — the second
        form is a common user guess when typing in the address bar."""
        status, _, body = self._invoke("/settings.html")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>Settings", body)

    def test_unknown_path_still_404s(self):
        """Guardrail: adding /settings must not have swallowed the
        catch-all 404 branch."""
        status, _, _ = self._invoke("/does-not-exist")
        self.assertEqual(status, 404)


class TestSetHighlightsPost(unittest.TestCase):
    """POST /set-highlights {highlights: [...]} rewrites HIGHLIGHTS in
    data/user_config.py, mutates the in-memory list, and patches the
    `const HIGHLIGHTS = …;` line in data/jobs.html so a reload picks up
    the new list without a full /refresh."""

    def _invoke(self, body_bytes):
        class _Shim(jobs.Handler):
            def __init__(self):
                self.rfile = BytesIO(body_bytes)
                self.wfile = BytesIO()
                self.headers = {
                    "Content-Length": str(len(body_bytes)),
                    "Content-Type": "application/json",
                }
                self.path = "/set-highlights"
                self.command = "POST"
                self._status = None
                self._headers = {}

            def send_response(self, code, msg=None):
                self._status = code

            def send_header(self, k, v):
                self._headers[k] = v

            def end_headers(self): pass
            def log_message(self, *a, **kw): pass

        shim = _Shim()
        shim.do_POST()
        return shim._status

    def test_updates_user_config_and_mutates_in_memory(self):
        import tempfile, json as _json
        with tempfile.TemporaryDirectory() as tmp:
            # Pre-populate the user_config.py so the regex replace path hits.
            with open(os.path.join(tmp, "user_config.py"), "w") as f:
                f.write("HIGHLIGHTS = ['old']\nSOURCES = []\n")
            with mock.patch.object(jobs._cfg, "DATA_DIR", tmp), \
                 mock.patch.object(jobs, "HIGHLIGHTS", ["old"]), \
                 mock.patch.object(jobs._cfg, "HIGHLIGHTS", ["old"]):
                body = _json.dumps({"highlights": ["crypto", "security"]})
                status = self._invoke(body.encode())
                self.assertEqual(status, 204)
                # In-memory mutated in place
                self.assertEqual(jobs.HIGHLIGHTS, ["crypto", "security"])
                # File on disk rewritten
                written = open(os.path.join(tmp, "user_config.py")).read()
                self.assertIn("'crypto'", written)
                self.assertIn("'security'", written)
                self.assertNotIn("'old'", written)

    def test_dedupes_case_insensitively(self):
        import tempfile, json as _json
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "user_config.py"), "w") as f:
                f.write("HIGHLIGHTS = []\n")
            with mock.patch.object(jobs._cfg, "DATA_DIR", tmp), \
                 mock.patch.object(jobs, "HIGHLIGHTS", []), \
                 mock.patch.object(jobs._cfg, "HIGHLIGHTS", []):
                body = _json.dumps({"highlights": ["Security", "security", "CRYPTO"]})
                status = self._invoke(body.encode())
                self.assertEqual(status, 204)
                self.assertEqual(jobs.HIGHLIGHTS, ["Security", "CRYPTO"])

    def test_rejects_non_list(self):
        status = self._invoke(b'{"highlights": "not-a-list"}')
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
