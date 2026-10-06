"""Interactive onboarding wizard — HTML dialog served by a short-lived
local HTTP server. Entry point: `jobs.py --onboard` (also wired to
`make onboarding`).

Flow:
  1. Pick a free port, start http.server.ThreadingHTTPServer.
  2. Open the user's browser on /onboarding.html.
  3. Page lists the ~150 companies grouped per src/catalog.py.
  4. User ticks companies, clicks Save → POST /write-user-config.
  5. Server writes data/user_config.py (+ a timestamped backup if an
     existing file was present), responds 200, prints a confirmation
     to the terminal, then stops the server.

MVP scope: only the SOURCES list. HIGHLIGHTS / TITLE_BLACKLIST /
LOCATION_BLACKLIST ship as empty stubs; a future ticket will cover
them.
"""
from __future__ import annotations

import datetime as _dt
import http.server
import importlib.util as _ilu
import json
import os
import pprint
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from catalog import CATALOG
from config import SERVE_HOST, SERVE_PORT


# =============================================================================
# Preset content shown on steps 2 / 3 / 4. Hard-coded, user-tunable at
# runtime through chip selection / textarea entry. Kept here so src/
# stays self-contained (no runtime config file lookup).
# =============================================================================

HIGHLIGHT_PRESETS = [
    "Security", "Cryptography", "Cyber", "AI", "ML", "LLM", "GPU",
    "Python", "Rust", "Go", "TypeScript", "Kubernetes", "Terraform",
    "Remote", "Hybrid",
    "Senior", "Staff", "Principal", "Director", "VP",
    "Engineering Manager", "CTO",
]

# Grouped by continent so the wizard can show a <details> per group.
# Includes a "Regions" group at the top for the common multi-country
# aggregates (APAC, EMEA, LATAM, …). All UN member states are listed so
# nobody is left out — users can scroll to their own country, click,
# done.
LOCATION_BLACKLIST_GROUPS = {
    "Regions / aggregates": [
        "APAC", "EMEA", "LATAM", "MENA", "GCC",
        "Nordics", "Benelux", "DACH", "Sub-Saharan Africa",
    ],
    "Africa": [
        "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
        "Cabo Verde", "Cameroon", "Central African Republic", "Chad",
        "Comoros", "Côte d'Ivoire", "DR Congo", "Djibouti", "Egypt",
        "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia", "Gabon",
        "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Kenya", "Lesotho",
        "Liberia", "Libya", "Madagascar", "Malawi", "Mali", "Mauritania",
        "Mauritius", "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria",
        "Rwanda", "São Tomé and Príncipe", "Senegal", "Seychelles",
        "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Sudan",
        "Tanzania", "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe",
    ],
    "North America & Caribbean": [
        "Antigua and Barbuda", "Bahamas", "Barbados", "Belize", "Canada",
        "Costa Rica", "Cuba", "Dominica", "Dominican Republic",
        "El Salvador", "Grenada", "Guatemala", "Haiti", "Honduras",
        "Jamaica", "Mexico", "Nicaragua", "Panama", "Saint Kitts and Nevis",
        "Saint Lucia", "Saint Vincent and the Grenadines",
        "Trinidad and Tobago", "United States",
    ],
    "South America": [
        "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador",
        "Guyana", "Paraguay", "Peru", "Suriname", "Uruguay", "Venezuela",
    ],
    "Asia": [
        "Afghanistan", "Armenia", "Azerbaijan", "Bahrain", "Bangladesh",
        "Bhutan", "Brunei", "Cambodia", "China", "Cyprus", "Georgia",
        "Hong Kong", "India", "Indonesia", "Iran", "Iraq", "Israel",
        "Japan", "Jordan", "Kazakhstan", "Kuwait", "Kyrgyzstan", "Laos",
        "Lebanon", "Malaysia", "Maldives", "Mongolia", "Myanmar", "Nepal",
        "North Korea", "Oman", "Pakistan", "Palestine", "Philippines",
        "Qatar", "Saudi Arabia", "Singapore", "South Korea", "Sri Lanka",
        "Syria", "Taiwan", "Tajikistan", "Thailand", "Timor-Leste",
        "Turkey", "Turkmenistan", "UAE", "Uzbekistan", "Vietnam", "Yemen",
    ],
    "Europe": [
        "Albania", "Andorra", "Austria", "Belarus", "Belgium",
        "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Czechia",
        "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
        "Hungary", "Iceland", "Ireland", "Italy", "Kosovo", "Latvia",
        "Liechtenstein", "Lithuania", "Luxembourg", "Malta", "Moldova",
        "Monaco", "Montenegro", "Netherlands", "North Macedonia", "Norway",
        "Poland", "Portugal", "Romania", "Russia", "San Marino", "Serbia",
        "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Ukraine",
        "United Kingdom",
    ],
    "Oceania": [
        "Australia", "Fiji", "Kiribati", "Marshall Islands", "Micronesia",
        "Nauru", "New Zealand", "Palau", "Papua New Guinea", "Samoa",
        "Solomon Islands", "Tonga", "Tuvalu", "Vanuatu",
    ],
}

