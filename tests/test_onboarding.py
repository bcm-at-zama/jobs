"""Onboarding wizard — hits the HTTP endpoints in a background server
and asserts the generated user_config.py is a valid Python module.

Run:  python3 -m unittest tests.test_onboarding
"""
import importlib.util
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request

import onboarding


class TestBuildUserConfig(unittest.TestCase):
    """Pure-function tests on the serializer."""

    def test_build_user_config_is_valid_python(self):
        content = onboarding._build_user_config({"Anthropic", "OpenAI"})
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            spec = importlib.util.spec_from_file_location("_test_uc", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertEqual(len(mod.SOURCES), 2)
            names = {s["name"] for s in mod.SOURCES}
            self.assertEqual(names, {"Anthropic", "OpenAI"})
            for s in mod.SOURCES:
                self.assertIn("kind", s)
                self.assertIn("slug", s)
                self.assertEqual(s["queries"], [])
            self.assertEqual(mod.HIGHLIGHTS, [])
            self.assertEqual(mod.TITLE_BLACKLIST, [])
            self.assertEqual(mod.LOCATION_BLACKLIST, [])
        finally:
            os.unlink(path)

    def test_build_user_config_strips_group_field(self):
        content = onboarding._build_user_config({"Anthropic"})
        self.assertNotIn("'group'", content)
        self.assertNotIn('"group"', content)

    def test_catalog_entries_have_mandatory_fields(self):
        from catalog import CATALOG
        self.assertGreater(len(CATALOG), 50, "catalog should ship >50 entries")
        groups = {e["group"] for e in CATALOG}
        self.assertGreater(len(groups), 1, "catalog should span multiple groups")
        for e in CATALOG:
            for key in ("name", "kind", "slug", "group"):
                self.assertIn(key, e, f"catalog entry missing {key!r}: {e}")


class TestHttpWizard(unittest.TestCase):
    """Spin up the real wizard server in a thread, POST at it, assert
    the file lands on disk with the right content."""

    def _start_server(self, tmpdir):
        """Return (server, thread, url, done_event)."""
        port = onboarding._pick_free_port()
        done = threading.Event()
        server = onboarding._OnboardingServer(
            ("127.0.0.1", port), onboarding._OnboardingHandler,
            data_dir=tmpdir,
            out_path=os.path.join(tmpdir, "user_config.py"),
            done_event=done,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{port}"
        # Tiny wait for the socket to be ready — serve_forever is sync.
        time.sleep(0.05)
        return server, thread, url, done

    def test_get_renders_html_with_inlined_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, _ = self._start_server(tmp)
            try:
                with urllib.request.urlopen(url + "/onboarding.html") as r:
                    body = r.read().decode()
                self.assertEqual(r.status, 200)
                # CATALOG is inlined (otherwise the browser has nothing
                # to render).
                self.assertIn('"name"', body)
                # Fallback placeholder should NOT survive — we inject
                # the real data.
                self.assertNotIn("window.__CATALOG__", body)
                self.assertNotIn("window.__EXISTING__", body)
            finally:
                server.shutdown()

    def test_post_write_user_config_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, done = self._start_server(tmp)
            try:
                payload = json.dumps({"names": ["Anthropic", "OpenAI"]}).encode()
                req = urllib.request.Request(
                    url + "/write-user-config",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as r:
                    resp = json.loads(r.read())
                self.assertTrue(resp["ok"])
                self.assertEqual(resp["n"], 2)
                self.assertTrue(done.is_set(), "server should mark done")
                # File now exists and parses as a module.
                out = os.path.join(tmp, "user_config.py")
                self.assertTrue(os.path.isfile(out))
                spec = importlib.util.spec_from_file_location("_uc", out)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                names = {s["name"] for s in mod.SOURCES}
                self.assertEqual(names, {"Anthropic", "OpenAI"})
            finally:
                server.shutdown()

    def test_post_write_backs_up_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = os.path.join(tmp, "user_config.py")
            with open(existing, "w") as f:
                f.write(
                    "HIGHLIGHTS=[]\nTITLE_BLACKLIST=[]\nLOCATION_BLACKLIST=[]\n"
                    "SOURCES=[{'name':'Keep me','kind':'greenhouse','slug':'keepme'}]\n"
                )
            server, _, url, _ = self._start_server(tmp)
            try:
                payload = json.dumps({"names": ["Anthropic"]}).encode()
                req = urllib.request.Request(
                    url + "/write-user-config",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as r:
                    resp = json.loads(r.read())
                self.assertTrue(resp["ok"])
                self.assertIsNotNone(resp["backup"])
                # Backup exists + still contains the old entry.
                self.assertTrue(os.path.isfile(resp["backup"]))
                with open(resp["backup"]) as f:
                    self.assertIn("Keep me", f.read())
                # New file has Anthropic, NOT Keep me.
                with open(existing) as f:
                    new = f.read()
                self.assertIn("Anthropic", new)
                self.assertNotIn("Keep me", new)
            finally:
                server.shutdown()

    def test_post_write_rejects_empty_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, _ = self._start_server(tmp)
            try:
                payload = json.dumps({"names": []}).encode()
                req = urllib.request.Request(
                    url + "/write-user-config",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                raised = False
                try:
                    urllib.request.urlopen(req)
                except urllib.error.HTTPError as e:
                    raised = True
                    self.assertEqual(e.code, 400)
                self.assertTrue(raised, "empty names should return HTTP 400")
                self.assertFalse(os.path.isfile(os.path.join(tmp, "user_config.py")))
            finally:
                server.shutdown()

    def test_post_cancel_sets_done_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, done = self._start_server(tmp)
            try:
                req = urllib.request.Request(
                    url + "/cancel", data=b"", method="POST",
                )
                with urllib.request.urlopen(req) as r:
                    self.assertEqual(r.status, 200)
                self.assertTrue(done.is_set())
                self.assertFalse(os.path.isfile(os.path.join(tmp, "user_config.py")))
                self.assertEqual(server.result["status"], "cancelled")
            finally:
                server.shutdown()


if __name__ == "__main__":
    unittest.main()
