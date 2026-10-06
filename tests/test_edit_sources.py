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


if __name__ == "__main__":
    unittest.main()