TITLE_BLACKLIST_PACKS = {
    "Entry-level": [
        "Intern", "Internship", "Junior", "Associate", "New Grad",
        "Student", "Apprenti", "Stage", "Trainee",
    ],
    "Non-engineering": [
        "Sales", "Marketing", "Recruiter", "Recruiting", "Human Resources",
        "Finance", "Legal", "Counsel", "Communications", "PR Director",
        "People Operations", "Accounting",
    ],
    "Hardware / electrical": [
        "ASIC", "Firmware Engineer", "Electrical Engineer", "Hardware Engineer",
        "Mechanical Engineer", "Design Engineer", "Semiconductor",
    ],
    "Operations / admin": [
        "IT Support", "Office Manager", "Workplace", "Facilities",
        "Administrative", "Executive Assistant", "People Success",
    ],
    "Field / customer-facing": [
        "Field Engineer", "Field CTO", "Deployed Engineer",
        "Partner Deployed Engineer", "Customer Success", "Customer Support",
        "Account Executive", "Account Manager", "Technical Support",
    ],
    "Hiring / content": [
        "Technical Recruiter", "Technical Sourcer", "Technical Writer",
        "Content Manager", "Content Strategy",
    ],
    "Engineer (specializations)": [
        "Data Engineer", "Analytics Engineer",
        "QA Engineer", "Test Engineer", "SDET",
        "Sales Engineer", "Solutions Engineer",
        "Support Engineer", "Technical Support Engineer",
        "Customer Engineer", "Integration Engineer",
        "DevOps Engineer", "Site Reliability Engineer",
        "Platform Engineer", "Build Engineer", "Release Engineer",
        "Network Engineer",
    ],
}


# =============================================================================
# Content building
# =============================================================================

def _dedupe_preserve_order(items):
    seen = set()
    out = []
    for it in items:
        if not isinstance(it, str):
            continue
        t = it.strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _build_user_config(
    selected_names: set[str],
    highlights: list[str] | None = None,
    title_blacklist: list[str] | None = None,
    location_blacklist: list[str] | None = None,
    existing_queries: dict | None = None,
) -> str:
    """Serialise the wizard's output into a user_config.py string.
    Every list is deduped (case-insensitive, order preserved); empty
    lists ship as `[]`.

    `existing_queries` is {company_name: [queries...]} — used by the
    board's /write-user-config endpoint to preserve the per-source
    `queries` filters the user already tuned. Without it, re-saving via
    the edit-companies modal would blow away every custom query the
    user had set up (which happened once in the wild — see
    planning/closed/… if we ever write a postmortem).
    """
    chosen = [e for e in CATALOG if e["name"] in selected_names]
    chosen.sort(key=lambda e: (e["group"].lower(), e["name"].lower()))
    sources = []
    existing_queries = existing_queries or {}
    for e in chosen:
        entry = {k: v for k, v in e.items() if k != "group"}
        entry["queries"] = list(existing_queries.get(e["name"], []))
        sources.append(entry)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    header = f'''"""data/user_config.py — generated by `make onboarding` on {now}.

Personal preferences live here, outside src/, so src/ can stay
open-sourceable with zero personal data. src/config.py loads this file
at import time and overrides its empty defaults.

Edit by hand or re-run `make onboarding` to pick a different set of
companies. The wizard asks before overwriting an existing file.
"""

'''
    hl = _dedupe_preserve_order(highlights or [])
    tb = _dedupe_preserve_order(title_blacklist or [])
    lb = _dedupe_preserve_order(location_blacklist or [])
    body = (
        f"HIGHLIGHTS = {pprint.pformat(hl, width=120)}\n\n"
        f"TITLE_BLACKLIST = {pprint.pformat(tb, width=120)}\n\n"
        f"LOCATION_BLACKLIST = {pprint.pformat(lb, width=120)}\n\n"
        f"SOURCES = {pprint.pformat(sources, width=120, sort_dicts=False)}\n"
    )
    return header + body


def _backup_path(path: str) -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{path}.bak.{stamp}"


