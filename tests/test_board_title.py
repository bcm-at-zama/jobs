"""Configurable board title — rendered in the main board's <title> tag,
in a visible `.board-title` span inside the tabs nav, and editable from
the /settings page via POST /set-settings {board_title: ...}.

Covers:
  - config.BOARD_TITLE exists with a neutral default (no personal data
    in src/, per CLAUDE.md house rule).
  - render_html_tabs() embeds the title in the nav.
  - _render_settings_html() inlines __BOARD_TITLE__ (so the Settings
    input pre-fills with the current value).
  - /set-settings POST accepts and persists `board_title` to
    data/user_config.py.
  - onboarding.html landing heading says "JobBoard" (users personalize
    after onboarding via Settings — not during the wizard).

Run:  python3 -m unittest tests.test_board_title
"""
import os
import unittest
from io import BytesIO
from unittest import mock

import jobs


class TestConfigDefault(unittest.TestCase):

    def test_board_title_default_exists(self):
        self.assertTrue(hasattr(jobs._cfg, "BOARD_TITLE"))
        self.assertIsInstance(jobs._cfg.BOARD_TITLE, str)
        self.assertTrue(jobs._cfg.BOARD_TITLE.strip())


class TestRenderHtmlTabs(unittest.TestCase):
    """The tabs nav must carry the title on the left of the tab buttons."""

    def test_board_title_span_present(self):
        with mock.patch.object(jobs._cfg, "BOARD_TITLE", "Test Board"):
            out = jobs.render_html_tabs()
        self.assertIn('class="board-title"', out)
        self.assertIn("Test Board", out)

    def test_board_title_is_html_escaped(self):
        with mock.patch.object(jobs._cfg, "BOARD_TITLE", "A & B <script>"):
            out = jobs.render_html_tabs()
        self.assertIn("A &amp; B &lt;script&gt;", out)
        self.assertNotIn("<script>", out)


class TestSettingsHtmlInline(unittest.TestCase):

    def test_board_title_placeholder_replaced(self):
        with mock.patch.object(jobs._cfg, "BOARD_TITLE", "Hello Board"):
            data = jobs._render_settings_html().decode("utf-8")
        self.assertNotIn("__BOARD_TITLE__", data)
        self.assertIn("Hello Board", data)

    def test_section_heading_present(self):
        text = jobs._render_settings_html().decode("utf-8")
        self.assertIn(">Board title<", text)
        self.assertIn('id="board-title-input"', text)


class TestSetSettingsPost(unittest.TestCase):
    """POST /set-settings {board_title: "X"} must update _cfg + rewrite
    data/user_config.py. We mock the file write path with a tmp dir."""

    def _invoke(self, body_bytes):
        class _Shim(jobs.Handler):
            def __init__(self):
                self.rfile = BytesIO(body_bytes)
                self.wfile = BytesIO()
                self.headers = {
                    "Content-Length": str(len(body_bytes)),
                    "Content-Type": "application/json",
                }
                self.path = "/set-settings"
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

    def test_board_title_updates_cfg(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # The handler writes to os.path.join(_cfg.DATA_DIR, "user_config.py").
            with mock.patch.object(jobs._cfg, "DATA_DIR", tmp), \
                 mock.patch.object(jobs._cfg, "BOARD_TITLE", "Old"):
                status = self._invoke(b'{"board_title": "Benoit\'s JobBoard"}')
                self.assertEqual(status, 204)
                self.assertEqual(jobs._cfg.BOARD_TITLE, "Benoit's JobBoard")
                written = open(os.path.join(tmp, "user_config.py")).read()
                self.assertIn("BOARD_TITLE = ", written)
                self.assertIn("Benoit's JobBoard", written)

    def test_rejects_empty_title(self):
        status = self._invoke(b'{"board_title": "   "}')
        self.assertEqual(status, 400)

    def test_rejects_oversized_title(self):
        status = self._invoke(
            ('{"board_title": "' + "x" * 200 + '"}').encode()
        )
        self.assertEqual(status, 400)


class TestOnboardingHeading(unittest.TestCase):
    """Onboarding stays neutral — the wizard isn't the place to collect
    the personalized title. Users set it from Settings afterwards."""

    def test_onboarding_h1_is_jobboard(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, "src", "onboarding.html")
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("<h1>JobBoard</h1>", html)
        self.assertNotIn("Welcome to your Personalized Job Board", html)


if __name__ == "__main__":
    unittest.main()
