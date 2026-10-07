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
from unittest import mock
import urllib.request

import onboarding


class TestBuildUserConfig(unittest.TestCase):
    """Pure-function tests on the serializer."""

    def test_build_user_config_is_valid_python(self):
        content = onboarding._build_user_config(
            {"Anthropic", "OpenAI"},
            highlights=["Security", "Rust"],
            title_blacklist=["Intern", "Associate"],
            location_blacklist=["India", "Dubai"],
        )
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
            self.assertEqual(mod.HIGHLIGHTS, ["Security", "Rust"])
            self.assertEqual(mod.TITLE_BLACKLIST, ["Intern", "Associate"])
            self.assertEqual(mod.LOCATION_BLACKLIST, ["India", "Dubai"])
        finally:
            os.unlink(path)

    def test_build_user_config_dedupes_case_insensitive(self):
        """`security` and `Security` should collapse to one entry."""
        content = onboarding._build_user_config(
            {"Anthropic"},
            highlights=["Security", "security", "  SECURITY  ", "Rust"],
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            spec = importlib.util.spec_from_file_location("_t", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertEqual(mod.HIGHLIGHTS, ["Security", "Rust"])
        finally:
            os.unlink(path)

    def test_build_user_config_defaults_empty_lists(self):
        """Call without the optional kwargs — the three lists stay []."""
        content = onboarding._build_user_config({"Anthropic"})
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            spec = importlib.util.spec_from_file_location("_t", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertEqual(mod.HIGHLIGHTS, [])
            self.assertEqual(mod.TITLE_BLACKLIST, [])
            self.assertEqual(mod.LOCATION_BLACKLIST, [])
        finally:
            os.unlink(path)

    def test_build_user_config_strips_group_field(self):
        content = onboarding._build_user_config({"Anthropic"})
        self.assertNotIn("'group'", content)
        self.assertNotIn('"group"', content)


class TestPickFreePort(unittest.TestCase):
    """`_pick_free_port` must honour the `avoid` set so the wizard and
    the sandbox board it spawns never collide with the main board."""

    def test_avoid_excludes_preferred(self):
        """When preferred is in avoid, we must get something else."""
        from config import SERVE_PORT
        port = onboarding._pick_free_port(preferred=8767, avoid=(8767,))
        self.assertNotEqual(port, 8767)
        # Should still be a usable high port.
        self.assertGreater(port, 1024)

    def test_avoid_multiple_ports(self):
        port = onboarding._pick_free_port(
            preferred=8767, avoid=(8765, 8766, 8767),
        )
        self.assertNotIn(port, {8765, 8766, 8767})

    def test_prefers_requested_when_allowed(self):
        """A free preferred port that isn't avoided should be returned."""
        import socket
        # Grab an OS-assigned free port, release it, then ask for it.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            wanted = s.getsockname()[1]
        got = onboarding._pick_free_port(preferred=wanted, avoid=())
        self.assertEqual(got, wanted)

    def test_run_wizard_honours_explicit_port(self):
        """`run_wizard(port=N)` must bind N, not auto-pick 8766. Lets
        `make onboarding PORT=N` pin the wizard's URL."""
        import socket
        import tempfile as _t
        # Grab an OS-assigned free port and release it so run_wizard
        # can bind it below.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            wanted = s.getsockname()[1]

        with _t.TemporaryDirectory() as tmp:
            # Fire run_wizard in a thread, cancel it via /cancel, assert
            # the wizard was reachable at `wanted` while it ran.
            exit_code = []
            def _runner():
                exit_code.append(
                    onboarding.run_wizard(tmp, open_browser=False, port=wanted)
                )
            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            # Wait for the server to come up.
            deadline = time.time() + 3
            reached = False
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{wanted}/onboarding.html",
                        timeout=0.5,
                    ) as r:
                        if r.status == 200:
                            reached = True
                            break
                except Exception:
                    time.sleep(0.05)
            self.assertTrue(
                reached, f"wizard never answered on explicit port {wanted}",
            )
            # Cancel so run_wizard returns.
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{wanted}/cancel",
                    data=b"{}", method="POST",
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=1).read()
            except Exception:
                pass
            t.join(timeout=3)

    def test_spawned_board_port_differs_from_wizard_and_main(self):
        """The board port chosen in _OnboardingServer.__init__ must
        differ from both the wizard port and the main board's
        SERVE_PORT so three servers can coexist."""
        from config import SERVE_PORT
        with tempfile.TemporaryDirectory() as tmp:
            port = onboarding._pick_free_port()
            done = threading.Event()
            server = onboarding._OnboardingServer(
                ("127.0.0.1", port), onboarding._OnboardingHandler,
                data_dir=tmp,
                out_path=os.path.join(tmp, "user_config.py"),
                done_event=done,
            )
            try:
                self.assertNotEqual(server._board_port, port)
                self.assertNotEqual(server._board_port, SERVE_PORT)
                self.assertIn(
                    f":{server._board_port}/",
                    server.launch_state["board_url"],
                )
            finally:
                server.server_close()

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
        """Return (server, thread, url, done_event). Each test must
        call `_stop(server)` in its finally block to release the port."""
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

    @staticmethod
    def _stop(server):
        """Shutdown + close socket so the port is released immediately."""
        server.shutdown()
        server.server_close()

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
                self._stop(server)

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
                # Note: save does NOT trigger done anymore — the server
                # must stay up so the browser can POST /launch-board.
                self.assertFalse(done.is_set(),
                                 "save alone should not shut the server down")
                # File now exists and parses as a module.
                out = os.path.join(tmp, "user_config.py")
                self.assertTrue(os.path.isfile(out))
                spec = importlib.util.spec_from_file_location("_uc", out)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                names = {s["name"] for s in mod.SOURCES}
                self.assertEqual(names, {"Anthropic", "OpenAI"})
            finally:
                self._stop(server)

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
                self._stop(server)

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
                self._stop(server)

    def test_post_cancel_sets_done_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, done = self._start_server(tmp)
            try:
                req = urllib.request.Request(
                    url + "/cancel", data=b"", method="POST",
                )
                with urllib.request.urlopen(req) as r:
                    self.assertEqual(r.status, 200)
                # Response may be flushed before the handler's final
                # done.set() — give it a beat.
                self.assertTrue(done.wait(timeout=1))
                self.assertFalse(os.path.isfile(os.path.join(tmp, "user_config.py")))
                self.assertEqual(server.result["status"], "cancelled")
            finally:
                self._stop(server)

    def test_post_write_persists_all_four_lists(self):
        """The new multi-step payload (names + highlights + blacklists)
        all land in the generated file."""
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, _ = self._start_server(tmp)
            try:
                payload = json.dumps({
                    "names": ["Anthropic"],
                    "highlights": ["Security", "AI"],
                    "title_blacklist": ["Intern", "Associate"],
                    "location_blacklist": ["India", "Dubai"],
                }).encode()
                req = urllib.request.Request(
                    url + "/write-user-config",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as r:
                    self.assertTrue(json.loads(r.read())["ok"])
                out = os.path.join(tmp, "user_config.py")
                spec = importlib.util.spec_from_file_location("_uc", out)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self.assertEqual([s["name"] for s in mod.SOURCES], ["Anthropic"])
                self.assertEqual(mod.HIGHLIGHTS, ["Security", "AI"])
                self.assertEqual(mod.TITLE_BLACKLIST, ["Intern", "Associate"])
                self.assertEqual(mod.LOCATION_BLACKLIST, ["India", "Dubai"])
            finally:
                self._stop(server)

    def test_get_renders_html_with_inlined_presets(self):
        """The presets JSON for keywords / locations / title packs is
        inlined so the browser can render chips + checkboxes without a
        second round trip."""
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, _ = self._start_server(tmp)
            try:
                with urllib.request.urlopen(url + "/onboarding.html") as r:
                    body = r.read().decode()
                self.assertIn("Security", body)   # from HIGHLIGHT_PRESETS
                self.assertIn("Entry-level", body)  # from TITLE_BLACKLIST_PACKS
                self.assertIn("India", body)      # from LOCATION_BLACKLIST_GROUPS/Asia
                self.assertIn("Africa", body)     # continent group header
                self.assertNotIn("window.__PRESETS__", body)
            finally:
                self._stop(server)

    def test_launch_board_spawns_subprocess_and_exposes_state(self):
        """`/launch-board` must POST → start the subprocess + flip our
        launch state to 'running'. We mock subprocess.Popen so the real
        jobs.py never runs in CI."""
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, _ = self._start_server(tmp)
            fake_proc = mock.MagicMock()
            fake_proc.poll.return_value = None  # still running
            try:
                with mock.patch(
                    "onboarding.subprocess.Popen", return_value=fake_proc
                ) as popen:
                    req = urllib.request.Request(
                        url + "/launch-board", data=b"", method="POST",
                    )
                    with urllib.request.urlopen(req) as r:
                        data = json.loads(r.read())
                    self.assertEqual(data["status"], "running")
                    self.assertIn("127.0.0.1", data["board_url"])
                    popen.assert_called_once()
                    args = popen.call_args
                    # Spawned with jobs.py --no-open in a new session.
                    cmd = args[0][0]
                    self.assertIn("jobs.py", cmd[1])
                    self.assertIn("--no-open", cmd)
                    self.assertTrue(args[1].get("start_new_session"))
            finally:
                self._stop(server)

    def test_launch_status_returns_elapsed_and_detects_ready(self):
        """Flip the launch_state manually to 'ready' and verify the
        /launch-status endpoint propagates it + the 1.5 s delayed
        shutdown fires."""
        with tempfile.TemporaryDirectory() as tmp:
            server, _, url, done = self._start_server(tmp)
            try:
                with server.launch_lock:
                    server.launch_state["status"] = "ready"
                    server.launch_state["started_at"] = time.time() - 7
                req = urllib.request.Request(
                    url + "/launch-status", data=b"", method="POST",
                )
                with urllib.request.urlopen(req) as r:
                    data = json.loads(r.read())
                self.assertEqual(data["status"], "ready")
                self.assertGreaterEqual(data["elapsed"], 6)
                # done_event fires ~5 s after /launch-status reports ready
                # (grace was bumped to let the browser redirect reliably).
                self.assertTrue(done.wait(timeout=8),
                                "server should auto-shutdown once ready")
            finally:
                self._stop(server)


if __name__ == "__main__":
    unittest.main()