def _summarize_existing(path: str) -> dict:
    """Return a dict describing an existing user_config.py (sources
    count + modification time) so the wizard can show a sensible
    warning banner. Falls back to '?' values when the file is unreadable."""
    info = {"exists": True, "n_sources": "?", "mtime": "?"}
    try:
        spec = _ilu.spec_from_file_location("_existing_uc", path)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        info["n_sources"] = len(getattr(mod, "SOURCES", []) or [])
    except Exception:
        pass
    try:
        info["mtime"] = _dt.datetime.fromtimestamp(
            os.path.getmtime(path)
        ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return info


# =============================================================================
# HTTP server
# =============================================================================

def _pick_free_port(preferred: int = 8766) -> int:
    """Return `preferred` if it's bindable on localhost, otherwise ask
    the OS for any free port. Keeps the wizard off the main board's
    8765 so both can coexist."""
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
        except OSError:
            continue
    raise RuntimeError("could not find a free port for the onboarding server")


def _load_html(data_dir: str, out_path: str) -> bytes:
    """Load src/onboarding.html and inline the CATALOG + EXISTING JSON
    so the browser doesn't need a second round-trip."""
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "onboarding.html"), encoding="utf-8") as f:
        html = f.read()
    existing = {"exists": False}
    if os.path.isfile(out_path):
        existing = _summarize_existing(out_path)
        existing["backup_path"] = _backup_path(out_path)
    catalog_json = json.dumps(CATALOG, ensure_ascii=False)
    existing_json = json.dumps(existing, ensure_ascii=False)
    presets_json = json.dumps({
        "highlights": HIGHLIGHT_PRESETS,
        "location_groups": LOCATION_BLACKLIST_GROUPS,
        "title_packs": TITLE_BLACKLIST_PACKS,
    }, ensure_ascii=False)
    html = html.replace(
        "/*__CATALOG__*/ (window.__CATALOG__ || [])",
        catalog_json,
    )
    html = html.replace(
        "/*__EXISTING__*/ (window.__EXISTING__ || null)",
        existing_json,
    )
    html = html.replace(
        "/*__PRESETS__*/ (window.__PRESETS__ || {\n"
        "  highlights: [], location_groups: {}, title_packs: {}\n"
        "})",
        presets_json,
    )
    return html.encode("utf-8")


class _OnboardingServer(http.server.ThreadingHTTPServer):
    """Carries the shared state so handlers can post results back."""

    daemon_threads = True

    def __init__(self, address, handler_cls, data_dir, out_path, done_event):
        super().__init__(address, handler_cls)
        self.data_dir = data_dir
        self.out_path = out_path
        self.done_event = done_event
        self.result = {"status": "cancelled", "path": None, "backup": None, "n": 0}
        # Launch-board subprocess state. Driven by /launch-board + /launch-status.
        self.launch_lock = threading.Lock()
        self.launch_state = {
            "status": "idle",      # idle | running | ready | failed
            "started_at": None,
            "board_url": f"http://{SERVE_HOST}:{SERVE_PORT}/",
            "error": None,
        }
        self._launch_proc = None

    def spawn_board(self):
        """Spawn `jobs.py --no-open` as a detached subprocess so it
        survives this server's shutdown. Idempotent: a second call
        while the board is already running is a no-op."""
        with self.launch_lock:
            if self.launch_state["status"] in ("running", "ready"):
                return self.launch_state
            self.launch_state["status"] = "running"
            self.launch_state["started_at"] = time.time()
            self.launch_state["error"] = None
        try:
            # start_new_session detaches from our process group so the
            # board survives when this wizard server exits.
            here = os.path.dirname(os.path.abspath(__file__))
            self._launch_proc = subprocess.Popen(
                [sys.executable, os.path.join(here, "jobs.py"), "--no-open"],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            with self.launch_lock:
                self.launch_state["status"] = "failed"
                self.launch_state["error"] = str(e)[:300]
            return self.launch_state
        # Background poller watches localhost:SERVE_PORT, flips to
        # "ready" once it responds.
        threading.Thread(target=self._poll_board_ready, daemon=True).start()
        return self.launch_state

    def _poll_board_ready(self):
        deadline = time.time() + 900  # 15 min upper bound for first fetch
        board_url = self.launch_state["board_url"]
        while time.time() < deadline:
            # Dead subprocess means the board failed early (bad config,
            # port conflict, …). Surface it as a failure instead of
            # polling forever.
            proc = self._launch_proc
            if proc and proc.poll() is not None:
                with self.launch_lock:
                    self.launch_state["status"] = "failed"
                    self.launch_state["error"] = (
                        f"board exited early (code {proc.returncode}); "
                        "run `make run` in a terminal to see the error"
                    )
                return
            try:
                with urllib.request.urlopen(board_url, timeout=1) as r:
                    if 200 <= r.status < 500:
                        with self.launch_lock:
                            self.launch_state["status"] = "ready"
                        return
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                pass
            time.sleep(1.0)
        with self.launch_lock:
            self.launch_state["status"] = "failed"
            self.launch_state["error"] = "timed out waiting for the board (15 min)"


class _OnboardingHandler(http.server.BaseHTTPRequestHandler):

    # Silence the default per-request stderr log — we have our own prints.
    def log_message(self, fmt, *args):  # noqa: N802 — stdlib signature
        return

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/onboarding.html"):
            body = _load_html(self.server.data_dir, self.server.out_path)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            payload = {}

        if self.path == "/write-user-config":
            self._handle_write(payload)
            return
        if self.path == "/launch-board":
            # Spawn jobs.py in a detached subprocess + flip our state
            # so the browser can poll /launch-status. Does NOT shut this
            # server down yet — we need to keep answering status pings
            # until the browser redirects.
            state = self.server.spawn_board()
            self._json(200, dict(state, elapsed=self._elapsed(state)))
            return
        if self.path == "/launch-status":
            with self.server.launch_lock:
                state = dict(self.server.launch_state)
            state["elapsed"] = self._elapsed(state)
            self._json(200, state)
            # When ready, schedule shutdown so the user doesn't leave a
            # zombie port behind. A short grace lets the browser read
            # this reply before the connection drops.
            if state["status"] in ("ready", "failed"):
                threading.Timer(
                    1.5, lambda: self.server.done_event.set()
                ).start()
            return
        if self.path == "/cancel":
            self._json(200, {"ok": True})
            self.server.result["status"] = "cancelled"
            self.server.done_event.set()
            return
        self.send_response(404)
        self.end_headers()

    @staticmethod
    def _elapsed(state):
        start = state.get("started_at")
        return int(time.time() - start) if start else 0

    def _handle_write(self, payload):
        raw = payload.get("names") or []
        selected = {str(n).strip() for n in raw if str(n).strip()}
        valid = {e["name"] for e in CATALOG}
        selected = selected & valid
        if not selected:
            self._json(400, {"error": "no valid company names"})
            return
        highlights = [str(x) for x in (payload.get("highlights") or [])]
        title_blacklist = [str(x) for x in (payload.get("title_blacklist") or [])]
        location_blacklist = [str(x) for x in (payload.get("location_blacklist") or [])]
        try:
            os.makedirs(self.server.data_dir, exist_ok=True)
            backup = None
            if os.path.isfile(self.server.out_path):
                backup = _backup_path(self.server.out_path)
                shutil.copy2(self.server.out_path, backup)
            content = _build_user_config(
                selected,
                highlights=highlights,
                title_blacklist=title_blacklist,
                location_blacklist=location_blacklist,
            )
            with open(self.server.out_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.server.result = {
                "status": "saved",
                "path": self.server.out_path,
                "backup": backup,
                "n": len(selected),
            }
            print(f"✓ Wrote {self.server.out_path} ({len(selected)} companies).")
            if backup:
                print(f"  Backup: {backup}")
            self._json(200, {
                "ok": True,
                "path": self.server.out_path,
                "backup": backup,
                "n": len(selected),
            })
            # NOTE: we do NOT set done_event here anymore — the server
            # must keep running so the browser can POST /launch-board
            # from the done screen. Shutdown is triggered either by
            # /cancel or (automatically) when /launch-status reports
            # the board is ready.
        except Exception as e:
            self._json(500, {"error": str(e)[:300]})

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# =============================================================================
# Entry point
# =============================================================================

def run_wizard(data_dir: str = "data", open_browser: bool = True) -> int:
    """Run the HTML onboarding wizard. Returns a POSIX exit code.
    `open_browser=False` is used by tests."""
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, "user_config.py")

    port = _pick_free_port()
    done = threading.Event()
    server = _OnboardingServer(
        ("127.0.0.1", port), _OnboardingHandler,
        data_dir=data_dir, out_path=out_path, done_event=done,
    )
    url = f"http://127.0.0.1:{port}/onboarding.html"

    print("=" * 70)
    print("Onboarding wizard")
    print("=" * 70)
    print(f"Serving on {url}")
    print("Pick your companies in the browser, then click Save.")
    print("(Ctrl-C to abort.)")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        done.wait()
    except KeyboardInterrupt:
        print("\nAborted.")
        server.shutdown()
        return 1

    server.shutdown()
    result = server.result
    launch = server.launch_state

    print()
    if launch["status"] == "ready":
        print(f"✓ Board is up at {launch['board_url']} — enjoy.")
        return 0
    if launch["status"] == "running":
        print(f"⚠ Board is still building. It will be at {launch['board_url']} "
              "when ready.")
        return 0
    if launch["status"] == "failed":
        print(f"✗ Board launch failed: {launch.get('error')}")
        print("  Try  make run  in a terminal to see the full error.")
        return 1
    if result["status"] == "saved":
        print(f"Next: run  make run  to fetch and open your board.")
        return 0
    print("Cancelled — nothing was written.")
    return 0


if __name__ == "__main__":
    sys.exit(run_wizard(os.environ.get("JOBS_DATA_DIR", "data")))
