#!/usr/bin/env python3
"""
jobs.py — aggregate job postings from multiple career boards into a single
HTML page with reject/persistence and client-side filters.

Everything you may want to tweak lives in the CONFIG section below.

Pipeline
--------
Step 1 — Load state
    Read `rejected.json`, `liked.json`, `score_cache.json`, `desc_cache.json`,
    (optional). Parse env-var knobs (JOBS_ONLY / JOBS_SKIP /
    JOBS_SKIP_PLAYWRIGHT / JOBS_SKIP_LLM) to decide which sources run.

Step 2 — Fetch (parallel across sources)
    A ThreadPoolExecutor calls `collect(source)` on each active SOURCE:
      • Ashby / Greenhouse       → plain HTTP GET on the public JSON board.
      • Apple / Google / Microsoft → Playwright + Chromium: render the SPA,
        extract job links + titles from the DOM, then hit each detail page
        for descriptions (with `desc_cache.json` to skip already-fetched URLs).
      • Ableton / Arturia / Neural DSP / Steinberg → Playwright, then regex
        on the rendered HTML for their bespoke URL schemes.
    Each fetcher returns `{"jobs": [...], "spontaneous_url": Optional[str]}`.

Step 3 — Normalize per job
    - Split locations on `;`/`|`, strip `+ N more`, `Hybrid `/`Remote ` prefixes.
    - Detect city vs country (handles Microsoft's reverse order).
    - Fold accents, normalize US states → USA, CA provinces → Canada.
    - Dedupe city variants (`NYC`, `New York, NY`, `New York City` → one).
    Then apply TITLE_BLACKLIST and LOCATION_BLACKLIST filters.

Step 4 — (no auto-scoring; the UI's "AI" button sends every visible job
    to Claude.ai via the paste-bar flow. See `_openClaudePasteBar` in the
    inline JS. The red Score badge is populated from any legacy
    `score_cache.json` entries if present.)

Step 5 — Render HTML
    Per source: an <h1> with the board name (linking to the public board),
    query pills, visible/rejected counters, optional Spontaneous ✉ link, then
    a <ul> where each <li> has: × reject, +1 like, score badge, title with
    highlighted keywords, seniority badge, locations. Descriptions are
    dropped inside a <details>. Sort key: liked → score DESC → seniority.
    Filter bar (seniority checkboxes, per-country location panel, text
    inputs) uses localStorage to persist your choices across refreshes.

Step 6 — Serve
    Start a local HTTP server on SERVE_HOST:SERVE_PORT, auto-open in your
    default browser (macOS-friendly). Two endpoints:
      • GET /            → jobs.html
      • POST /reject     → append URL to rejected.json
      • POST /like       → append URL to liked.json (with /unlike inverse)
    Client-side JS in the page calls these on × / +1 clicks.
"""

# =============================================================================
# CONFIG — see config.py in the same directory
# =============================================================================
# Everything a user might reasonably want to tweak lives in `config.py`.
# The engine below imports it wholesale. If you want to fork this for a
# different profile, keep this file untouched and duplicate `config.py`.
from config import (  # noqa: E402,F401 — public config surface
    DATA_DIR,
    OUTPUT_HTML, REJECTED_DB, LIKED_DB, TO_APPLY_DB, APPLIED_DB, APP_REJECTED_DB, HISTORY_DB, SEEN_DB, JOB_INDEX_DB,
    SCORE_CACHE, DESC_CACHE, CLAUDE_FIT_CACHE, RAW_LOCATIONS_FILE,
    LIST_CACHE_DIR, LIST_CACHE_TTL_HOURS,
    SERVE_HOST, SERVE_PORT,
    HIGHLIGHTS, TITLE_CASE_OVERRIDES,
    TITLE_BLACKLIST, LOCATION_BLACKLIST,
    SENIORITY_GROUPS, SENIORITY_RANK, SENIORITY, SENIORITY_TOGGLES,
    SENIORITY_XP, SENIORITY_XP_DEFAULT, IC_LEVEL_XP,
    SOURCES, SPONTANEOUS_PATTERNS,
    GROUP_ORDER, GROUP_OF, COMPANY_INFO,
)


import argparse
import concurrent.futures
import html
import http.server
import json
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

import os

# ANSI red for error lines. Auto-disabled when stdout is redirected to a file
# or when NO_COLOR is set (https://no-color.org).
_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
_RED    = "\033[31m"      if _USE_COLOR else ""
_CYAN   = "\033[36m"      if _USE_COLOR else ""
_ORANGE = "\033[38;5;208m" if _USE_COLOR else ""  # 256-color orange
_RESET  = "\033[0m"       if _USE_COLOR else ""


def err(msg):
    """Print an error line in red to stdout."""
    print(f"{_RED}{msg}{_RESET}", file=sys.stdout)


def warn(msg):
    """Print a warning line in orange to stdout (used for high cache-miss rates
    or other 'not broken but sub-optimal' conditions)."""
    print(f"{_ORANGE}{msg}{_RESET}", file=sys.stdout)


def timing(msg):
    """Print a timing/duration line in cyan to stdout."""
    print(f"{_CYAN}{msg}{_RESET}", file=sys.stdout)


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def http_get_text(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _load_set(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_set(path, s):
    # Ensure the parent directory exists — state lives in `data/` now,
    # which may not have been created yet on a fresh clone.
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(s), f, indent=2)


def load_rejected():
    return _load_set(REJECTED_DB)


def save_rejected(rejected):
    _save_set(REJECTED_DB, rejected)


def load_liked():
    return _load_set(LIKED_DB)


def save_liked(liked):
    _save_set(LIKED_DB, liked)


def load_seen():
    """URLs we have already surfaced in a previous run. Anything not in this
    set on the current run is a NEW posting and gets a badge. Never cleared
    by --clear-cache (unless the user explicitly asks for `seen`)."""
    return _load_set(SEEN_DB)


def save_seen(seen):
    _save_set(SEEN_DB, seen)


def load_to_apply():   return _load_set(TO_APPLY_DB)
def save_to_apply(s):  _save_set(TO_APPLY_DB, s)


def load_history():    return _load_set(HISTORY_DB)
def save_history(s):   _save_set(HISTORY_DB, s)


def load_applied():
    """Load applied jobs as {url: {ts}} dict. Backwards-compatible with the
    old set-of-URLs format: any legacy list gets migrated on read using
    today's date as the fallback timestamp."""
    try:
        with open(APPLIED_DB, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if isinstance(data, list):
        today = time.strftime("%Y-%m-%d %H:%M:%S")
        return {u: {"ts": today} for u in data}
    if isinstance(data, dict):
        # Filter out non-dict values just in case.
        return {u: (v if isinstance(v, dict) else {"ts": time.strftime("%Y-%m-%d %H:%M:%S")}) for u, v in data.items()}
    return {}


def save_applied(d):
    """Persist applied dict `{url: {ts}}` sorted by URL for stable diffs."""
    ordered = dict(sorted(d.items()))
    with open(APPLIED_DB, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2)


def load_app_rejected():
    """{url: {reason, feedback, ts}} — company rejected my application.
    Persistent, keyed by URL. Separate from `rejected.json` (user hides posting)."""
    try:
        with open(APP_REJECTED_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_app_rejected(d):
    with open(APP_REJECTED_DB, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def load_job_index():
    """Persistent {url: {title, locations, source}} map. Every job we fetch
    is remembered here so that liked/to_apply/applied URLs which vanish from
    a source board can still be rendered as "orphans" in their section."""
    try:
        with open(JOB_INDEX_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_job_index(idx):
    with open(JOB_INDEX_DB, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2)


_UNSAFE_RE = re.compile(r"<(script|iframe|object|embed|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_EVENT_RE = re.compile(r'\son[a-z]+\s*=\s*"[^"]*"', re.IGNORECASE)
# Boilerplate footer sections — kill the heading and everything after it.
_BOILERPLATE_MARKERS = [
    r"About\s+[A-Z][A-Za-z0-9.&]{1,50}",
    r"How\s+we[\u2019']?re\s+different",
    r"Come\s+work\s+with\s+us!?",
    r"Who\s+are\s+we[?!]?",
    r"How\s+and\s+Where\s+We\s+Work:?",
]
_MARKER_RE = re.compile(
    "|".join(f"(?:{m})" for m in _BOILERPLATE_MARKERS), re.IGNORECASE
)
_BLOCK_OPEN_RE = re.compile(
    r"<(?:h[1-6]|p|div|section|hr|ul|ol|blockquote|article)\b[^>]*>",
    re.IGNORECASE,
)


def _strip_boilerplate(s):
    # Find the LAST occurrence — first occurrence may be a genuine "About X"
    # intro paragraph that opens some job descriptions (e.g. OpenAI).
    last = None
    for m in _MARKER_RE.finditer(s):
        last = m
    if last is None:
        return s
    # Only trim if the marker sits in the latter half of the document;
    # otherwise it's probably intro content, not a footer.
    if last.start() < len(s) * 0.4:
        return s
    prefix = s[: last.start()]
    opens = list(_BLOCK_OPEN_RE.finditer(prefix))
    cut = opens[-1].start() if opens else last.start()
    return s[:cut]


def sanitize_html(s):
    if not s:
        return ""
    s = _UNSAFE_RE.sub("", s)
    s = _EVENT_RE.sub("", s)
    s = _strip_boilerplate(s)
    return s


def highlight_title(text):
    # Decode any HTML entities already present (Greenhouse and some Ashby
    # boards double-escape "&" as "&amp;") before re-escaping cleanly.
    escaped = html.escape(html.unescape(text))
    if not HIGHLIGHTS:
        return escaped
    pattern = "|".join(re.escape(w) for w in HIGHLIGHTS)
    return re.sub(rf"\b({pattern})\b", r"<mark>\1</mark>", escaped, flags=re.IGNORECASE)


def detect_seniority(title):
    padded = f" {title} "
    lower = padded.lower()
    for needle, label in SENIORITY:
        if needle.lower() in lower:
            return label
    return None


# Internal level bands companies use in their compensation tables. We match the
# common shapes: IC5, L5, E6, M2, "Level 5", "Staff (IC5)", "Principal (IC6)".
# Anchored on word boundaries so we don't match parts of unrelated tokens.
_IC_LEVEL_RE = re.compile(
    r"\b("
    r"IC[3-9]|IC1[0-2]|"          # IC3..IC12 (OpenAI, Anthropic use IC5..IC7)
    r"L[3-9]|L1[0-2]|"            # L3..L12 (Google, Meta E-track etc.)
    r"E[3-9]|E1[0-2]|"            # E3..E12 (Meta engineering track)
    r"M[1-6]|"                    # M1..M6 (management tracks)
    r"Level\s?[3-9]|Level\s?1[0-2]"
    r")\b",
    re.IGNORECASE,
)


def detect_ic_level(*sources):
    """Return an uppercased IC/L/E/M level ('IC5', 'L6', ...) if any source
    string mentions one. Sources are searched in order; first hit wins."""
    for s in sources:
        if not s:
            continue
        m = _IC_LEVEL_RE.search(s)
        if m:
            return re.sub(r"\s+", "", m.group(1).upper())
    return None


def is_spontaneous(job):
    title = (job.get("title") or "").lower()
    return any(pat in title for pat in SPONTANEOUS_PATTERNS)


def normalize_ashby(raw):
    out = []
    for j in raw.get("jobs", []):
        locs = []
        primary = j.get("location")
        if primary:
            locs.append(primary)
        for sec in j.get("secondaryLocations") or []:
            loc = sec.get("location") if isinstance(sec, dict) else sec
            if loc and loc not in locs:
                locs.append(loc)
        desc_html = j.get("descriptionHtml") or ""
        desc_plain = j.get("descriptionPlain") or re.sub(r"<[^>]+>", " ", desc_html)
        description = desc_html or desc_plain
        # Ashby ships the salary in a sidebar field (?includeCompensation=true).
        # Append it to the description so the scoring LLM sees it — OpenAI and
        # a few others only surface pay via that field, never in the HTML body.
        comp = j.get("compensation") or {}
        comp_summary = (
            comp.get("compensationTierSummary")
            or comp.get("summary")
            or ""
        )
        if comp_summary:
            description = f"{description}\n<p><strong>Compensation:</strong> {html.escape(comp_summary)}</p>"
        out.append({
            "title": j.get("title", ""),
            "locations": locs,
            "url": j.get("jobUrl") or j.get("applyUrl") or "",
            "description": description,
            "blob": " ".join([j.get("title", ""), j.get("department", ""), j.get("team", "")]),
        })
    return out


def normalize_workable(raw, account_slug=""):
    out = []
    for j in raw.get("results", []):
        loc = j.get("location") or {}
        if not isinstance(loc, dict):
            loc = {}
        # Some Workable payloads use lists; join them defensively.
        def _flat(v):
            if isinstance(v, list):
                return ", ".join(str(x) for x in v if x)
            return str(v) if v else ""
        city = _flat(loc.get("city"))
        country = _flat(loc.get("country"))
        workplace = _flat(loc.get("workplace") or loc.get("workplace_type"))
        loc_str = ", ".join(x for x in [city, country] if x) or workplace
        dept = j.get("department") or ""
        if isinstance(dept, list):
            dept = ", ".join(str(x) for x in dept)
        shortcode = j.get("shortcode", "")
        # Workable's public apply URL is apply.workable.com/<account>/j/<shortcode>
        # (the /j/ segment is required — the account root alone 404s).
        # The API's j["url"] field is the bare shortcode form which 404s, so
        # always reconstruct when we have both account and shortcode.
        if account_slug and shortcode:
            url = f"https://apply.workable.com/{account_slug}/j/{shortcode}"
        elif shortcode:
            url = f"https://apply.workable.com/j/{shortcode}"
        else:
            url = j.get("url", "")
        out.append({
            "title": _flat(j.get("title")),
            "locations": [loc_str] if loc_str else [],
            "url": url,
            "description": j.get("description", "") or "",
            "blob": " ".join([_flat(j.get("title")), dept]),
        })
    return out


def fetch_eightfold(source):
    """Eightfold.ai careers (used by Netflix via explore.jobs.netflix.net,
    and many Fortune 500s). Config keys:
      - `host`   : the public base URL (e.g. https://explore.jobs.netflix.net)
      - `domain` : the Eightfold `domain` filter (e.g. netflix.com)
    API: GET {host}/api/apply/v2/jobs?domain=<domain>&num=50&start=<offset>
    """
    host = (source.get("host") or "").rstrip("/")
    domain = source.get("domain") or ""
    if not host or not domain:
        err(f"[{source['name']}] Eightfold needs host + domain")
        return {"jobs": [], "spontaneous_url": None}
    out = []
    total_board = None
    offset = 0
    num = 50
    while True:
        api = (
            f"{host}/api/apply/v2/jobs?"
            f"domain={urllib.parse.quote(domain)}&num={num}&start={offset}&sort_by=relevance"
        )
        try:
            req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                page = json.load(resp)
        except Exception as e:
            err(f"[{source['name']}] Eightfold page {offset} failed: {e}")
            break
        positions = page.get("positions") or []
        if total_board is None:
            total_board = page.get("count") or 0
        if not positions:
            break
        for p in positions:
            pid = p.get("id") or p.get("canonical_positionId") or ""
            title = p.get("name") or ""
            loc = p.get("location") or ""
            locs = p.get("locations") if isinstance(p.get("locations"), list) else []
            if loc and loc not in locs:
                locs = [loc] + locs
            team = p.get("team") or ""
            desc = p.get("job_description") or ""
            url_full = f"{host}/careers?pid={pid}&domain={urllib.parse.quote(domain)}&sort_by=relevance" if pid else ""
            out.append({
                "title": title,
                "locations": locs,
                "url": url_full,
                "description": desc,
                "blob": " ".join([title, team]),
            })
        offset += num
        if len(out) >= (total_board or 0):
            break
        if offset >= 1000:
            break   # safety cap
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board or len(out)}


def fetch_lever(source):
    """Lever (jobs.lever.co) — public JSON API. Returns the full posting list.
    Docs: https://github.com/lever/postings-api"""
    slug = source["slug"]
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.load(resp)
    except Exception as e:
        err(f"[{source['name']}] Lever fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    all_jobs = []
    for p in raw if isinstance(raw, list) else []:
        title = p.get("text") or ""
        cat = p.get("categories") or {}
        locs = []
        loc = cat.get("location") or ""
        if loc: locs.append(loc)
        team = cat.get("team") or ""
        desc = p.get("descriptionPlain") or p.get("description") or ""
        all_jobs.append({
            "title": title,
            "locations": locs,
            "url": p.get("hostedUrl") or "",
            "description": desc,
            "blob": " ".join([title, team, cat.get("commitment", "")]),
        })
    matched = [j for j in all_jobs if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(all_jobs),
            "total_board": len(all_jobs)}


def fetch_workable(source):
    slug = source["slug"]
    url = f"https://apply.workable.com/api/v3/accounts/{slug}/jobs"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"query": "", "location": [], "department": [], "workplace": []}).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.load(resp)
    except Exception as e:
        err(f"[{source['name']}] Workable fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    all_jobs = normalize_workable(raw, account_slug=slug)
    matched = [j for j in all_jobs if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(all_jobs),
            "total_board": len(all_jobs)}


def normalize_greenhouse(raw):
    out = []
    for j in raw.get("jobs", []):
        locs = []
        loc = (j.get("location") or {}).get("name")
        if loc:
            locs.append(loc)
        for off in j.get("offices") or []:
            name = off.get("name")
            if name and name not in locs:
                locs.append(name)
        depts = " ".join(d.get("name", "") for d in j.get("departments") or [])
        content = j.get("content") or ""
        content_decoded = html.unescape(content)
        out.append({
            "title": j.get("title", ""),
            "locations": locs,
            "url": j.get("absolute_url", ""),
            "description": content_decoded,
            "blob": " ".join([j.get("title", ""), depts]),
        })
    return out


def matches(job, queries):
    if not queries:
        return True
    blob = job["blob"].lower()
    return any(q.lower() in blob for q in queries)


# =============================================================================
# Runaway guard — stops a per-query paginated scraper from fetching 10
# pages for a word like "engineer" that matches ~every job on the board.
#
# Trigger: a single query has yielded more than RUNAWAY_THRESHOLD matching
# jobs so far.
#
# When invoked from `/refresh` (interactive mode), the fetcher writes a
# `pending.json` signal file and polls for a `decision.json` written by
# the board's modal (POST /refresh-decision). Timeout defaults to "stop"
# so a forgotten tab doesn't pin Playwright forever.
#
# Outside interactive mode (initial make run, sandbox board, debug runs)
# there is no browser to prompt — we hard-stop at the same threshold and
# print a loud log line.
# =============================================================================

# RUNAWAY_THRESHOLD now lives in config.py (default 300) and is
# user-tunable from data/user_config.py and from the ⚙ Settings page.
# We import the module (not the bare name) so a mid-session update to
# config.RUNAWAY_THRESHOLD from /set-settings is picked up by the next
# check_runaway() call — a bare `from config import X` would snapshot
# the old value at import time.
import config as _cfg
RUNAWAY_TIMEOUT_S = 60

# collect() skips the list_cache write when a fresh fetch returned fewer
# than CACHE_MIN_JOBS. Rationale: a partial / failed fetch (Playwright
# flake, incomplete scroll, 403) would otherwise sit in cache for the
# full LIST_CACHE_TTL_HOURS (default 6 h), silently zeroing out that
# source until the TTL expired. See the Zama post-mortem in
# tests/test_collect_cache_queries.py::TestCollectRefusesToCacheEmpty.
# 5 is low enough that small-but-real boards (e.g. Zama's 3 jobs) retry
# cheaply, high enough that a half-scrolled 50-job board doesn't poison.
CACHE_MIN_JOBS = 5

# Flipped on by --interactive-runaway (passed in by /refresh). Module-global
# so fetchers running in the thread pool don't need the flag threaded
# through their signatures.
_interactive_runaway_enabled = False


def _runaway_dir():
    """Lazy-created {DATA_DIR}/.runaway/ where pending + decision files land."""
    path = os.path.join(DATA_DIR, ".runaway")
    os.makedirs(path, exist_ok=True)
    return path


def _runaway_file(source_name, kind):
    """kind ∈ {'pending', 'decision'}. One file per source — a second
    runaway on the same source during the same refresh overwrites the
    first entry, which is fine (user only needs to decide once per
    source for the stop-source semantics)."""
    return os.path.join(_runaway_dir(), f"{slug(source_name)}.{kind}.json")


def _clear_runaway_signals():
    """Wipe stale pending/decision files from a prior refresh. Called
    once per fetch run so the browser isn't shown yesterday's prompt."""
    try:
        d = _runaway_dir()
    except Exception:
        return
    for name in os.listdir(d):
        if name.endswith(".pending.json") or name.endswith(".decision.json"):
            try:
                os.remove(os.path.join(d, name))
            except OSError:
                pass


def check_runaway(source_name, query, pages_so_far, jobs_so_far):
    """Return True if the caller should break out of THIS query's
    pagination loop (stop paginating this one query, then move on to
    the next query in the source), False to keep paginating.

    Call this after each page's results have been accumulated for a
    single query, with `jobs_so_far` = running count of matching jobs
    discovered for this query on THIS source during this fetch.

    Pre-fix, callers used a source-wide flag that also broke the OUTER
    (per-query) loop — meaning a single runaway query (e.g. "security"
    at Apple, which matches thousands) silently skipped every subsequent
    query in the config. Now a runaway hit stops only this query;
    "cryptography" / "Logic" / … still run.
    """
    if jobs_so_far <= _cfg.RUNAWAY_THRESHOLD:
        return False
    if not _interactive_runaway_enabled:
        sys.stdout.write(
            f"[{source_name}] runaway: {jobs_so_far} jobs on query={query!r} "
            f"after {pages_so_far} pages — hard-stopping this source "
            f"(no live dialog; invoke refresh from the board to decide).\n"
        )
        return True
    pending = _runaway_file(source_name, "pending")
    decision = _runaway_file(source_name, "decision")
    try:
        with open(pending, "w", encoding="utf-8") as f:
            json.dump({
                "source": source_name,
                "query": query,
                "pages": pages_so_far,
                "jobs": jobs_so_far,
                "at": time.time(),
            }, f)
    except Exception as e:
        err(f"[{source_name}] runaway: pending write failed: {e}")
        return True
    sys.stdout.write(
        f"[{source_name}] runaway: {jobs_so_far} jobs on query={query!r} "
        f"— waiting up to {RUNAWAY_TIMEOUT_S}s for user decision.\n"
    )
    deadline = time.time() + RUNAWAY_TIMEOUT_S
    action = "stop"  # safe default on timeout
    while time.time() < deadline:
        if os.path.exists(decision):
            try:
                with open(decision, encoding="utf-8") as f:
                    data = json.load(f)
                a = (data or {}).get("action")
                if a in ("stop", "continue"):
                    action = a
                    break
            except Exception:
                pass  # malformed file — keep polling until timeout
        time.sleep(0.3)
    for p in (pending, decision):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    sys.stdout.write(f"[{source_name}] runaway: decision={action}\n")
    return action == "stop"


def _pick_spontaneous(all_jobs):
    for j in all_jobs:
        if is_spontaneous(j):
            return j.get("url") or None
    return None


def fetch_ashby(source):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{source['slug']}?includeCompensation=true"
    try:
        raw = http_get_json(url)
    except Exception as e:
        err(f"[{source['name']}] Ashby fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    all_jobs = normalize_ashby(raw)
    # Cursor kept Ashby as their ATS but their public job pages live at
    # cursor.com/careers/<title-slug>. Verified via a real page:
    #   "Software Engineer, Security" → cursor.com/careers/software-engineer-security
    #   "Account Executive, Commercial (Singapore)" → account-executive-commercial-singapore
    # We slugify the title (lowercase, non-alphanumeric → "-", collapse doubles).
    if source["slug"] == "cursor":
        for j in all_jobs:
            title = j.get("title") or ""
            slug_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            if slug_title:
                j["url"] = f"https://cursor.com/careers/{slug_title}"
    matched = [j for j in all_jobs if matches(j, source["queries"])]
    if not matched and all_jobs:
        sys.stdout.write(
            f"[{source['name']}] Ashby returned {len(all_jobs)} jobs but 0 matched "
            f"queries {source['queries']!r}. Set queries=[] to see them all.\n"
        )
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(all_jobs),
            "total_board": len(all_jobs)}


def fetch_greenhouse(source):
    url = f"https://boards-api.greenhouse.io/v1/boards/{source['slug']}/jobs?content=true"
    try:
        raw = http_get_json(url)
    except Exception as e:
        err(f"{source['name']} fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    all_jobs = normalize_greenhouse(raw)
    return {
        "jobs": [j for j in all_jobs if matches(j, source["queries"])],
        "spontaneous_url": _pick_spontaneous(all_jobs),
        "total_board": len(all_jobs),
    }


_APPLE_JOB_RE = re.compile(r'/en-us/details/(\d[\d-]*)/([a-z0-9-]+)', re.IGNORECASE)
_APPLE_STATE_RE = re.compile(
    r'window\.(?:APP_STATE|__INITIAL_STATE__|__DATA__)\s*=\s*(\{.*?\});',
    re.DOTALL,
)
_NEXT_DATA_RE = re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def _walk_for_key(obj, key):
    """DFS a nested dict/list looking for the first value under `key` that is a list."""
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], list):
            return obj[key]
        for v in obj.values():
            r = _walk_for_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _walk_for_key(v, key)
            if r is not None:
                return r
    return None


def _apple_extract_from_json(text):
    blob = None
    m = _NEXT_DATA_RE.search(text)
    if m:
        try:
            blob = json.loads(m.group(1))
        except Exception:
            blob = None
    if blob is None:
        m2 = _APPLE_STATE_RE.search(text)
        if m2:
            try:
                blob = json.loads(m2.group(1))
            except Exception:
                blob = None
    if blob is None:
        return []
    data = blob
    results = _walk_for_key(data, "searchResults") or _walk_for_key(data, "jobs") or []
    out = []
    for r in results:
        if not isinstance(r, dict):
            continue
        pos_id = r.get("positionId") or r.get("id") or ""
        title = r.get("postingTitle") or r.get("title") or ""
        locs = []
        loc_field = r.get("locations") or r.get("postLocation") or []
        if isinstance(loc_field, list):
            for l in loc_field:
                n = l.get("name") if isinstance(l, dict) else str(l)
                if n and n not in locs:
                    locs.append(n)
        team = r.get("team") or {}
        team_name = team.get("teamName") if isinstance(team, dict) else ""
        out.append({
            "title": title,
            "locations": locs,
            "url": f"https://jobs.apple.com/en-us/details/{pos_id}" if pos_id else "",
            "description": r.get("jobSummary") or r.get("description") or "",
            "blob": " ".join(filter(None, [title, team_name])),
        })
    return out


def _apple_extract_from_links(text, queries=None):
    out = []
    seen = set()
    for jid, sl in _APPLE_JOB_RE.findall(text):
        if not sl or jid in seen:
            continue
        seen.add(jid)
        title = _title_from_slug(sl)
        out.append({
            "title": title,
            "locations": [],
            "url": f"https://jobs.apple.com/en-us/details/{jid}/{sl}",
            "description": "",
            "blob": title,
        })
    return out


def _close_shared_browser():
    """No-op kept for backwards compatibility with callers that still invoke
    it after fetch. The current design starts a fresh Playwright per fetcher,
    which each fetcher closes in its own finally block."""
    pass


def _open_browser():
    """Start a fresh Playwright + Chromium + page. Each fetcher call gets its
    own instance, tied to the current thread's greenlet. Callers MUST call
    `browser.close(); p.stop()` in their finally block.

    Rationale: Playwright's sync API binds the browser to the greenlet that
    launched it, so a shared browser cannot be used by another thread — that
    triggers "Cannot switch to a different thread" crashes when running under
    ThreadPoolExecutor. Starting per-fetcher costs ~1-2s of Chromium boot per
    source but keeps every Playwright source parallelizable, which is a
    massive net win over sequential execution."""
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    page = ctx.new_page()
    return p, browser, page


def _fetch_description_via_page(page, url):
    """Navigate to a job posting and return the main content as HTML."""
    if not url:
        return ""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except Exception:
        return ""
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    try:
        return page.evaluate(
            "() => { const m = document.querySelector("
            "'main, article, [role=\"main\"], .job-description, "
            ".jd-description, .job-details, .job-detail'); "
            "return m ? m.innerHTML : document.body.innerHTML; }"
        ) or ""
    except Exception:
        return ""


_desc_cache_lock = threading.Lock()


def _load_desc_cache():
    try:
        with open(DESC_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_desc_cache_merge(new_entries):
    """Reload the on-disk cache, merge in-memory additions, save atomically.
    Guarded by a lock so parallel Playwright fetchers don't clobber each other."""
    with _desc_cache_lock:
        merged = _load_desc_cache()
        merged.update(new_entries)
        try:
            with open(DESC_CACHE, "w", encoding="utf-8") as f:
                json.dump(merged, f)
        except Exception:
            pass


def _fetch_descriptions(page, jobs, source_name):
    n = len(jobs)
    if not n:
        return
    with _desc_cache_lock:
        cache = _load_desc_cache()
    new_entries = {}
    fetched = 0
    for i, j in enumerate(jobs, 1):
        url = j.get("url") or ""
        if url in cache:
            j["description"] = cache[url]
        else:
            j["description"] = _fetch_description_via_page(page, url)
            if url:
                new_entries[url] = j["description"]
            fetched += 1
        if i % 10 == 0 or i == n:
            line = f"[{source_name}] {i}/{n} ({fetched} fetched, {i - fetched} cached)"
            miss_ratio = fetched / max(1, i)
            # Only warn when the source is substantive (≥5 jobs) — small
            # sources will almost always start at 100% miss.
            if i >= 5 and miss_ratio >= 0.8:
                warn(f"{line}  ← high cache miss ({miss_ratio:.0%})")
            else:
                sys.stdout.write(line + "\n")
            # Incremental save so a Ctrl-C mid-source doesn't lose everything.
            if new_entries:
                _save_desc_cache_merge(new_entries)
                new_entries = {}
    if new_entries:
        _save_desc_cache_merge(new_entries)


_DEBUG_DIR = "debug"


def _ensure_debug_dir():
    try:
        os.makedirs(_DEBUG_DIR, exist_ok=True)
    except OSError:
        pass


def _render(page, url, wait_selector=None, timeout=15000, debug_path=None):
    if debug_path:
        _ensure_debug_dir()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception as e:
        err(f"[render] {url} nav failed: {e}")
    selector_ok = False
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=8000)
            selector_ok = True
        except Exception:
            pass
    if not selector_ok:
        # Give React SPAs (Greenhouse job-boards, Workday, etc.) time to fetch
        # their initial data before we read the DOM.
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
    try:
        content = page.content()
    except Exception as e:
        err(f"[render] content read failed: {e}")
        return ""
    if debug_path:
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass
    return content


def _scroll_until_stable(page, max_scrolls=25, settle_ms=700, debug_name=""):
    """Drive an infinite-scroll SPA to the bottom until it stops growing.

    Pattern: `scrollTo(bottom)` → wait a beat → compare `scrollHeight` before
    and after → if unchanged twice in a row, we're done. Cheaper than
    `networkidle` (analytics beacons keep that alive forever on some pages)
    and more reliable than a fixed `sleep`.

    Opt in per source via `"scroll": True` on the catalog entry. Default off
    so small static boards (Zama, Fhenix) don't pay a 10-20 s tax.
    """
    try:
        prev_h = page.evaluate("document.documentElement.scrollHeight")
    except Exception:
        return 0
    stable = 0
    scrolls = 0
    for _ in range(max_scrolls):
        try:
            page.evaluate(
                "window.scrollTo(0, document.documentElement.scrollHeight)"
            )
        except Exception:
            break
        scrolls += 1
        try:
            page.wait_for_timeout(settle_ms)
        except Exception:
            pass
        try:
            new_h = page.evaluate("document.documentElement.scrollHeight")
        except Exception:
            break
        if new_h <= prev_h:
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
            prev_h = new_h
    if debug_name:
        sys.stdout.write(
            f"[{debug_name}] scroll: {scrolls} iterations, "
            f"final height ~{prev_h}px\n"
        )
    return scrolls


_APPLE_RESULT_COUNT_RE = re.compile(
    r'id="search-result-count"[^>]*>\s*([0-9,]+)\+?\s*Result',
    re.IGNORECASE,
)


def fetch_apple(source):
    if not HAS_PLAYWRIGHT:
        sys.stdout.write(
            "[Apple] Playwright not installed. Run:\n"
            "  pip install playwright && playwright install chromium\n"
        )
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    total_board = None
    p, browser, page = _open_browser()
    try:
        for q in source["queries"]:
            q_jobs = 0  # matches discovered for this specific query so far
            for pnum in range(1, 11):
                url = (
                    f"https://jobs.apple.com/en-us/search?"
                    f"search={urllib.parse.quote(q)}&page={pnum}&sort=newest"
                )
                debug = f"debug/debug-apple-{q}-{pnum}.html" if pnum == 1 else None
                text = _render(page, url, wait_selector="a[href*='/details/']", debug_path=debug)
                from_json = _apple_extract_from_json(text)
                from_links = _apple_extract_from_links(text, source["queries"])
                jobs = from_json or from_links
                if pnum == 1:
                    sys.stdout.write(
                        f"[Apple] q='{q}' rendered {len(text)}B, "
                        f"json={len(from_json)}, links={len(from_links)} "
                        f"(HTML dumped to {debug})\n"
                    )
                    # Apple's search page shows "600+ Result(s)" — the board
                    # global open-position count, independent of the query.
                    # Grab it from any of our per-query fetches.
                    if total_board is None:
                        m = _APPLE_RESULT_COUNT_RE.search(text)
                        if m:
                            total_board = int(m.group(1).replace(",", ""))
                if not jobs:
                    break
                added = 0
                for j in jobs:
                    if not j["url"] or j["url"] in seen:
                        continue
                    seen.add(j["url"])
                    out.append(j)
                    added += 1
                q_jobs += added
                if added == 0:
                    break
                if check_runaway("Apple", q, pnum, q_jobs):
                    break  # per-query: stop this query's pagination,
                           # fall through to the next query in the outer loop.
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, "Apple")
    finally:
        browser.close()
        p.stop()
    return {
        "jobs": filtered,
        "spontaneous_url": _pick_spontaneous(out),
        "total_board": total_board,
    }


_LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL)
_GOOGLE_JOB_RE = re.compile(r'jobs/results/(\d+)-([a-z0-9-]+)', re.IGNORECASE)


def _google_extract_from_ld(text):
    out = []
    for m in _LD_RE.finditer(text):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict) or it.get("@type") != "JobPosting":
                continue
            title = it.get("title", "")
            locs = []
            loc_field = it.get("jobLocation")
            loc_list = loc_field if isinstance(loc_field, list) else ([loc_field] if loc_field else [])
            for l in loc_list:
                if not isinstance(l, dict):
                    continue
                addr = l.get("address") or {}
                city = addr.get("addressLocality") or ""
                region = addr.get("addressRegion") or ""
                country = addr.get("addressCountry") or ""
                parts = [x for x in [city, region, country] if x]
                n = ", ".join(parts)
                if n and n not in locs:
                    locs.append(n)
            out.append({
                "title": title,
                "locations": locs,
                "url": it.get("url") or "",
                "description": it.get("description") or "",
                "blob": title,
            })
    return out


_GOOGLE_TOTAL_RE = re.compile(r'class="SWhIm">\s*([0-9,]+)\s*</span>')


def fetch_google(source):
    if not HAS_PLAYWRIGHT:
        sys.stdout.write(
            "[Google] Playwright not installed. Run:\n"
            "  pip install playwright && playwright install chromium\n"
        )
        return {"jobs": [], "spontaneous_url": None}
    base = source.get("search_url") or "https://www.google.com/about/careers/applications/jobs/results/?hl=en_US"
    out, seen = [], set()
    total_board = None
    p, browser, page = _open_browser()
    try:
        # One extra query-less fetch to grab the full board total. Google's
        # careers SPA renders "N jobs matched" in <span class="SWhIm">.
        try:
            text = _render(page, base, wait_selector="span.SWhIm", debug_path="debug/debug-google-total.html")
            m = _GOOGLE_TOTAL_RE.search(text)
            if m:
                total_board = int(m.group(1).replace(",", ""))
                sys.stdout.write(f"[Google] board total = {total_board}\n")
        except Exception as e:
            err(f"[Google] board-total fetch failed: {e}")
        queries = source.get("queries") or [""]
        for q in queries:
            for pnum in range(1, 2):     # 1 page only — Google's SPA shows all matches page 1
                url = base
                if q:
                    sep = "&" if "?" in url else "?"
                    url += f"{sep}q={urllib.parse.quote(q)}"
                sep = "&" if "?" in url else "?"
                url += f"{sep}page={pnum}"
                debug = f"debug/debug-google-{q or 'nofilter'}-{pnum}.html" if pnum == 1 else None
                text = _render(page, url, wait_selector="a[href*='/jobs/results/']", debug_path=debug)
                ld = _google_extract_from_ld(text)
                urls = set(_GOOGLE_JOB_RE.findall(text))
                if pnum == 1:
                    sys.stdout.write(
                        f"[Google] q='{q}' rendered {len(text)}B, "
                        f"ld={len(ld)}, urls={len(urls)} "
                        f"(HTML dumped to {debug})\n"
                    )
                    # Fast exit: if page 1 already has 0 hits, don't try page 2+.
                    if not ld and not urls:
                        break
                jobs = ld
                if not jobs:
                    for jid, sl in urls:
                        if not sl:
                            continue
                        title = _title_from_slug(sl)
                        jobs.append({
                            "title": title,
                            "locations": [],
                            "url": f"https://www.google.com/about/careers/applications/jobs/results/{jid}-{sl}",
                            "description": "",
                            "blob": title,
                        })
                if not jobs:
                    break
                added = 0
                for j in jobs:
                    if j["url"] in seen:
                        continue
                    seen.add(j["url"])
                    out.append(j)
                    added += 1
                if added == 0:
                    break
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, "Google")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board}


_MICROSOFT_JOB_RE = re.compile(
    r'href="/careers/job/(\d+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

# Phenom-based boards (Microsoft, NVIDIA) render the running total as
# `<h2 aria-level="2">2430 jobs</h2>`. Same regex works on both.
_PHENOM_TOTAL_RE = re.compile(r'>\s*([0-9,]+)\s+jobs\b', re.IGNORECASE)


def _phenom_board_total(page, label, base_url, debug_path):
    """Fetch the query-less board page for a Phenom-hosted careers site and
    extract the "N jobs" summary count. Used for Microsoft and NVIDIA."""
    try:
        text = _render(page, base_url, wait_selector='a[id^="job-card-"]', debug_path=debug_path)
        m = _PHENOM_TOTAL_RE.search(text)
        if m:
            n = int(m.group(1).replace(",", ""))
            sys.stdout.write(f"[{label}] board total = {n}\n")
            return n
    except Exception as e:
        err(f"[{label}] board-total fetch failed: {e}")
    return None


def fetch_microsoft(source):
    if not HAS_PLAYWRIGHT:
        sys.stdout.write(
            "[Microsoft] Playwright not installed. Run:\n"
            "  pip install playwright && playwright install chromium\n"
        )
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    total_board = None
    try:
        total_board = _phenom_board_total(
            page, "Microsoft",
            "https://apply.careers.microsoft.com/careers?start=0&sort_by=relevance",
            "debug/debug-microsoft-total.html",
        )
        for q in source["queries"]:
            q_jobs = 0
            for pnum in range(10):
                start = pnum * 20
                url = (
                    f"https://apply.careers.microsoft.com/careers?"
                    f"query={urllib.parse.quote(q)}&start={start}&sort_by=relevance"
                )
                debug = f"debug/debug-microsoft-{q}-{pnum}.html" if pnum == 0 else None
                text = _render(
                    page, url,
                    wait_selector='a[id^="job-card-"][id$="-job-list"]',
                    debug_path=debug,
                )
                urls = _MICROSOFT_JOB_RE.findall(text)
                if pnum == 0:
                    sys.stdout.write(
                        f"[Microsoft] q='{q}' rendered {len(text)}B, "
                        f"urls={len(urls)} (HTML dumped to {debug})\n"
                    )
                if not urls:
                    break
                added = 0
                for jid, body in urls:
                    if jid in seen:
                        continue
                    text_body = re.sub(r'<[^>]+>', '|', body)
                    parts = [p.strip() for p in text_body.split('|') if p.strip()]
                    title = parts[0] if parts else f"Microsoft job {jid}"
                    location = parts[1] if len(parts) > 1 else ""
                    seen.add(jid)
                    out.append({
                        "title": title,
                        "locations": [location] if location else [],
                        "url": f"https://apply.careers.microsoft.com/careers/job/{jid}",
                        "description": "",
                        "blob": title,
                    })
                    added += 1
                q_jobs += added
                if added == 0:
                    break
                if check_runaway("Microsoft", q, pnum + 1, q_jobs):
                    break  # per-query stop (see comment in fetch_apple)
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, "Microsoft")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board}


def _pw_scrape_links(source_name, url, link_re_pattern, origin,
                     wait_selector="a", scroll=False):
    """Render `url` with Playwright, then extract hrefs matching `link_re_pattern`.
    Titles are derived from the last URL segment. Returns list of job dicts.

    When `scroll=True`, drives infinite-scroll pagination to the bottom
    after the initial render — needed for GM / DoorDash / Shopify style
    boards whose first paint only shows the first 10-25 postings.
    """
    if not HAS_PLAYWRIGHT:
        err(f"[{source_name}] Playwright not installed")
        return []
    debug = f"debug/debug-{slug(source_name)}-1.html"
    p, browser, page = _open_browser()
    try:
        text = _render(page, url, wait_selector=wait_selector, debug_path=debug)
        if scroll:
            _scroll_until_stable(page, debug_name=source_name)
            # Re-read + re-dump after scroll so our debug file reflects the
            # full list, not just the first paint.
            try:
                text = page.content()
            except Exception:
                pass
            try:
                _ensure_debug_dir()
                with open(debug, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass
    finally:
        browser.close()
        p.stop()
    sys.stdout.write(f"[{source_name}] rendered {len(text)}B (dumped {debug})\n")
    link_re = re.compile(link_re_pattern, re.IGNORECASE)
    uuid_tail = re.compile(
        r"([-_][A-Fa-f0-9]{8}[-_][A-Fa-f0-9]{4}[-_][A-Fa-f0-9]{4}[-_][A-Fa-f0-9]{4}[-_][A-Fa-f0-9]{12})/?$",
        re.IGNORECASE,
    )
    out, seen = [], set()
    for m in link_re.finditer(text):
        path = m.group(1)
        if path in seen:
            continue
        seen.add(path)
        tail = uuid_tail.sub("", path.rstrip("/")).rsplit("/", 1)[-1]
        title = _title_from_slug(tail)
        full = path if path.startswith("http") else origin + path
        out.append({
            "title": title,
            "locations": [],
            "url": full,
            "description": "",
            "blob": title,
        })
    return out


def fetch_ableton(source):
    if not HAS_PLAYWRIGHT:
        err("[Ableton] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    url = source.get("search_url") or "https://www.ableton.com/en/jobs/"
    debug = "debug/debug-ableton-1.html"
    p, browser, page = _open_browser()
    try:
        text = _render(page, url, wait_selector="a[href*='/jobs/apply/']", debug_path=debug)
    finally:
        browser.close()
        p.stop()
    sys.stdout.write(f"[Ableton] rendered {len(text)}B (dumped {debug})\n")
    pattern = re.compile(
        r'<a[^>]+href="(/[a-z]{2}/jobs/apply/\d+/?)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    out, seen = [], set()
    for path, body in pattern.findall(text):
        if path in seen:
            continue
        seen.add(path)
        # strip inner tags to get the title text
        title = re.sub(r"<[^>]+>", " ", body)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            title = "Ableton job"
        out.append({
            "title": title,
            "locations": [],
            "url": f"https://www.ableton.com{path}",
            "description": "",
            "blob": title,
        })
    return {"jobs": out, "spontaneous_url": _pick_spontaneous(out)}


def fetch_pixee(source):
    """Pixee careers (hosted on Dover) — anchor body has title + location."""
    if not HAS_PLAYWRIGHT:
        err("[Pixee] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        url = source.get("search_url") or "https://app.dover.com/jobs/pixee"
        debug = "debug/debug-pixee-1.html"
        text = _render(page, url, wait_selector='a[href*="/apply/Pixee/"]', debug_path=debug)
        pattern = re.compile(
            r'<a[^>]+href="(/apply/Pixee/[a-f0-9-]{20,}[^"]*)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for path, body in pattern.findall(text):
            uuid_match = re.search(r'([a-f0-9-]{20,})', path)
            if not uuid_match:
                continue
            uuid = uuid_match.group(1)
            if uuid in seen:
                continue
            text_body = re.sub(r'<[^>]+>', '|', body)
            parts = [p.strip() for p in text_body.split('|') if p.strip()]
            parts = [p for p in parts if p.lower() not in ('apply', 'apply now', 'read more')]
            if not parts:
                continue
            seen.add(uuid)
            title = parts[0]
            location = parts[1] if len(parts) > 1 else ""
            out.append({
                "title": title,
                "locations": [location] if location else [],
                "url": f"https://app.dover.com{path}",
                "description": "",
                "blob": " ".join(filter(None, [title, location])),
            })
        sys.stdout.write(f"[Pixee] rendered {len(text)}B, jobs={len(out)}\n")
        filtered = [j for j in out if matches(j, source.get("queries") or [])]
        _fetch_descriptions(page, filtered, "Pixee")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


def fetch_lucca(source):
    slug_seg = source["slug"]
    jobs = _pw_scrape_links(
        source["name"],
        source.get("search_url") or f"https://jobs.world.luccasoftware.com/{slug_seg}",
        rf'href="(/{re.escape(slug_seg)}/[^"#?]+)"',
        origin="https://jobs.world.luccasoftware.com",
    )
    return {"jobs": jobs, "spontaneous_url": _pick_spontaneous(jobs)}


_CISCO_JOB_CARD_RE = re.compile(
    # Pull title + href from attributes on the <a id="job-link"> tag directly.
    # Attribute order on Cisco's rendered DOM is stable: data-ph-at-job-title-text
    # comes BEFORE href. Grabbing from attributes (not the anchor body) avoids
    # noise when the title contains inline chips like "<span>12+ Years</span>",
    # which previously got mis-parsed as the job location.
    r'<a[^>]+id="job-link"[^>]+data-ph-at-job-title-text="([^"]+)"[^>]+href="(?:https?://[^"/]+)?(/global/en/job/\d+/[^"#?]+)"',
    re.IGNORECASE | re.DOTALL,
)


def fetch_cisco(source):
    """Cisco careers portal (careers.cisco.com/global/en). Phenom-powered but
    uses a different URL / pagination shape than the generic fetch_phenom.
    - Job URL: /global/en/job/<id>/<slug>
    - Pagination: ?from=0, 10, 20, ... (NOT ?start=)
    - Job anchor id: "job-link" (not "job-card-N-job-list")
    Scrapes each category page under /c/<category-jobs> and dedupes."""
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    origin = "https://careers.cisco.com"
    # Base category pages — covers the whole board.
    categories = source.get("categories") or [
        "/global/en/c/product-and-engineering-jobs",
    ]
    out, seen = [], set()
    max_pages = int(source.get("max_pages") or 20)   # 20 pages × 10 jobs = 200 jobs/cat
    p, browser, page = _open_browser()
    try:
        for cat in categories:
            cat_url = f"{origin}{cat}"
            for pnum in range(max_pages):
                from_offset = pnum * 10
                page_url = f"{cat_url}?from={from_offset}&s=1"
                debug = f"debug/debug-cisco-{slug(cat.rsplit('/',1)[-1])}-{pnum}.html" if pnum < 2 else None
                try:
                    text = _render(
                        page, page_url,
                        wait_selector='a[id="job-link"]',
                        debug_path=debug,
                    )
                except Exception as e:
                    err(f"[Cisco] page {pnum} ({page_url}) failed: {e}")
                    break
                # NOTE: don't name this variable `matches` — it shadows the
                # top-level matches(job, queries) helper used below for the
                # queries filter, which caused "'list' object is not callable".
                hits = _CISCO_JOB_CARD_RE.findall(text)
                sys.stdout.write(
                    f"[Cisco] cat={cat.rsplit('/',1)[-1]} page {pnum+1}/{max_pages} "
                    f"from={from_offset} matches={len(hits)} total_so_far={len(out)}\n"
                )
                sys.stdout.flush()
                if not hits:
                    break
                added = 0
                for title_attr, path in hits:
                    jid_m = re.search(r"/job/(\d+)/", path)
                    jid = jid_m.group(1) if jid_m else path
                    if jid in seen:
                        continue
                    seen.add(jid)
                    title = html.unescape(title_attr).strip() or f"Cisco job {jid}"
                    out.append({
                        "title": title,
                        "locations": [],
                        "url": origin + path,
                        "description": "",
                        "blob": title,
                    })
                    added += 1
                if added == 0:
                    sys.stdout.write(
                        f"[Cisco] no new jobs on page {pnum+1} — stopping pagination\n"
                    )
                    break
    finally:
        browser.close()
        p.stop()
    sys.stdout.write(f"[Cisco] total unique jobs scraped: {len(out)}\n")
    # Apply per-source queries filter if any (lets the user narrow scope
    # beyond the category URLs). Empty queries → keep everything.
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


_BOSE_JOB_CARD_RE = re.compile(
    # Bose is Phenom-based but uses a different URL layout and attribute order
    # than Cisco: data-ph-at-job-title-text comes BEFORE href, and the href is
    # an ABSOLUTE URL under careers.bose.com/us/en/job/<id>/<slug> where <id>
    # is alphanumeric (e.g. R28789), not pure digits. Grab from attributes so
    # inline chips in the anchor body don't pollute the title.
    r'<a[^>]+id="job-link"[^>]+data-ph-at-job-title-text="([^"]+)"[^>]+'
    r'href="(?:https?://[^"/]+)?(/us/en/job/[A-Za-z0-9]+/[^"#?]+)"',
    re.IGNORECASE | re.DOTALL,
)


def fetch_bose(source):
    """Bose careers portal (careers.bose.com/us/en). Phenom-powered but with
    a different URL layout than Cisco or generic Phenom:
    - Job URL: /us/en/job/<alnum-id>/<slug>  (NOT /careers/job/<digits>)
    - Pagination: ?start=0, 20, 40 (same as generic Phenom)
    - Job anchor id: "job-link"; title in data-ph-at-job-title-text attribute.
    Board is small (~3 jobs as of 2026-10) so one pass per query suffices."""
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    origin = "https://careers.bose.com"
    base = source.get("search_url") or f"{origin}/us/en?query=&sort_by=relevance"
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        # Single pass (no per-query loop): Bose's query= param doesn't filter
        # server-side (verified from debug-bose-*-0.html — all queries returned
        # the same 3 jobs). One fetch of the board page is enough; the queries
        # filter is applied client-side via matches().
        for pnum in range(10):
            start = pnum * 20
            sep = "&" if "?" in base else "?"
            page_url = f"{base}{sep}start={start}"
            debug = f"debug/debug-bose-page-{pnum}.html" if pnum < 2 else None
            try:
                text = _render(
                    page, page_url,
                    wait_selector='a[id="job-link"]',
                    debug_path=debug,
                )
            except Exception as e:
                err(f"[Bose] page {pnum} ({page_url}) failed: {e}")
                break
            hits = _BOSE_JOB_CARD_RE.findall(text)
            sys.stdout.write(
                f"[Bose] page {pnum+1} start={start} matches={len(hits)} "
                f"total_so_far={len(out)}\n"
            )
            sys.stdout.flush()
            if not hits:
                break
            added = 0
            for title_attr, path in hits:
                jid_m = re.search(r"/job/([A-Za-z0-9]+)/", path)
                jid = jid_m.group(1) if jid_m else path
                if jid in seen:
                    continue
                seen.add(jid)
                title = html.unescape(title_attr).strip() or f"Bose job {jid}"
                out.append({
                    "title": title,
                    "locations": [],
                    "url": origin + path,
                    "description": "",
                    "blob": title,
                })
                added += 1
            if added == 0:
                break
    finally:
        browser.close()
        p.stop()
    sys.stdout.write(f"[Bose] total unique jobs scraped: {len(out)}\n")
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


_LINKEDIN_CARD_RE = re.compile(
    # One job card = a div with both base-card and job-search-card classes,
    # carrying data-entity-urn="urn:li:jobPosting:<id>". We grab the card body
    # (up to the next card or the closing <ul>) so title/loc/link regexes
    # below only match within a single card.
    r'<div[^>]*class="[^"]*base-card[^"]*job-search-card[^"]*"[^>]*'
    r'data-entity-urn="urn:li:jobPosting:(\d+)"[^>]*>'
    r'(.*?)'
    r'(?=<div[^>]*class="[^"]*base-card[^"]*job-search-card[^"]*"|</ul>)',
    re.DOTALL | re.IGNORECASE,
)
_LINKEDIN_LINK_RE  = re.compile(r'<a[^>]+class="[^"]*base-card__full-link[^"]*"[^>]+href="([^"]+)"', re.IGNORECASE)
_LINKEDIN_TITLE_RE = re.compile(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h3>', re.DOTALL | re.IGNORECASE)
_LINKEDIN_LOC_RE   = re.compile(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span>', re.DOTALL | re.IGNORECASE)


def _linkedin_clean(s):
    """Strip inner tags + collapse whitespace + unescape entities."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def fetch_linkedin(source):
    """LinkedIn company jobs via the PUBLIC /jobs/search/ page (no login).

    - /jobs/search-results/ (logged-in UI) hits a login wall; /jobs/search/
      is the guest-facing variant that renders job cards server-side.
    - LinkedIn caps the page at ~60 cards and ignores &start=N for pagination
      (verified empirically — 3 probe pages at start=0/60/120 returned the
      exact same 60 URNs). So each URL = one 60-job slice.
    - To widen coverage we accept a LIST of search URLs (`source["urls"]`),
      typically variations of f_TPR / f_SAL / keywords. Each URL yields a
      different top-60 slice; we union them and dedupe by job URN.
      Example: strict (last 7d, salary bands) + medium (last 30d) + loose
      (no filter) → ~110 unique jobs out of the 200 total LinkedIn posts."""
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    urls = source.get("urls") or ([source["search_url"]] if source.get("search_url") else [])
    if not urls:
        err(f"[{source['name']}] no urls configured")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        for i, url in enumerate(urls):
            try:
                text = _render(
                    page, url,
                    wait_selector='div.base-card.job-search-card',
                    timeout=20000,
                    debug_path=f"debug/debug-linkedin-{i}.html" if i < 3 else None,
                )
            except Exception as e:
                err(f"[LinkedIn] url#{i} failed: {e}")
                continue
            cards = _LINKEDIN_CARD_RE.findall(text)
            added = 0
            for jid, body in cards:
                if jid in seen:
                    continue
                seen.add(jid)
                link_m = _LINKEDIN_LINK_RE.search(body)
                title_m = _LINKEDIN_TITLE_RE.search(body)
                loc_m = _LINKEDIN_LOC_RE.search(body)
                if not link_m or not title_m:
                    continue
                title = _linkedin_clean(title_m.group(1)) or f"LinkedIn job {jid}"
                loc = _linkedin_clean(loc_m.group(1)) if loc_m else ""
                # Drop LinkedIn's query-string noise (tracking tokens, pageNum).
                url_clean = link_m.group(1).split("?")[0]
                out.append({
                    "title": title,
                    "locations": [loc] if loc else [],
                    "url": url_clean,
                    "description": "",
                    "blob": title,
                })
                added += 1
            sys.stdout.write(
                f"[LinkedIn] url#{i} cards={len(cards)} new={added} total_unique={len(out)}\n"
            )
            sys.stdout.flush()
    finally:
        browser.close()
        p.stop()
    sys.stdout.write(f"[LinkedIn] total unique jobs scraped: {len(out)}\n")
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


_IBM_CARD_RE = re.compile(
    # One IBM card: <div class="bx--card-group__cards__col" role="region" aria-label="TITLE">
    # Carries the full title (incl. special chars) in aria-label. Body contains
    # category / level / location in <div class="bx--card__eyebrow"> and
    # <div class="ibm--card__copy__inner">LEVEL<br>LOCATION</div>.
    r'<div[^>]*class="bx--card-group__cards__col"[^>]*aria-label="([^"]+)"[^>]*>'
    r'(.*?)'
    r'(?=<div[^>]*class="bx--card-group__cards__col"|</div>\s*</div>\s*</div>\s*<script)',
    re.DOTALL | re.IGNORECASE,
)
_IBM_HREF_RE = re.compile(
    r'href="(https?://careers\.ibm\.com/en_US/careers/JobDetail\?jobId=\d+[^"]*)"',
    re.IGNORECASE,
)
_IBM_COPY_RE = re.compile(
    r'<div class="ibm--card__copy__inner">([^<]*(?:<br[^>]*>[^<]*)*)</div>',
    re.IGNORECASE,
)


def fetch_ibm(source):
    """IBM careers (careers.ibm.com) via its Carbon-Design search page.

    The generic fetch_pw_generic derives titles from the URL tail — but IBM's
    URLs end in /JobDetail?jobId=12345, so every title came out as 'Jobdetail'.
    Fix: parse the real cards from the rendered HTML (title in aria-label,
    location in .ibm--card__copy__inner).
    """
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    url = source.get("search_url") or source.get("board") or "https://www.ibm.com/careers/search?q=security"
    p, browser, page = _open_browser()
    try:
        text = _render(page, url, wait_selector='a[href*="JobDetail"]',
                       timeout=20000, debug_path="debug/debug-ibm-1.html")
    finally:
        browser.close()
        p.stop()
    out, seen = [], set()
    for title_raw, body in _IBM_CARD_RE.findall(text):
        href_m = _IBM_HREF_RE.search(body)
        if not href_m:
            continue
        # Clean &amp; and other entities out of the href before dedup.
        url_clean = html.unescape(href_m.group(1))
        if url_clean in seen:
            continue
        seen.add(url_clean)
        title = html.unescape(title_raw).strip()
        loc = ""
        copy_m = _IBM_COPY_RE.search(body)
        if copy_m:
            parts = [html.unescape(p).strip() for p in re.split(r"<br[^>]*>", copy_m.group(1)) if p.strip()]
            # First line is usually the level ("Professional", "Internship"),
            # second is the location — keep the latter.
            if len(parts) >= 2:
                loc = parts[1]
            elif parts:
                loc = parts[0]
        # IBM uses "Multiple Cities" as a catch-all for multi-location jobs.
        # It pollutes the city-picker without being actionable — drop it.
        if loc == "Multiple Cities":
            loc = ""
        out.append({
            "title": title,
            "locations": [loc] if loc else [],
            "url": url_clean,
            "description": "",
            "blob": title,
        })
    sys.stdout.write(f"[IBM] total jobs scraped: {len(out)}\n")
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


def fetch_pw_generic(source):
    """Generic Playwright link scraper. Requires `search_url`, `link_re`,
    `origin`. Pass `"scroll": True` on the catalog entry to drive
    infinite-scroll pagination to the bottom before extracting links."""
    if not source.get("search_url") or not source.get("link_re"):
        err(f"[{source['name']}] missing search_url/link_re")
        return {"jobs": [], "spontaneous_url": None}
    jobs = _pw_scrape_links(
        source["name"],
        source["search_url"],
        source["link_re"],
        source.get("origin") or source["search_url"].rsplit("/", 1)[0],
        wait_selector=source.get("wait_selector", "a"),
        scroll=bool(source.get("scroll", False)),
    )
    return {"jobs": jobs, "spontaneous_url": _pick_spontaneous(jobs)}


def fetch_checkmarx(source):
    """Checkmarx careers page — jobs are in a table with title/dept/location
    in <td> cells and a separate <a> anchor pointing to the position URL."""
    if not HAS_PLAYWRIGHT:
        err("[Checkmarx] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        url = source.get("search_url") or "https://checkmarx.com/company/careers/"
        debug = "debug/debug-checkmarx-1.html"
        text = _render(page, url, wait_selector='a[href*="/job-openings/position/"]', debug_path=debug)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', text, re.IGNORECASE | re.DOTALL)
        for row in rows:
            u = re.search(r'href="(https?://checkmarx\.com/job-openings/position/[^"]+)"', row)
            if not u:
                continue
            job_url = u.group(1)
            if job_url in seen:
                continue
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            texts = []
            for c in cells:
                stripped = re.sub(r'<[^>]+>', ' ', c)
                stripped = re.sub(r'\s+', ' ', stripped).strip()
                if stripped and stripped.lower() not in ('apply now', 'apply'):
                    texts.append(stripped)
            if not texts:
                continue
            seen.add(job_url)
            title = html.unescape(texts[0])
            location = texts[2] if len(texts) >= 3 else (texts[1] if len(texts) >= 2 else "")
            out.append({
                "title": title,
                "locations": [location] if location else [],
                "url": job_url,
                "description": "",
                "blob": " ".join(filter(None, [title, location])),
            })
        sys.stdout.write(f"[Checkmarx] rendered {len(text)}B, jobs={len(out)}\n")
        filtered = [j for j in out if matches(j, source.get("queries") or [])]
        _fetch_descriptions(page, filtered, "Checkmarx")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


_GITHUB_TOTAL_RE = re.compile(
    r'search-results-indicator[^>]*>\s*([0-9,]+)\s+results',
    re.IGNORECASE,
)


def fetch_github(source):
    """GitHub careers page — anchors carry the title as text; the generic
    scraper would use the URL slug instead which loses the title."""
    if not HAS_PLAYWRIGHT:
        err("[GitHub] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    total_board = None
    p, browser, page = _open_browser()
    try:
        # Query-less fetch first to grab the board total; extract N from
        # <h2 id="search-results-indicator">78 results</h2>.
        try:
            base_text = _render(
                page,
                "https://www.github.careers/careers-home/jobs",
                wait_selector='#search-results-indicator',
                debug_path="debug/debug-github-total.html",
            )
            m = _GITHUB_TOTAL_RE.search(base_text)
            if m:
                total_board = int(m.group(1).replace(",", ""))
                sys.stdout.write(f"[GitHub] board total = {total_board}\n")
        except Exception as e:
            err(f"[GitHub] board-total fetch failed: {e}")

        url = source.get("search_url") or "https://www.github.careers/careers-home/jobs"
        debug = "debug/debug-github-1.html"
        text = _render(page, url, wait_selector='a[href*="/careers-home/jobs/"]', debug_path=debug)
        pattern = re.compile(
            r'<a[^>]+href="(/careers-home/jobs/(\d+)[^"]*)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for path, jid, body in pattern.findall(text):
            if jid in seen:
                continue
            text_body = re.sub(r'<[^>]+>', '|', body)
            parts = [p.strip() for p in text_body.split('|') if p.strip()]
            parts = [p for p in parts if p.lower() not in ("read more", "apply", "learn more")]
            if not parts:
                continue
            title = parts[0]
            location = parts[1] if len(parts) > 1 else ""
            seen.add(jid)
            out.append({
                "title": title,
                "locations": [location] if location else [],
                "url": f"https://www.github.careers{path}",
                "description": "",
                "blob": " ".join(filter(None, [title, location])),
            })
        sys.stdout.write(f"[GitHub] rendered {len(text)}B, jobs={len(out)}\n")
        filtered = [j for j in out if matches(j, source.get("queries") or [])]
        _fetch_descriptions(page, filtered, "GitHub")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board}


_SCALE_TOTAL_RE = re.compile(
    r'>\s*([0-9,]{2,7})\s+(?:roles|jobs|positions?|openings?)\b',
    re.IGNORECASE,
)


def fetch_scale(source):
    """Scale AI careers page — job cards have title + location inside the
    anchor body, so we can extract both at once."""
    if not HAS_PLAYWRIGHT:
        err("[Scale AI] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    total_board = None
    p, browser, page = _open_browser()
    try:
        url = source.get("search_url") or "https://scale.com/careers"
        debug = "debug/debug-scale-ai-1.html"
        text = _render(page, url, wait_selector='a[href*="/careers/"]', debug_path=debug)
        m = _SCALE_TOTAL_RE.search(text)
        if m:
            total_board = int(m.group(1).replace(",", ""))
            sys.stdout.write(f"[Scale AI] board total = {total_board}\n")
        pattern = re.compile(
            r'<a[^>]+href="(/careers/(\d+))"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for path, jid, body in pattern.findall(text):
            if jid in seen:
                continue
            seen.add(jid)
            text_body = re.sub(r'<[^>]+>', '|', body)
            parts = [p.strip() for p in text_body.split('|') if p.strip()]
            # Drop the trailing "Apply →" call-to-action if present.
            parts = [p for p in parts if not p.lower().startswith("apply")]
            title = parts[0] if parts else f"Scale AI job {jid}"
            location = parts[1] if len(parts) > 1 else ""
            out.append({
                "title": title,
                "locations": [location] if location else [],
                "url": f"https://scale.com{path}",
                "description": "",
                "blob": " ".join(filter(None, [title, location])),
            })
        sys.stdout.write(f"[Scale AI] rendered {len(text)}B, jobs={len(out)}\n")
        filtered = [j for j in out if matches(j, source.get("queries") or [])]
        _fetch_descriptions(page, filtered, "Scale AI")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board}


_META_JOB_RE = re.compile(r'/profile/job_details/(\d{5,})', re.IGNORECASE)


_META_TOTAL_RE = re.compile(
    r'>\s*([0-9,]{2,7})\s+(?:items|results|jobs|open positions?|roles)\b',
    re.IGNORECASE,
)


_META_LOC_RE = re.compile(r"^[A-Za-zÀ-ÿ.' -]+,\s*[A-Za-zÀ-ÿ. ]+$")
# City-states / cities Meta renders without a trailing ", Country" suffix.
# Add to this set if a legitimate single-token location gets filtered out.
_META_CITY_STATES = {
    "Singapore", "Hong Kong", "Dubai", "Dublin", "Taipei", "Seoul",
    "Zurich", "Tel Aviv", "Luxembourg", "Monaco", "Doha", "Kuwait City",
    "Macau", "Bahrain",
}


def _is_meta_location(s):
    """True if the string looks like a Meta location, False if it's a department
    name leaking into the anchor body ("Machine Learning", "Product Strategy").
    Meta renders locations as 'City, Country' or as a city-state token."""
    if s in _META_CITY_STATES:
        return True
    if not s or s == "⋅":
        return False
    if s.startswith("+") and "more" in s:  # "+21 more" marker
        return False
    if "&" in s:  # dept names like "People & Recruiting", never locations
        return False
    return bool(_META_LOC_RE.match(s))


def fetch_meta(source):
    if not HAS_PLAYWRIGHT:
        err("[Meta] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    total_board = None
    p, browser, page = _open_browser()
    try:
        try:
            base_text = _render(
                page,
                "https://www.metacareers.com/jobsearch/",
                wait_selector="a[href*='/profile/job_details/']",
                debug_path="debug/debug-meta-total.html",
            )
            m = _META_TOTAL_RE.search(base_text)
            if m:
                total_board = int(m.group(1).replace(",", ""))
                sys.stdout.write(f"[Meta] board total = {total_board}\n")
        except Exception as e:
            err(f"[Meta] board-total fetch failed: {e}")

        for q in source["queries"]:
            url = f"https://www.metacareers.com/jobsearch/?q={urllib.parse.quote(q)}"
            debug = f"debug/debug-meta-{q}-1.html"
            text = _render(page, url, wait_selector="a[href*='/profile/job_details/']", debug_path=debug)
            pattern = re.compile(
                r'<a[^>]+href="(/profile/job_details/\d+)"[^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )
            found = 0
            for path_match, body in pattern.findall(text):
                m = _META_JOB_RE.search(path_match)
                if not m:
                    continue
                jid = m.group(1)
                if jid in seen:
                    continue
                seen.add(jid)
                text_body = re.sub(r'<[^>]+>', '|', body)
                parts = [p.strip() for p in text_body.split('|') if p.strip()]
                title = parts[0] if parts else f"Meta job {jid}"
                # Meta's anchor body is: title | loc1 | ⋅ | loc2 | ... | +N more
                # | dept1 | subdept2. Keep only location-looking tokens; stop at
                # the first dept so we don't scoop up "Product Strategy", etc.
                # NOTE: do not name this loop variable `p` — the enclosing
                # scope's `p` is the Playwright instance used in `p.stop()`
                # inside the `finally` block.
                locs = []
                for part in parts[1:]:
                    if _is_meta_location(part):
                        locs.append(part)
                    elif part == "⋅" or (part.startswith("+") and "more" in part):
                        continue  # bullet or "+N more" — skip but keep scanning
                    else:
                        break  # hit a department — locations block is over
                out.append({
                    "title": title,
                    "locations": locs,
                    "url": f"https://www.metacareers.com{path_match}",
                    "description": "",
                    "blob": " ".join([title] + locs),
                })
                found += 1
            sys.stdout.write(f"[Meta] q='{q}' rendered {len(text)}B, jobs={found}\n")
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, "Meta")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board}


_PHENOM_JOB_RE = re.compile(
    r'href="/careers/job/(\d+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def fetch_phenom(source):
    """Generic Phenom People ATS scraper (NVIDIA, and similar)."""
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    # Compute origin (scheme://netloc) from `search_url` via urlparse — the
    # previous `.split("/careers")` heuristic broke on hostnames containing
    # "careers" (e.g. Bose → "https://careers.bose.com/..." split at the
    # first "/careers" match yields origin="https:/" and a bogus URL).
    _su = source.get("search_url", "")
    _pu = urllib.parse.urlparse(_su) if _su else None
    origin = f"{_pu.scheme}://{_pu.netloc}" if _pu and _pu.scheme and _pu.netloc else "https://jobs.example.com"
    total_board = None
    try:
        total_board = _phenom_board_total(
            page, source["name"],
            f"{origin}/careers?start=0&sort_by=relevance",
            f"debug/debug-{slug(source['name'])}-total.html",
        )
        for q in source["queries"]:
            q_jobs = 0
            for pnum in range(10):
                start = pnum * 20
                base = source.get("search_url") or ""
                sep = "&" if "?" in base else "?"
                url = f"{base}{sep}start={start}"
                debug = f"debug/debug-{slug(source['name'])}-{q}-{pnum}.html" if pnum == 0 else None
                text = _render(
                    page, url,
                    wait_selector='a[id^="job-card-"][id$="-job-list"]',
                    debug_path=debug,
                )
                urls = _PHENOM_JOB_RE.findall(text)
                if pnum == 0:
                    sys.stdout.write(
                        f"[{source['name']}] q='{q}' rendered {len(text)}B, urls={len(urls)}\n"
                    )
                if not urls:
                    break
                added = 0
                for jid, body in urls:
                    if jid in seen:
                        continue
                    text_body = re.sub(r'<[^>]+>', '|', body)
                    parts = [p.strip() for p in text_body.split('|') if p.strip()]
                    title = parts[0] if parts else f"{source['name']} job {jid}"
                    location = parts[1] if len(parts) > 1 else ""
                    seen.add(jid)
                    out.append({
                        "title": title,
                        "locations": [location] if location else [],
                        "url": f"{origin}/careers/job/{jid}",
                        "description": "",
                        "blob": title,
                    })
                    added += 1
                q_jobs += added
                if added == 0:
                    break
                if check_runaway(source["name"], q, pnum + 1, q_jobs):
                    break  # per-query stop (see comment in fetch_apple)
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, source["name"])
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board}


# =============================================================================
# NOTE: fetch_wttj (Welcome to the Jungle aggregator) was removed —
# see planning/open/wtj-discovery.md. The aggregator never surfaced
# `/fr/companies/<slug>/jobs/<slug>` URLs in its rendered HTML (jobs
# were fetched client-side after Playwright's networkidle) AND
# CloudFront's WAF blocks headless chromium with a 403. Individual
# WTJ-hosted companies (e.g. Zama's jobs.zama.org — a different
# domain, no WAF) still work fine as kind=pw entries.
# =============================================================================


# =============================================================================
# BambooHR — public careers page embeds jobs in a JSON script tag.
# =============================================================================

_BAMBOOHR_JOB_JSON_RE = re.compile(
    r'<script[^>]*id="jobs-listing-data"[^>]*type="application/json"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
# Fallback: some BambooHR sites embed via window.__PRELOADED_STATE__
_BAMBOOHR_PRELOAD_RE = re.compile(
    r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
    re.IGNORECASE | re.DOTALL,
)


def fetch_bamboohr(source):
    """Fetches jobs from a BambooHR careers page. The visible /careers URL
    embeds a JSON payload of all open jobs. We just parse that.

    Uses Playwright since BambooHR sits behind Cloudflare which blocks
    plain HTTP clients."""
    slug = source["slug"]
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright required")
        return {"jobs": [], "spontaneous_url": None}
    urls_to_try = [
        f"https://{slug}.bamboohr.com/careers",
        f"https://{slug}.bamboohr.com/careers/list",
    ]
    text = ""
    p, browser, page = _open_browser()
    try:
        for u in urls_to_try:
            try:
                text = _render(page, u, wait_selector='a[href*="/careers/"]',
                               debug_path=f"debug/debug-{slug}-bamboo-1.html")
                if text and len(text) > 5000:
                    break
            except Exception:
                continue
    finally:
        browser.close()
        p.stop()
    if not text:
        err(f"[{source['name']}] BambooHR fetch failed: no response")
        return {"jobs": [], "spontaneous_url": None}
    # Try to parse the embedded JSON.
    data = None
    m = _BAMBOOHR_JOB_JSON_RE.search(text)
    if m:
        try:
            data = json.loads(m.group(1))
        except Exception:
            data = None
    if data is None:
        m = _BAMBOOHR_PRELOAD_RE.search(text)
        if m:
            try:
                data = json.loads(m.group(1))
            except Exception:
                data = None
    if data is None:
        # Last resort: BambooHR renders a straightforward HTML table when
        # JS is disabled. Extract anchors like <a href="/careers/123">
        anchors = re.findall(
            r'<a[^>]+href="(/careers/\d+)"[^>]*>([^<]+)</a>',
            text, re.IGNORECASE,
        )
        out = []
        seen = set()
        for path, title in anchors:
            jid = path.rsplit("/", 1)[-1]
            if jid in seen:
                continue
            seen.add(jid)
            out.append({
                "title": html.unescape(title).strip(),
                "locations": [],
                "url": f"https://{slug}.bamboohr.com{path}",
                "description": "",
                "blob": html.unescape(title).strip(),
            })
        matched = [j for j in out if matches(j, source["queries"])]
        return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
                "total_board": len(out)}
    # JSON path: BambooHR's payload is either a list of jobs at the root
    # (list.json) or nested under something like {jobs: [...]} for careers.
    raw_list = data
    if isinstance(data, dict):
        for k in ("openings", "jobs", "results", "data"):
            if k in data and isinstance(data[k], list):
                raw_list = data[k]
                break
    if not isinstance(raw_list, list):
        err(f"[{source['name']}] BambooHR JSON unexpected shape")
        return {"jobs": [], "spontaneous_url": None}
    out = []
    for j in raw_list:
        if not isinstance(j, dict):
            continue
        jid = j.get("id") or j.get("jobOpeningId") or ""
        title = j.get("jobOpeningName") or j.get("title") or j.get("name") or ""
        dept = j.get("departmentLabel") or j.get("department") or ""
        loc_field = j.get("location") or j.get("jobLocation") or {}
        if isinstance(loc_field, dict):
            city = loc_field.get("city") or ""
            state = loc_field.get("state") or ""
            country = loc_field.get("country") or ""
            loc_str = ", ".join(x for x in [city, state, country] if x)
        else:
            loc_str = str(loc_field or "")
        locs = [loc_str] if loc_str else []
        job_url = j.get("jobOpeningShareUrl") or (
            f"https://{slug}.bamboohr.com/careers/{jid}" if jid else ""
        )
        out.append({
            "title": title,
            "locations": locs,
            "url": job_url,
            "description": j.get("description", "") or "",
            "blob": " ".join([title, dept, loc_str]),
        })
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


# =============================================================================
# Pinpoint HQ — <company>.pinpointhq.com. Careers page has jobs in a JSON
# blob (window.pinpointJobsData) and/or renders anchor <a> tags to each job.
# =============================================================================

def fetch_pinpoint(source):
    """Pinpoint HQ scraper. Pattern: <slug>.pinpointhq.com/. Job rows are
    <div class="rt-tr" data-location="..." data-department="...">, and
    each row contains anchors <a href="/en/postings/<uuid>">Title</a>.
    Uses Playwright (Cloudflare blocks direct HTTP)."""
    slug = source["slug"]
    root = f"https://{slug}.pinpointhq.com"
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright required")
        return {"jobs": [], "spontaneous_url": None}
    p, browser, page = _open_browser()
    try:
        text = _render(page, root + "/", wait_selector='a[href*="/postings/"]',
                       debug_path=f"debug/debug-{slug}-pinpoint-1.html")
    except Exception as e:
        err(f"[{source['name']}] Pinpoint fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    finally:
        browser.close()
        p.stop()
    # Match each row div with its data-* attributes plus the anchor inside.
    row_re = re.compile(
        r'<div[^>]+class="rt-tr[^"]*"[^>]*?'
        r'(?:data-department="([^"]*)")?[^>]*?'
        r'(?:data-division="([^"]*)")?[^>]*?'
        r'(?:data-location="([^"]*)")?[^>]*>'
        r'(.*?)</div></div></div>',
        re.IGNORECASE | re.DOTALL,
    )
    anchor_re = re.compile(
        r'<a[^>]+href="(/(?:en/)?postings/([0-9a-f-]{20,}))"[^>]*>([^<]{3,200})</a>',
        re.IGNORECASE,
    )
    out = []
    seen = set()
    for dept, division, location, body in row_re.findall(text):
        m = anchor_re.search(body)
        if not m:
            continue
        path, uuid, title = m.group(1), m.group(2), html.unescape(m.group(3)).strip()
        if uuid in seen:
            continue
        seen.add(uuid)
        locs = [html.unescape(location).strip()] if location else []
        out.append({
            "title": title,
            "locations": locs,
            "url": root + path,
            "description": "",
            "blob": " ".join(filter(None, [title, dept, division, location])),
        })
    # Fallback: if row parsing found nothing, take all anchors directly.
    if not out:
        for m in anchor_re.finditer(text):
            path, uuid, title = m.group(1), m.group(2), html.unescape(m.group(3)).strip()
            if uuid in seen:
                continue
            seen.add(uuid)
            out.append({
                "title": title,
                "locations": [],
                "url": root + path,
                "description": "",
                "blob": title,
            })
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


# =============================================================================
# Umantis — recruitingapp-<id>.<region>.umantis.com. HTML page with a table
# of jobs. Simple regex scrape.
# =============================================================================

def fetch_umantis(source):
    """Umantis scraper. Pattern: recruitingapp-<id>.<region>.umantis.com/Jobs/All.
    The response is an HTML table where each <a> is a job link."""
    board = source.get("board") or source.get("search_url", "")
    if not board:
        err(f"[{source['name']}] Umantis needs a `board` URL")
        return {"jobs": [], "spontaneous_url": None}
    try:
        text = http_get_text(board)
    except Exception as e:
        err(f"[{source['name']}] Umantis fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    # Umantis anchors: <a href="/Vacancies/<id>/Description/1">Title</a>
    # with optional location column in the sibling <td>.
    origin = re.match(r"(https?://[^/]+)", board).group(1)
    # Job rows: <tr>...<a href=...>TITLE</a>...LOCATION...</tr>
    row_re = re.compile(
        r'<tr[^>]*>.*?<a[^>]+href="(/Vacancies/[^"]+)"[^>]*>([^<]+)</a>(.*?)</tr>',
        re.IGNORECASE | re.DOTALL,
    )
    out = []
    seen = set()
    for path, title, tail in row_re.findall(text):
        if path in seen:
            continue
        seen.add(path)
        title = html.unescape(title).strip()
        # Location often in a later <td>
        loc = ""
        loc_m = re.search(r'<td[^>]*>([^<]{2,80})</td>', tail)
        if loc_m:
            loc = html.unescape(loc_m.group(1)).strip()
        out.append({
            "title": title,
            "locations": [loc] if loc else [],
            "url": origin + path,
            "description": "",
            "blob": title,
        })
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


# =============================================================================
# Workday — POST /wday/cxs/<tenant>/<board>/jobs with body {limit,offset,search}.
# Huge unlock: covers Sonos, Dolby, Amazon, Adobe, Intel, Uber, Netflix,
# Palantir, Tesla, Cisco, VMware, Oracle, Zoom, Booking.com, PayPal…
# =============================================================================

def fetch_workday(source):
    """Workday generic fetcher. Config keys:
      - `board`     : full public URL e.g. https://sonos.wd1.myworkdayjobs.com/Sonos
      - `slug`      : Workday tenant (extracted from URL: "sonos" here)
      - `board_id`  : the second segment ("Sonos" in the URL above)
    We derive slug + board_id from `board` if not explicit."""
    board = source.get("board") or ""
    # Extract tenant + board_id from board URL:
    #   https://<tenant>.wd<N>.myworkdayjobs.com/<board_id>
    m = re.match(
        r'https?://([^.]+)\.wd(\d+)\.myworkdayjobs\.com/(?:en-US/)?([^/?#]+)',
        board, re.IGNORECASE,
    )
    if not m:
        err(f"[{source['name']}] Workday: cannot parse tenant from board URL: {board}")
        return {"jobs": [], "spontaneous_url": None}
    tenant, wd_num, board_id = m.group(1), m.group(2), m.group(3)
    api_url = f"https://{tenant}.wd{wd_num}.myworkdayjobs.com/wday/cxs/{tenant}/{board_id}/jobs"
    all_jobs = []
    total_board = None
    limit = 20
    offset = 0
    for _ in range(200):
        payload = json.dumps({
            "limit": limit, "offset": offset,
            "searchText": "", "appliedFacets": {},
        }).encode()
        try:
            req = urllib.request.Request(
                api_url, data=payload, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                page = json.load(resp)
        except Exception as e:
            err(f"[{source['name']}] Workday page {offset} failed: {e}")
            break
        postings = page.get("jobPostings") or []
        if total_board is None:
            total_board = page.get("total", 0)
        if not postings:
            break
        for p in postings:
            all_jobs.append(p)
        offset += limit
        if len(all_jobs) >= (total_board or 0):
            break
    out = []
    origin = f"https://{tenant}.wd{wd_num}.myworkdayjobs.com"
    for p in all_jobs:
        title = p.get("title", "")
        loc = p.get("locationsText") or p.get("bulletFields", [""])[0] or ""
        # Some Workday tenants (notably Intel) encode remote as "Virtual, <X>".
        # Normalize to "Remote (<X>)" so it isn't mistaken for a city.
        m_virt = re.match(r'^\s*Virtual\s*,\s*(.+?)\s*$', loc, re.IGNORECASE)
        if m_virt:
            loc = f"Remote ({m_virt.group(1)})"
        elif loc.strip().lower() == "virtual":
            loc = "Remote"
        external_path = p.get("externalPath") or ""
        # Workday job URLs need the board_id prefix: /en-US/<board>/job/...
        # externalPath is /job/<location>/<slug>. Include a locale for full
        # canonicalization — /en-US/ works reliably.
        if external_path:
            job_url = f"{origin}/en-US/{board_id}{external_path}"
        else:
            job_url = ""
        out.append({
            "title": title,
            "locations": [loc] if loc else [],
            "url": job_url,
            "description": "",
            "blob": title,
        })
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": total_board or len(out)}


# =============================================================================
# SuccessFactors (SAP) — used by Sennheiser and many large industrials.
# The public search endpoint is <company>.sfrs.myworkday.com or, more often,
# careers.<company>.com/... which reverse-proxies to careers.sap.com.
# Sennheiser: jobs.sennheiser.com/search/ — returns HTML with job cards.
# =============================================================================

# Primary: matches Sennheiser-style jobCardTitle anchors with direct text.
# Uses lookaheads so class/href attribute order doesn't matter.
_SF_JOB_LINK_RE = re.compile(
    r'<a\b(?=[^>]*\bclass="[^"]*jobCardTitle)(?=[^>]*\bhref="(/job/[^"]+)")[^>]*>\s*([^<]{3,200})\s*<',
    re.IGNORECASE,
)
# Legacy: nested-tag layout (older SF themes).
_SF_JOB_LINK_LEGACY_RE = re.compile(
    r'<a[^>]+href="(/job/[^"]+)"[^>]*>\s*<[^>]+>\s*([^<]{5,200})\s*<',
    re.IGNORECASE | re.DOTALL,
)
# Strips ", job posting N of NN" suffix that SF adds inside aria-label.
_SF_ARIA_SUFFIX_RE = re.compile(r',\s*job posting\s+\d+\s+of\s+\d+\s*$', re.IGNORECASE)


def fetch_successfactors(source):
    """SuccessFactors scraper (Sennheiser + others). Pulls the HTML page
    and extracts job cards. Uses Playwright — SF pages are React apps."""
    board = source.get("board") or source.get("search_url", "")
    if not board:
        err(f"[{source['name']}] SuccessFactors needs a `board` URL")
        return {"jobs": [], "spontaneous_url": None}
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright required")
        return {"jobs": [], "spontaneous_url": None}
    origin = re.match(r"(https?://[^/]+)", board).group(1)
    p, browser, page = _open_browser()
    try:
        text = _render(page, board, wait_selector='a[href*="/job/"]',
                       debug_path=f"debug/debug-{source['slug']}-sf-1.html")
    except Exception as e:
        err(f"[{source['name']}] SuccessFactors fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    finally:
        browser.close()
        p.stop()
    out = []
    seen = set()

    def _emit(path, title):
        title = _SF_ARIA_SUFFIX_RE.sub('', html.unescape(title).strip()).strip()
        jid_m = re.search(r'/job/([^/?#]+)', path)
        jid = jid_m.group(1) if jid_m else path
        if jid in seen or not title:
            return
        seen.add(jid)
        out.append({
            "title": title,
            "locations": [],
            "url": origin + path,
            "description": "",
            "blob": title,
        })

    for path, title in _SF_JOB_LINK_RE.findall(text):
        _emit(path, title)
    if not out:
        for path, title in _SF_JOB_LINK_LEGACY_RE.findall(text):
            _emit(path, title)
    # Final fallback: anchors with aria-label (strip the "job posting N of NN" suffix).
    if not out:
        alt_re = re.compile(
            r'<a[^>]+href="(/job/[^"]+)"[^>]+aria-label="([^"]+)"',
            re.IGNORECASE,
        )
        for path, title in alt_re.findall(text):
            _emit(path, title)
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


# =============================================================================
# Teamtailor — hosted careers pages (Roland, Marshall, Elektron). Pattern:
#   href="https://careers.<company>.com/jobs/<jobid>-<slug>"
# JS-rendered page but the anchors are present in the initial HTML.
# =============================================================================

def fetch_boss(source):
    """Boss.info employment page: all listings inline on one page, no
    individual URLs. Extract each <h3> as a job with the shared URL."""
    board = source.get("board") or ""
    if not board or not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Boss needs board + Playwright")
        return {"jobs": [], "spontaneous_url": None}
    p, browser, page = _open_browser()
    try:
        text = _render(page, board, wait_selector='h3',
                       debug_path="debug/debug-boss-1.html")
    except Exception as e:
        err(f"[{source['name']}] Boss fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    finally:
        browser.close()
        p.stop()
    # Extract every <h3> that looks like a job title (contains a role keyword).
    # Skip generic content headings.
    role_re = re.compile(
        r'<h3[^>]*>([^<]{5,200}(?:engineer|manager|developer|specialist|lead|analyst|coordinator|designer|technician|internship|intern|director|architect|consultant|representative|associate|assistant|clerk|administrator)[^<]*)</h3>',
        re.IGNORECASE,
    )
    out = []
    seen = set()
    for m in role_re.finditer(text):
        title = html.unescape(m.group(1)).strip()
        title = re.sub(r'\s+', ' ', title)
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append({
            "title": title,
            "locations": [],
            "url": board,   # shared URL
            "description": "",
            "blob": title,
        })
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": None,
            "total_board": len(out)}


def fetch_teamtailor(source):
    """Teamtailor generic. Uses Playwright, extracts <a href="/jobs/<id>-<slug>">
    entries with their text content as the title."""
    board = source.get("board") or source.get("search_url", "")
    if not board:
        err(f"[{source['name']}] Teamtailor needs a `board` URL")
        return {"jobs": [], "spontaneous_url": None}
    if not HAS_PLAYWRIGHT:
        err(f"[{source['name']}] Playwright required")
        return {"jobs": [], "spontaneous_url": None}
    origin = re.match(r"(https?://[^/]+)", board).group(1)
    p, browser, page = _open_browser()
    try:
        text = _render(page, board, wait_selector='a[href*="/jobs/"]',
                       debug_path=f"debug/debug-{source['slug']}-teamtailor-1.html")
    except Exception as e:
        err(f"[{source['name']}] Teamtailor fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    finally:
        browser.close()
        p.stop()
    # Extract job anchors: href="<absolute or /jobs/id-slug>". Title is
    # everything between the tags (may span nested elements).
    anchor_re = re.compile(
        r'<a[^>]+href="((?:https?://[^"]*)?/jobs/(\d+)-[a-z0-9-]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    out = []
    seen = set()
    for path, jid, body in anchor_re.findall(text):
        if jid in seen:
            continue
        seen.add(jid)
        # Extract inner text.
        clean = re.sub(r"<[^>]+>", " ", body)
        clean = re.sub(r"\s+", " ", clean).strip()
        # Skip if the text is empty (nav / hidden anchor).
        if not clean or len(clean) < 3:
            continue
        # Title is the first line-worth of text.
        title = clean[:150]
        job_url = path if path.startswith("http") else origin + path
        out.append({
            "title": title,
            "locations": [],
            "url": job_url,
            "description": "",
            "blob": title,
        })
    matched = [j for j in out if matches(j, source["queries"])]
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(out),
            "total_board": len(out)}


# Fetcher kinds we trust to say "job is no longer on the board". These call
# APIs that return the full board (we filter client-side via matches()). For
# other kinds (per-query Playwright/Phenom/Google/etc.), a missing URL just
# means "not in this run's query subset" — could still be on the board — so
# we don't render the REMOVED badge for them.
_TRUSTED_REMOVAL_KINDS = frozenset({
    "ashby", "greenhouse", "workable",
    "bamboohr", "pinpoint", "umantis", "successfactors", "workday",
})


# Kinds that iterate `for q in source["queries"]` with no empty-query
# fallback — so a source with queries=[] fetches literally zero jobs. We
# flag these in the UI with a red "⚠ keyword required" chip when the
# pill list is empty, so a fresh-off-onboarding user doesn't quietly end
# up with a dead Apple/Microsoft/Meta section. Google uses
# `queries or [""]` so empty is fine; sources like Greenhouse/Ashby/
# Workday fetch the whole board and filter — empty = fetch everything.
_QUERY_REQUIRED_KINDS = frozenset({
    "apple", "microsoft", "meta", "phenom",
})


def fetch_wttj_company(source):
    """Fetch all WTJ-advertised jobs for one company via the public
    WTJ API (api.welcometothejungle.com/api/v3/organizations/<slug>/jobs).
    No Playwright, no CloudFront challenge — just a JSON GET.

    `source["slug"]` is the WTJ organization slug (e.g. "zama"). The
    optional `queries` list filters titles client-side after fetch."""
    slug = source.get("slug")
    if not slug:
        err(f"[{source.get('name') or '?'}] wttj_company source has no slug")
        return {"jobs": [], "spontaneous_url": None}
    try:
        import wttj_discovery
        jobs = wttj_discovery.fetch_wttj_jobs(slug)
    except Exception as e:
        err(f"[{source.get('name') or slug}] wttj API fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    sys.stdout.write(f"[{source['name']}] wttj API returned {len(jobs)} jobs\n")
    filtered = [j for j in jobs if matches(j, source.get("queries") or [])]
    return {"jobs": filtered, "spontaneous_url": None}


FETCHERS = {
    "ashby": fetch_ashby,
    "greenhouse": fetch_greenhouse,
    "workable": fetch_workable,
    "lever": fetch_lever,
    "eightfold": fetch_eightfold,
    "apple": fetch_apple,
    "google": fetch_google,
    "microsoft": fetch_microsoft,
    "meta": fetch_meta,
    "phenom": fetch_phenom,
    "cisco": fetch_cisco,
    "bose": fetch_bose,
    "linkedin": fetch_linkedin,
    "ibm": fetch_ibm,
    "scale": fetch_scale,
    "github": fetch_github,
    "checkmarx": fetch_checkmarx,
    "pixee": fetch_pixee,
    "ableton": fetch_ableton,
    "lucca": fetch_lucca,
    "pw": fetch_pw_generic,
    "wttj_company": fetch_wttj_company,
    "bamboohr": fetch_bamboohr,
    "pinpoint": fetch_pinpoint,
    "umantis": fetch_umantis,
    "workday": fetch_workday,
    "successfactors": fetch_successfactors,
    "teamtailor": fetch_teamtailor,
    "boss": fetch_boss,
}


def board_url_for(source):
    if source.get("board"):
        return source["board"]
    kind = source["kind"]
    slug = source["slug"]
    if kind == "ashby":
        return f"https://jobs.ashbyhq.com/{slug}"
    if kind == "greenhouse":
        return f"https://job-boards.greenhouse.io/{slug}"
    if kind == "workable":
        return f"https://apply.workable.com/{slug}/"
    if kind == "apple":
        return "https://jobs.apple.com/en-us/search"
    if kind == "google":
        return "https://www.google.com/about/careers/applications/jobs/results/"
    return ""


def _load_score_cache():
    try:
        with open(SCORE_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_score_cache(cache):
    with open(SCORE_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _load_claude_fit_cache():
    try:
        with open(CLAUDE_FIT_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_claude_fit_cache(cache):
    with open(CLAUDE_FIT_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


# Workday job requisition IDs like "JR2021883". Not a location.
_JR_ID_RE = re.compile(r"^JR\d{5,}$", re.IGNORECASE)


def _pre_split(part):
    """Handle concatenated locations like 'London UK, Geneva CH' where the
    comma separates two distinct city+country pairs (no comma between the
    city and the country). Returns a list of candidate parts."""
    if "," not in part:
        return [part]
    segments = [s.strip() for s in part.split(",") if s.strip()]
    # If every segment is "<something> <country-code-or-name>" pattern, treat
    # them all as independent locations.
    def is_cc_pair(s):
        toks = s.rsplit(None, 1)
        if len(toks) != 2:
            return False
        last = toks[1]
        normalized = _normalize_country(last)
        # Accept if the last token is a known country name, a US state, a CA
        # province, or a 2-3 letter code that normalizes to something new.
        return (
            last.lower() in _KNOWN_COUNTRIES
            or normalized != last
            or last.lower() in _US_STATES
            or last.lower() in _CA_PROVINCES
        )
    if all(is_cc_pair(s) for s in segments):
        return segments
    return [part]
_LOC_SPLIT_RE = re.compile(r"\s*[;|]\s*")
_PLUS_MORE_RE = re.compile(r"\s*\+\s*\d+\s*more\s*$", re.IGNORECASE)

# "CH - Geneva", "FR - Paris", "GB - London" → strip the "XX - " prefix.
_CC_PREFIX_RE = re.compile(
    r"^([A-Z]{2}|[A-Z]{3})\s*[-–—:]\s*",
    re.IGNORECASE,
)

# City aliases used to collapse "NYC", "New York City", "New York" to one entry.
_CITY_ALIASES = {
    "nyc": "new york",
    "new york city": "new york",
    "new york, ny": "new york",
    # German cities with local-language forms
    "koln": "cologne",     # Köln → Cologne
    "munchen": "munich",   # München → Munich
    "osnabruck": "osnabrück",
    "sf": "san francisco",
    "sfo": "san francisco",
    "sf bay": "san francisco",
    "sfbay": "san francisco",
    "san francisco bay": "san francisco",
    "san francisco bay area": "san francisco",
    "bay area": "san francisco",
    "la": "los angeles",
    "dc": "washington",
    "washington dc": "washington",
    "washington d.c.": "washington",
    "us remote": "remote friendly",
    "usa remote": "remote friendly",
    "remote us": "remote friendly",
    "remote usa": "remote friendly",
    "remote": "remote friendly",
    "us remote": "remote friendly",
    "remote friendly usa": "remote friendly",
    "remote friendly us": "remote friendly",
    "us remote friendly": "remote friendly",
    "friendly": "remote friendly",
    "friendly (travel required)": "remote friendly (travel required)",
    "friendly (travel-required)": "remote friendly (travel required)",
    "remote friendly (travel required)": "remote friendly (travel required)",
    "remote friendly (travel-required)": "remote friendly (travel required)",
    "remote friendly us (travel required)": "remote friendly (travel required)",
    "remote friendly usa (travel required)": "remote friendly (travel required)",
}

# Cities we always want in a specific country group (defends against
# ambiguity like Ontario/CA state vs Ontario province).
_CITY_TO_COUNTRY = {
    # USA
    "san francisco": "USA", "new york": "USA", "seattle": "USA",
    "washington": "USA", "boston": "USA", "chicago": "USA",
    "los angeles": "USA", "austin": "USA", "denver": "USA",
    "redmond": "USA", "cupertino": "USA", "mountain view": "USA",
    "san jose": "USA", "palo alto": "USA", "sunnyvale": "USA",
    "atlanta": "USA", "dallas": "USA", "philadelphia": "USA",
    "miami": "USA", "houston": "USA", "portland": "USA",
    # UK
    "london": "UK", "manchester": "UK", "edinburgh": "UK", "glasgow": "UK",
    "cambridge": "UK", "oxford": "UK", "bristol": "UK", "leeds": "UK",
    # France
    "paris": "France", "lyon": "France", "toulouse": "France",
    "grenoble": "France", "nice": "France", "bordeaux": "France",
    "marseille": "France", "issy les moulineaux": "France", "issy": "France",
    # Brazil / LatAm
    "sao paulo": "Brazil", "são paulo": "Brazil",
    "rio de janeiro": "Brazil", "buenos aires": "Argentina",
    # Germany
    "berlin": "Germany", "munich": "Germany", "hamburg": "Germany",
    "frankfurt": "Germany", "cologne": "Germany", "stuttgart": "Germany",
    # Netherlands / Ireland
    "amsterdam": "Netherlands", "rotterdam": "Netherlands", "dublin": "Ireland",
    # Canada
    "toronto": "Canada", "montreal": "Canada", "vancouver": "Canada",
    "ottawa": "Canada", "calgary": "Canada", "quebec": "Canada",
    "ontario": "Canada",
    # Switzerland
    "zurich": "Switzerland", "geneva": "Switzerland", "basel": "Switzerland",
    # Others
    "madrid": "Spain", "barcelona": "Spain",
    "milan": "Italy", "rome": "Italy",
    "sydney": "Australia", "melbourne": "Australia",
    "tokyo": "Japan", "osaka": "Japan",
    "singapore": "Singapore",
    "tel aviv": "Israel",
    "manila": "Philippines",
    "ho chi minh": "Vietnam", "ho chi minh city": "Vietnam", "hanoi": "Vietnam",
    "hsinchu city": "Taiwan", "hsinchu": "Taiwan", "taipei": "Taiwan",
    # Additional
    "bengaluru": "India", "bangalore": "India",
    "mumbai": "India", "new delhi": "India", "delhi": "India",
    "doha": "Qatar", "dubai": "UAE",
    "riyadh": "Saudi Arabia",
    "skopje": "North Macedonia",
    "sofia": "Bulgaria",
    "vilnius": "Lithuania",
    "taipei": "Taiwan",
    "peru": "Peru",
    # Portugal / Iberia
    "braga": "Portugal", "lisbon": "Portugal", "porto": "Portugal",
    # Additional US cities that were slipping through
    "menlo park": "USA", "bellevue": "USA",
    # Nordics / Central Europe
    "copenhagen": "Denmark",
    "budapest": "Hungary",
    "prague": "Czech Republic",
    "warsaw": "Poland", "krakow": "Poland",
    "athens": "Greece",
    # Meta-regions kept as-is (not tied to a country)
    "emea": "EMEA", "europe": "EMEA",
    "southern europe": "EMEA",
    "us east coast": "USA",
    "north america": "USA",
    # India cities that were slipping through
    "noida": "India", "hyderabad": "India", "pune": "India",
    "gurgaon": "India", "chennai": "India", "kolkata": "India",
    "gurugram": "India",
    # France cities
    "nantes": "France", "montpellier": "France",
    "sophia antipolis": "France", "annecy": "France",
    "biarritz": "France", "bethune": "France", "béthune": "France",
    "hauts de france": "France", "hauts-de-france": "France",
    # Germany cities (including non-ASCII variants)
    "cologne": "Germany", "koln": "Germany", "köln": "Germany",
    "munich": "Germany", "munchen": "Germany", "münchen": "Germany",
    "hannover": "Germany", "hanover": "Germany",
    "osnabruck": "Germany", "osnabrück": "Germany",
    "north rhine westphalia": "Germany",
    # Other missing cities
    "chiba": "Japan", "seoul": "South Korea",
    "vienna": "Austria",
    "belgrade": "Serbia",
    "kaunas": "Lithuania", "tallinn": "Estonia",
    "ramat gan": "Israel",
    "yerevan": "Armenia",
    "dakar": "Senegal",
    "shanghai": "China", "beijing": "China",
    "taoyuan": "Taiwan",
}

# Known country names / codes. If the FIRST segment matches, the location is
# in Microsoft's reverse order (country, state, city).
_US_STATES = {
    "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in",
    "ia","ks","ky","la","me","md","ma","mi","mn","ms","mo","mt","ne","nv",
    "nh","nj","nm","ny","nc","nd","oh","ok","or","pa","ri","sc","sd","tn",
    "tx","ut","vt","va","wa","wv","wi","wy","dc",
    "alabama","alaska","arizona","arkansas","california","colorado","connecticut",
    "delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa",
    "kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
    "minnesota","mississippi","missouri","montana","nebraska","nevada",
    "new hampshire","new jersey","new mexico","new york","north carolina",
    "north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island",
    "south carolina","south dakota","tennessee","texas","utah","vermont",
    "virginia","washington","west virginia","wisconsin","wyoming",
    "district of columbia",
}

_COUNTRY_ALIASES = {
    "united states": "USA", "usa": "USA", "us": "USA", "u.s.": "USA",
    "u.s.a.": "USA", "u.s.a": "USA", "united states of america": "USA",
    "united kingdom": "UK", "uk": "UK", "u.k.": "UK", "great britain": "UK",
    "england": "UK", "scotland": "UK", "wales": "UK",
    "canada": "Canada", "can": "Canada",
    "ch": "Switzerland", "che": "Switzerland",
    "deutschland": "Germany", "france": "France", "germany": "Germany",
    "spain": "Spain", "italy": "Italy",
    "japan": "Japan", "china": "China", "india": "India",
    "australia": "Australia", "netherlands": "Netherlands",
    "switzerland": "Switzerland", "ireland": "Ireland",
    "singapore": "Singapore", "brazil": "Brazil",
    # Mexico variants
    "mx": "Mexico", "mexico": "Mexico", "méxico": "Mexico", "mexique": "Mexico",
    # "Delhi NCR" (National Capital Region) is India
    "delhi ncr": "India", "ncr": "India",
    # Sometimes Israel comes through as IL (state code collision — but if we
    # only match single-segment, IL alone will more often be Illinois. Leave alone.)
}


_CA_PROVINCES = {
    "ab", "bc", "mb", "nb", "nl", "ns", "nt", "nu", "on", "pe", "qc", "sk", "yt",
    "alberta", "british columbia", "manitoba", "new brunswick",
    "newfoundland", "newfoundland and labrador", "nova scotia", "ontario",
    "quebec", "québec", "saskatchewan", "yukon", "northwest territories", "nunavut",
    "prince edward island",
}


# Cities whose known country overrides the ambiguous "CA" state suffix.
# E.g. "Ontario, CA" and "British Columbia, CA" are Canada, not California.
_CA_AMBIGUOUS_CITIES = {
    "ontario", "british columbia", "alberta", "quebec", "québec", "manitoba",
    "toronto", "montreal", "montréal", "vancouver", "ottawa", "calgary",
}


def _normalize_country(country):
    if not country:
        return ""
    n = re.sub(r"[.\-']", "", country.lower().strip())
    n = re.sub(r"\s+", " ", n)
    if n in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[n]
    if n in _US_STATES:
        return "USA"
    if n in _CA_PROVINCES:
        return "Canada"
    return country.strip()


_KNOWN_COUNTRIES = {
    "united states", "united states of america", "usa", "us", "u.s.", "u.s.a.",
    "united kingdom", "uk", "u.k.",
    "france", "germany", "spain", "italy", "canada", "mexico", "japan",
    "china", "india", "brazil", "australia", "netherlands", "sweden",
    "norway", "denmark", "finland", "switzerland", "austria", "belgium",
    "poland", "portugal", "ireland", "singapore", "south korea", "korea",
    "argentina", "chile", "colombia", "new zealand", "south africa",
    "russia", "turkey", "greece", "czechia", "czech republic",
    "hungary", "romania", "ukraine", "vietnam", "thailand", "philippines",
    "indonesia", "malaysia", "taiwan", "hong kong", "israel", "uae",
    "united arab emirates", "saudi arabia", "egypt", "nigeria", "kenya",
    "luxembourg", "estonia", "latvia", "lithuania", "iceland", "malta",
    "cyprus", "bulgaria", "slovakia", "slovenia", "croatia", "serbia",
}


# Strips "Hybrid <city>", "Onsite <city>", etc. so those match plain "<city>".
# Deliberately NOT stripping "Remote" — "Remote", "Remote-Friendly (Travel
# Required)" etc. are meaningful locations on their own.
_WORK_MODE_PREFIX_RE = re.compile(
    r"^\s*(?:hybrid|on[- ]site|onsite)\s*[-–—:,]?\s*",
    re.IGNORECASE,
)

# Leading "Remote ..." / "Remote - ..." prefix. When we can identify a real
# country/city after it, strip the "Remote" prefix so the location gets
# grouped by country (Remote - New York → New York, USA), not lumped into
# the generic "Remote" bucket. Common typo "Unites States" also caught.
_LEADING_REMOTE_RE = re.compile(
    r"^\s*remote\s*[-–—:,/]?\s*",
    re.IGNORECASE,
)
# Common typos in Remote+country strings.
_REMOTE_TYPO_FIX = {
    "unites states": "United States",
    "united states": "United States",
    "united kingdom": "United Kingdom",
    "north america": "USA",
    "europe": "Europe",
}

# Simple ASCII fold for common accented chars (é, è → e etc.).
try:
    import unicodedata
    def _fold(s): return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )
except Exception:
    def _fold(s): return s


_MEANINGLESS_CITY = re.compile(
    r"^(multiple\s+locations?|various(\s+locations?)?|remote|any(where)?|"
    r"nationwide|global|worldwide)$",
    re.IGNORECASE,
)

# Words that look like team/department names, not locations. These sometimes
# leak into the "location" slot when a scraper pulls the second segment of a
# card (Meta, GitHub, etc. list "Team | Location" and swaps them).
_DEPARTMENT_WORDS = {
    "engineering", "privacy", "program management", "security",
    "software engineering", "technical security", "product", "design",
    # Meta team names that leak into the location slot.
    "ai infrastructure ar/vr", "ai infrastructure",
    "facebook reality labs", "reality labs", "facebook",
    # Office descriptors that aren't locations.
    "office", "headquarters", "hq",
    # More generic non-location leaks.
    "pebl", "privy", "network engineering", "technical account management",
    "client solutions", "artificial intelligence",
    "federal", "distributed",
    "amer", "ar/vr", "ar vr",
    # "Worldwide" / "Global" convey no useful place — drop them so a job
    # listed as such groups under Remote (if also tagged remote) or
    # disappears entirely rather than cluttering the location filter.
    "worldwide", "global",
    "research", "data", "marketing", "sales", "operations",
    "infrastructure", "legal", "finance", "people", "hr", "recruiting",
    "customer success", "customer support", "support", "trust & safety",
    "trust and safety", "safety", "policy", "communications",
}
_NON_LOCATION_CHARS_RE = re.compile(r"^[\W\s]+$")   # only punctuation/whitespace


def _looks_like_location(s):
    if not s or _NON_LOCATION_CHARS_RE.match(s):
        return False
    if s.lower().strip() in _DEPARTMENT_WORDS:
        return False
    # Prose stuffed into a location field — e.g. PQShield's Greenhouse feed
    # emits "Spain. Some travel to our offices (Oxford/London/Paris) will be
    # required from time-to-time, UK". Real locations in the corpus top out
    # around 42 chars; 60 gives safe margin and still catches sentence-length
    # garbage before it taints country grouping.
    if len(s) > 60:
        return False
    # Timezone-only strings like "Remote (UTC-5) to UTC+2" are not locations.
    if re.search(r"\butc\s*[+-−–—]?\s*\d", s, re.IGNORECASE):
        return False
    # Phenom-style UI labels: "2 Locations", "5 locations". These come from
    # multi-office job cards where the ATS shows a count instead of a list;
    # the string is a UI element, not a place name.
    if re.match(r"^\s*\d+\s+locations?\s*$", s, re.IGNORECASE):
        return False
    # Truncated department names ending in a dangling "&" ("People &",
    # "Trust &", "Sales &") — Meta's board emits these when a location
    # field runs into a "People & Culture"-style team suffix that got
    # sliced. Not real locations.
    if re.match(r"^\s*[A-Za-z]+\s*&\s*$", s):
        return False
    return True


_TRAILING_REMOTE_RE = re.compile(
    r"\s*[\(\[]?\s*remote\s*[\)\]]?\s*$",
    re.IGNORECASE,
)


_MS_STATE_DC_SUFFIX_RE = re.compile(
    # Microsoft data-center flags: "CA - DC", "OH - DC", "LA - US", "OK - US (1)",
    # "IL - Data Center". Drop the suffix — the leading token is a US state
    # so the location falls back to that state, which then normalizes to USA.
    r"\s*[-–—]\s*(?:DC|US|Data\s*Center)\s*(?:\(\d+\))?\s*$",
    re.IGNORECASE,
)
# Cleanup for trailing parenthesized status / tag: "(DL/IDL)", "(STAFF)",
# "(East Coast)", "(SoHo)", "(1)", "(First St)", "(preferred)", "(HQ)".
_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")
# Trailing dash / hyphen with nothing after: "Remote -", "France -".
_TRAILING_DASH_RE = re.compile(r"\s*[-–—]\s*$")
# Trailing office/status word: "Palo Alto Office", "Bellevue Office",
# "Santa Clara Hybrid", "Palo Alto HQ".
_TRAILING_OFFICE_RE = re.compile(
    r"\s+(?:Office|HQ|Hybrid|Headquarters|Local)\s*$", re.IGNORECASE,
)
# Trailing "-XYZ" suffixes on cities: "Bangalore-MSO", "Warsaw-Lixa C".
# Only strip when the prefix is a plausible city.
_TRAILING_DASH_TAG_RE = re.compile(r"\s*[-–—]\s*[A-Za-z][A-Za-z0-9 ]{0,15}\s*$")
# Street-address trailer, e.g. "1730 Fox Drive" / "4100 1st St" /
# "Innovation Drive". Matches a <number> + <word>+ + {Drive|Street|...}
# OR a bare {Drive|Street|...} at end of segment (prefixed by a word).
_STREET_ADDR_RE = re.compile(
    r"\s*[-–—,]?\s*(?:\d+\s+)?[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+"
    r"(?:Drive|Dr|Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Way|Lane|Ln|Court|Ct|Plaza|Pkwy|Parkway)\.?\s*$",
    re.IGNORECASE,
)
# Workday multi-dash "State- City - Street" format emitted by Cisco:
# "California- San Jose - 1730 Fox Drive". Extract the middle segment
# (always the city) when there are 2+ dashes and the tail looks like
# a street address or number.
_WD_STATE_CITY_STREET_RE = re.compile(
    r"^\s*(?:[A-Z]{2}|[A-Za-z]+)\s*[-–—]\s*([A-Za-z][A-Za-z \-]+?)\s*[-–—]\s*\d+.*$"
)
# Reversed "<US-state-or-country> - <City>" shape — Salesforce's Workday emits
# "California - San Francisco" and Snyk's Ashby emits "United States - Boston"
# (plus "United States - Boston Local" after " Local" gets stripped above).
# Flipped to "<City>, <Region>" so downstream city/country lookup works.
# We require space-dash-space to avoid eating hyphenated city names like
# "Winston-Salem", and we reject suffixes containing another " - " to avoid
# mis-splitting 3-segment inputs like "USA - California - San Francisco".
_REGION_DASH_CITY_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z. ]{1,40}?)\s+[-–—]\s+([A-Za-z][A-Za-zÀ-ÿ. '-]+?)\s*$"
)


def _clean_loc(part):
    """Strip UI artifacts like ' + N more' suffixes and work-mode prefixes
    (Hybrid, Remote, Onsite …)."""
    s = _PLUS_MORE_RE.sub("", part).strip()
    s = _WORK_MODE_PREFIX_RE.sub("", s).strip()
    # Workday "State- City - Street" format: extract just the city.
    # Cisco emits e.g. "California- San Jose - 1730 Fox Drive".
    m = _WD_STATE_CITY_STREET_RE.match(s)
    if m:
        s = m.group(1).strip()
    # Trailing street address: "<something> 1730 Fox Drive" → "<something>".
    s = _STREET_ADDR_RE.sub("", s).strip()
    # Leading "/" or "- " leftover from a splitter that already consumed the
    # first token: "Remote / Friendly" → post-split "/ Friendly". Strip.
    s = re.sub(r"^\s*[/\-–—]\s*", "", s).strip()
    # "(Baltimore, MD)" → "Baltimore, MD"
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    # Microsoft "CA - DC", "OK - US (1)", "IL - Data Center" style: drop suffix.
    s = _MS_STATE_DC_SUFFIX_RE.sub("", s).strip()
    # Generic trailing parenthesized tag: "(HQ)", "(East Coast)", "(1)".
    # Skip if it eats the whole string.
    tmp = _TRAILING_PAREN_RE.sub("", s).strip()
    if tmp and _looks_like_location(tmp):
        s = tmp
    # Trailing office/HQ/Hybrid word.
    tmp = _TRAILING_OFFICE_RE.sub("", s).strip()
    if tmp != s:
        # Something got stripped. If what remains is a real location, use it.
        # If what remains is a department word (e.g. "Pebl Office" → "Pebl",
        # which is in _DEPARTMENT_WORDS), the whole string was an internal
        # office code — drop it by returning empty so _parse_loc bails out.
        if tmp and _looks_like_location(tmp):
            s = tmp
        else:
            return ""
    # Flip "<US-state-or-country> - <City>" → "<City>, <Region>" (Salesforce
    # Workday, Snyk Ashby). Must run AFTER _TRAILING_OFFICE_RE so trailing
    # " Local"/" Office" tokens are already stripped from the city segment.
    m = _REGION_DASH_CITY_RE.match(s)
    if m:
        prefix, suffix = m.group(1).strip(), m.group(2).strip()
        low = prefix.lower()
        if (low in _US_STATES or low in _KNOWN_COUNTRIES) and " - " not in suffix:
            s = f"{suffix}, {prefix}"
    # Trailing dash: "Remote -", "France -", "Australia -".
    s = _TRAILING_DASH_RE.sub("", s).strip()
    # Mid-segment trailing dash before a comma: "Tel Aviv -, USA" → "Tel Aviv, USA".
    s = re.sub(r"\s*[-–—]\s*(?=,)", "", s)
    # Trailing dangling comma or closing paren: "Canada)", "Remote (United States"
    s = re.sub(r"[,)]\s*$", "", s).strip()
    # Leading dangling open paren: "(United States" (from "Remote (United States")
    s = re.sub(r"^\s*\(\s*", "", s).strip()
    # "Austria (Remote)" / "Denmark(Remote)" / "Canada remote" → strip suffix.
    stripped = _TRAILING_REMOTE_RE.sub("", s).strip()
    if stripped and stripped.lower() != s.lower():
        if _looks_like_location(stripped):
            s = stripped
    # Leading "Remote - <country>" / "Remote <city>" — drop the "Remote"
    # prefix so what remains gets classified by country/city instead of
    # dumped into the generic Remote bucket.
    leading = _LEADING_REMOTE_RE.sub("", s).strip()
    if leading and leading.lower() != s.lower():
        # Common typos in what's left.
        low = leading.lower()
        if low in _REMOTE_TYPO_FIX:
            leading = _REMOTE_TYPO_FIX[low]
        if _looks_like_location(leading):
            s = leading
    # "Anywhere in France" / "Anywhere in <Country>" — extract the country.
    m = re.match(r"^\s*anywhere\s+in\s+(.+)$", s, re.IGNORECASE)
    if m:
        rest = m.group(1).strip().rstrip(",").strip()
        # Handle "Anywhere in France, Spain" (mis-split OR) by taking just
        # the first token before the comma.
        rest_head = rest.split(",", 1)[0].strip()
        if rest_head:
            s = rest_head
    # Trailing "-Tag" suffixes on cities: "Bangalore-MSO" → "Bangalore",
    # "Warsaw-Lixa C" → "Warsaw". Only strip when the head looks like a city
    # we already know about.
    tmp = _TRAILING_DASH_TAG_RE.sub("", s).strip()
    if tmp and tmp != s and _city_key(tmp) in _CITY_TO_COUNTRY:
        s = tmp
    return s


def _city_key(city):
    n = _fold(city).lower().strip()
    n = re.sub(r"[.']", "", n)                  # remove . and '
    n = re.sub(r"[-–—/]+", " ", n)              # dashes / slashes → space
    n = re.sub(r"\s+", " ", n)
    # Try alias match on the raw normalized form first (catches "bay area",
    # "sf bay area", "new york city" etc.).
    if n in _CITY_ALIASES:
        return _CITY_ALIASES[n]
    n = re.sub(r"\s+city$", "", n)
    n = re.sub(r"\s+area$", "", n)
    return _CITY_ALIASES.get(n, n)


def _parse_loc(part):
    """Return (city, country, canonical_display) for a raw location string.
    Handles both Western order (city, state, country) and Microsoft's
    reverse order (country, state, city) via a known-country probe."""
    cleaned = _clean_loc(part)
    # Split on commas that are NOT inside parens. Otherwise
    # "The Americas (North, South)" splits into "The Americas (North" and
    # "South)" — the latter then bubbles up as a fake country.
    segments = []
    buf, depth = "", 0
    for ch in cleaned:
        if ch == "(":
            depth += 1
            buf += ch
        elif ch == ")":
            depth = max(0, depth - 1)
            buf += ch
        elif ch == "," and depth == 0:
            if buf.strip():
                segments.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        segments.append(buf.strip())
    # Drop segments that are department words / meaningless tags. Catches
    # "Distributed, AMER" (both segments dropped → entry disappears) and
    # mixed cases like "Distributed, USA" (Distributed dropped, USA kept).
    segments = [s for s in segments if _looks_like_location(s)]
    if not segments:
        # Nothing salvageable — return empty so _flatten_locations drops it.
        return "", "", ""
    if len(segments) == 1:
        s = segments[0]
        if s.lower() in _KNOWN_COUNTRIES:
            c = _normalize_country(s)
            return c, c, c
        # US state standalone ("Delaware", "New Jersey", "Texas") → state, USA
        if s.lower() in _US_STATES:
            return s.title(), "USA", f"{s.title()}, USA"
        # Remote-like tokens ("Remote", "Friendly", "Remote-Friendly (Travel
        # Required)", "US Remote", etc.) all map to "remote friendly" via
        # _CITY_ALIASES. Canonicalize so partial matches (Anthropic's
        # standalone "Friendly") don't survive as a city name.
        s_key = _city_key(s)
        if "remote" in s_key or "friendly" in s_key:
            title = " ".join(w.capitalize() for w in s_key.split())
            return title, "", title
        # Known city → pin to its country and canonicalize the display name.
        if s_key in _CITY_TO_COUNTRY:
            country = _CITY_TO_COUNTRY[s_key]
            city = " ".join(w.capitalize() for w in s_key.split())
            if city.lower() == country.lower():
                return country, country, country
            return city, country, f"{city}, {country}"
        # Try "London UK" pattern — last space-separated token is a country.
        toks = s.rsplit(None, 1)
        if len(toks) == 2:
            last = toks[1]
            if last.lower() in _KNOWN_COUNTRIES or _normalize_country(last) != last:
                city = toks[0]
                country = _normalize_country(last)
                return city, country, f"{city}, {country}"
        return s, "", s
    # Drop "Multiple Locations" placeholders so we surface the real country.
    segments = [s for s in segments if not _MEANINGLESS_CITY.match(s)] or segments
    if len(segments) == 1:
        s = segments[0]
        if s.lower() in _KNOWN_COUNTRIES:
            c = _normalize_country(s)
            return c, c, c
        return s, "", s
    first, last = segments[0], segments[-1]
    if first.lower() in _KNOWN_COUNTRIES and last.lower() not in _KNOWN_COUNTRIES:
        # Microsoft-style: country, state, city
        city, country_raw = last, first
    else:
        city, country_raw = first, last
    # Ambiguity fix: "Ontario, CA" is Canada, not California.
    if country_raw.lower() == "ca" and city.lower() in _CA_AMBIGUOUS_CITIES:
        country_raw = "Canada"
    # Known city always wins over the country segment (e.g. "Geneva, France"
    # is really Geneva, Switzerland — the "France" was a scraper artifact).
    city_ckey = _city_key(city)
    # Remote-like tokens ("Friendly, USA" from Anthropic) collapse to the
    # canonical "Remote Friendly" with no country before country/alias
    # matching runs, so multi-segment inputs like "Friendly, USA" don't
    # emit "Friendly" as a fake city.
    if "remote" in city_ckey or "friendly" in city_ckey:
        title = " ".join(w.capitalize() for w in city_ckey.split())
        return title, "", title
    if city_ckey in _CITY_TO_COUNTRY:
        country_raw = _CITY_TO_COUNTRY[city_ckey]
        # Also canonicalize the display name (SF/Bay Area → San Francisco).
        city = " ".join(w.capitalize() for w in city_ckey.split())
    elif city.lower() in _CITY_TO_COUNTRY:
        country_raw = _CITY_TO_COUNTRY[city.lower()]
    country = _normalize_country(country_raw)
    # Remote-like "cities" should not carry a country — otherwise
    # "Remote-Friendly, USA" and "US Remote" don't dedupe.
    if "remote" in city.lower() or "friendly" in city.lower():
        return city, "", city
    display = f"{city}, {country}" if country and country.lower() != city.lower() else city
    return city, country, display


def _flatten_locations(locs):
    """Split on `;`/`|`, strip '+ N more' suffixes, normalize city/country
    order, and dedupe variants of the same city. If some entries have no
    country and another entry with the same city has one, promote it."""
    parsed = []
    for loc in locs or []:
        if not loc:
            continue
        # Decode HTML entities up front — Meta's board leaks "People &amp"
        # (truncated "People & Culture"), and any &nbsp;/&#8212; etc. that
        # slips through the scrapers can propagate a garbage token forever.
        loc = html.unescape(loc)
        for part in _LOC_SPLIT_RE.split(loc):
            part = part.strip()
            if not part:
                continue
            if _JR_ID_RE.match(part):
                continue                 # skip Workday requisition IDs
            if not _looks_like_location(part):
                continue                 # skip department names, symbols, etc.
            for sub in _pre_split(part):
                sub = _CC_PREFIX_RE.sub("", sub).strip()
                if not sub or not _looks_like_location(sub):
                    continue
                city, country, display = _parse_loc(sub)
                # _parse_loc returns empty ("", "", "") when everything was
                # filtered out (all-department-word segments) — drop those.
                if not display:
                    continue
                parsed.append((_city_key(city), city, country, display))

    # First pass: find a country for each city_key when at least one entry has one.
    promoted = {}
    for ckey, city, country, _display in parsed:
        if country and ckey not in promoted:
            promoted[ckey] = country
        # Known city → country override wins over ambiguous promotion.
        if ckey in _CITY_TO_COUNTRY:
            promoted[ckey] = _CITY_TO_COUNTRY[ckey]
        elif city.lower() in _CITY_TO_COUNTRY:
            promoted[ckey] = _CITY_TO_COUNTRY[city.lower()]

    # Second pass: dedupe by (city_key, resolved-country).
    best = {}
    order = []
    for ckey, city, country, display in parsed:
        if not country and ckey in promoted:
            country = promoted[ckey]
            if city.lower() != country.lower():
                display = f"{city}, {country}"
            else:
                display = city
        key = (ckey, country.lower())
        score = (display.count(","), len(display))
        if key not in best:
            order.append(key)
            best[key] = (score, display)
        elif score > best[key][0]:
            best[key] = (score, display)
    results = [best[k][1] for k in order]
    # Third pass: drop a bare country ("UK") when any other result already
    # references that country ("London, UK") — the bare entry is redundant.
    # Only runs when the input had 2+ entries so we don't strip single-value
    # legitimate "UK"-only jobs.
    if len(results) > 1:
        countries_in_cities = set()
        for r in results:
            if "," in r:
                tail = r.rsplit(",", 1)[1].strip().lower()
                if tail:
                    countries_in_cities.add(tail)
        results = [r for r in results if "," in r or r.strip().lower() not in countries_in_cities]
    return results


def dedup_by_url(jobs):
    seen = {}
    for j in jobs:
        key = j["url"] or f"{j['title']}|{','.join(j['locations'])}"
        seen.setdefault(key, j)
    return list(seen.values())


_JAPANESE_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uff66-\uff9f]")


def is_title_blacklisted(job):
    title_orig = job["title"] or ""
    if _JAPANESE_RE.search(title_orig):
        return True
    if not TITLE_BLACKLIST:
        return False
    title = title_orig.lower()
    return any(w.lower() in title for w in TITLE_BLACKLIST)


def _location_is_blacklisted_str(loc, bl_lower):
    """True if this single location string matches any blacklist substring."""
    l = loc.lower()
    return any(b in l for b in bl_lower)


def is_location_blacklisted(job):
    """Filter blacklisted locations out of job['locations'] in place. Returns
    True (drop the job) only when NO location survives. This way a job listed
    as ['Berlin, Germany', 'Warsaw, Poland'] with Poland blacklisted keeps
    only 'Berlin, Germany' instead of being either kept-with-Poland or fully
    dropped."""
    if not LOCATION_BLACKLIST or not job.get("locations"):
        return False
    bl = [b.lower() for b in LOCATION_BLACKLIST]
    kept = [loc for loc in job["locations"] if not _location_is_blacklisted_str(loc, bl)]
    if not kept:
        return True   # every location was blacklisted → drop the job
    job["locations"] = kept
    return False


def _list_cache_path(source):
    safe = slug(source["name"])
    return os.path.join(LIST_CACHE_DIR, f"{safe}.json")


def _load_list_cache(source):
    """Return {jobs, spontaneous_url} if we have a fresh cache for this
    source, else None."""
    if LIST_CACHE_TTL_HOURS <= 0:
        return None
    path = _list_cache_path(source)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    age_h = (time.time() - st.st_mtime) / 3600.0
    if age_h > LIST_CACHE_TTL_HOURS:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_list_cache(source, result):
    try:
        os.makedirs(LIST_CACHE_DIR, exist_ok=True)
        with open(_list_cache_path(source), "w", encoding="utf-8") as f:
            json.dump(result, f)
    except OSError:
        pass


def collect(source):
    t_start = time.perf_counter()
    cached = _load_list_cache(source)
    # Treat a tiny cached result (< CACHE_MIN_JOBS) as stale and
    # re-fetch. This is the READ-side complement to the write-side
    # guard added for the Zama bug: before this, if an earlier run had
    # cached [] (pre-fix) or a partial scroll result, we'd keep serving
    # it for the full 6 h TTL. Nuke the file too so subsequent runs
    # don't keep re-checking the same stale blob.
    if cached is not None and len(cached.get("jobs") or []) < CACHE_MIN_JOBS:
        timing(
            f"[{source['name']:22}] cached {len(cached.get('jobs') or [])} jobs "
            f"(< {CACHE_MIN_JOBS}) — treating as stale, re-fetching"
        )
        try:
            os.remove(_list_cache_path(source))
        except OSError:
            pass
        cached = None
    if cached is not None:
        st = os.stat(_list_cache_path(source))
        age_min = (time.time() - st.st_mtime) / 60.0
        result = cached
        source_kind = "cached"
        dt = time.perf_counter() - t_start
        timing(f"[{source['name']:22}] list-cache hit ({age_min:.0f}min old) → {dt*1000:.0f}ms")
    else:
        result = FETCHERS[source["kind"]](source)
        source_kind = "fresh"
        dt = time.perf_counter() - t_start
        timing(f"[{source['name']:22}] fresh fetch → {dt:.1f}s")
    # Re-apply the per-source `queries` filter even on a cache hit. The
    # fetcher applies it at fetch time, but if the user tightens queries
    # between runs (or if the cache was populated when queries=[] by a
    # bug — this really happened once with the edit-companies modal), a
    # cache-hit must not bypass the filter and dump the full unfiltered
    # board on the user.
    _q = source.get("queries") or []
    if _q and result.get("jobs"):
        before = len(result["jobs"])
        result = dict(result)
        result["jobs"] = [j for j in result["jobs"] if matches(j, _q)]
        after = len(result["jobs"])
        if after < before:
            timing(f"[{source['name']:22}] queries filter: {before} → {after}")
    raw_jobs = result["jobs"]
    # Per-source URL rewrites — applied on every run (cache-hit or fresh) so
    # stale cached URLs also get fixed. BeyondTrust's Greenhouse page hides
    # the description on both `job-boards.` and `boards.` layouts; their own
    # careers site at /company/careers/<greenhouse-id> shows it.
    if source.get("slug") == "beyondtrust" and source.get("kind") == "greenhouse":
        for j in raw_jobs:
            m = re.search(r"/jobs/(\d+)", j.get("url") or "")
            if m:
                j["url"] = f"https://www.beyondtrust.com/company/careers/{m.group(1)}"
    for j in raw_jobs:
        j["locations"] = _flatten_locations(j.get("locations"))
    jobs = [
        j for j in raw_jobs
        if not is_title_blacklisted(j) and not is_location_blacklisted(j)
    ]
    jobs = dedup_by_url(jobs)
    jobs.sort(key=lambda j: j["title"].lower())
    final = {
        "jobs": jobs,
        "spontaneous_url": result.get("spontaneous_url"),
        "total_board": result.get("total_board"),
        # Pre-blacklist count from the fetcher — lets the UI distinguish
        # "scraper worked, everything blacklisted" (raw_fetched close to
        # total_board) from "scraper likely broken" (raw_fetched << total_board).
        "raw_fetched": len(raw_jobs),
    }
    if source_kind == "fresh":
        # Don't cache a tiny result — a transient Playwright flake / 403
        # / incomplete scroll was silently poisoning the cache for the
        # full 6 h TTL. First spotted on Zama (dump had 3 links but
        # list_cache/zama.json was []). The threshold also catches the
        # partial-fetch mode where a scrolled board stopped at 3 jobs
        # instead of 50.
        # API sources (greenhouse/ashby) are ~500 ms so re-fetching a
        # small board every run is free; pw sources that LEGITIMATELY
        # have 1-4 jobs re-fetch at ~3-5 s, also acceptable. The cost
        # of a wrong cache (6 h of 0 or near-0 jobs) massively outweighs
        # the cost of a few seconds of re-fetch.
        if len(raw_jobs) >= CACHE_MIN_JOBS:
            _save_list_cache(source, {
                "jobs": raw_jobs,
                "spontaneous_url": result.get("spontaneous_url"),
                "total_board": result.get("total_board"),
            })
        else:
            timing(
                f"[{source['name']:22}] fetched {len(raw_jobs)} jobs "
                f"(< {CACHE_MIN_JOBS}) — NOT caching, will retry next run"
            )
    return final


def slug(name):
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")


def _cap_word(w):
    return TITLE_CASE_OVERRIDES.get(w.lower(), w.capitalize())


def _title_from_slug(s):
    # Strip typical scraper artifacts:
    #  - leading numeric ordinal IDs (Arturia: "6-prospective-application-…")
    #  - leading short hexa/base62 IDs (Corgea: "28hnjyf-", "AxEYjCf-")
    #  - trailing "?param=..." query strings
    #  - trailing "_R<digits>" Workday requisition IDs
    s = re.sub(r"\?.*$", "", s)
    s = re.sub(r"_R\d{4,}$", "", s)
    s = re.sub(r"^\d+[-_]", "", s)
    # Strip a leading ID that either contains a digit OR mixes upper+lowercase
    # letters (so "28hnjyf-", "AxEYjCf-", "flq0ShW-" go but real words like
    # "senior-" or "founding-" don't).
    m = re.match(r"^([A-Za-z0-9]{5,10})[-_]", s)
    if m:
        head = m.group(1)
        if re.search(r"\d", head) or (
            re.search(r"[A-Z]", head) and re.search(r"[a-z]", head)
        ):
            s = s[len(head) + 1:]
    return " ".join(_cap_word(w) for w in re.split(r"[-_]", s) if w)


def _seniority_rank(label):
    if label and label in SENIORITY_RANK:
        return SENIORITY_RANK.index(label)
    return len(SENIORITY_RANK)


_SECTION_HEADER_RE = re.compile(
    r"(?<!\n)\s*(\*\*[A-Z][A-Za-z /]{2,32}:\*\*|(?:Missions?|Team|Salary|"
    r"Responsibilities|Requirements|Qualifications|Compensation|"
    r"Benefits|Location|Tech(?:\s+Stack)?|Stack|Role|About the role|"
    r"Seniority|Experience|Level|"
    r"Minimal profile|Preferred profile|Good fit if|Strong candidates if|"
    r"Nice[- ]to[- ]have|Must[- ]have)\s*:)"
)
_BULLET_INLINE_RE = re.compile(r"(?<!^)(?<!\n)\s+-\s+")


_COMPANY_LEAD_MARKERS = (
    # Anything up to (but not including) one of these markers is company
    # boilerplate we drop.
    r"about\s+the\s+role",
    r"the\s+role",
    r"role\s*:",
    r"missions?\s*:",
    r"responsibilities\s*:",
    r"what\s+you.?ll\s+do",
    r"key\s+responsibilities",
    r"your\s+mission",
    r"in\s+this\s+role",
)


def _strip_company_boilerplate(text):
    """LLMs sometimes ignore the 'no company blurb' rule. If the payload
    starts with a company/mission preamble followed by a real role section
    (e.g. 'About the Role'), drop the preamble.

    Only applies when the prefix looks like prose — if we already see a
    proper `**Section:**` marker before the cut, the text is already
    structured and slicing would break section boundaries."""
    if re.search(r"\*\*[A-Z][A-Za-z /]{2,32}:\*\*", text):
        return text
    lower = text.lower()
    best_cut = -1
    for pat in _COMPANY_LEAD_MARKERS:
        m = re.search(rf"\b{pat}\b", lower)
        if m and (best_cut == -1 or m.start() < best_cut):
            best_cut = m.start()
    if best_cut > 80 and len(text) - best_cut > 150:
        return text[best_cut:].lstrip()
    return text


def _normalize_role_long_text(text):
    """LLMs sometimes return the whole payload on one line, dropping the
    newlines we asked for. Re-inject them around section headers and bullet
    points so the markdown renderer downstream can do its job."""
    s = _strip_company_boilerplate(text)
    # Insert a blank line before each section header if there isn't already one.
    s = _SECTION_HEADER_RE.sub(lambda m: "\n\n" + m.group(1).lstrip(), s)
    # Put each " - <bullet>" on its own line (leave first "- " alone since it
    # comes after a section header).
    s = _BULLET_INLINE_RE.sub("\n- ", s)
    # Collapse >2 consecutive newlines to exactly 2.
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def _render_role_long(text):
    """Turn the LLM's markdown-lite output into HTML: **bold**, bullets,
    blank lines → paragraphs. Escapes everything else."""
    text = _normalize_role_long_text(text)
    lines = text.split("\n")
    out = []
    in_ul = False
    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False
    def format_inline(s):
        return re.sub(
            r"\*\*(.+?)\*\*",
            lambda m: f"<strong>{html.escape(m.group(1))}</strong>",
            html.escape(s),
        )
    for raw in lines:
        line = raw.rstrip()
        if not line:
            close_ul()
            continue
        stripped = line.lstrip()
        if stripped.startswith(("- ", "* ", "• ")):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{format_inline(stripped[2:])}</li>")
        else:
            close_ul()
            # Bare "Missions:" etc. → treat as a section heading.
            if re.match(r"^[A-Z][A-Za-z ]{2,25}:\s*$", stripped):
                out.append(f"<div class=\"role-heading\"><strong>{format_inline(stripped)}</strong></div>")
            else:
                out.append(f"<div>{format_inline(stripped)}</div>")
    close_ul()
    return "".join(out)


def render_html_section(name, visible, rejected_count, board_url, spontaneous_url, liked, queries, rejected_jobs=None, to_apply=None, applied=None, app_rejected=None, history=None, history_jobs=None, fetched_count=None, display_name=None, kind=None):
    to_apply = to_apply or set()
    applied = applied or set()
    app_rejected = app_rejected or {}
    history = history or set()
    history_jobs = history_jobs or []
    # `name` is the stable internal key used for sid / state attribution.
    # `display_name` is what gets rendered in the H1 and board link, so
    # a source like inMusic Brands can display as "inMusic Brands
    # (including Native Instruments)" without breaking job_index/GROUP_OF.
    display = display_name or name
    sid = slug(name)
    def _state_rank(u):
        # Lower rank = higher on the page.
        if u in applied and u not in app_rejected: return 0
        if u in to_apply: return 1
        if u in liked:    return 2
        if u in app_rejected: return 3   # applied → rejected, keep grouped but below fresh applications
        return 4
    ordered = sorted(
        visible,
        key=lambda j: (
            _state_rank(j["url"]),
            0 if j.get("is_new") else 1,
            _seniority_rank(detect_seniority(j["title"])),
            j["title"].lower(),
        ),
    )
    items = []
    for j in ordered:
        title_html = highlight_title(j["title"])
        title_attr = html.escape(j["title"], quote=True)
        # Skip the " — N/A" tail when no locations. Spontaneous applications
        # (and any job with an empty locations list) render without it.
        has_locs = bool(j["locations"])
        locs_txt = ", ".join(j["locations"]) if has_locs else ""
        locs = html.escape(locs_txt)
        locs_attr = html.escape(locs_txt, quote=True)
        url = j["url"]
        url_esc = html.escape(url, quote=True)
        seniority = detect_seniority(j["title"]) or ""
        seniority_attr = html.escape(seniority, quote=True)
        seniority_html = (
            f'<span class="badge seniority">{html.escape(seniority)}</span>' if seniority else ""
        )
        # Typical years-of-experience for this job — purple pill. Resolution order:
        #   1. SENIORITY_XP[company][seniority] — company-specific grid keyed
        #      by seniority LABEL (Senior, Staff, Principal, ...)
        #   2. IC_LEVEL_XP[company][level] — company-specific grid keyed by
        #      INTERNAL LEVEL CODE (L5, E6, IC4, ...) parsed from the title.
        #      Used for companies like Netflix that put "L5" in titles without
        #      ever saying "Senior".
        #   3. SENIORITY_XP_DEFAULT[seniority] — generic startup fallback.
        xp_specific = SENIORITY_XP.get(name, {}).get(seniority, "") if seniority else ""
        ic_from_title = detect_ic_level(j.get("title", ""))
        xp_from_level = IC_LEVEL_XP.get(name, {}).get(ic_from_title, "") if ic_from_title else ""
        xp_txt = (
            xp_specific
            or xp_from_level
            or (SENIORITY_XP_DEFAULT.get(seniority, "") if seniority else "")
        )
        if xp_specific:
            xp_tooltip = f"Typical years-of-experience at {name} for {seniority} — from public leveling guide."
        elif xp_from_level:
            xp_tooltip = f"Typical years-of-experience at {name} for level {ic_from_title} — from public leveling guide."
        elif xp_txt:
            xp_tooltip = f"Generic startup estimate for {seniority} ({name} has no published leveling grid)."
        else:
            xp_tooltip = ""
        xp_html = (
            f'<span class="badge xp" title="{html.escape(xp_tooltip, quote=True)}">🎓 {html.escape(xp_txt)}</span>'
            if xp_txt else ""
        )
        # Salary extracted by the LLM (verbatim, no conversion). Shown as a
        # green badge to the right of the seniority badge.
        salary_txt = (j.get("salary") or "").strip()
        salary_html = (
            f'<span class="badge salary" title="Salary range extracted from the description (verbatim, no conversion)">💰 {html.escape(salary_txt)}</span>'
            if salary_txt else ""
        )
        role_long = j.get("role_long") or ""
        # IC/L/E/M level from the description raw text.
        ic_level = detect_ic_level(j.get("description", ""))
        ic_html = (
            f'<span class="badge ic-level" title="Internal level band from the description">{html.escape(ic_level)}</span>'
            if ic_level else ""
        )
        new_html = (
            '<span class="badge new-badge" title="First seen in this run — not present in the previous run">NEW</span>'
            if j.get("is_new") else ""
        )
        orphan_html = (
            '<span class="badge orphan-badge" title="You marked this job before, but it is no longer listed on the source board. Cached data shown.">REMOVED</span>'
            if j.get("is_orphan") else ""
        )
        # Highlight badges: one per HIGHLIGHTS word actually present in the
        # title / description / role_long. Longest-first so "Codex Security"
        # takes precedence over "Codex" alone when both would match. Decode
        # HTML entities first — otherwise "&mdash;" in a raw description
        # matches the literal word "MDASH" from HIGHLIGHTS and produces a
        # bogus badge (Anthropic's Greenhouse pay-range HTML does this).
        highlight_hits = []
        _search_blob = html.unescape(" ".join([
            j.get("title") or "", j.get("description") or "", role_long,
        ]))
        for kw in sorted(HIGHLIGHTS, key=lambda s: -len(s)):
            if re.search(rf"\b{re.escape(kw)}\b", _search_blob, re.I):
                highlight_hits.append(kw)
        # Suppress a shorter keyword if another kept hit already contains it
        # (case-insensitive). Avoids rendering both "Cybersecurity" and
        # "Security" on the same job — the longer label subsumes the shorter.
        if len(highlight_hits) > 1:
            _lowers = [h.lower() for h in highlight_hits]
            highlight_hits = [
                h for i, h in enumerate(highlight_hits)
                if not any(j != i and _lowers[i] in _lowers[j] and _lowers[i] != _lowers[j]
                           for j in range(len(highlight_hits)))
            ]
        highlight_html = "".join(
            f'<span class="badge highlight-badge" title="Match on '
            f'{html.escape(kw, quote=True)}">{html.escape(kw)}</span>'
            for kw in highlight_hits
        )
        # Score / reason removed from the UI — noisy and the LLM's absolute
        # numbers weren't useful. Only role_long (the structured job summary)
        # is rendered. The scorer still runs (same LLM call produces both) so
        # the cache stays warm and role_long remains available.
        score_html = ""
        # role_long section removed — the LLM now only extracts salary.
        score_summary_html = ""
        desc = sanitize_html(j["description"])
        desc_html = desc if desc else '<em>No description available.</em>'
        is_liked = url in liked
        is_toapply = url in to_apply
        is_applied = url in applied
        is_app_rejected = url in app_rejected
        like_state = "on" if is_liked else "off"
        like_btn = (
            f'<button class="like" data-url="{url_esc}" data-state="{like_state}" title="Like">+1</button>'
            if url else ""
        )
        reject_btn = (
            f'<button class="reject" data-url="{url_esc}" title="Reject">×</button>'
            if url else ""
        )
        # "Review" button: only visible on jobs with no state yet. Clicking
        # appends the title to planning/TOREVIEW.md AND rejects the URL, so the user
        # can later batch-add common patterns to TITLE_BLACKLIST.
        review_btn = (
            f'<button class="review" data-url="{url_esc}" data-title="{title_attr}" '
            f'title="Queue title for review (writes to planning/TOREVIEW.md) and remove">R</button>'
            if url else ""
        )
        # TA / ✓ / R / K are always rendered (greyed out via CSS when
        # data-state="off") so every job row has the same horizontal
        # button layout — titles line up across rows regardless of state.
        keep_btn = (
            f'<button class="keep" data-url="{url_esc}" '
            f'title="Keep in history (archive without rejecting)">K</button>'
            if url else ""
        )
        toapply_state = "on" if is_toapply else "off"
        toapply_btn = (
            f'<button class="toapply" data-url="{url_esc}" data-state="{toapply_state}" '
            f'title="Mark as To apply">TA</button>'
            if url else ""
        )
        applied_state = "on" if is_applied else "off"
        applied_meta = applied.get(url, {}) if isinstance(applied, dict) and is_applied else {}
        applied_tooltip = (
            f"Applied on {applied_meta['ts']}" if applied_meta.get("ts")
            else "Mark as Applied"
        )
        applied_btn = (
            f'<button class="applied" data-url="{url_esc}" data-state="{applied_state}" '
            f'title="{html.escape(applied_tooltip, quote=True)}">\u2713</button>'
            if url else ""
        )
        app_rej_state = "on" if is_app_rejected else "off"
        app_rej_meta = app_rejected.get(url, {}) if is_app_rejected else {}
        # Full tooltip: timestamp, reason, feedback (each on its own line).
        # The native `title` attribute renders newlines as line breaks in every
        # modern browser tooltip, so the whole story fits into one hover.
        if is_app_rejected:
            _lines = [f"Rejected on {app_rej_meta.get('ts','')}"]
            if app_rej_meta.get("reason"):
                _lines.append(f"Reason: {app_rej_meta['reason']}")
            if app_rej_meta.get("feedback"):
                _lines.append(f"Feedback: {app_rej_meta['feedback']}")
            app_rej_tooltip = html.escape("\n".join(_lines), quote=True)
        else:
            app_rej_tooltip = "Mark this application as rejected by the company"
        app_rej_btn = (
            f'<button class="app-rejected-btn" data-url="{url_esc}" data-state="{app_rej_state}" '
            f'title="{app_rej_tooltip}">R</button>'
            if url else ""
        )
        app_rej_panel_html = ""
        open_link = (
            f'<a href="{url_esc}" target="_blank" rel="noopener">Open original ↗</a>'
            if url else ""
        )
        # Compact "↗" link shown in the summary row itself (before the location)
        # so we always see it without opening the description.
        summary_link = (
            f'<a class="summary-link" href="{url_esc}" target="_blank" rel="noopener" '
            f'title="Open original ↗" onclick="event.stopPropagation()">↗</a>'
            if url else ""
        )
        # "$" button (right of the arrow) — opens a prompt to set a manual
        # salary range. Persisted client-side in localStorage; overrides the
        # LLM-extracted value in the badge.
        salary_edit_btn = (
            f'<button class="salary-edit" data-url="{url_esc}" '
            f'title="Set salary range manually" '
            f'onclick="event.stopPropagation()">$</button>'
            if url else ""
        )
        # "?" button — opens claude.ai/new in a new tab, pre-filled with a
        # prompt asking whether this job is a good fit. Job title, company,
        # location, salary and description are pulled from the DOM client-side.
        ask_claude_btn = (
            f'<button class="ask-claude" data-url="{url_esc}" '
            f'data-title="{title_attr}" '
            f'data-company="{html.escape(name, quote=True)}" '
            f'title="Ask Claude whether this role fits your profile" '
            f'onclick="event.stopPropagation()">?</button>'
            if url else ""
        )
        # Highest state wins for the <li> visual class (used to move to top).
        # app-rejected takes precedence over applied — the row goes grey.
        state_class = ""
        if is_app_rejected:
            state_class = "app-rejected"
        elif is_applied:
            state_class = "applied"
        elif is_toapply:
            state_class = "toapply"
        elif is_liked:
            state_class = "liked"
        li_class = ("job " + state_class).strip()
        items.append(
            f'    <li class="{li_class}" data-seniority="{seniority_attr}" '
            f'data-locations="{locs_attr}">'
            f'{review_btn}{reject_btn}{like_btn}{toapply_btn}{applied_btn}{app_rej_btn}{keep_btn}<details>\n'
            f'      <summary title="{title_attr}{" — " + locs_attr if has_locs else ""}">'
            f'{score_html}'
            f'<span class="title">{title_html}</span>'
            f'{new_html}{orphan_html}{seniority_html}{xp_html}{ic_html}{salary_html}{highlight_html}'
            f'{summary_link}{salary_edit_btn}{ask_claude_btn}'
            f'{"".join(["<span class=\"locs\"> — ", locs, "</span>"]) if has_locs else ""}'
            f'</summary>\n'
            f'      <div class="description">\n'
            f'        <div class="desc-actions">{open_link}</div>\n'
            f'        <div class="desc-body">{desc_html}</div>\n'
            f'      </div>\n'
            f'    </details>{app_rej_panel_html}{score_summary_html}</li>'
        )
    ul_content = "\n".join(items) if items else ""
    visible_count = len(visible)
    total_bit = ""
    if fetched_count is not None:
        total_bit = (
            f' · <span class="t" title="Total open positions on this board, '
            f'before our query filter and before rejects.">'
            f'{fetched_count} total</span>'
        )
    counter = (
        f'<span class="counter">'
        f'<span class="v">{visible_count}</span> visible · '
        f'<span class="r">{rejected_count}</span> rejected'
        f'{total_bit}'
        f'</span>'
    )
    # Per-section bulk reject: rejects only untouched jobs in this section
    # (the client-side handler filters by :not(.liked):not(.toapply):not(.applied):not(.app-rejected),
    # mirroring the CSS that hides the per-row × on touched rows).
    reject_section_btn = (
        f'<button class="reject-section" data-sid="{sid}" '
        f'data-name="{html.escape(display, quote=True)}" '
        f'title="Reject every untouched job in this section">×</button>'
    )
    # Unfollow: drop this company from the user's sources. Rewrites
    # data/user_config.py; takes effect on the next refresh. `data-name`
    # carries the internal SOURCES key (not display), since that's what
    # the server matches against.
    unfollow_btn = (
        f'<button class="unfollow-company" data-sid="{sid}" '
        f'data-name="{html.escape(name, quote=True)}" '
        f'title="Unfollow this company — stop watching its board">🚫</button>'
    )
    board_link = (
        f'<a class="board-link" href="{html.escape(board_url, quote=True)}" '
        f'target="_blank" rel="noopener">{html.escape(display)}</a>'
        if board_url else html.escape(display)
    )
    # Company info line: blurb + employees + revenue. Only rendered when
    # we have data for the company; empty otherwise.
    info = COMPANY_INFO.get(name) or {}
    info_parts = []
    if info.get("blurb"):
        info_parts.append(html.escape(info["blurb"]))
    if info.get("employees") and info["employees"] != "n/a":
        info_parts.append(f'👥 {html.escape(info["employees"])}')
    if info.get("revenue") and info["revenue"] != "n/a":
        info_parts.append(f'💰 {html.escape(info["revenue"])}')
    company_info_row = (
        f'  <div class="company-info">{" · ".join(info_parts)}</div>\n'
        if info_parts else ""
    )
    if spontaneous_url:
        # +1 → TA → ✓ → R chain, same as regular job rows. All four state
        # stores are keyed by URL so the spontaneous URL just piggybacks on
        # the same liked.json / to_apply.json / applied.json / app_rejected.json.
        _sp_url_esc = html.escape(spontaneous_url, quote=True)
        _sp_liked   = spontaneous_url in liked
        _sp_toapply = spontaneous_url in to_apply
        _sp_applied = spontaneous_url in applied
        _sp_app_rej = spontaneous_url in app_rejected
        # +1 / TA / ✓ / R are always rendered (greyed via CSS when
        # data-state="off") so every spontaneous row has the same
        # horizontal button layout. This matches the li.job behavior and
        # keeps alignment consistent in the Ranked view.
        _sp_like_btn = (
            f'<button class="like spontaneous-like" data-url="{_sp_url_esc}" '
            f'data-state="{"on" if _sp_liked else "off"}" '
            f'title="Like this spontaneous application">+1</button>'
        )
        _sp_toapply_btn = (
            f'<button class="toapply" data-url="{_sp_url_esc}" '
            f'data-state="{"on" if _sp_toapply else "off"}" '
            f'title="Mark as To apply">TA</button>'
        )
        _sp_applied_meta = applied.get(spontaneous_url, {}) if isinstance(applied, dict) and _sp_applied else {}
        _sp_applied_tooltip = (
            f"Applied on {_sp_applied_meta['ts']}" if _sp_applied_meta.get("ts")
            else "Mark as Applied"
        )
        _sp_applied_btn = (
            f'<button class="applied" data-url="{_sp_url_esc}" '
            f'data-state="{"on" if _sp_applied else "off"}" '
            f'title="{html.escape(_sp_applied_tooltip, quote=True)}">\u2713</button>'
        )
        _sp_app_rej_meta = app_rejected.get(spontaneous_url, {}) if _sp_app_rej else {}
        if _sp_app_rej:
            _lines = [f"Rejected on {_sp_app_rej_meta.get('ts','')}"]
            if _sp_app_rej_meta.get("reason"):
                _lines.append(f"Reason: {_sp_app_rej_meta['reason']}")
            if _sp_app_rej_meta.get("feedback"):
                _lines.append(f"Feedback: {_sp_app_rej_meta['feedback']}")
            _sp_ar_tooltip = html.escape("\n".join(_lines), quote=True)
        else:
            _sp_ar_tooltip = "Mark this application as rejected by the company"
        _sp_app_rej_btn = (
            f'<button class="app-rejected-btn" data-url="{_sp_url_esc}" '
            f'data-state="{"on" if _sp_app_rej else "off"}" '
            f'title="{_sp_ar_tooltip}">R</button>'
        )
        spontaneous = (
            f'{_sp_like_btn}{_sp_toapply_btn}{_sp_applied_btn}{_sp_app_rej_btn}'
            f'<a class="spontaneous-link" href="{_sp_url_esc}" '
            f'target="_blank" rel="noopener" title="Spontaneous application">'
            f'✉ Spontaneous</a>'
        )
    else:
        spontaneous = ""
    # Query pills are editable: × on each pill removes it, the trailing +
    # pops an inline input to add a new word. Changes POST to
    # /update-queries which rewrites data/user_config.py; the new filter
    # applies on the next refresh. We always render the .queries wrapper
    # (even when the list is empty) so the + button is reachable for
    # sources the user hasn't customised yet.
    pills_html = "".join(
        f'<span class="query-pill" data-q="{html.escape(q, quote=True)}">'
        f'{html.escape(q)}'
        f'<button class="query-remove" type="button" '
        f'title="Remove this query word" aria-label="Remove">×</button>'
        f'</span>'
        for q in (queries or [])
    )
    # Sources that need queries to work (Apple/Microsoft/Meta/Phenom
    # iterate `for q in queries` with no fallback) get a data attribute
    # that drives a CSS-only "⚠ keyword required" chip when the pill
    # list is empty. Updates automatically as pills come and go — no JS
    # needed because the ::before uses :has().
    _req_attr = (
        ' data-query-required="1"' if kind in _QUERY_REQUIRED_KINDS else ""
    )
    _tooltip = (
        "This source only returns jobs that match a query word. "
        "Add at least one (e.g. 'security', 'cryptography') or no jobs will be fetched. "
        "Changes save automatically — hit refresh to apply."
        if kind in _QUERY_REQUIRED_KINDS else
        "Board-side search queries. Add words to narrow what gets "
        "fetched for this company; empty = fetch everything. Changes save "
        "automatically — hit refresh to apply."
    )
    query_pills = (
        f'<span class="queries" data-source="{html.escape(name, quote=True)}"'
        f'{_req_attr} '
        f'title="{html.escape(_tooltip, quote=True)}">'
        f'{pills_html}'
        f'<button class="query-add" type="button" '
        f'title="Add a query word" aria-label="Add query">+</button>'
        f'</span>'
    )
    # Tint the row with the highest-priority state, matching li.job classes
    # (app-rejected > applied > toapply > liked). Client keeps it in sync on
    # every state-button toggle — see wireStateButton.
    _spontaneous_cls = "spontaneous-row"
    if spontaneous_url:
        if spontaneous_url in app_rejected:
            _spontaneous_cls += " app-rejected"
        elif spontaneous_url in applied:
            _spontaneous_cls += " applied"
        elif spontaneous_url in to_apply:
            _spontaneous_cls += " toapply"
        elif spontaneous_url in liked:
            _spontaneous_cls += " liked"
    spontaneous_row = f'  <div class="{_spontaneous_cls}">{spontaneous}</div>\n' if spontaneous else ""

    # Rejected jobs collapsible block — one line per rejected job in this
    # section, each with a "Restore" button.
    rejected_block = ""
    if rejected_jobs:
        rej_items = []
        for j in sorted(rejected_jobs, key=lambda j: j["title"].lower()):
            url = j["url"]
            url_esc = html.escape(url, quote=True)
            title_esc = html.escape(j["title"])
            locs_txt = ", ".join(j["locations"]) if j["locations"] else "N/A"
            locs_esc = html.escape(locs_txt)
            # Salary badge for rejected jobs too — useful to spot mispriced
            # matches you'd revisit. Same green badge as the visible list.
            sal_txt = (j.get("salary") or "").strip()
            sal_html = (
                f'<span class="badge salary" title="Salary from the LLM extractor">'
                f'💰 {html.escape(sal_txt)}</span>'
                if sal_txt else ""
            )
            rej_items.append(
                f'      <li class="rejected-job">'
                f'<button class="restore" data-url="{url_esc}" title="Restore">↩</button>'
                f'<a href="{url_esc}" target="_blank" rel="noopener">{title_esc}</a>'
                f'{sal_html}'
                f'<span class="locs"> — {locs_esc}</span></li>'
            )
        rejected_block = (
            f'  <details class="rejected-block" data-section="{sid}">\n'
            f'    <summary>{len(rejected_jobs)} rejected in this section — click to expand</summary>\n'
            f'    <ul class="rejected-list">\n' + "\n".join(rej_items) + '\n'
            f'    </ul>\n'
            f'  </details>\n'
        )

    # History block — same shape as rejected, different label and store.
    history_block = ""
    if history_jobs:
        hist_items = []
        for j in sorted(history_jobs, key=lambda j: j["title"].lower()):
            url = j["url"]
            url_esc = html.escape(url, quote=True)
            title_esc = html.escape(j["title"])
            locs_txt = ", ".join(j["locations"]) if j["locations"] else "N/A"
            locs_esc = html.escape(locs_txt)
            sal_txt = (j.get("salary") or "").strip()
            sal_html = (
                f'<span class="badge salary" title="Salary from the LLM extractor">'
                f'💰 {html.escape(sal_txt)}</span>'
                if sal_txt else ""
            )
            hist_items.append(
                f'      <li class="history-job">'
                f'<button class="unkeep" data-url="{url_esc}" title="Remove from history (bring back to the main list)">↩</button>'
                f'<a href="{url_esc}" target="_blank" rel="noopener">{title_esc}</a>'
                f'{sal_html}'
                f'<span class="locs"> — {locs_esc}</span></li>'
            )
        history_block = (
            f'  <details class="history-block" data-section="{sid}">\n'
            f'    <summary>{len(history_jobs)} kept in history — click to expand</summary>\n'
            f'    <ul class="history-list">\n' + "\n".join(hist_items) + '\n'
            f'    </ul>\n'
            f'  </details>\n'
        )

    # Sections with a spontaneous application link get `has-spontaneous`;
    # applyFilters keeps them visible even when 0 visible jobs pass filters,
    # so the user can still see the ✉ link and apply spontaneously.
    section_cls = "company-section" + (" has-spontaneous" if spontaneous_url else "")
    return (
        f'  <section class="{section_cls}" data-section="{sid}">\n'
        f'  <h1 id="{sid}">{board_link} {query_pills} {counter} {reject_section_btn} {unfollow_btn}</h1>\n'
        f'{company_info_row}'
        f'{spontaneous_row}'
        f'{rejected_block}'
        f'{history_block}'
        f'  <ul data-section="{sid}">\n{ul_content}\n  </ul>\n'
        f'  </section>'
    )


TABS = [
    ("all",         "All"),
    ("new",         "New"),
    ("untouched",   "Untouched"),
    ("ranked",      "Ranked"),
    ("spontaneous", "Spontaneous"),
    ("liked",       "Liked"),
    ("toapply",     "To Apply"),
    ("pipeline",    "Pipeline"),
]


def render_html_tabs():
    """Primary view-mode tabs. Each tab is a preset that drives the per-state
    Show toggles + an optional body class for extra client-side filtering.
    The JS side (TAB_PRESETS, activateTab) owns the semantics; this just
    emits the buttons. The active class is applied by JS after reading the
    last-used tab from localStorage.

    The R / AI / ⚙ action buttons live inside the tabs nav (pushed to
    the right via .tab-actions) so they stay on the same visual row as
    the tabs — matches the user's layout expectation."""
    # The tooltip surfaces the digit shortcut (1..8) so the user can
    # discover it just by hovering a tab. Positional: tab index + 1.
    buttons = "\n".join(
        f'    <button type="button" class="tab" data-tab="{tid}" '
        f'title="{html.escape(label)} ({i + 1})">{html.escape(label)}</button>'
        for i, (tid, label) in enumerate(TABS)
    )
    # Keep the shortcut suffix in sync with the Cmd+X map in the keydown
    # handler further down. The ⌘ glyph is the Mac convention; Ctrl works
    # too (both are checked in the listener).
    actions = (
        '    <div class="tab-actions">\n'
        '      <button type="button" class="refresh-btn" id="refresh-btn" '
        'title="Re-fetch all sources (equivalent to --clear-cache list), then reload the page. (⌘R)" aria-label="Refresh">'
        '<span class="mi refresh-icon" aria-hidden="true">refresh</span></button>\n'
        '      <button type="button" class="refresh-btn claude-c-btn" id="claude-score-all" '
        'title="Ask your LLM to rate every visible job /10 — opens a new tab with the batched prompt and a dialog to paste the response back. (⌘I) rates every visible job; (⌘U) rates only the ones that don\'t have a score yet." aria-label="AI fit scores">'
        '<span class="mi" aria-hidden="true">auto_awesome</span></button>\n'
        '      <button type="button" class="refresh-btn edit-sources-btn" id="edit-sources-setup" '
        'title="Edit the companies you track. The badge counts new companies added to the catalog since you last saved. (⌘E)" aria-label="Edit companies">'
        '<span class="mi" aria-hidden="true">domain</span>'
        '<span class="new-companies-badge" id="new-companies-badge" style="display:none">0</span>'
        '</button>\n'
        '      <a class="refresh-btn claude-chat-url-btn" id="settings-link" href="/settings" '
        'title="Settings: row display, AI assistant, scraping. (⌘,)" aria-label="Settings">'
        '<span class="mi" aria-hidden="true">settings</span></a>\n'
        '    </div>'
    )
    board_title_html = (
        f'    <span class="board-title" id="board-title">'
        f'{html.escape(_cfg.BOARD_TITLE)}</span>\n'
    )
    return (
        '  <nav class="tabs" id="tabs">\n'
        + board_title_html
        + buttons + "\n"
        + actions + "\n"
        + '  </nav>'
    )


def render_html_nav(entries):
    """Groups nav buttons per GROUP_ORDER, with a labelled row per group.

    Each entry is (name, visible_count, fetched_count, error?). We emit one
    of four classes so the CSS colour tells you WHY a company shows (0):
      - has-jobs   : at least one job passes the current filters (green)
      - no-match   : the source returned jobs but none pass the filters or
                     all were rejected (orange — worth revisiting)
      - broken     : the scraper crashed with an exception (red — needs fix)
      - no-fetched : the source itself returned zero and did not crash
                     (grey — likely blocked / URL changed / empty board)
    """
    def _btn_class(visible, fetched, error):
        if error:            return "broken"
        if visible > 0:      return "has-jobs"
        if fetched > 0:      return "no-match"
        return "no-fetched"
    by_group = {g: [] for g in GROUP_ORDER}
    for entry in entries:
        # Back-compat: entries may be 2-, 3-, 4- or 5-tuples. Pad to 5 with defaults.
        padded = tuple(entry) + ("",) * (5 - len(entry)) if len(entry) < 5 else tuple(entry)
        name, visible_count, fetched_count, error, display_name = padded[:5]
        group = GROUP_OF.get(name, "Other")
        by_group.setdefault(group, []).append((name, visible_count, fetched_count, error, display_name))
    rows = []
    for group in GROUP_ORDER + [g for g in by_group if g not in GROUP_ORDER]:
        items = by_group.get(group) or []
        if not items:
            continue
        items.sort(key=lambda kv: kv[0].lower())
        def _btn_html(name, visible_count, fetched_count, error, display_name):
            cls = _btn_class(visible_count, fetched_count, error)
            tooltip = {
                "broken":     f"Scraper crashed: {error}" if error else "Scraper crashed",
                "no-fetched": "Source returned 0 jobs this run — probably blocked, URL changed, or the board is empty.",
                "no-match":   f"Source returned {fetched_count} jobs but all were filtered out (blacklist / rejected / queries).",
                "has-jobs":   f"{visible_count} job(s) match your filters.",
            }.get(cls, "")
            title_attr = f' title="{html.escape(tooltip, quote=True)}"' if tooltip else ""
            label = display_name or name
            return (
                f'<a class="nav-btn {cls}" '
                f'href="#{slug(name)}" data-fetched="{fetched_count}"{title_attr}>'
                f'{html.escape(label)} '
                f'(<span class="nav-count">{visible_count}</span>)</a>'
            )
        buttons = "".join(
            _btn_html(name, visible_count, fetched_count, error, display_name)
            for name, visible_count, fetched_count, error, display_name in items
        )
        rows.append(
            '    <div class="nav-row">'
            f'<a class="nav-group-label" href="#group-{slug(group)}">{html.escape(group)}</a>'
            f'<span class="nav-btns">{buttons}</span>'
            '</div>'
        )
    return '  <nav class="nav">\n' + "\n".join(rows) + "\n  </nav>"


def _group_locations(locations):
    groups = {}
    for loc in locations:
        low = loc.lower()
        if "remote" in low or "friendly" in low:
            country = "Remote"
        elif "," in loc:
            tail = loc.rsplit(",", 1)[1].strip()
            # If the "country" segment is actually a known city (e.g. "New
            # York City", "San Francisco"), don't group under it — the raw
            # location is malformed. Reroute via _CITY_TO_COUNTRY of the
            # first segment.
            tail_key = _city_key(tail)
            if tail_key in _CITY_TO_COUNTRY:
                country = _CITY_TO_COUNTRY[tail_key]
            else:
                normalized = _normalize_country(tail)
                country = normalized or tail
        else:
            # Country-only entries (e.g. "Canada") go in that country's group.
            normalized = _normalize_country(loc)
            if normalized and normalized.lower() != loc.strip().lower():
                country = normalized
            elif loc.strip().lower() in _KNOWN_COUNTRIES:
                country = normalized
            else:
                # Bare city with no country info: look up known city → country.
                ck = _city_key(loc)
                if ck in _CITY_TO_COUNTRY:
                    country = _CITY_TO_COUNTRY[ck]
                else:
                    country = "Other"
        groups.setdefault(country, []).append(loc)
    for k in groups:
        groups[k] = sorted(set(groups[k]))
    return sorted(groups.items(), key=lambda kv: (kv[0] == "Other", kv[0].lower()))


def _render_location_picker(locations):
    if not locations:
        return ""
    blacklist_lower = {b.lower() for b in LOCATION_BLACKLIST}
    blocks = []
    for country, locs in _group_locations(locations):
        # Hide entire country groups blacklisted by the user.
        if country.lower() in blacklist_lower:
            continue
        # Also drop any city where the raw string contains a blacklisted term.
        locs = [
            l for l in locs
            if not any(b in l.lower() for b in blacklist_lower)
        ]
        # Drop entries where the "city" segment is just the country name
        # (e.g. "USA" bare) — those are noise as a city checkbox.
        locs = [
            l for l in locs
            if (l.rsplit(",", 1)[0].strip() if "," in l else l).strip().lower()
            != country.strip().lower()
        ]
        if not locs:
            continue
        checks = "".join(
            f'<label class="loc-check"><input type="checkbox" class="loc-cb" '
            f'data-value="{html.escape(l, quote=True)}"> '
            f'{html.escape(l.rsplit(",", 1)[0].strip() if "," in l else l)}</label>'
            for l in locs
        )
        blocks.append(
            f'      <div class="loc-group">'
            f'<button type="button" class="loc-country loc-country-toggle" '
            f'title="Toggle all cities in this country">{html.escape(country)}</button>'
            f'<div class="loc-cities">{checks}</div></div>'
        )
    if not blocks:
        return ""
    return (
        '      <div class="loc-panel">\n'
        '        <div class="loc-bulk">'
        '<button type="button" class="loc-bulk-btn" id="loc-all">All</button>'
        '<button type="button" class="loc-bulk-btn" id="loc-none">None</button>'
        '</div>\n'
        + "\n".join(blocks) + "\n"
        '      </div>\n'
    )


def _seniority_check(label):
    return (
        f'      <label class="filter-check"><input type="checkbox" '
        f'class="seniority-toggle" data-seniority="{html.escape(label, quote=True)}" checked> '
        f'{html.escape(label)}</label>'
    )


def render_html_filters(seniority_labels, all_locations=None):
    # Seniority filter checkboxes (Management / IC / Other groups) were
    # removed on user request. The JS still queries `.seniority-toggle`
    # elements but harmlessly finds none, so applyFilters keeps working.
    blocks = []
    return (
        '  <section class="filters">\n'
        + ("\n".join(blocks) + "\n" if blocks else "") +
        '    <div class="filter-group">\n'
        '      <span class="filter-label">Location:</span>\n'
        '      <input type="text" id="loc-filter" placeholder="Paris or SF, USA (use + for AND)">\n'
        + _render_location_picker(all_locations or []) +
        '    </div>\n'
        '    <div class="filter-group full-row">\n'
        '      <span class="filter-label">Title:</span>\n'
        '      <input type="text" id="title-filter" placeholder="security + engineer or manager">\n'
        '    </div>\n'
        '    <div class="filter-group full-row">\n'
        '      <span class="filter-label">Text:</span>\n'
        '      <input type="text" id="text-filter" placeholder="kubernetes + rust or golang">\n'
        '    </div>\n'
        '    <div class="filter-group">\n'
        '      <label class="filter-check"><input type="checkbox" id="hide-empty-toggle"> Hide sections with no matching jobs</label>\n'
        '      <label class="filter-check"><input type="checkbox" id="hide-spontaneous-toggle"> Hide Spontaneous which are not liked</label>\n'
        '    </div>\n'
        '  </section>'
    )


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>__BOARD_TITLE__</title>
  <!-- Google Material Symbols — used for the top-right action buttons
       (refresh / AI / 🏢 edit / ⚙ settings). Loaded with display=block
       so the page doesn't flicker swapping emojis to real icons. -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet"
    href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,500,0,0&display=block">
  <style>
    /* Google Material Symbols helper. Applied to the <span class="mi">…</span>
       elements inside action buttons so we get crisp vector icons at
       any zoom. The font ligatures turn plain words like "refresh" or
       "settings" into the right glyph automatically. */
    .mi {
      font-family: 'Material Symbols Rounded', sans-serif;
      font-weight: 500;
      font-style: normal;
      font-size: 1.25rem;
      line-height: 1;
      letter-spacing: normal;
      text-transform: none;
      display: inline-block;
      white-space: nowrap;
      direction: ltr;
      -webkit-font-smoothing: antialiased;
      font-feature-settings: 'liga';
      vertical-align: middle;
    }
    /* GitHub light palette */
    :root {
      color-scheme: light;
      --bg: #ffffff;
      --bg-subtle: #f6f8fa;
      --bg-inset: #eaeef2;
      --border: #d0d7de;
      --border-muted: #d8dee4;
      --fg: #1f2328;
      --fg-muted: #656d76;
      --fg-subtle: #6e7781;
      --accent: #0969da;
      --accent-emphasis: #0550ae;
      --success: #1a7f37;
      --success-emphasis: #116329;
      --attention: #9a6700;
      --severe: #bc4c00;
      --danger: #d1242f;
      --danger-emphasis: #a40e26;
    }
    /* Shrink the root font-size 3px below the browser default (16 → 13).
       Every rem-based size in this stylesheet scales down proportionally so
       we get ~19% more content per screenful with no per-rule tweaking. */
    html { scroll-behavior: smooth; font-size: 12px; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
      max-width: 960px;
      margin: 2rem auto;
      padding: 0 1rem;
      background: var(--bg);
      color: var(--fg);
      line-height: 1.5;
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    em { color: var(--fg-muted); }
    mark {
      background: #fff8c5;
      color: #1f2328;
      padding: 0 0.15rem;
      border-radius: 3px;
    }
    body.no-highlights mark {
      background: transparent;
      color: inherit;
      padding: 0;
      border-radius: 0;
    }

    h1 {
      display: flex;
      align-items: baseline;
      gap: 0.75rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.3rem;
      margin-top: 2rem;
      font-size: 1.5rem;
    }
    h1 .board-link { color: var(--severe); text-decoration: none; }
    h1 .board-link:hover { text-decoration: underline; }
    .counter {
      font-size: 0.85rem;
      font-weight: normal;
      color: var(--fg-muted);
    }
    .counter .v { color: var(--fg); }
    .counter .r { color: var(--danger); }
    .counter .t { color: var(--fg-muted); }
    .queries {
      display: inline-flex;
      gap: 0.3rem;
      font-size: 0.75rem;
      font-weight: normal;
    }
    .query-pill {
      padding: 0.05rem 0.5rem;
      border: 1px solid var(--border);
      border-radius: 2em;
      color: var(--fg-muted);
      background: var(--bg-subtle);
      font-weight: normal;
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
    }
    .query-pill .query-remove {
      background: transparent;
      border: none;
      color: var(--fg-muted);
      cursor: pointer;
      font-size: 0.95rem;
      line-height: 1;
      padding: 0;
      margin-left: 0.1rem;
      border-radius: 50%;
    }
    .query-pill .query-remove:hover { color: var(--danger); }
    .queries .query-add {
      padding: 0.05rem 0.5rem;
      border: 1px dashed var(--border);
      border-radius: 2em;
      font-size: 0.75rem;
      background: transparent;
      color: var(--fg-muted);
      cursor: pointer;
      font-weight: normal;
    }
    .queries .query-add:hover {
      color: var(--accent);
      border-color: var(--accent);
    }
    .queries .query-input {
      font-size: 0.75rem;
      padding: 0.05rem 0.5rem;
      border: 1px solid var(--accent);
      border-radius: 2em;
      outline: none;
      min-width: 6rem;
      color: var(--fg);
      background: var(--bg);
      font-family: inherit;
    }
    /* Red "keyword required" chip — rendered via ::before so it tracks
       the empty-pill state automatically (no JS). Only shown on sources
       whose fetcher iterates `for q in queries` with no empty-string
       fallback: Apple, Microsoft, Meta, Phenom-based big-techs.
       An empty query list on those = 0 jobs fetched, silently. */
    .queries[data-query-required="1"]:not(:has(.query-pill))::before {
      content: "⚠ keyword required";
      padding: 0.05rem 0.5rem;
      border: 1px solid var(--danger);
      border-radius: 2em;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--danger);
      background: rgba(207, 34, 46, 0.08);
    }
    .spontaneous-row {
      margin: 0.4rem 0 0.8rem;
      display: flex; align-items: center; gap: 0.5rem;
    }
    /* +1 button next to the ✉ Spontaneous link inherits .like styling. */
    button.spontaneous-like { align-self: center; }
    /* Tint the spontaneous row with the same palette as li.job for each
       state, so it visually behaves like a regular job row. */
    .spontaneous-row.liked,
    .spontaneous-row.toapply,
    .spontaneous-row.applied,
    .spontaneous-row.app-rejected {
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    .spontaneous-row.liked {
      background: rgba(63, 185, 80, 0.08);
      border-left: 3px solid var(--success);
    }
    .spontaneous-row.toapply {
      background: rgba(207, 34, 46, 0.08);
      border-left: 3px solid var(--danger);
    }
    .spontaneous-row.applied {
      background: rgba(130, 80, 223, 0.08);
      border-left: 3px solid #8250df;
    }
    .spontaneous-row.app-rejected {
      background: rgba(87, 96, 106, 0.15);
      border-left: 3px solid #57606a;
      opacity: 0.6;
    }
    .company-info {
      margin: 0.2rem 0 0.6rem;
      font-size: 0.82rem;
      color: var(--fg-muted);
      font-style: italic;
    }
    .spontaneous-link {
      display: inline-block;
      font-size: 0.9rem;
      font-weight: 600;
      padding: 0.35rem 0.9rem;
      border: 1.5px solid var(--severe);
      border-radius: 6px;
      color: #ffffff;
      background: var(--severe);
    }
    .spontaneous-link:hover {
      background: #a44215;
      border-color: #a44215;
      text-decoration: none;
    }

    /* --- Primary tabs (All / Liked / To Apply / Pipeline / Top fit /
       Spontaneous / New). Driven by JS: activateTab() sets the active
       class and the per-tab body class, then calls applyFilters(). */
    .tabs {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.3rem;
      margin: 0.8rem 0 0.6rem;
      padding-bottom: 0.4rem;
      border-bottom: 1px solid var(--border);
    }
    /* User-configurable title at the far left of the tabs row. Set in
       the ⚙ Settings page; persisted to data/user_config.py.
       margin-right: 1.2rem opens breathing room before the tab buttons. */
    .board-title {
      font-weight: 700;
      font-size: 1rem;
      color: var(--fg);
      margin-right: 1.2rem;
      white-space: nowrap;
    }
    /* R / AI / ⚙ action buttons live at the right end of the tabs
       row — margin-left: auto pushes them to the far right. */
    .tab-actions {
      margin-left: auto;
      display: flex;
      gap: 0.3rem;
    }
    .tab {
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      padding: 0.45rem 1rem;
      border-radius: 6px 6px 0 0;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.95rem;
      color: var(--fg);
    }
    .tab:hover:not(.active) {
      background: var(--bg-inset);
      border-color: var(--fg-subtle);
    }
    .tab.active {
      background: var(--accent);
      color: #ffffff;
      border-color: var(--accent-emphasis);
    }
    /* Per-state color accents on the tab labels — keeps the same palette
       the old top-bar Liked / To Apply / Applied / Rejected buttons used
       so the Pipeline/Liked/To Apply tabs are recognizable at a glance.
       The accent is applied as a left border + text color in the inactive
       state. When .active, the active-tab fill wins over these. */
    .tab[data-tab="liked"]       { color: var(--success); border-left: 4px solid var(--success); }
    .tab[data-tab="toapply"]     { color: var(--danger);  border-left: 4px solid var(--danger); }
    .tab[data-tab="pipeline"]    { color: #8250df;        border-left: 4px solid #8250df; }
    .tab[data-tab="ranked"]      { color: #0969da;        border-left: 4px solid #0969da; }
    .tab[data-tab="spontaneous"] { color: var(--severe);  border-left: 4px solid var(--severe); }
    .tab[data-tab="new"]         { color: var(--danger-emphasis); border-left: 4px solid var(--danger-emphasis); }
    .tab[data-tab="untouched"]   { color: var(--fg-muted);        border-left: 4px solid var(--fg-muted); }
    .tab[data-tab="liked"].active       { background: var(--success);        border-color: var(--success-emphasis); }
    .tab[data-tab="toapply"].active     { background: var(--danger);         border-color: var(--danger-emphasis); }
    .tab[data-tab="pipeline"].active    { background: #8250df;               border-color: #6639ba; }
    .tab[data-tab="ranked"].active      { background: #0969da;               border-color: var(--accent-emphasis); }
    .tab[data-tab="spontaneous"].active { background: var(--severe);         border-color: #a44215; }
    .tab[data-tab="new"].active         { background: var(--danger-emphasis); border-color: #7a0e1f; }
    .tab[data-tab="untouched"].active   { background: var(--fg-muted);        border-color: var(--fg); }
    .tab.active { color: #ffffff; }
    /* ---- Shared per-tab visibility rules ------------------------------
       All, Ranked, Spontaneous, Top fit, New each already drive <li.job>
       display via body.tab-X rules below. The 3 state-specific tabs
       (Liked / To Apply / Pipeline) do the same so we no longer need
       the Show-X checkboxes or applyFilters stateShow logic. */
    body.tab-liked li.job:not(.liked),
    body.tab-liked .spontaneous-row:not(.liked) { display: none; }
    body.tab-toapply li.job:not(.toapply),
    body.tab-toapply .spontaneous-row:not(.toapply) { display: none; }
    body.tab-pipeline li.job:not(.applied):not(.app-rejected),
    body.tab-pipeline .spontaneous-row:not(.applied):not(.app-rejected) { display: none; }
    /* Hide sections that have no matching row for the current tab so the
       user is not scrolling through empty company headers. The :has()
       selector matches the section only when it contains at least one
       row that passes the tab's filter. */
    body.tab-liked .company-section:not(:has(li.job.liked, .spontaneous-row.liked)) { display: none; }
    body.tab-toapply .company-section:not(:has(li.job.toapply, .spontaneous-row.toapply)) { display: none; }
    body.tab-pipeline .company-section:not(:has(li.job.applied, li.job.app-rejected, .spontaneous-row.applied, .spontaneous-row.app-rejected)) { display: none; }

    /* Filters UI, problems banners and the per-company nav row are only
       meaningful on the All tab. Every other tab is a preset view with
       its own count in the tab label — showing those extras would just
       duplicate info. */
    body:not(.tab-all) .filters,
    body:not(.tab-all) .problems-banner,
    body:not(.tab-all) .nav { display: none; }
    /* Category headings ("Big Tech", "AI Startups", …) disappear on
       non-All tabs when every section in that category is hidden by the
       tab's CSS. refreshGroupHeadings adds the .empty class after
       walking the siblings; getComputedStyle makes it CSS-aware. */
    body:not(.tab-all) h2.group-heading.empty { display: none; }

    /* Spontaneous tab: hide every regular job row — only the ✉
       Spontaneous rows remain. The preset sets hideSpont=false so the
       body.hide-spontaneous rule above does not kick in and every
       source's spontaneous row shows regardless of state. Sections
       without a spontaneous row are hidden entirely so the user is not
       scrolling through empty company headers. */
    body.tab-spontaneous li.job { display: none; }
    body.tab-spontaneous .company-section:not(:has(.spontaneous-row)) { display: none; }
    /* New tab: show only rows whose summary has a .new-badge
       (first-seen in current run). Spontaneous rows have no NEW badge
       so they are hidden too. Sections that contain no NEW job at all
       are hidden entirely so the user is not scrolling through empty
       company headers. */
    body.tab-new li.job:not(:has(.badge.new-badge)) { display: none; }
    body.tab-new .spontaneous-row { display: none; }
    body.tab-new .company-section:not(:has(li.job .badge.new-badge)) { display: none; }

    /* Untouched tab: show only jobs the user has NOT acted on yet —
       no +1, no To Apply, no Applied, no app-rejected. The raw review
       pile. Rejected (×) rows are already filtered out server-side so
       they don't need to be excluded here. Spontaneous rows live in
       their own tab, so hide them too. Sections with zero untouched
       rows collapse so the user isn't scrolling past empty headers. */
    body.tab-untouched li.job.liked,
    body.tab-untouched li.job.toapply,
    body.tab-untouched li.job.applied,
    body.tab-untouched li.job.app-rejected { display: none; }
    body.tab-untouched .spontaneous-row { display: none; }
    body.tab-untouched .company-section:not(:has(li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected))) { display: none; }

    /* Ranked tab: flat cross-company list sorted by Claude fit DESC.
       JS moves every <li.job> into #ranked-list; CSS hides the company
       sections so the user only sees the flat ranked view. */
    .ranked-list { list-style: none; padding: 0; margin: 1rem 0 2rem; }
    .ranked-controls {
      display: flex;
      gap: 0.6rem;
      align-items: center;
      margin: 0.6rem 0 0;
      padding: 0.4rem 0;
      font-size: 0.9rem;
    }
    body:not(.tab-ranked) #ranked-list,
    body:not(.tab-ranked) #ranked-controls { display: none; }
    /* "Show spontaneous" checkbox: when off, hide every spontaneous row
       inside the ranked list. Spontaneous li.job are regular jobs — this
       only applies to .spontaneous-row entries that _buildRankedView
       moved in. */
    body.tab-ranked.hide-ranked-spontaneous #ranked-list .spontaneous-row {
      display: none;
    }
    /* Per-element hide toggles from the top bar. Each driven by a body
       class so they apply across every tab, not just All. */
    body.hide-seniority .badge.seniority,
    body.hide-seniority .badge.xp,
    body.hide-seniority .badge.ic-level { display: none; }
    body.hide-score .badge.claude-fit,
    body.hide-score .badge.score { display: none; }
    body.hide-salary .badge.salary { display: none; }
    body.hide-keywords .badge.highlight-badge { display: none; }
    body.hide-location .locs { display: none; }

    /* "Show marks" checkbox: when off, hide the state BUTTONS (+1 /
       TA / ✓ / R / K / review / reject) in Ranked so only the titles +
       badges remain. Scoped to `button.*` and `.ranked-spacer` so the
       row-level state classes (li.toapply / li.applied / …) are NOT
       matched — otherwise the whole row would disappear and the count
       shown in the tab label would appear to drop. */
    body.tab-ranked.hide-ranked-marks #ranked-list button.like,
    body.tab-ranked.hide-ranked-marks #ranked-list button.toapply,
    body.tab-ranked.hide-ranked-marks #ranked-list button.applied,
    body.tab-ranked.hide-ranked-marks #ranked-list button.app-rejected-btn,
    body.tab-ranked.hide-ranked-marks #ranked-list button.keep,
    body.tab-ranked.hide-ranked-marks #ranked-list button.review,
    body.tab-ranked.hide-ranked-marks #ranked-list button.reject,
    body.tab-ranked.hide-ranked-marks #ranked-list .ranked-spacer {
      display: none;
    }
    body.tab-ranked .company-section,
    body.tab-ranked .nav,
    body.tab-ranked .spontaneous-row { display: none; }
    body.tab-ranked #ranked-list { display: block; }
    /* Scored spontaneous rows are moved into #ranked-list by
       _buildRankedView — override the hide-all rule above so they
       actually render in the ranked view. Match li.job's flex settings
       exactly (gap: 0.6rem, align-items: baseline) because the base
       .spontaneous-row rule uses 0.5rem/center, which accumulates to a
       visible ~8px misalignment across the 7-item button chain. */
    body.tab-ranked #ranked-list .spontaneous-row {
      display: flex;
      gap: 0.6rem;
      align-items: baseline;
    }
    /* Rows WITHOUT a state class don't get the stateful padding +
       border-left (0.4rem + 3px = ~7.8px) that liked/toapply/applied/
       app-rejected rows do, which left-shifts their +1 column. Give them
       a transparent 3px border + the same padding so every row in Ranked
       has the same left edge regardless of state. Specificity trick:
       :not() filter targets only the unstyled rows so the stateful
       border colors keep winning without !important. */
    body.tab-ranked #ranked-list li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected),
    body.tab-ranked #ranked-list .spontaneous-row:not(.liked):not(.toapply):not(.applied):not(.app-rejected) {
      padding: 0.2rem 0.4rem;
      border-left: 3px solid transparent;
      border-radius: 4px;
    }
    /* Alignment of spontaneous rows with li.job rows in Ranked view:
       3 invisible placeholder buttons (Review + Reject + Keep) match
       li.job's extra state-button slots. The ▶ marker that li.job's
       <details> renders inside the summary is simulated with
       padding-left on the prefix so the title text starts at the same
       x-offset in both row types. */
    .ranked-spacer {
      visibility: hidden;
      pointer-events: none;
    }
    /* Visible ▶ marker before the prefix on spontaneous rows in Ranked —
       matches the <details> ::marker that li.job gets natively. Use
       U+25B6 (BLACK RIGHT-POINTING TRIANGLE) to match Chrome/Firefox/
       Safari's native details marker glyph; U+25B8 (small triangle) is
       noticeably thinner. Font color = --fg so it reads the same weight
       as the native black marker. */
    body.tab-ranked #ranked-list .spontaneous-row .company-prefix::before {
      content: '\u25B6';
      display: inline-block;
      color: var(--fg);
      margin-right: 0.35rem;
    }
    /* Strip the big orange ✉ Spontaneous button in Ranked view —
       within a flat ranked list that visual weight competes with the
       job titles. Fall back to plain text that reads as "Spontaneous
       application" so the row is still identifiable at a glance.
       Font-size is inherited (not forced to 0.9rem) so the link text
       matches the regular job titles' size. */
    body.tab-ranked #ranked-list .spontaneous-row .spontaneous-link {
      background: transparent;
      color: var(--fg);
      border: none;
      padding: 0;
      font-weight: 400;
      /* Explicit font-size overrides the base .spontaneous-link rule
         (0.9rem) so the text matches the ~1rem titles on li.job. */
      font-size: 1rem;
    }
    /* Prefix inherits body font-size (1rem) — match it explicitly so
       the triangle marker (::before) and the "Company —" text are the
       same size as li.job's title column. */
    body.tab-ranked #ranked-list .spontaneous-row .company-prefix {
      font-size: 1rem;
    }
    body.tab-ranked #ranked-list .spontaneous-row .spontaneous-link:hover {
      background: transparent;
      color: var(--accent);
      text-decoration: underline;
    }
    .ranked-list .company-prefix {
      color: var(--fg-muted);
      font-weight: 500;
      margin-right: 0.3em;
    }

    .nav {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin: 1rem 0 1.5rem;
    }
    .nav-btn {
      display: inline-block;
      padding: 0.35rem 0.9rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--fg);
      font-size: 0.85rem;
      font-weight: 500;
    }
    .nav-btn:hover {
      background: var(--border-muted);
      border-color: var(--fg-subtle);
      text-decoration: none;
    }
    .nav-btn.has-jobs {
      background: rgba(63, 185, 80, 0.12);
      border-color: rgba(63, 185, 80, 0.5);
      color: var(--success);
    }
    .nav-btn.has-jobs:hover {
      background: rgba(63, 185, 80, 0.22);
      border-color: var(--success);
    }
    /* Two "empty" states: no-match (source has jobs, none pass filters —
       orange, still worth checking) vs no-fetched (source returned zero —
       grey, likely unsupported or broken). */
    .nav-btn.no-match {
      color: var(--attention);
      border-color: rgba(154, 103, 0, 0.4);
      background: rgba(255, 213, 128, 0.15);
    }
    .nav-btn.no-match:hover {
      background: rgba(255, 213, 128, 0.30);
      border-color: var(--attention);
    }
    .nav-btn.no-fetched {
      color: var(--fg-muted);
      opacity: 0.7;
    }
    /* Broken: the scraper actually raised — different problem class from
       no-fetched (where scrape ran fine but returned nothing). Red so you
       can spot which sources need code fixes vs. which just returned nothing. */
    .nav-btn.broken {
      color: #ffffff;
      background: var(--danger);
      border-color: var(--danger-emphasis);
      font-weight: 700;
    }
    .nav-btn.broken:hover {
      background: var(--danger-emphasis);
    }
    .nav-btn.broken::before {
      content: "⚠ ";
    }
    .nav-count { font-weight: 600; }
    .nav-btn.has-jobs   .nav-count { color: var(--success); }
    .nav-btn.no-match   .nav-count { color: var(--attention); }
    .nav-btn.no-fetched .nav-count { color: var(--fg-muted); }
    .nav-btn.broken     .nav-count { color: #ffffff; }
    /* Top-of-page banner listing sources with issues this run. */
    .problems-banner {
      margin: 0.5rem 0 1rem;
      padding: 0.4rem 0.8rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--bg-subtle);
      font-size: 0.85rem;
    }
    .problems-banner > summary {
      cursor: pointer;
      font-weight: 700;
      color: var(--fg);
      list-style: none;
    }
    .problems-banner > summary::-webkit-details-marker { display: none; }
    .problems-banner > summary::before {
      content: "▶ ";
      display: inline-block;
      transition: transform 0.15s;
    }
    .problems-banner[open] > summary::before {
      content: "▼ ";
    }
    .problems-line { margin-top: 0.4rem; line-height: 1.5; }
    .problems-line a { margin-right: 0.35rem; text-decoration: none; }
    .problems-line a:hover { text-decoration: underline; }
    .problems-broken strong { color: var(--danger); }
    .problems-broken a       { color: var(--danger); }
    .problems-suspect strong { color: var(--attention); }
    .problems-suspect a       { color: var(--attention); }
    .problems-empty  strong { color: var(--fg-muted); }
    .problems-empty  a       { color: var(--fg-muted); }
    .problems-never-matched strong { color: var(--accent); }
    .problems-never-matched a       { color: var(--accent); }
    /* Second banner (never-matched) is closed by default; keep visual
       distance from the first one. */
    .never-matched-banner { margin-top: -0.6rem; }
    .top-bar {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      flex-wrap: wrap;
      margin-bottom: 1rem;
    }
    .total-count {
      font-size: 1rem;
      font-weight: 600;
      color: #ffffff;
      background: var(--danger);
      border: 1px solid #000;
      border-radius: 6px;
      padding: 0.5rem 0.9rem;
    }
    #total-count { color: #ffffff; }
    .top-bar-row2 { margin-top: -0.5rem; }
    .shortcuts-legend {
      margin: 0.1rem 0 0.6rem;
      font-size: 0.8rem;
      color: var(--fg-muted);
    }
    .shortcuts-legend kbd {
      display: inline-block;
      padding: 0 0.3rem;
      font: inherit;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--fg);
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: 4px;
      line-height: 1.3;
    }
    .state-count {
      font-size: 1rem;
      font-weight: 600;
      color: #ffffff;
      border: 1px solid #000;
      border-radius: 6px;
      padding: 0.5rem 0.9rem;
    }
    .state-count.state-liked   { background: var(--success); }
    .state-count.state-toapply { background: var(--danger); }
    .state-count.state-applied { background: #8250df; }
    .dump-btn {
      font-size: 1rem;
      font-weight: 600;
      color: #ffffff;
      background: var(--accent);
      border: 1px solid #000;
      border-radius: 6px;
      padding: 0.5rem 0.9rem;
      cursor: pointer;
    }
    .dump-btn:hover { background: var(--accent-emphasis); }
    /* Per-state open buttons — colour matches the state counters. */
    .dump-btn.open-btn-liked   { background: var(--success); }
    .dump-btn.open-btn-liked:hover   { background: var(--success-emphasis); }
    .dump-btn.open-btn-toapply { background: var(--danger); }
    .dump-btn.open-btn-toapply:hover { background: var(--danger-emphasis); }
    .dump-btn.open-btn-applied { background: #8250df; }
    .dump-btn.open-btn-applied:hover { background: #6639ba; }
    .dump-btn.open-btn-app-rejected { background: #000; border-color: #000; }
    .dump-btn.open-btn-app-rejected:hover { background: #2c2c2c; }
    /* Refresh button — right-aligned yellow circle with rotating icon while busy. */
    .refresh-btn {
      margin-left: auto;
      width: 3rem; height: 3rem;
      border-radius: 999px;
      border: 1px solid #000;
      background: #ffd60a;
      color: #000;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 1.1rem;
      font-weight: 700;
      line-height: 1;
      padding: 0;
      flex-shrink: 0;
    }
    .refresh-btn:hover { background: #f5c400; text-decoration: none; }
    .refresh-btn:disabled { opacity: 0.55; cursor: wait; }
    /* Gear is an <a> navigating to /settings — kill the generic link
       underline so it renders identically to the sibling <button>s. */
    a.refresh-btn, a.refresh-btn:hover { color: inherit; text-decoration: none; }
    .refresh-btn.busy .refresh-icon {
      display: inline-block;
      animation: refresh-spin 1s linear infinite;
    }
    @keyframes refresh-spin {
      from { transform: rotate(0deg); }
      to   { transform: rotate(360deg); }
    }
    .refresh-btn .refresh-icon {
      display: inline-block;
      transform: rotate(0deg);
    }
    /* Rescore button: sibling of refresh, no auto-margin so it sits right
       next to it. Same size/shape, different color to distinguish "compute
       (LLM)" from "fetch (network)". */
    /* Purple "AI" button — hand every visible job to the LLM of choice. */
    .claude-c-btn { margin-left: 0.4rem; background: #d0bfff; color: #6639ba; font-size: 1.1rem; }
    .claude-c-btn:hover { background: #b197fc; }
    /* Settings gear next to AI — set/clear the pinned chat URL. Same
       circle size as R / AI; glyph size bumped so the gear visually
       matches the letter buttons (⚙ renders smaller at the same em).
       Green by default, deeper green when a URL is pinned. */
    .claude-chat-url-btn {
      margin-left: 0.4rem;
      background: #b2f2bb; color: #2b8a3e;
      font-size: 1.8rem;
    }
    .claude-chat-url-btn:hover { background: #8ce99a; color: #1b5e20; }
    .claude-chat-url-btn.has-url { background: #2b8a3e; color: #ffffff; }
    .claude-chat-url-btn.has-url:hover { background: #1b5e20; }
    /* Edit-companies button — orange, with a floating red badge
       counting new companies added to src/catalog.py since the user last
       saved from the editor. Badge hidden when count = 0. */
    .edit-sources-btn {
      margin-left: 0.4rem;
      background: #ffd8a8;
      color: #cc5500;
      position: relative;
    }
    .edit-sources-btn:hover { background: #ffa94d; color: #ffffff; }
    /* Centre the material icon inside the circular action buttons. */
    .refresh-btn .mi { font-size: 1.15rem; }
    .claude-c-btn .mi { font-size: 1.2rem; }
    .new-companies-badge {
      position: absolute;
      top: -4px;
      right: -4px;
      min-width: 1.3rem;
      height: 1.3rem;
      padding: 0 0.3rem;
      background: var(--danger);
      color: #ffffff;
      border-radius: 999px;
      font-size: 0.72rem;
      line-height: 1.3rem;
      font-weight: 700;
      box-sizing: border-box;
      box-shadow: 0 0 0 2px var(--bg);
    }
    /* Edit-companies modal: wider than the default modal, body
       scrolls while header + footer stay pinned. */
    .modal-backdrop.wide .modal {
      width: min(900px, 95vw);
      max-height: 92vh;
      display: flex;
      flex-direction: column;
      padding: 0;
    }
    .modal-head {
      padding: 1rem 1.3rem 0.6rem;
      border-bottom: 1px solid var(--border);
    }
    .modal-body {
      padding: 0.8rem 1.3rem;
      overflow-y: auto;
      flex: 1;
    }
    .modal-foot {
      padding: 0.8rem 1.3rem;
      border-top: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 0.8rem;
      background: var(--bg-subtle);
      border-radius: 0 0 8px 8px;
    }
    .edit-sources-group {
      border: 1px solid var(--border);
      border-radius: 6px;
      margin: 0.5rem 0;
      padding: 0 0.8rem;
      background: var(--bg-subtle);
    }
    /* 📡 Discovered-on-WTJ section header + rows. Visually distinct
       from the catalog groups so users don't confuse "already tracked"
       with "proposed to add". */
    .edit-sources-discovered { border-color: var(--accent); }
    .edit-sources-discovered > summary { color: var(--accent-emphasis); }
    .es-discovered-hint {
      font-size: 0.85rem;
      color: var(--fg-muted);
      margin: 0.2rem 0 0.6rem;
    }
    .es-discovered-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 0.5rem;
    }
    .es-discovered-row {
      display: block;
      padding: 0.5rem 0.7rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--bg);
      color: var(--fg);
      text-decoration: none;
    }
    .es-discovered-row:hover { border-color: var(--accent); background: var(--bg-inset); }
    .es-discovered-name { font-weight: 600; font-size: 0.95rem; }
    .es-discovered-desc {
      font-size: 0.8rem;
      color: var(--fg-muted);
      margin-top: 0.15rem;
      line-height: 1.3;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .es-discovered-tags {
      font-size: 0.75rem;
      color: var(--accent-emphasis);
      margin-top: 0.25rem;
    }
    .edit-sources-group[open] { padding-bottom: 0.8rem; }
    .edit-sources-group > summary {
      cursor: pointer;
      padding: 0.6rem 0;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      list-style: none;
    }
    .edit-sources-group > summary::-webkit-details-marker { display: none; }
    .edit-sources-group > summary::before {
      content: '▶';
      display: inline-block;
      transition: transform 0.15s;
      color: var(--fg-muted);
      font-size: 0.7rem;
    }
    .edit-sources-group[open] > summary::before { transform: rotate(90deg); }
    .edit-sources-group .group-count {
      margin-left: auto;
      font-weight: normal;
      color: var(--fg-muted);
      font-size: 0.85rem;
    }
    .edit-sources-group .group-count.has-picks { color: var(--success); font-weight: 600; }
    .edit-sources-group .group-actions {
      padding: 0.2rem 0 0.5rem;
      display: flex;
      gap: 0.4rem;
    }
    .edit-sources-group .group-actions button {
      background: var(--bg);
      border: 1px solid var(--border);
      padding: 0.25rem 0.6rem;
      border-radius: 5px;
      cursor: pointer;
      font-size: 0.8rem;
    }
    .edit-sources-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.2rem 1rem;
    }
    /* Beat the generic `.modal label { display: block }` rule below —
       grab the modal id for extra specificity. Without this the
       checkbox stacks on top of the company name instead of sitting
       inline on its left. */
    .modal #es-body .edit-sources-grid label {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 0.4rem;
      padding: 0.12rem 0;
      margin-bottom: 0;
      cursor: pointer;
      font-size: 0.9rem;
      color: var(--fg);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    /* The generic .modal input rule forces width:100% + padding on
       every input, which blows up our checkboxes into huge filled
       rectangles and pushes the company name to the other end of the
       cell. Reset them to native sizes. */
    .modal #es-body .edit-sources-grid input[type="checkbox"] {
      width: auto;
      height: auto;
      padding: 0;
      margin: 0;
      flex: 0 0 auto;
      accent-color: var(--accent-emphasis);
    }
    /* Toolbar in the modal header: segmented mode pills + search. */
    .modal-head .es-toolbar {
      display: flex;
      align-items: center;
      gap: 0.8rem;
      flex-wrap: wrap;
    }
    .es-mode {
      display: inline-flex;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--bg);
      padding: 2px;
      gap: 2px;
    }
    .es-mode button {
      padding: 0.35rem 0.9rem;
      border-radius: 999px;
      border: none;
      background: transparent;
      color: var(--fg-muted);
      font-size: 0.85rem;
      font-weight: 500;
      line-height: 1;
      cursor: pointer;
    }
    .es-mode button:hover:not(.active) {
      background: var(--bg-subtle);
      color: var(--fg);
    }
    .es-mode button.active {
      background: var(--accent);
      color: #ffffff;
      font-weight: 600;
    }
    .modal-head input.es-search {
      flex: 1;
      max-width: 300px;
      padding: 0.4rem 0.7rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.9rem;
      margin: 0;
    }
    .edit-sources-grid .new-tag {
      font-size: 0.65rem;
      font-weight: 700;
      color: #ffffff;
      background: var(--danger);
      padding: 0.05rem 0.35rem;
      border-radius: 3px;
      margin-left: 0.3rem;
    }
    .modal-foot .es-counter {
      font-weight: 600;
      color: var(--fg);
    }
    /* Any label the filter hides. Applied by _esFilter. The modal-id
       prefix is required to beat the `.modal #es-body …label { display:
       flex }` rule above — without it, es-hide would be ignored. */
    .modal #es-body .edit-sources-grid label.es-hide { display: none; }
    /* Collapse groups that have zero visible labels while filtering. */
    .modal #es-body .edit-sources-group.es-collapsed { display: none; }
    .dump-btn.total-btn { background: #fb8500; border-color: #000; cursor: default; }
    .dump-btn.total-btn:hover { background: #d97400; }
    /* "Total New" — red like the NEW badge, so the visual link is obvious. */
    .dump-btn.total-new-btn { background: var(--danger); border-color: #000; cursor: default; color: #fff; }
    .dump-btn.total-new-btn:hover { background: var(--danger-emphasis); }
    /* Probe button: pushed to the far right of the row, black. */
    .dump-btn.dump-btn-probe { margin-left: auto; background: #000; border-color: #000; }
    .dump-btn.dump-btn-probe:hover { background: #2c2c2c; }
    .dump-status { font-size: 0.85rem; color: var(--fg-muted); }
    .nav-break { flex-basis: 100%; height: 0; }
    .nav-row {
      display: flex;
      align-items: flex-start;
      gap: 0.6rem;
      width: 100%;
    }
    .nav-row.empty { display: none; }
    .nav-group-label {
      flex: 0 0 12rem;
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--fg-muted);
      text-transform: uppercase;
      letter-spacing: 0.03em;
      padding-top: 0.4rem;
      text-align: right;
      text-decoration: none;
      cursor: pointer;
    }
    .nav-group-label:hover {
      color: var(--accent);
      text-decoration: underline;
    }
    .nav-btns {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      flex: 1;
    }
    .group-heading {
      margin-top: 2.5rem;
      margin-bottom: 0.5rem;
      padding-bottom: 0.3rem;
      border-bottom: 2px solid var(--border);
      font-size: 1.15rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--fg-muted);
    }

    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 1.5rem;
      align-items: center;
      padding: 0.75rem 1rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-bottom: 1.5rem;
      font-size: 0.85rem;
    }
    .filter-group { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
    .filter-group.full-row { flex-basis: 100%; }
    .filter-group.full-row input[type="text"] { flex: 1; }
    /* Force IC row onto its own line, below Management. */
    .filter-group.filter-group-ic { flex-basis: 100%; }
    .filter-label { color: var(--fg-muted); font-weight: 700; }
    .filter-check { display: flex; align-items: center; gap: 0.3rem; cursor: pointer; }
    .filter-check input { accent-color: var(--accent-emphasis); }
    /* Small pill buttons that flip all Show-state checkboxes at once. */
    button.show-all-btn {
      padding: 0.15rem 0.55rem;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--fg);
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
    }
    button.show-all-btn:hover {
      background: var(--border);
    }
    #loc-filter {
      background: var(--bg-inset);
      color: var(--fg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.3rem 0.6rem;
      font: inherit;
      min-width: 18rem;
    }
    #loc-filter:focus { outline: 1px solid var(--accent); border-color: var(--accent); }
    .filter-btn {
      background: var(--bg);
      color: var(--fg-muted);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.3rem 0.7rem;
      cursor: pointer;
      font: inherit;
    }
    .filter-btn:hover { color: var(--fg); border-color: var(--fg-subtle); }
    .loc-panel {
      flex-basis: 100%;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      max-height: 22rem;
      overflow-y: auto;
      padding: 0.6rem 0.8rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-top: 0.5rem;
    }
    /* Two-column grid: fixed-width country label, then a wrapping list of
       city checkboxes. When the cities wrap onto a 2nd/3rd line they align
       under the first city instead of tucking under the country name. */
    .loc-group {
      display: grid;
      grid-template-columns: 8rem 1fr;
      align-items: baseline;
      gap: 0.4rem 0.8rem;
      padding: 0.3rem 0;
      border-bottom: 1px dashed var(--border-muted);
    }
    .loc-group:last-child { border-bottom: none; }
    .loc-country {
      font-weight: 700;
      color: var(--severe);
      font-size: 0.85rem;
    }
    button.loc-country-toggle {
      text-align: left;
      background: transparent;
      border: 1px solid transparent;
      padding: 0.05rem 0.3rem;
      border-radius: 3px;
      cursor: pointer;
      font-family: inherit;
      /* Country label stays in its own column (see .loc-group grid). */
      justify-self: start;
    }
    button.loc-country-toggle:hover {
      background: var(--border-muted);
      border-color: var(--border);
    }
    .loc-cities {
      display: flex;
      flex-wrap: wrap;
      gap: 0.25rem 0.6rem;
    }
    .loc-bulk {
      display: flex;
      gap: 0.4rem;
      align-items: center;
      padding-bottom: 0.3rem;
      border-bottom: 1px solid var(--border);
    }
    .loc-bulk-btn {
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--fg);
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.2rem 0.6rem;
      cursor: pointer;
    }
    .loc-bulk-btn:hover { background: var(--bg-inset); border-color: var(--fg-subtle); }
    .loc-check {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      cursor: pointer;
      font-size: 0.82rem;
      color: var(--fg);
      padding: 0.05rem 0.35rem;
      border-radius: 3px;
    }
    .loc-check:hover { background: var(--border-muted); }
    .loc-cb { accent-color: var(--accent-emphasis); }

    ul { padding-left: 0.25rem; list-style: none; }
    li {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 0.6rem;
      margin: 0.4rem 0;
    }
    li.hidden { display: none; }
    li > details { flex: 1; min-width: 0; }
    li > .score-summary,
    li > .role-summary  { flex-basis: 100%; margin-left: 2.1rem; }
    /* Summary stays on one line and overflows to the right instead of wrapping */
    summary {
      cursor: pointer;
      white-space: nowrap;
      overflow-x: auto;
      overflow-y: visible;
      scrollbar-width: thin;
    }
    summary::-webkit-scrollbar { height: 4px; }
    summary::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
    summary .title { color: var(--fg); }
    summary .locs { color: var(--fg-muted); }

    .reject {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--danger);
      color: var(--danger);
      border-radius: 50%;
      width: 1.3rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.95rem;
      font-weight: 700;
      line-height: 1;
      padding: 0;
      align-self: center;
    }
    .reject:hover {
      background: var(--danger);
      color: #ffffff;
      border-color: var(--danger-emphasis);
    }
    .reject:disabled { opacity: 0.4; cursor: wait; }

    /* Section-level × — mirrors .reject but a touch larger so it reads as
       "nuke the whole section" at a glance. Sits in the <h1> next to the
       counter; hidden when the section has no untouched rows left. */
    .reject-section {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--danger);
      color: var(--danger);
      border-radius: 50%;
      width: 1.5rem;
      height: 1.5rem;
      cursor: pointer;
      font-size: 1.05rem;
      font-weight: 700;
      line-height: 1;
      padding: 0;
      margin-left: 0.3rem;
      vertical-align: middle;
    }
    .reject-section:hover {
      background: var(--danger);
      color: #ffffff;
      border-color: var(--danger-emphasis);
    }
    .reject-section:disabled { opacity: 0.4; cursor: wait; }
    .company-section:not(:has(li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected))) .reject-section {
      display: none;
    }

    /* Unfollow × — sits next to .reject-section in the h1. Visually quieter
       (grey border, no fill, muted emoji) so it reads as "stop watching"
       rather than "reject jobs". Hover emphasises red because the action
       rewrites the user's sources file. */
    .unfollow-company {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--border);
      color: var(--fg-muted);
      border-radius: 50%;
      width: 1.5rem;
      height: 1.5rem;
      cursor: pointer;
      font-size: 0.85rem;
      line-height: 1;
      padding: 0;
      margin-left: 0.25rem;
      vertical-align: middle;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .unfollow-company:hover {
      border-color: var(--danger);
      background: #fff5f5;
    }
    .unfollow-company:disabled { opacity: 0.4; cursor: wait; }

    /* Review button: orange circle, only rendered when the job has no state.
       Sends title to planning/TOREVIEW.md + rejects the URL in one click. */
    button.review {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--attention);
      color: var(--attention);
      border-radius: 50%;
      width: 1.3rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 700;
      line-height: 1;
      padding: 0;
      align-self: center;
    }
    button.review:hover { background: var(--attention); color: #ffffff; border-color: var(--severe); }
    button.review:disabled { opacity: 0.4; cursor: wait; }
    /* "Keep in history" button — grey outlined circle, sits at the far right
       of the state-button row (only shown for jobs at least +1'd). */
    button.keep {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--fg-muted);
      color: var(--fg-muted);
      border-radius: 50%;
      width: 1.3rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 700;
      line-height: 1;
      padding: 0;
      align-self: center;
    }
    button.keep:hover { background: var(--fg-muted); color: #ffffff; }
    button.keep:disabled { opacity: 0.4; cursor: wait; }

    .like {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--success);
      color: var(--success);
      border-radius: 999px;
      padding: 0 0.4rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 700;
      line-height: 1;
      align-self: center;
    }
    .like:hover { background: var(--success); color: #ffffff; border-color: var(--success-emphasis); }
    .like[data-state="on"] { background: var(--success); color: #ffffff; }
    .like:disabled { opacity: 0.4; cursor: wait; }

    li.liked {
      background: rgba(63, 185, 80, 0.08);
      border-left: 3px solid var(--success);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    li.liked .reject { visibility: hidden; }

    /* To apply — red pill, "TA" glyph. Scoped to button so the same class
       name on <li> (li.toapply, used for row highlight) doesn't inherit
       these pill styles. */
    button.toapply {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--danger);
      color: var(--danger);
      border-radius: 999px;
      padding: 0 0.4rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.72rem;
      font-weight: 700;
      line-height: 1;
      align-self: center;
    }
    button.toapply:hover { background: var(--danger); color: #ffffff; border-color: var(--danger-emphasis); }
    button.toapply[data-state="on"] { background: var(--danger); color: #ffffff; }
    li.toapply {
      background: rgba(209, 36, 47, 0.10);
      border-left: 3px solid var(--danger);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    li.toapply .reject { visibility: hidden; }

    /* Applied — purple pill, "✓" glyph. Scoped to button (same reasoning
       as button.toapply above). */
    button.applied {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid #8250df;
      color: #8250df;
      border-radius: 999px;
      padding: 0 0.4rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 700;
      line-height: 1;
      align-self: center;
    }
    button.applied:hover { background: #8250df; color: #ffffff; border-color: #6639ba; }
    button.applied[data-state="on"] { background: #8250df; color: #ffffff; }
    li.applied {
      background: rgba(130, 80, 223, 0.10);
      border-left: 3px solid #8250df;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    li.applied .reject { visibility: hidden; }

    /* Application rejected by company — much darker grey. */
    button.app-rejected-btn {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid #1c1f24;
      color: #1c1f24;
      border-radius: 999px;
      padding: 0 0.4rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 700;
      line-height: 1;
      align-self: center;
    }
    button.app-rejected-btn:hover { background: #1c1f24; color: #ffffff; border-color: #000; }
    button.app-rejected-btn[data-state="on"] { background: #1c1f24; color: #ffffff; }
    /* State buttons are always rendered server-side so every job row has
       the same button chain, keeping titles vertically aligned. When
       `data-state="off"` the button sits in a muted grey resting state,
       hover restores its state color (via the specific :hover rules
       above). */
    button.toapply[data-state="off"],
    button.applied[data-state="off"],
    button.app-rejected-btn[data-state="off"] {
      opacity: 0.35;
      border-color: var(--border);
      color: var(--fg-muted);
    }
    button.toapply[data-state="off"]:hover,
    button.applied[data-state="off"]:hover,
    button.app-rejected-btn[data-state="off"]:hover {
      opacity: 1;
    }
    /* Visual cascade: when a row has reached a later state, show every
       earlier state button as if it were also "on" — so the chain reads
       consistently (even if the user skipped intermediate clicks when
       marking the job app-rejected directly). The underlying
       data-state attributes stay as the user set them; this is a pure
       display override. Higher specificity than the [data-state="off"]
       muted style above, so it wins when both match. */
    li.toapply button.like,
    li.applied button.like,
    li.app-rejected button.like,
    .spontaneous-row.toapply button.like,
    .spontaneous-row.applied button.like,
    .spontaneous-row.app-rejected button.like {
      background: var(--success);
      color: #ffffff;
      border-color: var(--success);
      opacity: 1;
    }
    li.applied button.toapply,
    li.app-rejected button.toapply,
    .spontaneous-row.applied button.toapply,
    .spontaneous-row.app-rejected button.toapply {
      background: var(--danger);
      color: #ffffff;
      border-color: var(--danger);
      opacity: 1;
    }
    li.app-rejected button.applied,
    .spontaneous-row.app-rejected button.applied {
      background: #8250df;
      color: #ffffff;
      border-color: #8250df;
      opacity: 1;
    }
    /* The .review (R → write-to-planning/TOREVIEW.md) and .app-rejected-btn (R → mark
       application rejected) share one slot: on a bare row the Review
       button is the "R" shown, on any state row the app-rejected one is.
       We render BOTH server-side and swap their visibility so the row
       keeps the same width across state transitions. */
    li.job:is(.liked, .toapply, .applied, .app-rejected) .review {
      visibility: hidden;
    }
    li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected) .app-rejected-btn {
      visibility: hidden;
    }
    li.app-rejected {
      background: rgba(28, 31, 36, 0.35);
      border-left: 3px solid #1c1f24;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      opacity: 0.85;
    }
    li.app-rejected .reject { visibility: hidden; }
    /* Feedback / reason panel injected under the summary when applicable. */
    .app-reject-panel {
      flex-basis: 100%;
      margin: 0.15rem 0 0 2.1rem;
      padding: 0.35rem 0.6rem;
      font-size: 0.82rem;
      line-height: 1.4;
      border-left: 3px solid #1c1f24;
      background: rgba(28, 31, 36, 0.15);
      color: var(--fg);
    }
    .app-reject-panel strong { color: #1c1f24; margin-right: 0.4rem; }
    .app-reject-panel .app-reject-fb {
      display: block; margin-top: 0.25rem;
      white-space: pre-wrap; color: var(--fg-muted); font-style: italic;
    }

    /* Modal used for the "Application rejected" reason + feedback dialog. */
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,0.4);
      display: none; align-items: center; justify-content: center;
      z-index: 1000;
    }
    .modal-backdrop.visible { display: flex; }
    .modal-backdrop .modal {
      background: var(--bg);
      color: var(--fg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.2rem 1.4rem;
      width: min(520px, 92vw);
      box-shadow: 0 12px 40px rgba(0,0,0,0.25);
    }
    .modal h3 { margin-top: 0; margin-bottom: 0.9rem; font-size: 1.1rem; }
    .modal label { display: block; margin-bottom: 0.7rem; font-size: 0.9rem; color: var(--fg-muted); }
    .modal input, .modal textarea {
      width: 100%; box-sizing: border-box;
      padding: 0.4rem 0.6rem;
      border: 1px solid var(--border); border-radius: 4px;
      background: var(--bg); color: var(--fg);
      font: inherit;
      margin-top: 0.25rem;
    }
    .modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.4rem; }
    .modal-actions button {
      padding: 0.4rem 0.9rem; border-radius: 6px; cursor: pointer;
      border: 1px solid var(--border); background: var(--bg-subtle); color: var(--fg);
      font-weight: 600;
    }
    .modal-actions button.primary {
      background: var(--accent); color: #ffffff; border-color: var(--accent-emphasis);
    }
    .modal-actions button.primary:hover { background: var(--accent-emphasis); }
    /* Runaway modal — a per-refresh prompt when one query is pulling in
       so many jobs that it would peg Playwright for minutes. */
    .runaway-backdrop .modal { width: min(520px, 92vw); }
    .runaway-backdrop code {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      background: var(--bg-subtle);
      padding: 0.05rem 0.35rem;
      border-radius: 4px;
    }
    .runaway-backdrop .runaway-info,
    .runaway-backdrop .runaway-tip {
      margin: 0.5rem 0;
      font-size: 0.9rem;
      color: var(--fg);
    }
    .runaway-backdrop .runaway-tip { color: var(--fg-muted); }
    .runaway-backdrop .runaway-tip em {
      font-style: normal;
      color: var(--fg);
      background: var(--bg-subtle);
      padding: 0.02rem 0.3rem;
      border-radius: 3px;
    }
    /* Floating refresh indicator — visible for the entire duration of a
       /refresh so the user always sees progress, even scrolled a mile
       down. Starts hidden; JS toggles .visible when the poller is in
       `running`. Position matches other floating widgets (top-right)
       so it doesn't collide with the bottom-centered paste bar. */
    #refresh-floater {
      position: fixed;
      top: 0.8rem;
      right: 0.8rem;
      z-index: 998;
      display: none;
      align-items: center;
      gap: 0.5rem;
      padding: 0.45rem 0.9rem;
      background: var(--bg);
      color: var(--fg);
      border: 2px solid var(--accent);
      border-radius: 10px;
      box-shadow: 0 6px 24px rgba(0,0,0,0.2);
      font-size: 0.88rem;
      font-weight: 600;
    }
    #refresh-floater.visible { display: inline-flex; }
    /* One-shot pill shown after the onboarding wizard redirects here.
       Same geometry as #refresh-floater but green (success) and offset
       so both can co-exist if a refresh kicks off during the welcome. */
    .onboarded-toast {
      position: fixed;
      top: 0.8rem;
      right: 0.8rem;
      z-index: 999;
      display: none;
      align-items: center;
      gap: 0.6rem;
      padding: 0.5rem 0.9rem 0.5rem 0.75rem;
      background: var(--bg);
      color: var(--fg);
      border: 2px solid var(--success);
      border-radius: 10px;
      box-shadow: 0 6px 24px rgba(0,0,0,0.2);
      font-size: 0.9rem;
      font-weight: 600;
    }
    .onboarded-toast.visible { display: inline-flex; }
    .onboarded-toast .onboarded-icon {
      display: inline-flex;
      width: 1.1rem; height: 1.1rem;
      align-items: center; justify-content: center;
      background: var(--success);
      color: #ffffff;
      border-radius: 50%;
      font-size: 0.75rem;
      font-weight: 700;
    }
    .onboarded-toast .onboarded-dismiss {
      background: none;
      border: none;
      cursor: pointer;
      color: var(--fg-muted);
      font-size: 1.2rem;
      line-height: 1;
      padding: 0 0.2rem;
    }
    .onboarded-toast .onboarded-dismiss:hover { color: var(--fg); }
    #refresh-floater.visible + .onboarded-toast,
    .onboarded-toast + #refresh-floater.visible { top: 4rem; }
    #refresh-floater::before {
      content: "";
      width: 0.65rem; height: 0.65rem;
      border-radius: 50%;
      background: var(--accent);
      animation: refresh-pulse 1.2s ease-in-out infinite;
    }
    @keyframes refresh-pulse {
      0%, 100% { opacity: 0.3; transform: scale(0.75); }
      50%      { opacity: 1;   transform: scale(1); }
    }
    /* Sticky "paste the reply here" bar — appears when you click AI. */
    #claude-paste-bar {
      position: fixed; left: 50%; bottom: 1rem; transform: translateX(-50%);
      z-index: 999;
      width: min(720px, 94vw);
      background: var(--bg); color: var(--fg);
      border: 2px solid #6639ba; border-radius: 10px;
      padding: 0.5rem 0.7rem;
      box-shadow: 0 10px 36px rgba(0,0,0,0.3);
    }
    #claude-paste-bar.done { border-color: var(--success); }
    .paste-bar-inner { display: grid; grid-template-columns: 1fr auto; gap: 0.3rem 0.6rem; align-items: start; }
    .paste-bar-label {
      grid-column: 1 / 2; font-size: 0.82rem; color: var(--fg-muted);
    }
    .paste-bar-hint {
      grid-column: 1 / 3; font-size: 0.82rem; color: var(--attention);
      margin-bottom: 0.2rem;
    }
    .paste-bar-hint strong { color: var(--severe); }
    #claude-paste-area {
      grid-column: 1 / 2;
      width: 100%; box-sizing: border-box;
      padding: 0.4rem 0.6rem;
      border: 1px solid var(--border); border-radius: 6px;
      font: inherit; font-size: 0.85rem;
      background: var(--bg-subtle); color: var(--fg);
      resize: vertical;
    }
    #claude-paste-close {
      grid-column: 2 / 3; grid-row: 1 / 3;
      align-self: start;
      width: 1.6rem; height: 1.6rem;
      padding: 0; cursor: pointer;
      background: transparent; color: var(--fg-muted);
      border: 1px solid var(--border); border-radius: 50%;
      font-size: 1rem; line-height: 1;
    }
    #claude-paste-close:hover { background: var(--bg-subtle); color: var(--fg); }
    /* Shared modal buttons / status for the Claude-score dialog. */
    .modal .modal-step { margin: 0.3rem 0; font-size: 0.88rem; color: var(--fg-muted); }
    .modal .modal-buttons { display: flex; gap: 0.5rem; margin-top: 0.6rem; }
    .modal button.modal-primary {
      padding: 0.4rem 0.9rem; border-radius: 6px; cursor: pointer; font-weight: 600;
      background: var(--accent); color: #fff; border: 1px solid var(--accent-emphasis);
    }
    .modal button.modal-primary:hover { background: var(--accent-emphasis); }
    .modal button.modal-secondary {
      padding: 0.4rem 0.9rem; border-radius: 6px; cursor: pointer; font-weight: 600;
      background: var(--bg-subtle); color: var(--fg); border: 1px solid var(--border);
    }
    .modal .modal-status { margin-top: 0.5rem; font-size: 0.85rem; color: var(--fg-muted); min-height: 1.1rem; }

    .badge {
      display: inline-block;
      padding: 0 0.5rem;
      border: 1px solid var(--border);
      border-radius: 2em;
      font-size: 0.72rem;
      line-height: 1.4;
      color: var(--fg-muted);
      margin: 0 0.3rem;
      background: var(--bg-subtle);
      vertical-align: middle;
    }
    .badge.seniority {
      border-color: rgba(63, 185, 80, 0.4);
      color: var(--success);
      background: rgba(63, 185, 80, 0.1);
    }
    .badge.salary {
      border-color: rgba(9, 105, 218, 0.5);
      color: var(--accent-emphasis);
      background: rgba(9, 105, 218, 0.15);
      font-weight: 600;
    }
    /* Typical YoE at this company for this seniority — purple, sits just
       left of the salary badge. Cursor: help because the tooltip carries
       the "indicative" caveat. */
    .badge.xp {
      border-color: rgba(130, 80, 223, 0.5);
      color: #6639ba;
      background: rgba(130, 80, 223, 0.12);
      font-weight: 600;
      cursor: help;
    }
    /* Claude /10 fit badge — unified red style. */
    .badge.claude-fit {
      font-weight: 700;
      cursor: help;
      min-width: 2rem;
      text-align: center;
      color: #ffffff;
      background: var(--danger);
      border-color: var(--danger-emphasis);
    }
    /* Floating tooltip appended to <body> on mouseenter so no parent's
       overflow:hidden can clip it. Styled here. */
    .claude-fit-tooltip {
      position: fixed;
      max-width: 32rem;
      padding: 0.5rem 0.7rem;
      font-weight: 500;
      font-size: 0.82rem;
      line-height: 1.4;
      white-space: normal;
      text-align: left;
      color: var(--fg);
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.3);
      z-index: 10000;
      pointer-events: none;
    }
    .badge.ic-level {
      border-color: rgba(154, 103, 0, 0.4);
      color: var(--attention);
      background: rgba(255, 213, 128, 0.25);
      font-weight: 600;
    }
    .badge.new-badge {
      color: #ffffff;
      background: var(--danger);
      border-color: #000;
      font-weight: 700;
      letter-spacing: 0.03em;
    }
    .badge.orphan-badge {
      color: #ffffff;
      background: #57606a;
      border-color: #000;
      font-weight: 700;
      letter-spacing: 0.03em;
    }
    .badge.highlight-badge {
      color: #1f2328;
      background: #fff8c5;
      border-color: rgba(154, 103, 0, 0.4);
      font-weight: 500;
    }
    .summary-link {
      display: inline-block;
      margin: 0 0.35rem 0 0.15rem;
      color: var(--accent);
      text-decoration: none;
      font-size: 0.95rem;
    }
    .summary-link:hover { text-decoration: underline; }
    /* Small "$" pill next to the ↗ link — opens a prompt to set a manual
       salary range (persisted client-side in localStorage). */
    button.salary-edit {
      display: inline-block;
      margin: 0 0.35rem 0 0;
      padding: 0 0.35rem;
      font-size: 0.8rem;
      font-weight: 700;
      line-height: 1.4;
      color: var(--accent-emphasis);
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
    }
    button.salary-edit:hover {
      background: rgba(9, 105, 218, 0.15);
      border-color: rgba(9, 105, 218, 0.5);
    }
    /* "?" button — same pill shape as $, purple accent to signal "Claude". */
    button.ask-claude {
      display: inline-block;
      margin: 0 0.35rem 0 0;
      padding: 0 0.4rem;
      font-size: 0.8rem;
      font-weight: 700;
      line-height: 1.4;
      color: #6639ba;
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
    }
    button.ask-claude:hover {
      background: rgba(130, 80, 223, 0.12);
      border-color: rgba(130, 80, 223, 0.5);
    }
    /* Manual salary badge — same look as the LLM-extracted one, just a
       thicker border so it's visually distinguishable at a glance. */
    .badge.salary.manual {
      border-style: dashed;
    }
    .badge.score {
      font-weight: 700;
      min-width: 1.3rem;
      text-align: center;
      cursor: help;
    }
    .badge.score-hi  { color: #ffffff;         background: var(--success); border-color: var(--success); }
    .badge.score-mid { color: var(--attention);background: #fff8c5;         border-color: rgba(154,103,0,0.4); }
    .badge.score-lo  { color: var(--fg-muted); background: var(--bg-subtle);border-color: var(--border); }
    .score-summary, .role-summary {
      margin-top: 0.15rem;
      padding: 0.25rem 0.6rem;
      font-size: 0.82rem;
      line-height: 1.35;
      color: var(--fg-muted);
      border-left: 3px solid var(--border);
      background: transparent;
    }
    .score-summary strong, .role-summary strong {
      color: var(--fg);
      margin-right: 0.35rem;
    }
    .role-summary { border-left-color: var(--accent); }
    .role-summary strong { color: var(--accent); }
    .score-summary.score-hi  { border-left-color: var(--success); color: var(--fg); }
    .score-summary.score-mid { border-left-color: var(--attention); }
    .score-summary.score-lo  { border-left-color: var(--border); }
    body.hide-score-summary .score-summary { display: none; }
    body.hide-role-summary  .role-summary  { display: none; }
    body.hide-empty-sections .company-section.empty:not(.has-spontaneous) { display: none; }
    /* Hide the spontaneous row when the toggle is on, EXCEPT if the user has
       flagged it in any state — hiding a spontaneous you're actively tracking
       would surprise the user. */
    body.hide-spontaneous .spontaneous-row:not(.liked):not(.toapply):not(.applied):not(.app-rejected) { display: none; }
    /* When Spontaneous is hidden AND the section has no other visible jobs,
       treat the section as empty for the hide-empty-sections toggle — UNLESS
       the spontaneous row carries any state (liked / toapply / applied /
       app-rejected), which means the user has explicitly flagged it. */
    body.hide-spontaneous.hide-empty-sections .company-section.empty:not(:has(.spontaneous-row.liked, .spontaneous-row.toapply, .spontaneous-row.applied, .spontaneous-row.app-rejected)) {
      display: none;
    }
    /* Same combo: also hide top-nav buttons for companies that currently
       have no matching jobs. Keeps the nav in sync with the sections.
       Green (.has-jobs) buttons stay visible. */
    body.hide-spontaneous.hide-empty-sections .nav-btn.no-match,
    body.hide-spontaneous.hide-empty-sections .nav-btn.no-fetched { display: none; }
    /* And hide the category label + row when zero buttons in it are green.
       :has() selector so it works even if applyFilters hasn't run yet
       (defensive; the JS also toggles .nav-row.empty for the same case). */
    body.hide-spontaneous.hide-empty-sections .nav-row:not(:has(.nav-btn.has-jobs)) {
      display: none;
    }
    /* Same combo: hide the body-side group heading ("AI Startups",
       "Security Companies", …) when every company-section under it is
       empty. The .empty class on the h2 is toggled by JS in
       refreshGroupHeadings() after every applyFilters pass. */
    body.hide-spontaneous.hide-empty-sections h2.group-heading.empty {
      display: none;
    }

    .role-more {
      display: block;
      margin-top: 0.35rem;
      font-size: 0.8rem;
    }
    .role-more > summary {
      cursor: pointer;
      color: var(--accent);
      font-weight: 500;
      list-style: none;
    }
    .role-more[open] > summary::after { content: " ▴"; }
    .role-more:not([open]) > summary::after { content: " ▾"; }
    .role-long {
      margin-top: 0.4rem;
      padding: 0.5rem 0.7rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      line-height: 1.4;
    }
    .role-long > div { margin: 0.25rem 0; }
    .role-long > div.role-heading { margin: 0.6rem 0 0.2rem; }
    .role-long > div.role-heading:first-child { margin-top: 0; }
    .role-long strong { color: var(--accent); }
    .role-long ul { margin: 0.15rem 0 0.35rem 0; padding-left: 1.2rem; }
    .role-long li { margin: 0.1rem 0; }

    .undo-toast {
      position: fixed;
      bottom: 1.2rem;
      left: 50%;
      transform: translateX(-50%) translateY(120%);
      background: var(--fg);
      color: var(--bg);
      padding: 0.6rem 1rem;
      border-radius: 8px;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      box-shadow: 0 6px 24px rgba(0,0,0,0.25);
      font-size: 0.9rem;
      z-index: 999;
      transition: transform 0.2s ease;
      max-width: 90vw;
    }
    .undo-toast.visible { transform: translateX(-50%) translateY(0); }
    .undo-toast .undo-msg { color: inherit; }
    .undo-toast em { font-style: normal; opacity: 0.85; }
    .undo-btn {
      background: var(--severe);
      color: #ffffff;
      border: none;
      padding: 0.35rem 0.8rem;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.85rem;
    }
    .undo-btn:hover { background: #a04113; }

    .rejected-block {
      margin-top: 0.7rem;
      margin-left: 0.25rem;
      padding: 0.35rem 0.5rem;
      font-size: 0.8rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    .rejected-block > summary {
      cursor: pointer;
      color: var(--fg-muted);
      font-weight: 500;
    }
    .rejected-block[open] > summary { margin-bottom: 0.4rem; }
    .rejected-list { list-style: none; padding-left: 0.25rem; margin: 0; }
    .rejected-list li.rejected-job {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      padding: 0.15rem 0;
      color: var(--fg-muted);
    }
    .rejected-list li.rejected-job a { color: var(--fg-muted); text-decoration: line-through; }
    .rejected-list li.rejected-job a:hover { color: var(--accent); }
    /* History block — same layout as rejected, no strike-through since these
       are kept intentionally, and a distinct pill accent to tell them apart. */
    .history-block {
      margin-top: 0.7rem;
      margin-left: 0.25rem;
      padding: 0.35rem 0.5rem;
      font-size: 0.8rem;
      background: rgba(130, 80, 223, 0.05);
      border: 1px solid rgba(130, 80, 223, 0.3);
      border-radius: 6px;
    }
    .history-block > summary { cursor: pointer; color: #6639ba; font-weight: 500; }
    .history-block[open] > summary { margin-bottom: 0.4rem; }
    .history-list { list-style: none; padding-left: 0.25rem; margin: 0; }
    .history-list li.history-job {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      padding: 0.15rem 0;
      color: var(--fg);
    }
    .history-list li.history-job a { color: var(--fg); }
    .history-list li.history-job a:hover { color: var(--accent); }
    button.unkeep {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid #6639ba;
      color: #6639ba;
      border-radius: 50%;
      width: 1.3rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 700;
      line-height: 1;
      padding: 0;
    }
    button.unkeep:hover { background: #6639ba; color: #ffffff; }
    .restore {
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid var(--success);
      color: var(--success);
      border-radius: 50%;
      width: 1.3rem;
      height: 1.3rem;
      cursor: pointer;
      font-size: 0.95rem;
      font-weight: 700;
      line-height: 1;
      padding: 0;
    }
    .restore:hover { background: var(--success); color: #ffffff; }

    .description {
      margin: 0.6rem 0 1rem 0.25rem;
      padding: 0.8rem 1rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-left: 3px solid var(--severe);
      border-radius: 6px;
      white-space: normal;
    }
    .desc-actions { margin-bottom: 0.6rem; font-size: 0.85rem; }
    .desc-body { font-size: 0.9rem; line-height: 1.55; color: var(--fg); }
    .desc-body h1, .desc-body h2, .desc-body h3, .desc-body h4 {
      font-size: 0.95rem;
      margin: 0.9rem 0 0.3rem;
      color: var(--fg);
      border: 0;
      padding: 0;
      display: block;
    }
    .desc-body p { margin: 0.5rem 0; }
    .desc-body ul, .desc-body ol { padding-left: 1.4rem; }
    .desc-body code {
      background: var(--bg-inset);
      padding: 0.1rem 0.35rem;
      border-radius: 3px;
      font-size: 0.85em;
    }
    .desc-body pre {
      background: var(--bg-inset);
      padding: 0.7rem 1rem;
      border-radius: 6px;
      overflow-x: auto;
    }
    .desc-body img { max-width: 100%; }
    .desc-body a { color: var(--accent); }
  </style>
</head>
<body>
__BODY__
<script>
const HIGHLIGHTS = __HIGHLIGHTS__;
// Edit-companies dialog: catalog (menu) + current config (pre-check).
const CATALOG_FOR_EDIT = __CATALOG_FOR_EDIT__;
const SOURCES_NAMES = __SOURCES_NAMES__;
// Discovered on WTJ (via Algolia public API) during the last refresh.
// List of {slug, name, description, sectors, website_url}. Shown as a
// read-only "📡 Discovered" section at the top of the Edit-companies
// modal so the user can browse and decide which to add manually.
const WTTJ_DISCOVERED = __WTTJ_DISCOVERED__;
// Server-side per-query runaway threshold (data/user_config.py or default).
// Shown + editable on the ⚙ Settings page; POST /set-settings persists it.
const RUNAWAY_THRESHOLD = __RUNAWAY_THRESHOLD__;
const SERVER_URL = '__SERVER_URL__';
// Server-side Claude fit cache (claude_fit_cache.json) for jobs currently
// visible. Hydrated into localStorage on load so badges render on open.
const CLAUDE_FITS_SERVER = __CLAUDE_FITS__;

function highlightIn(node) {
  if (!HIGHLIGHTS.length) return;
  const pat = HIGHLIGHTS.map(w => w.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')).join('|');
  const re = new RegExp('\\\\b(' + pat + ')\\\\b', 'gi');
  const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
  const targets = [];
  let n;
  while ((n = walker.nextNode())) {
    if (n.parentElement.closest('mark, script, style')) continue;
    if (re.test(n.nodeValue)) targets.push(n);
    re.lastIndex = 0;
  }
  for (const t of targets) {
    const span = document.createElement('span');
    span.innerHTML = t.nodeValue.replace(re, '<mark>$1</mark>');
    t.replaceWith(...span.childNodes);
  }
}

document.querySelectorAll('details').forEach(d => {
  d.addEventListener('toggle', () => {
    if (d.open && !d.dataset.highlighted) {
      const body = d.querySelector('.desc-body');
      if (body) highlightIn(body);
      d.dataset.highlighted = '1';
    }
  });
});

/* --- Debug mode: enable via ?debug=1 URL param or #debug hash ---------- */
const DEBUG = /(?:^|[?&])debug=1(?:&|$)/.test(location.search) || location.hash === '#debug';
if (DEBUG) console.log('%c[jobs.html] debug mode on', 'color: orange; font-weight: bold');
function dlog(...a) { if (DEBUG) console.log('[dbg]', ...a); }

/* --- Persistence: filter state survives page refreshes ----------------- */
const STORAGE_KEY = 'jobs:filters:v1';

function saveFilters() {
  // The display toggles (highlight, show*, scoreSummary, roleSummary)
  // live on the /settings page — their checkboxes aren't in THIS DOM.
  // Reading from body classes keeps the saved blob accurate when the
  // user toggles a filter here without having visited settings; a
  // naive `?.checked ?? true` would clobber "false" states set by the
  // settings page.
  const body = document.body.classList;
  const state = {
    locChecks: [...document.querySelectorAll('.loc-cb:checked')]
      .map(cb => cb.dataset.value),
    loc:   (document.getElementById('loc-filter')?.value)   || '',
    title: (document.getElementById('title-filter')?.value) || '',
    text:  (document.getElementById('text-filter')?.value)  || '',
    highlight:       !body.contains('no-highlights'),
    scoreSummary:    !body.contains('hide-score-summary'),
    roleSummary:     !body.contains('hide-role-summary'),
    hideEmpty:       document.getElementById('hide-empty-toggle')?.checked ?? false,
    hideSpontaneous: document.getElementById('hide-spontaneous-toggle')?.checked ?? false,
    showSeniority:   !body.contains('hide-seniority'),
    showScore:       !body.contains('hide-score'),
    showSalary:      !body.contains('hide-salary'),
    showKeywords:    !body.contains('hide-keywords'),
    showLocation:    !body.contains('hide-location'),
  };
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) {}
}

function loadFilters() {
  let s;
  try { s = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch (e) { s = null; }
  if (!s) return;
  const loc = new Set(s.locChecks || []);
  document.querySelectorAll('.loc-cb').forEach(cb => {
    cb.checked = loc.has(cb.dataset.value);
  });
  const li = document.getElementById('loc-filter');   if (li) li.value = s.loc   || '';
  const ti = document.getElementById('title-filter'); if (ti) ti.value = s.title || '';
  const tx = document.getElementById('text-filter');  if (tx) tx.value = s.text  || '';
  // The display toggles (highlight, score/role summary, show*) live on
  // the /settings page now — their checkboxes aren't in THIS DOM. The
  // body class is the source of truth; apply it straight from the blob
  // regardless of DOM presence so the settings page's writes take
  // effect on reload. The two "hide*" toggles still have DOM elements
  // in the filter bar (hide-empty, hide-spontaneous), so they also
  // need their .checked state restored.
  const displayToggles = [
    // [storage key, body class, inverted (true if key=false → add class)]
    ['highlight',    'no-highlights',    true],
    ['scoreSummary', 'hide-score-summary', true],
    ['roleSummary',  'hide-role-summary',  true],
    ['showSeniority', 'hide-seniority', true],
    ['showScore',     'hide-score',     true],
    ['showSalary',    'hide-salary',    true],
    ['showKeywords',  'hide-keywords',  true],
    ['showLocation',  'hide-location',  true],
  ];
  for (const [key, cls, inv] of displayToggles) {
    const shouldAdd = inv ? (s[key] === false) : (s[key] === true);
    if (shouldAdd) document.body.classList.add(cls);
  }
  const he = document.getElementById('hide-empty-toggle');
  if (he && s.hideEmpty === true) {
    he.checked = true;
    document.body.classList.add('hide-empty-sections');
  }
  const hs = document.getElementById('hide-spontaneous-toggle');
  if (hs && s.hideSpontaneous === true) {
    hs.checked = true;
    document.body.classList.add('hide-spontaneous');
  }
}

/* --- Filters: seniority toggle + location/title/text search ------------- */
/* Query syntax: OR groups separated by "," or " or " (case-insensitive).
   Within a group, AND terms separated by "+". Example: "security + engineer, product manager"
   matches either (security AND engineer) OR (product manager). */
function parseQuery(id) {
  const raw = (document.getElementById(id)?.value || '').trim().toLowerCase();
  if (!raw) return [];
  const orGroups = raw.split(/\\s*,\\s*|\\s+or\\s+/i).filter(Boolean);
  return orGroups.map(g => g.split(/\\s*\\+\\s*/).map(s => s.trim()).filter(Boolean)).filter(a => a.length);
}
function matchQuery(haystack, groups) {
  if (!groups.length) return true;
  return groups.some(andTerms => andTerms.every(t => haystack.includes(t)));
}
function applyFilters() {
  // On every tab EXCEPT All we skip the location/title/text search filters.
  // The tab IS the filter. Clear any .hidden left over from a prior All
  // pass so switching back to Liked / Pipeline / etc. doesn't inherit a
  // stale location search.
  const isAll = document.body.classList.contains('tab-all');
  if (!isAll) {
    document.querySelectorAll('li.hidden, .spontaneous-row.hidden')
      .forEach(el => el.classList.remove('hidden'));
    // Re-compute group-heading emptiness so category labels (e.g.
    // "Big Tech") disappear when all their sections are hidden by the
    // tab's CSS. On Ranked that's every section → every heading hides.
    refreshGroupHeadings();
    refreshStateCounts();
    if (typeof _updateTabCounts === 'function') _updateTabCounts();
    return;
  }
  const locQ   = parseQuery('loc-filter');
  const titleQ = parseQuery('title-filter');
  const textQ  = parseQuery('text-filter');

  document.querySelectorAll('li[data-seniority]').forEach(li => {
    let hide = false;
    if (locQ.length && !matchQuery((li.dataset.locations || '').toLowerCase(), locQ)) hide = true;
    if (!hide && titleQ.length && !matchQuery((li.querySelector('.title')?.textContent || '').toLowerCase(), titleQ)) hide = true;
    if (!hide && textQ.length && !matchQuery((li.querySelector('.desc-body')?.textContent || '').toLowerCase(), textQ)) hide = true;
    li.classList.toggle('hidden', hide);
  });
  let total = 0;
  document.querySelectorAll('ul[data-section]').forEach(ul => {
    const sid = ul.dataset.section;
    const jobsVisible = ul.querySelectorAll('li.job:not(.hidden)').length;
    // A spontaneous ✉ in any state (liked / toapply / applied / app-rejected)
    // is user-flagged content just like a job with the same state — count it
    // as +1 for this section so the nav pill turns green, the counter
    // increments, and hide-empty-sections keeps the section on screen.
    const section = ul.closest('.company-section');
    // Only count the spontaneous row if its state is actually visible —
    // otherwise toggling off "Show Liked" would still count a hidden
    // liked ✉ Spontaneous and leave the section with an inflated counter.
    const spontStateful = section?.querySelector(
      '.spontaneous-row.liked:not(.hidden), .spontaneous-row.toapply:not(.hidden), .spontaneous-row.applied:not(.hidden), .spontaneous-row.app-rejected:not(.hidden)'
    ) ? 1 : 0;
    const visible = jobsVisible + spontStateful;
    total += visible;
    const navCount = document.querySelector('.nav-btn[href="#' + sid + '"] .nav-count');
    if (navCount) {
      navCount.textContent = visible;
      const btn = navCount.closest('.nav-btn');
      if (btn) {
        const fetched = parseInt(btn.dataset.fetched) || 0;
        btn.classList.toggle('has-jobs',   visible > 0);
        btn.classList.toggle('no-match',   visible === 0 && fetched > 0);
        btn.classList.toggle('no-fetched', visible === 0 && fetched === 0);
      }
    }
    // getElementById tolerates leading digits in the sid ("1password" etc.);
    // document.querySelector('#1password …') would throw SyntaxError and kill
    // the whole filter pass, silently disabling all downstream event handlers.
    const v = document.getElementById(sid)?.querySelector('.counter .v');
    if (v) v.textContent = visible;
    // Mark the parent .company-section empty when there's nothing visible.
    if (section) section.classList.toggle('empty', visible === 0);
  });
  const totalEl = document.getElementById('total-count');
  if (totalEl) totalEl.textContent = total;
  // Total NEW: visible <li.job> that carry a .badge.new-badge. Doesn't
  // include spontaneous rows (they're not new-badged server-side).
  const totalNewEl = document.getElementById('total-new-count');
  if (totalNewEl) {
    const n = document.querySelectorAll('li.job:not(.hidden) .badge.new-badge').length;
    totalNewEl.textContent = n;
  }
  refreshStateCounts();
  // Hide a nav-row (category label + all its company buttons) when every
  // button inside it has zero visible jobs. Runs after per-btn counts are
  // updated above so we react to filters, not just the initial render.
  document.querySelectorAll('.nav-row').forEach(row => {
    const btns = row.querySelectorAll('.nav-btn');
    const anyHit = [...btns].some(b => b.classList.contains('has-jobs'));
    row.classList.toggle('empty', btns.length > 0 && !anyHit);
  });
  refreshGroupHeadings();
  if (typeof _updateTabCounts === 'function') _updateTabCounts();
  saveFilters();
}

// Body-side group headings (<h2 class="group-heading">"AI Startups"</h2>)
// don't live inside a wrapper — they're siblings of the .company-section
// blocks that follow. Walk each heading's following siblings up to the next
// heading and mark it .empty when every .company-section in that range is
// itself .empty. The CSS rule that hides .empty headings only fires when
// both hide toggles are on, matching the sections' own hide condition.
function refreshGroupHeadings() {
  // Walk each category heading's following siblings up to the next
  // heading. The heading is "empty" when every .company-section in that
  // range is actually hidden — on the All tab that's driven by the
  // .empty class applyFilters sets, on every other tab it's driven by
  // the body.tab-X CSS rules. getComputedStyle covers both cases.
  document.querySelectorAll('h2.group-heading').forEach(h => {
    let anyVisible = false;
    let el = h.nextElementSibling;
    while (el && !el.matches('h2.group-heading')) {
      if (el.matches('.company-section')
          && !el.classList.contains('empty')
          && getComputedStyle(el).display !== 'none') {
        anyVisible = true;
        break;
      }
      el = el.nextElementSibling;
    }
    h.classList.toggle('empty', !anyVisible);
  });
}

// Count visible <li> in each terminal state (applied excludes toapply/liked,
// toapply excludes liked). Kept as a function so we can call it after every
// state-button toggle without re-running the full filter pass. The
// per-state counts now live on the tab labels — delegate to the tab
// counter so every caller (there are several) refreshes both at once.
function refreshStateCounts() {
  if (typeof _updateTabCounts === 'function') _updateTabCounts();
}

loadFilters();
applyFilters();

/* --- Dump-URLs buttons -------------------------------------------------- */
function collectUrls(selector) {
  const urls = [];
  const seen = new Set();
  document.querySelectorAll(selector).forEach(li => {
    // Every visible job has a .reject or .like button with the canonical
    // URL in data-url, which is more reliable than parsing the desc-body link.
    const btn = li.querySelector('.reject[data-url], .like[data-url]');
    const url = btn?.dataset.url;
    if (url && !seen.has(url)) { seen.add(url); urls.push(url); }
  });
  return urls;
}
async function copyToClipboard(text, statusEl, okMsg) {
  try {
    await navigator.clipboard.writeText(text);
    statusEl.textContent = okMsg;
  } catch (e) {
    // Fallback for non-HTTPS contexts (localhost usually works, but just in case).
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); statusEl.textContent = okMsg; }
    catch (e2) { statusEl.textContent = 'Copy failed: ' + e2.message; }
    ta.remove();
  }
  setTimeout(() => { statusEl.textContent = ''; }, 3000);
}
document.getElementById('dump-all')?.addEventListener('click', () => {
  const urls = collectUrls('li.job:not(.hidden)');
  const status = document.getElementById('dump-status');
  if (!urls.length) { status.textContent = 'No visible jobs.'; setTimeout(() => status.textContent = '', 3000); return; }
  copyToClipboard(urls.join('\\n') + '\\n', status, 'Copied ' + urls.length + ' URLs.');
});
document.getElementById('dump-selected')?.addEventListener('click', () => {
  // "Selected" = any of +1, To apply, Applied (three states).
  const urls = collectUrls('li.job.liked:not(.hidden), li.job.toapply:not(.hidden), li.job.applied:not(.hidden)');
  const status = document.getElementById('dump-status');
  if (!urls.length) { status.textContent = 'No +1 jobs visible.'; setTimeout(() => status.textContent = '', 3000); return; }
  copyToClipboard(urls.join('\\n') + '\\n', status, 'Copied ' + urls.length + ' selected URLs.');
});

/* Build a self-contained bash script that curls every visible job URL and
   prints anything that looks broken, with enough debug info (final URL after
   redirects, HTTP code, size, content-type, page title, "not found"/"filled"
   markers) that we can tell WHY it broke — 404 vs Cloudflare vs job removed
   vs bad slug. */
function buildProbeScript(urls) {
  // Emit a Python + Playwright probe. curl misses every SPA-only failure
  // (blank Ashby shell, blank cursor.com/careers, etc.) because it can't run
  // JS. Playwright renders each page in real Chromium, waits for the SPA to
  // settle, then checks the rendered <h1>/<title>/body for "job not found"
  // markers. "ok" means the probe saw a real posting.
  const urlsJson = JSON.stringify(urls, null, 2);
  const now = new Date().toISOString();
  return [
    '#!/usr/bin/env python3',
    '# probe_visible.py - auto-generated ' + now,
    '#',
    '# Renders each visible job URL with headless Chromium (same engine used by',
    '# jobs.py itself). Prints one block per URL that looks broken. Anything',
    '# printed as "ok URL" is a URL that a real browser can open and see a real',
    '# job posting on.',
    '#',
    '# Run:  .venv-macos/bin/python debug/probe_visible.py',
    'import re, sys',
    'from playwright.sync_api import sync_playwright',
    '',
    'UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "',
    '      "AppleWebKit/537.36 (KHTML, like Gecko) "',
    '      "Chrome/120.0.0.0 Safari/537.36")',
    '',
    'URLS = ' + urlsJson,
    '',
    'MISSING_RE = re.compile(',
    '    r"("',
    '    r"job (not found|no longer available|has been filled|has been removed|has expired)|"',
    '    r"position (has been filled|is no longer|has closed|is no longer available)|"',
    '    r"posting (not found|no longer|has been closed|has expired)|"',
    '    r"page not found|404 not found|this page (isn.t|doesn.t exist)|"',
    '    r"we can.t find|couldn.t find (this|the) (job|role|posting)|"',
    '    r"you need to enable javascript"',
    '    r")",',
    '    re.I,',
    ')',
    '',
    '# Every visible job page must contain a positive signal — an obvious',
    '# "Apply" affordance or a big title header. If neither is present AND the',
    '# body is short, the SPA never resolved a real posting.',
    'APPLY_RE = re.compile(r"apply (now|for this|to this)|application form", re.I)',
    '',
    'def probe(page, url):',
    '    try:',
    '        resp = page.goto(url, wait_until="domcontentloaded", timeout=25000)',
    '    except Exception as e:',
    '        return {"error": str(e)[:200], "http": None}',
    '    try:',
    '        page.wait_for_timeout(2500)  # let the SPA finish rendering',
    '    except Exception:',
    '        pass',
    '    try:',
    '        title = (page.title() or "")[:200]',
    '    except Exception:',
    '        title = ""',
    '    try:',
    '        h1 = ""',
    '        if page.locator("h1").count():',
    '            h1 = (page.locator("h1").first.text_content(timeout=1500) or "").strip()[:200]',
    '    except Exception:',
    '        h1 = ""',
    '    try:',
    '        body = (page.locator("body").inner_text(timeout=3000) or "")',
    '    except Exception:',
    '        body = ""',
    '    flags = []',
    '    http = resp.status if resp else None',
    '    if http and http >= 400:',
    '        flags.append(f"http-{http}")',
    '    if MISSING_RE.search(body[:5000]) or MISSING_RE.search(title):',
    '        flags.append("job-missing-marker")',
    '    if len(body.strip()) < 400 and not APPLY_RE.search(body):',
    '        flags.append("empty-page")',
    '    final = page.url',
    '    if final and final != url and "/careers" in final and final.rstrip("/").endswith("/careers"):',
    '        flags.append("redirected-to-careers-root")',
    '    return {',
    '        "http": http, "final": final, "title": title, "h1": h1,',
    '        "body_len": len(body), "flags": flags,',
    '    }',
    '',
    'def main():',
    '    total = len(URLS); bad = 0',
    '    print(f"== Checking {total} URLs (headless Chromium) ==\\\\n")',
    '    with sync_playwright() as pw:',
    '        browser = pw.chromium.launch(headless=True)',
    '        ctx = browser.new_context(user_agent=UA)',
    '        page = ctx.new_page()',
    '        for u in URLS:',
    '            r = probe(page, u)',
    '            if "error" in r:',
    '                bad += 1',
    '                print("---")',
    '                print(f"URL:   {u}")',
    '                print(f"error: {r[\\"error\\"]}")',
    '                print()',
    '                continue',
    '            if not r["flags"]:',
    '                print(f"ok  {u}")',
    '            else:',
    '                bad += 1',
    '                print("---")',
    '                print(f"URL:      {u}")',
    '                print(f"http:     {r[\\"http\\"]}   body: {r[\\"body_len\\"]}B")',
    '                if r["final"] != u:',
    '                    print(f"final:    {r[\\"final\\"]}")',
    '                if r["h1"]:    print(f"h1:       {r[\\"h1\\"]}")',
    '                if r["title"]: print(f"title:    {r[\\"title\\"]}")',
    '                print(f"flags:    {\\",\\".join(r[\\"flags\\"])}")',
    '                print()',
    '        browser.close()',
    '    print(f"\\\\n== {bad} / {total} URLs flagged ==")',
    '    sys.exit(1 if bad else 0)',
    '',
    'if __name__ == "__main__":',
    '    main()',
    ''
  ].join('\\n');
}
document.getElementById('dump-sh')?.addEventListener('click', async () => {
  const urls = collectUrls('li.job:not(.hidden)');
  const status = document.getElementById('dump-status');
  if (!urls.length) { status.textContent = 'No visible jobs.'; setTimeout(() => status.textContent = '', 3000); return; }
  const script = buildProbeScript(urls);
  try {
    const base = location.protocol === 'file:' ? SERVER_URL : '';
    const res = await fetch(base + '/save-probe', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({script})
    });
    if (!res.ok) throw new Error('http ' + res.status);
    status.textContent = 'Wrote debug/probe_visible.py (' + urls.length + ' URLs) — run: .venv-macos/bin/python debug/probe_visible.py';
  } catch (e) {
    status.textContent = 'Save failed (' + e.message + ') — falling back to clipboard.';
    copyToClipboard(script, status, 'Copied probe script (' + urls.length + ' URLs) — paste into debug/probe_visible.py');
    return;
  }
  setTimeout(() => { status.textContent = ''; }, 5000);
});

// Build a bash script that opens each +1 URL in the default browser. Uses
// macOS `open`, Linux `xdg-open`, Windows `start` — the shebang picks bash
// so `open` works out of the box on the user's Mac.
function buildOpenSelectedScript(urls) {
  const arrLines = urls.map(u => '  "' + u.replace(/"/g, '\\\\"') + '"').join('\\n');
  return [
    '#!/usr/bin/env bash',
    '# open_selected.sh - opens every liked (+1) job URL in your browser.',
    '# Auto-generated ' + new Date().toISOString(),
    '# Run:  bash debug/open_selected.sh',
    '',
    'set -uo pipefail',
    '',
    'URLS=(',
    arrLines,
    ')',
    '',
    'opener() {',
    '  if command -v open >/dev/null 2>&1; then open "$1";',
    '  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1";',
    '  else echo "no browser opener found for $1"; fi',
    '}',
    '',
    'for u in "${URLS[@]}"; do',
    '  echo "opening $u"',
    '  opener "$u"',
    '  sleep 0.15   # avoid overwhelming the browser',
    'done',
    'echo "done - opened ${#URLS[@]} URLs"',
    ''
  ].join('\\n');
}
// Per-state "Open …" buttons: opens every URL in a new tab AND writes a .sh
// mirror to debug/. window.open must run inside the user-gesture handler
// (not inside an await continuation) or Safari/Firefox block popups. We
// open first, then POST the script save request in the background.
function wireOpenButton(btnId, selector, filename, emptyMsg, label) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.addEventListener('click', (ev) => {
    const urls = collectUrls(selector);
    const status = document.getElementById('dump-status');
    if (!urls.length) {
      status.textContent = emptyMsg;
      setTimeout(() => status.textContent = '', 3000);
      return;
    }
    const openMode = ev.metaKey || ev.ctrlKey;    // ⌘/Ctrl-click
    const copyMode = ev.altKey;                   // Alt-click
    const askMode  = ev.shiftKey;                 // ⇧-click
    // Bare click: do nothing — this is a passive counter/label now. The
    // modifier keys are the only way to trigger an action.
    if (!openMode && !copyMode && !askMode) {
      ev.preventDefault();
      status.textContent = 'Use ⌘/Ctrl-click to open · ⌥/Alt-click to copy · ⇧-click to ask Claude.';
      setTimeout(() => { if (status.textContent.startsWith('Use ')) status.textContent = ''; }, 4000);
      return;
    }
    if (askMode) {
      ev.preventDefault();
      openClaudeWithPrompt(buildClaudePromptForUrls(urls), status);
      status.textContent = 'Asking Claude about ' + urls.length + ' job' + (urls.length>1?'s':'') + '…';
      setTimeout(() => { if (status.textContent.startsWith('Asking')) status.textContent = ''; }, 4000);
      return;
    }
    if (copyMode) {
      ev.preventDefault();
      copyToClipboard(urls.join('\\n') + '\\n', status,
        urls.length + ' links copied to clipboard');
      return;
    }
    // openMode = ⌘/Ctrl-click — open every URL synchronously in the click
    // handler (otherwise Safari/Firefox block popups).
    let opened = 0;
    for (const u of urls) {
      const win = window.open(u, '_blank', 'noopener,noreferrer');
      if (win) opened++;
    }
    status.textContent = 'Opening ' + opened + '/' + urls.length + ' ' + label + ' URLs…';
    if (opened < urls.length) {
      status.textContent += ' (browser blocked some popups — allow popups for this site)';
    }
    // Fire-and-forget the .sh save.
    const script = buildOpenSelectedScript(urls);
    (async () => {
      try {
        const base = location.protocol === 'file:' ? SERVER_URL : '';
        const res = await fetch(base + '/save-open-selected', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({script, filename}),
        });
        if (!res.ok) throw new Error('http ' + res.status);
        status.textContent += ' · saved debug/' + filename;
      } catch (e) {
        status.textContent += ' · save failed (' + e.message + ')';
      }
      setTimeout(() => { status.textContent = ''; }, 6000);
    })();
  });
}
// The old top-bar #open-liked / #open-toapply / #open-applied /
// #open-app-rejected buttons were removed; the ⌘/⌥/⇧-click shortcuts live
// on the tab buttons now (see _handleTabShortcut in the Primary tabs block).

/* --- Refresh button: POST /refresh, poll /refresh-status ---------------- */
(() => {
  const status = document.getElementById('dump-status');
  const base = () => location.protocol === 'file:' ? SERVER_URL : '';
  // Sources we've already prompted the user about this refresh — guards
  // against re-popping the modal if the fetcher's pending file lingers
  // for a poll cycle after we POST a decision.
  const _runawayHandled = new Set();
  function _showRunawayModal(entry) {
    const key = entry.source;
    if (_runawayHandled.has(key)) return;
    _runawayHandled.add(key);
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop runaway-backdrop visible';
    backdrop.innerHTML =
      '<div class="modal">' +
      '  <h3>Lots of jobs for <code></code> on <strong></strong></h3>' +
      '  <p class="runaway-info"></p>' +
      '  <p class="runaway-tip">Broad single words (<em>engineer</em>, <em>developer</em>…) match hundreds of jobs. Narrower queries like <em>security engineer</em> finish in seconds.</p>' +
      '  <div class="modal-actions">' +
      '    <button type="button" class="runaway-stop primary">Stop this source</button>' +
      '    <button type="button" class="runaway-continue">Keep fetching</button>' +
      '  </div>' +
      '</div>';
    backdrop.querySelector('code').textContent = '"' + entry.query + '"';
    backdrop.querySelector('strong').textContent = entry.source;
    backdrop.querySelector('.runaway-info').textContent =
      entry.jobs + '+ jobs found after ' + entry.pages + ' page(s). '
      + 'Keeping going will fetch up to a few more pages and open each job for description extraction (slow).';
    document.body.appendChild(backdrop);
    const decide = async (action) => {
      backdrop.remove();
      try {
        await fetch(base() + '/refresh-decision', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source: entry.source, action}),
        });
      } catch (e) {
        console.error('refresh-decision failed', e);
      }
    };
    backdrop.querySelector('.runaway-stop').addEventListener('click', () => decide('stop'));
    backdrop.querySelector('.runaway-continue').addEventListener('click', () => decide('continue'));
  }
  // Floating "Refreshing… Ns" pill — fixed position, so it stays
  // visible no matter how far the user has scrolled. Shown for the
  // entire pollUntilDone lifecycle, hidden on terminal.
  const floater = document.getElementById('refresh-floater');
  function _showFloater(text) {
    if (!floater) return;
    floater.textContent = text;
    floater.classList.add('visible');
  }
  function _hideFloater() {
    if (!floater) return;
    floater.classList.remove('visible');
    floater.textContent = '';
  }
  async function pollUntilDone(label) {
    _runawayHandled.clear();
    _showFloater(label + '…');
    try {
      while (true) {
        await new Promise(r => setTimeout(r, 2000));
        let s;
        try {
          const r = await fetch(base() + '/refresh-status', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
          s = await r.json();
        } catch (e) {
          status.textContent = label + ' status check failed: ' + e.message;
          return false;
        }
        // Surface any pending runaway prompts BEFORE acting on terminal
        // states — a source might trigger right at the end of the fetch.
        if (Array.isArray(s.runaway)) {
          for (const entry of s.runaway) _showRunawayModal(entry);
        }
        if (s.status === 'running') {
          // Mirror onboarding's "N/M · latest · working on" line so the
          // user sees which sources have landed instead of a bare timer.
          const parts = [label + '… ' + s.elapsed + 's'];
          const p = s.progress || null;
          if (p && p.total) {
            parts.push(p.done_count + ' / ' + p.total + ' companies fetched');
            if (p.last_done) parts.push('latest: ' + p.last_done);
            if (p.currently_working) parts.push('working on: ' + p.currently_working);
          }
          const msg = parts.join(' · ');
          status.textContent = msg;
          _showFloater(msg);
        } else if (s.status === 'done') {
          status.textContent = label + ' done — reloading…';
          _showFloater(label + ' done — reloading…');
          return true;
        } else if (s.status === 'failed') {
          status.textContent = label + ' failed: ' + (s.error || 'unknown');
          alert(label + ' failed:\\n' + (s.error || 'unknown error'));
          return false;
        } else {
          // idle without ever running — retry once
          return false;
        }
      }
    } finally {
      // Only auto-hide on failure/idle; the `done` path reloads the
      // page, so leaving the pill up until reload gives the user
      // confirmation that the refresh finished.
      if (floater && !floater.textContent.includes('reloading')) {
        _hideFloater();
      }
    }
  }
  function wireActionButton(btnId, endpoint, label) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener('click', async () => {
      if (btn.disabled) return;
      btn.disabled = true;
      btn.classList.add('busy');
      status.textContent = label + '…';
      try {
        const r = await fetch(base() + endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
        if (!r.ok) throw new Error('http ' + r.status);
        const ok = await pollUntilDone(label);
        if (ok) {
          setTimeout(() => location.reload(), 400);
          return;
        }
      } catch (e) {
        status.textContent = label + ' failed: ' + e.message;
        alert(label + ' failed: ' + e.message);
      }
      btn.disabled = false;
      btn.classList.remove('busy');
    });
  }
  wireActionButton('refresh-btn', '/refresh', 'Refreshing');

  // Auto-refresh once per tab session so `make run` always starts with
  // a fresh fetch. sessionStorage survives the reload triggered when
  // the refresh completes (same tab), so we don't loop; a new tab or a
  // fresh `make run` opens a new session and re-triggers.
  const AUTO_REFRESH_KEY = 'jobs:auto-refresh-done';
  try {
    if (!sessionStorage.getItem(AUTO_REFRESH_KEY)) {
      sessionStorage.setItem(AUTO_REFRESH_KEY, '1');
      const btn = document.getElementById('refresh-btn');
      if (btn) setTimeout(() => btn.click(), 50);
    }
  } catch (e) { /* sessionStorage blocked — skip auto-refresh */ }
})();

/* --- "AI" button: ask the LLM to rate every visible job, paste result back - */
const CLAUDE_FIT_KEY = 'jobs:claude-fit:v1';
function _loadClaudeFits() {
  try { return JSON.parse(localStorage.getItem(CLAUDE_FIT_KEY) || '{}') || {}; }
  catch (e) { return {}; }
}
function _saveClaudeFits(m) {
  try { localStorage.setItem(CLAUDE_FIT_KEY, JSON.stringify(m)); } catch (e) {}
}
// Insert / update the fit badge on a single <li.job> or <.spontaneous-row>.
// If score is nullish, removes any existing badge.
function _renderClaudeFitOnLi(row, score, reason) {
  if (!row) return;
  const isSpont = row.classList && row.classList.contains('spontaneous-row');
  const scope = isSpont ? row : row.querySelector('summary');
  if (!scope) return;
  let badge = scope.querySelector('.badge.claude-fit');
  // Clean up any legacy inline reason span from the previous iteration.
  const stale = scope.querySelector('.claude-fit-reason');
  if (stale) stale.remove();
  if (!score) {
    if (badge) badge.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement('span');
    badge.className = 'badge claude-fit';
    let anchor;
    if (isSpont) {
      anchor = scope.querySelector('.spontaneous-link');
    } else {
      anchor = scope.querySelector('.badge.xp')
            || scope.querySelector('.badge.seniority')
            || scope.querySelector('.title');
    }
    if (anchor) anchor.after(badge); else scope.appendChild(badge);
  }
  const n = parseInt(score, 10);
  // Custom tooltip via data-tooltip (instant on hover — the native title
  // attribute has a 500-1000ms delay). CSS below styles .badge.claude-fit:hover::after.
  if (reason) {
    badge.dataset.tooltip = reason;
    badge.removeAttribute('title');
  } else {
    badge.title = 'Click AI to re-score';
    delete badge.dataset.tooltip;
  }
  badge.textContent = 'Score: ' + n + '/10';
  // Keep the Ranked tab in order if it is active while scores change.
  // Guarded on tab-ranked so this is a no-op in every other view.
  if (!isSpont && document.body.classList.contains('tab-ranked')
      && typeof _buildRankedView === 'function') {
    _buildRankedView();
  }
}
function _applyClaudeFitsToDOM() {
  const map = _loadClaudeFits();
  document.querySelectorAll('li.job').forEach(li => {
    const url = li.querySelector('button.like, button.reject')?.dataset.url;
    if (!url) return;
    const entry = map[url];
    if (entry) _renderClaudeFitOnLi(li, entry.score, entry.reason);
  });
  document.querySelectorAll('.spontaneous-row').forEach(row => {
    const url = row.querySelector('button.spontaneous-like')?.dataset.url;
    if (!url) return;
    const entry = map[url];
    if (entry) _renderClaudeFitOnLi(row, entry.score, entry.reason);
  });
}
// Merge server-side scores into localStorage so hydration + per-tab state
// stay consistent. When both sides have an entry we keep the FRESHER one
// (compared on `ts`, an ISO 8601 string so lexicographic order works).
// Rationale: re-scoring the same job via the paste bar updates localStorage
// but NOT claude_fit_cache.json. On refresh the server was blindly winning
// and reverting the just-pasted new score. Timestamp comparison fixes that
// without needing a server round-trip from the paste bar.
(function _mergeServerClaudeFits() {
  if (!CLAUDE_FITS_SERVER || typeof CLAUDE_FITS_SERVER !== 'object') return;
  const map = _loadClaudeFits();
  let changed = false;
  for (const [url, entry] of Object.entries(CLAUDE_FITS_SERVER)) {
    if (!entry || typeof entry.score !== 'number') continue;
    const local = map[url];
    if (local && typeof local.ts === 'string' && typeof entry.ts === 'string'
        && local.ts > entry.ts) {
      continue;   // localStorage entry is newer — keep it
    }
    map[url] = entry;
    changed = true;
  }
  if (changed) _saveClaudeFits(map);
})();
// Hydrate badges on first render.
_applyClaudeFitsToDOM();

// Floating tooltip for Claude fit badges — instant on hover, independent
// of any parent's overflow:hidden (appended to <body>).
(function _wireClaudeFitTooltip() {
  let tip = null;
  const show = (badge) => {
    const text = badge.dataset.tooltip;
    if (!text) return;
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'claude-fit-tooltip';
      document.body.appendChild(tip);
    }
    tip.textContent = text;
    const rect = badge.getBoundingClientRect();
    tip.style.visibility = 'hidden';
    tip.style.left = '0px';
    tip.style.top = '0px';
    // Measure after setting the text so width is correct.
    const tipRect = tip.getBoundingClientRect();
    let left = rect.left + rect.width / 2 - tipRect.width / 2;
    let top = rect.top - tipRect.height - 8;
    // Keep inside viewport horizontally.
    const margin = 8;
    left = Math.max(margin, Math.min(left, window.innerWidth - tipRect.width - margin));
    // If no room above, flip to below.
    if (top < margin) top = rect.bottom + 8;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
    tip.style.visibility = 'visible';
  };
  const hide = () => { if (tip) tip.style.visibility = 'hidden'; };
  // Delegate so it works for badges created after initial render.
  document.addEventListener('mouseover', (e) => {
    const badge = e.target.closest?.('.badge.claude-fit[data-tooltip]');
    if (badge) show(badge);
  });
  document.addEventListener('mouseout', (e) => {
    if (e.target.closest?.('.badge.claude-fit[data-tooltip]')) hide();
  });
  window.addEventListener('scroll', hide, true);
})();

function _collectVisibleJobUrls() {
  const urls = [];
  const seen = new Set();
  document.querySelectorAll('li.job:not(.hidden)').forEach(li => {
    const url = li.querySelector('button.like, button.reject')?.dataset.url;
    if (url && !seen.has(url)) { seen.add(url); urls.push(url); }
  });
  // Only include ✉ Spontaneous rows the user has already liked
  // (or moved further through the pipeline). The vast majority of
  // "general application" links are low-signal placeholders, not worth
  // paying for an LLM round-trip — only score the ones the user
  // explicitly flagged.
  document.querySelectorAll(
    '.spontaneous-row.liked, .spontaneous-row.toapply, '
    + '.spontaneous-row.applied, .spontaneous-row.app-rejected'
  ).forEach(row => {
    const url = row.querySelector('button.spontaneous-like')?.dataset.url;
    if (url && !seen.has(url)) { seen.add(url); urls.push(url); }
  });
  return urls;
}

// Same selection logic as _collectVisibleJobUrls, but skips rows that
// already carry a .badge.claude-fit (= already scored by the LLM).
// Powers ⌘U "AI score only the unscored" so the user avoids re-paying
// for jobs they've already rated.
function _collectUnscoredJobUrls() {
  const urls = [];
  const seen = new Set();
  document.querySelectorAll('li.job:not(.hidden)').forEach(li => {
    if (li.querySelector('.badge.claude-fit')) return;
    const url = li.querySelector('button.like, button.reject')?.dataset.url;
    if (url && !seen.has(url)) { seen.add(url); urls.push(url); }
  });
  document.querySelectorAll(
    '.spontaneous-row.liked, .spontaneous-row.toapply, '
    + '.spontaneous-row.applied, .spontaneous-row.app-rejected'
  ).forEach(row => {
    if (row.querySelector('.badge.claude-fit')) return;
    const url = row.querySelector('button.spontaneous-like')?.dataset.url;
    if (url && !seen.has(url)) { seen.add(url); urls.push(url); }
  });
  return urls;
}

// Prompt for a batched Claude.ai scoring request. Claude fetches each URL
// itself — this gives up-to-date, complete descriptions at the cost of a
// per-domain permission prompt. User's call: our rendered HTML can be
// stale/incomplete so forcing Claude to go to the source is preferred.
function _buildClaudeScoringPrompt(urls) {
  const numbered = urls.map((u, i) => (i + 1) + ". " + u).join('\\n');
  if (_getClaudeLang() === 'fr') {
    return (
      "Évalue le fit de chacun de ces " + urls.length + " jobs par rapport à mon profil (je te le partage sur demande).\\n" +
      "Pour chaque job, va chercher la description sur le site, puis :\\n" +
      " 1) donne un score de fit sur 10 et une justification de 2-3 phrases couvrant les points clés (missions, séniorité, techno, red flags) ;\\n" +
      " 2) extrait la fourchette salariale UNIQUEMENT en chiffres (ex: « $150k-$200k », « 70k€ », « £80k-£120k + equity »). Pas de phrase, pas de \\"Base salary:\\", pas de \\"Annual compensation range:\\". Juste les montants + la devise + \\"+ equity\\" si applicable. Si aucun salaire n'est publié, écris « none ».\\n\\n" +
      "FORMAT STRICT — EXACTEMENT DEUX LIGNES PAR JOB (score sur une ligne, salaire sur la suivante) :\\n" +
      "N. X/10 — <justification 2-3 phrases sur une seule ligne>\\n" +
      "SAL N: <chiffres uniquement ou none>\\n\\n" +
      "Jobs :\\n" +
      numbered
    );
  }
  return (
    "Rate the fit of each of these " + urls.length + " jobs against my profile (I'll share my profile on request).\\n" +
    "For each job, fetch the description from the site, then:\\n" +
    " 1) give a fit score out of 10 and a 2-3 sentence justification covering the key points (missions, seniority, tech, red flags);\\n" +
    " 2) extract the salary range in NUMBERS ONLY (e.g. \\"$150k-$200k\\", \\"70k€\\", \\"£80k-£120k + equity\\"). No sentence, no \\"Base salary:\\", no \\"Annual compensation range:\\". Just the amounts + currency + \\"+ equity\\" if applicable. If no salary is published, write \\"none\\".\\n\\n" +
    "STRICT RESPONSE FORMAT — EXACTLY TWO LINES PER JOB (score on one line, salary on the next):\\n" +
    "N. X/10 — <2-3 sentence justification on a single line>\\n" +
    "SAL N: <numbers only or none>\\n\\n" +
    "Jobs:\\n" +
    numbered
  );
}

// Parser tolerant to common markdown variants:
//   "1. 8/10 — fit raison" / "1) 8/10 - fit raison" / "**1.** 8/10 ..."
// Salaries live on their own line "SAL N: value" so the model is more
// likely to produce them reliably (the inline "— SAL" suffix on a long
// justification was being dropped by Claude). Two passes: score lines
// first, then salary lines keyed by job index.
const _CLAUDE_FIT_LINE_RE = /^[*\\s>-]*(\\d+)[.)]\\s*(\\d+)\\s*\\/\\s*10\\s*[—\\-–:]+\\s*(.*)$/gm;
const _CLAUDE_FIT_SAL_LINE_RE = /^[*\\s>-]*SAL\\s*(\\d+)\\s*[:\\-]\\s*(.+?)\\s*$/gim;
// Also accept a legacy inline "— SAL: <value>" suffix on the score line
// (older runs may have been pinned chats trained on the previous format).
const _CLAUDE_FIT_SAL_INLINE_RE = /\\s*[—\\-–]\\s*SAL\\s*:\\s*(.+?)\\s*$/i;
function _cleanSalary(raw) {
  const v = (raw || '').trim().replace(/^["']|["']$/g, '');
  if (!v) return '';
  if (/^(none|n\\/?a|unknown|not\\s+(?:disclosed|published|listed|specified))$/i.test(v)) {
    return '';
  }
  return v.slice(0, 100);
}
function _parseClaudeFits(text, urls) {
  const out = {};
  if (!text || !urls || !urls.length) return out;
  // Pass 1 — score + reason lines.
  _CLAUDE_FIT_LINE_RE.lastIndex = 0;
  let m;
  while ((m = _CLAUDE_FIT_LINE_RE.exec(text)) !== null) {
    const idx = parseInt(m[1], 10);
    const score = parseInt(m[2], 10);
    let reason = (m[3] || '').trim();
    // Legacy inline SAL suffix — strip it from the reason and remember.
    let salary = '';
    const inline = _CLAUDE_FIT_SAL_INLINE_RE.exec(reason);
    if (inline) {
      reason = reason.slice(0, inline.index).trim();
      salary = _cleanSalary(inline[1]);
    }
    if (idx >= 1 && idx <= urls.length && score >= 0 && score <= 10) {
      out[urls[idx - 1]] = { score, reason, salary, ts: new Date().toISOString() };
    }
  }
  // Pass 2 — standalone "SAL N: value" lines overwrite the salary slot.
  _CLAUDE_FIT_SAL_LINE_RE.lastIndex = 0;
  while ((m = _CLAUDE_FIT_SAL_LINE_RE.exec(text)) !== null) {
    const idx = parseInt(m[1], 10);
    if (idx < 1 || idx > urls.length) continue;
    const entry = out[urls[idx - 1]];
    if (!entry) continue;
    const cleaned = _cleanSalary(m[2]);
    if (cleaned) entry.salary = cleaned;
  }
  return out;
}

// 1-click flow: click AI → opens the pinned chat with the prompt AND shows a
// sticky paste bar at the bottom of the page. User pastes Claude's reply
// → scores save and badges appear automatically. No "Save" button.
function _openClaudePasteBar(urls, promptMode) {
  let bar = document.getElementById('claude-paste-bar');
  if (bar) bar.remove();
  // Explain how the Claude tab was opened so the user knows if they need
  // to paste the PROMPT first (long prompts don't fit in the URL).
  const promptHint =
      promptMode === 'copied-to-pinned'
      ? '<div class="paste-bar-hint">📎 Opened your pinned Claude chat. <strong>⌘V to send the prompt</strong>, then paste the reply here.</div>'
      : promptMode === 'copied'
      ? '<div class="paste-bar-hint">⚠ Prompt too long for URL — <strong>⌘V in Claude first</strong> to send it, then paste its reply here.</div>'
      : promptMode === 'failed'
      ? '<div class="paste-bar-hint">⚠ Could not copy prompt. Re-click AI or dismiss.</div>'
      : '';
  bar = document.createElement('div');
  bar.id = 'claude-paste-bar';
  bar.innerHTML =
    '<div class="paste-bar-inner">' +
    promptHint +
    '  <span class="paste-bar-label">Paste Claude\\'s reply here · <span id="claude-paste-status">' + urls.length + ' jobs</span></span>' +
    '  <textarea id="claude-paste-area" rows="2" placeholder="&quot;1. 8/10 — reason\\nSAL 1: $150k-$200k\\n2. ...&quot;"></textarea>' +
    '  <button type="button" id="claude-paste-close" title="Dismiss">×</button>' +
    '</div>';
  document.body.appendChild(bar);
  const ta = bar.querySelector('#claude-paste-area');
  const status = bar.querySelector('#claude-paste-status');
  const close = () => bar.remove();
  bar.querySelector('#claude-paste-close').onclick = close;
  // Auto-focus when the user returns to this tab (visibility change).
  const onVisible = () => { if (!document.hidden) ta.focus(); };
  document.addEventListener('visibilitychange', onVisible);
  bar.addEventListener('remove', () => document.removeEventListener('visibilitychange', onVisible));
  ta.focus();
  // Parse on paste OR when the user types enough. Debounce by 200ms so
  // paste events don't fire mid-paste. "paste" event always fires once
  // per Cmd-V so we handle that directly.
  const tryParse = () => {
    const text = ta.value;
    if (!text.trim()) return;
    const parsed = _parseClaudeFits(text, urls);
    const n = Object.keys(parsed).length;
    if (n === 0) {
      status.textContent = 'no scores parsed — expected "N. X/10 — reason"';
      return;
    }
    const map = _loadClaudeFits();
    Object.assign(map, parsed);
    _saveClaudeFits(map);
    const manualSalaries = (typeof loadManualSalaries === 'function')
      ? loadManualSalaries() : {};
    for (const [url, entry] of Object.entries(parsed)) {
      let row = [...document.querySelectorAll('li.job')].find(l =>
        l.querySelector('button.like, button.reject')?.dataset.url === url);
      if (!row) {
        row = [...document.querySelectorAll('.spontaneous-row')].find(r =>
          r.querySelector('button.spontaneous-like')?.dataset.url === url);
      }
      if (row) {
        _renderClaudeFitOnLi(row, entry.score, entry.reason);
        // Salary came back from Claude — refresh the badge unless the
        // user has set a manual override (which always wins).
        if (entry.salary && !manualSalaries[url]
            && row.matches('li.job') && typeof renderSalaryOnLi === 'function') {
          renderSalaryOnLi(row, entry.salary, false);
        }
      }
    }
    // Also persist to the server so claude_fit_cache.json gets the new
    // score + reason. Without this, a refresh would reinject the stale
    // server-side entry and the user's new score would disappear.
    (async () => {
      try {
        const base = location.protocol === 'file:' ? SERVER_URL : '';
        await fetch(base + '/claude-fit-paste', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({scores: parsed}),
        });
      } catch (e) {
        dlog('claude-fit-paste persist failed', e);
      }
    })();
    status.textContent = '✓ ' + n + ' score' + (n>1?'s':'') + ' saved';
    bar.classList.add('done');
    setTimeout(close, 1500);
  };
  ta.addEventListener('paste', () => setTimeout(tryParse, 50));
  ta.addEventListener('input', () => {
    // In case the user types manually or edits what they pasted.
    clearTimeout(ta.__parseTimer);
    ta.__parseTimer = setTimeout(tryParse, 400);
  });
  // Esc dismisses.
  const onKey = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } };
  document.addEventListener('keydown', onKey);
}

// AI button — one click: opens the pinned chat with the batched prompt pre-filled
// AND shows a bottom paste bar for the reply. Zero clicks after that in
// our UI: paste → auto-save → badges. Shared by ⌘I (all visible) and
// ⌘U (only visible rows without a Claude-fit badge yet).
async function _runClaudeScoring(urls, emptyMsg) {
  const status = document.getElementById('dump-status');
  if (!urls.length) {
    if (status) { status.textContent = emptyMsg || 'No visible jobs to rate.'; setTimeout(() => status.textContent = '', 3000); }
    return;
  }
  const mode = await openClaudeWithPrompt(_buildClaudeScoringPrompt(urls), status);
  _openClaudePasteBar(urls, mode);
}
document.getElementById('claude-score-all')?.addEventListener('click', () => {
  _runClaudeScoring(_collectVisibleJobUrls());
});

document.querySelectorAll('.seniority-toggle').forEach(cb => cb.addEventListener('change', applyFilters));
['loc-filter', 'title-filter', 'text-filter'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', applyFilters);
});

function syncLocInputFromChecks() {
  const input = document.getElementById('loc-filter');
  if (!input) return;
  const values = [];
  document.querySelectorAll('.loc-cb:checked').forEach(cb => values.push(cb.dataset.value));
  input.value = values.join(', ');
  applyFilters();
}
document.querySelectorAll('.loc-cb').forEach(cb => cb.addEventListener('change', syncLocInputFromChecks));

// Bulk-select: All / None + per-country toggle.
document.getElementById('loc-all')?.addEventListener('click', () => {
  document.querySelectorAll('.loc-cb').forEach(cb => cb.checked = true);
  syncLocInputFromChecks();
});
document.getElementById('loc-none')?.addEventListener('click', () => {
  document.querySelectorAll('.loc-cb').forEach(cb => cb.checked = false);
  syncLocInputFromChecks();
});
document.querySelectorAll('.loc-country-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const boxes = btn.parentElement.querySelectorAll('.loc-cb');
    if (!boxes.length) return;
    // Toggle direction: if any box is unchecked, check them all; otherwise uncheck all.
    const anyUnchecked = [...boxes].some(cb => !cb.checked);
    boxes.forEach(cb => cb.checked = anyUnchecked);
    syncLocInputFromChecks();
  });
});

// score-summary / role-summary / highlight / show-* toggles live on
// /settings now, not in this DOM. Their body classes are applied by
// loadFilters() on page load; the settings page writes STORAGE_KEY back
// when the user toggles there. Nothing to wire on this page.

const heToggle = document.getElementById('hide-empty-toggle');
if (heToggle) {
  heToggle.addEventListener('change', () => {
    document.body.classList.toggle('hide-empty-sections', heToggle.checked);
    applyFilters();  // recompute .empty markers below
    saveFilters();
  });
}

const hsToggle = document.getElementById('hide-spontaneous-toggle');
if (hsToggle) {
  hsToggle.addEventListener('change', () => {
    document.body.classList.toggle('hide-spontaneous', hsToggle.checked);
    saveFilters();
  });
}

/* --- Primary tabs ------------------------------------------------------- */
// Each preset drives the Show-state checkboxes, the hide-spontaneous toggle,
// and an optional body class (tab-topfit / tab-spontaneous / tab-new) for
// extra CSS filters. The active tab is persisted in localStorage so the
// user lands on their last-used view on next page load.
const TAB_STORAGE_KEY = 'jobs:active-tab';
// Each tab adds a `tab-<name>` body class. Row visibility per state is now
// driven entirely by CSS (body.tab-liked li.job:not(.liked) {display:none}
// etc.), so the preset no longer carries per-state flags — only the body
// class. hide-spontaneous is only a knob on the All tab (user checkbox);
// every other tab manages its own spontaneous-row visibility via CSS.
const TAB_PRESETS = {
  all:         'tab-all',
  liked:       'tab-liked',
  toapply:     'tab-toapply',
  pipeline:    'tab-pipeline',
  ranked:      'tab-ranked',
  spontaneous: 'tab-spontaneous',
  new:         'tab-new',
  untouched:   'tab-untouched',
};
const _TAB_BODY_CLASSES = Object.values(TAB_PRESETS);
// Which rows each tab's ⌘/Alt/Shift-click shortcuts should act on.
// Mirrors the per-tab CSS visibility so "open all liked URLs" collects
// exactly what the user sees in the Liked tab.
const TAB_URL_SELECTORS = {
  all:         'li.job:not(.hidden), .spontaneous-row.liked, .spontaneous-row.toapply, .spontaneous-row.applied, .spontaneous-row.app-rejected',
  liked:       'li.job.liked, .spontaneous-row.liked',
  toapply:     'li.job.toapply, .spontaneous-row.toapply',
  pipeline:    'li.job.applied, li.job.app-rejected, .spontaneous-row.applied, .spontaneous-row.app-rejected',
  ranked:      'li.job',
  spontaneous: '.spontaneous-row',
  new:         'li.job:has(.badge.new-badge)',
  untouched:   'li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected)',
};

// Ranked view: pull every <li.job> out of its section into #ranked-list
// (sorted by Claude fit DESC), and prefix each title with the company
// name. The move preserves event listeners (unlike cloning), so like /
// toapply / applied / reject keep working. On deactivation each li is
// restored to its original parent + sibling position.
function _rankedFitScore(li) {
  const badge = li.querySelector('.badge.claude-fit');
  if (!badge) return -1;
  const m = /(\\d+)\\s*\\/\\s*10/.exec(badge.textContent || '');
  return m ? parseInt(m[1], 10) : -1;
}
// For spontaneous rows in Ranked view we inject invisible placeholders
// that occupy exactly the slots li.job has but spont does NOT:
//   - Review (R)  — circle 1.3rem        → front of row
//   - Reject (×)  — circle 1.3rem        → front of row
//   - Keep (K)    — circle 1.3rem        → after state buttons
// The ▶ details-marker (~0.9rem wide) that li.job's <details> renders
// inside its summary is simulated with CSS padding-left on the prefix,
// NOT a flex sibling — that way the spont row has the same number of
// flex children before the content column as li.job (7), and the gap
// math stays symmetric.
function _injectRankedSpacers(row) {
  if (row._rankedSpacers) return;
  const mk = (cls) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = cls + ' ranked-spacer';
    b.setAttribute('aria-hidden', 'true');
    b.tabIndex = -1;
    return b;
  };
  // Front spacers: review + reject
  const frontReview = mk('review');
  const frontReject = mk('reject');
  row.prepend(frontReject);
  row.prepend(frontReview);
  // Tail spacer (keep), inserted right before the prefix / spontaneous
  // link so the content column lines up with li.job's details column.
  const tailKeep = mk('keep');
  const anchor = row.querySelector('.company-prefix') || row.querySelector('.spontaneous-link');
  if (anchor) anchor.before(tailKeep); else row.appendChild(tailKeep);
  row._rankedSpacers = [frontReview, frontReject, tailKeep];
}
function _removeRankedSpacers(row) {
  if (!row._rankedSpacers) return;
  for (const el of row._rankedSpacers) el.remove();
  delete row._rankedSpacers;
}
function _buildRankedView() {
  const list = document.getElementById('ranked-list');
  if (!list) return;
  // Jobs: every li.job. Spontaneous: only rows that already carry a
  // Claude fit badge (otherwise we'd append 50+ unscored "✉ Spontaneous"
  // entries at the bottom, which is just noise).
  const rows = [
    ...document.querySelectorAll('li.job'),
    ...document.querySelectorAll('.spontaneous-row:has(.badge.claude-fit)'),
  ];
  for (const row of rows) {
    // Already in the ranked list? Just need to re-sort (score may have
    // changed via C). Keep its _origParent / _origNext untouched.
    if (row.parentElement === list) continue;
    row._origParent = row.parentElement;
    row._origNext = row.nextElementSibling;
    // Company name — li.job carries it on button.ask-claude[data-company],
    // spontaneous rows get it from the parent section's .board-link.
    const company = row.querySelector('button.ask-claude')?.dataset.company
                 || row.closest('.company-section')?.querySelector('.board-link')?.textContent?.trim()
                 || '';
    // Prefix target: .title span for li.job, .spontaneous-link for ✉ rows.
    const target = row.querySelector('summary .title')
                || row.querySelector('.spontaneous-link');
    if (company && target && !row._companyPrefix) {
      const span = document.createElement('span');
      span.className = 'company-prefix';
      span.textContent = company + ' — ';
      target.before(span);
      row._companyPrefix = span;
    }
    // Spontaneous rows get placeholder slots for the buttons li.job has
    // but they don't — Review / Reject / Keep / ▶ marker — so the flex
    // layout naturally lines up the state-button chain and the title.
    if (row.classList.contains('spontaneous-row')) {
      _injectRankedSpacers(row);
      // Swap the link text from "✉ Spontaneous" (the big orange button
      // style) to plain "Spontaneous application" that reads as a label
      // alongside the ranked titles. CSS strips the button styling.
      const link = row.querySelector('.spontaneous-link');
      if (link && !link.dataset.origText) {
        link.dataset.origText = link.textContent;
        link.textContent = 'Spontaneous application';
      }
    }
    list.appendChild(row);
  }
  // Sort by Claude fit DESC, no-score at the bottom. Preserve DOM order
  // among equal scores (stable sort).
  const sorted = [...list.querySelectorAll(':scope > li.job, :scope > .spontaneous-row')]
    .map((el, i) => ({el, score: _rankedFitScore(el), i}))
    .sort((a, b) => (b.score - a.score) || (a.i - b.i));
  for (const {el} of sorted) list.appendChild(el);
}
function _restoreRankedView() {
  const list = document.getElementById('ranked-list');
  if (!list) return;
  const rows = [...list.querySelectorAll(':scope > li.job, :scope > .spontaneous-row')];
  for (const row of rows) {
    _removeRankedSpacers(row);
    // Restore the original "✉ Spontaneous" button text if we swapped it.
    const link = row.querySelector('.spontaneous-link');
    if (link && link.dataset.origText) {
      link.textContent = link.dataset.origText;
      delete link.dataset.origText;
    }
    if (row._companyPrefix) {
      row._companyPrefix.remove();
      delete row._companyPrefix;
    }
    const parent = row._origParent;
    const next = row._origNext;
    if (parent) {
      if (next && next.parentElement === parent) parent.insertBefore(row, next);
      else parent.appendChild(row);
    }
    delete row._origParent;
    delete row._origNext;
  }
}
function activateTab(name) {
  const resolved = TAB_PRESETS[name] ? name : 'all';
  const cls = TAB_PRESETS[resolved];
  // hide-spontaneous is a user checkbox on the All tab only. On any other
  // tab we force it off so the tab's own CSS (which decides whether to
  // show spontaneous rows for that view) wins without specificity fights.
  if (resolved === 'all') {
    const hs = document.getElementById('hide-spontaneous-toggle');
    document.body.classList.toggle('hide-spontaneous', !!hs?.checked);
  } else {
    document.body.classList.remove('hide-spontaneous');
  }
  // Ranked view requires DOM moves — tear down any prior build before
  // switching, then rebuild if the target is Ranked. Restore BEFORE
  // flipping body classes so the sections are visible when we put the
  // li.job back.
  const wasRanked = document.body.classList.contains('tab-ranked');
  if (wasRanked && resolved !== 'ranked') _restoreRankedView();
  for (const c of _TAB_BODY_CLASSES) document.body.classList.remove(c);
  document.body.classList.add(cls);
  if (resolved === 'ranked') _buildRankedView();
  document.querySelectorAll('.tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === resolved);
  });
  try { localStorage.setItem(TAB_STORAGE_KEY, resolved); } catch (e) {}
  // applyFilters is a no-op on non-All tabs (it clears .hidden and refreshes
  // counts). On All it re-runs the location/title/text search filters.
  applyFilters();
  _updateTabCounts();
}

// Tab click: bare click switches tab; ⌘/Ctrl / ⌥/Alt / ⇧ shortcuts act on
// the URLs in that tab's selector without switching. Mirrors the behavior
// the old #open-liked / #open-toapply / etc. top-bar buttons had.
function _handleTabShortcut(ev, name) {
  const openMode = ev.metaKey || ev.ctrlKey;
  const copyMode = ev.altKey;
  const askMode  = ev.shiftKey;
  if (!openMode && !copyMode && !askMode) return false;
  ev.preventDefault();
  const selector = TAB_URL_SELECTORS[name] || TAB_URL_SELECTORS.all;
  const urls = collectUrls(selector);
  const status = document.getElementById('dump-status');
  if (!urls.length) {
    if (status) {
      status.textContent = 'No URLs for this tab.';
      setTimeout(() => { if (status.textContent.startsWith('No URLs')) status.textContent = ''; }, 3000);
    }
    return true;
  }
  if (askMode) {
    openClaudeWithPrompt(buildClaudePromptForUrls(urls), status);
    if (status) status.textContent = 'Asking Claude about ' + urls.length + ' job' + (urls.length>1?'s':'') + '…';
    return true;
  }
  if (copyMode) {
    copyToClipboard(urls.join('\\n') + '\\n', status, urls.length + ' links copied to clipboard');
    return true;
  }
  // ⌘-click: open each URL in a new tab (sync so popup blockers behave).
  let opened = 0;
  for (const u of urls) {
    const win = window.open(u, '_blank', 'noopener,noreferrer');
    if (win) opened++;
  }
  if (status) {
    status.textContent = 'Opening ' + opened + '/' + urls.length + ' URLs…';
    if (opened < urls.length) status.textContent += ' (browser blocked some popups)';
    setTimeout(() => { if (status.textContent.startsWith('Opening')) status.textContent = ''; }, 4000);
  }
  // Fire-and-forget save of a .sh script so the user can re-open the same
  // batch later from a shell.
  const script = buildOpenSelectedScript(urls);
  (async () => {
    try {
      const base = location.protocol === 'file:' ? SERVER_URL : '';
      await fetch(base + '/save-open-selected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({script, filename: 'open_' + name + '.sh'}),
      });
    } catch (e) { /* silent — this is a convenience */ }
  })();
  return true;
}
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', (ev) => {
    const name = btn.dataset.tab;
    if (_handleTabShortcut(ev, name)) return;
    activateTab(name);
  });
});

// Per-tab job counters shown as "Liked (12)" in the tab label. Reads
// counts from the DOM so it stays accurate as the user likes/rejects
// without a server round-trip. Called on page init (via applyFilters →
// refreshStateCounts), after state changes, and after Claude fit updates.
// No module-level cache because applyFilters() fires early during script
// execution — any `const` referenced by this function would still be in
// its temporal dead zone and throw a ReferenceError, which would silently
// kill every event handler further down the script (tab clicks included).
function _computeTabCounts() {
  const q = (s) => document.querySelectorAll(s).length;
  // Stateful spontaneous rows (✉ with a liked/toapply/applied/rejected
  // class) are counted alongside li.job so the tab total matches the
  // top-bar "Total jobs:" formula from applyFilters.
  const statefulSpont = 'liked, .spontaneous-row.toapply, .spontaneous-row.applied, .spontaneous-row.app-rejected';
  return {
    all:         q('li.job') + q('.spontaneous-row.' + statefulSpont),
    liked:       q('li.job.liked') + q('.spontaneous-row.liked'),
    toapply:     q('li.job.toapply') + q('.spontaneous-row.toapply'),
    pipeline:    q('li.job.applied, li.job.app-rejected')
                 + q('.spontaneous-row.applied, .spontaneous-row.app-rejected'),
    ranked:      q('li.job') + (document.body.classList.contains('hide-ranked-spontaneous')
                                   ? 0
                                   : q('.spontaneous-row:has(.badge.claude-fit)')),
    spontaneous: q('.spontaneous-row'),
    new:         q('li.job:has(.badge.new-badge)'),
    untouched:   q('li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected)'),
  };
}
function _updateTabCounts() {
  const counts = _computeTabCounts();
  document.querySelectorAll('.tab').forEach(btn => {
    const id = btn.dataset.tab;
    if (!(id in counts)) return;
    // Strip any existing " (N)" suffix before re-appending the fresh one.
    const label = btn.textContent.replace(/\\s*\\(\\d+\\)\\s*$/, '').trim();
    btn.textContent = label + ' (' + counts[id] + ')';
  });
  // #total-count mirrors the current tab's visible count — on the All tab
  // applyFilters sets it based on filtered rows, elsewhere we take the raw
  // per-tab count.
  if (!document.body.classList.contains('tab-all')) {
    const active = [...document.querySelectorAll('.tab.active')][0]?.dataset.tab || 'all';
    const el = document.getElementById('total-count');
    if (el) el.textContent = counts[active] ?? counts.all;
  }
}
// "Show spontaneous" checkbox inside the Ranked tab. Persisted so the
// user's last setting sticks. Reading happens before activateTab so the
// body class is correct on first paint of the Ranked view.
const RANKED_SHOW_SPONT_KEY = 'jobs:ranked-show-spontaneous';
(() => {
  const cb = document.getElementById('ranked-show-spontaneous');
  if (!cb) return;
  let saved = null;
  try { saved = localStorage.getItem(RANKED_SHOW_SPONT_KEY); } catch (e) {}
  // Default on; only unchecked when the saved value is explicitly '0'.
  cb.checked = saved !== '0';
  document.body.classList.toggle('hide-ranked-spontaneous', !cb.checked);
  cb.addEventListener('change', () => {
    document.body.classList.toggle('hide-ranked-spontaneous', !cb.checked);
    try { localStorage.setItem(RANKED_SHOW_SPONT_KEY, cb.checked ? '1' : '0'); } catch (e) {}
    _updateTabCounts();
  });
})();

// "Show marks" checkbox inside the Ranked tab. When off, hides the
// state buttons (+1 / TA / ✓ / R / K) so Ranked becomes a clean
// title+score list. Persisted alongside the spontaneous toggle.
const RANKED_SHOW_MARKS_KEY = 'jobs:ranked-show-marks';
(() => {
  const cb = document.getElementById('ranked-show-marks');
  if (!cb) return;
  let saved = null;
  try { saved = localStorage.getItem(RANKED_SHOW_MARKS_KEY); } catch (e) {}
  cb.checked = saved !== '0';
  document.body.classList.toggle('hide-ranked-marks', !cb.checked);
  cb.addEventListener('change', () => {
    document.body.classList.toggle('hide-ranked-marks', !cb.checked);
    try { localStorage.setItem(RANKED_SHOW_MARKS_KEY, cb.checked ? '1' : '0'); } catch (e) {}
  });
})();

// Init: restore last-used tab (defaults to 'all' on first load). Runs AFTER
// loadFilters so the tab preset wins over any stale saved checkbox state.
// A URL hash of the form `#tab=<name>` wins over the saved value — used
// by the onboarding wizard to drop the user straight into the All tab
// after `make onboarding` has built the board.
(() => {
  const hashMatch = location.hash.match(/tab=([a-zA-Z-]+)/);
  const fromHash = hashMatch && TAB_PRESETS[hashMatch[1]] ? hashMatch[1] : null;
  const onboardedMatch = location.hash.match(/onboarded=(\\d+)/);
  const onboardedSecs = onboardedMatch ? parseInt(onboardedMatch[1], 10) : null;
  let last = null;
  try { last = localStorage.getItem(TAB_STORAGE_KEY); } catch (e) {}
  activateTab(fromHash || last || 'all');
  // Clear the hash so a subsequent reload doesn't re-pin the tab OR
  // re-pop the onboarding-completed toast.
  if ((fromHash || onboardedMatch) && history.replaceState) {
    history.replaceState(null, '', location.pathname + location.search);
  }
  if (onboardedSecs !== null) {
    _showOnboardingToast(onboardedSecs);
  }
})();

function _fmtDuration(secs) {
  if (secs < 60) return secs + ' s';
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return s === 0 ? m + ' min' : m + ' min ' + s + ' s';
}

/* Sticky pill shown once after onboarding redirects here. Mirrors the
   refresh floater's position (top-right); stays visible until the user
   dismisses it so the first-time user has a moment of "it worked, this
   took N min" before the board grabs their attention. */
function _showOnboardingToast(secs) {
  let el = document.getElementById('onboarded-toast');
  if (el) el.remove();
  el = document.createElement('div');
  el.id = 'onboarded-toast';
  el.className = 'onboarded-toast visible';
  el.innerHTML =
    '<span class="onboarded-icon" aria-hidden="true">✓</span>' +
    '<span class="onboarded-text"></span>' +
    '<button type="button" class="onboarded-dismiss" aria-label="Dismiss">×</button>';
  el.querySelector('.onboarded-text').textContent =
    'Onboarding finished in ' + _fmtDuration(secs) + '. Welcome.';
  el.querySelector('.onboarded-dismiss').addEventListener('click', () => el.remove());
  document.body.appendChild(el);
}

/* --- Like -------------------------------------------------------------- */
async function apiPost(path, url) {
  const base = location.protocol === 'file:' ? SERVER_URL : '';
  const body = JSON.stringify({url});
  const res = await fetch(base + path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body,
  });
  if (!res.ok) {
    // Include the actual URL and body we sent so a 400 tells us WHY.
    console.error('apiPost failed', {path, url, body, status: res.status});
    throw new Error('http ' + res.status + ' — url=' + JSON.stringify(url));
  }
}

/* --- Like / To apply / Applied state machine -------------------------- */
// Highest-priority active class on <li>. The trio is mutually exclusive
// from a visual standpoint (li can only be in one bucket) but the
// underlying stores are independent so we don't lose state when demoting.
function refreshLiState(li) {
  li.classList.remove('liked', 'toapply', 'applied', 'app-rejected');
  const likeOn = li.querySelector('button.like')?.dataset.state === 'on';
  const taOn   = li.querySelector('button.toapply')?.dataset.state === 'on';
  const apOn   = li.querySelector('button.applied')?.dataset.state === 'on';
  const arOn   = li.querySelector('button.app-rejected-btn')?.dataset.state === 'on';
  if (arOn)      li.classList.add('app-rejected');
  else if (apOn) li.classList.add('applied');
  else if (taOn) li.classList.add('toapply');
  else if (likeOn) li.classList.add('liked');
}
// Spontaneous rows use the same state class names but sit in a <div>, so
// refreshLiState is reused verbatim — this alias makes intent clearer at
// the call site.
const refreshSpontaneousState = refreshLiState;

// Insert a button into the action bar in the CORRECT left-to-right order:
//   × (reject)  +1 (like)  TA (toapply)  ✓ (applied)
// The anchor is the button representing the immediately-previous state so
// that newly-created buttons land in the right slot regardless of which
// buttons were server-rendered.
function ensureStateButton(container, cls, glyph, title) {
  // `container` is a <li.job> for regular jobs, or a <.spontaneous-row>
  // for the ✉ Spontaneous line. Both use the same button classes and
  // wireStateButton machinery.
  if (container.querySelector('.' + cls)) return container.querySelector('.' + cls);
  const url = container.querySelector('button.like')?.dataset.url
    || container.querySelector('button.reject')?.dataset.url;
  if (!url) return null;
  const btn = document.createElement('button');
  btn.className = cls;
  btn.dataset.url = url;
  btn.dataset.state = 'off';
  btn.title = title;
  btn.textContent = glyph;
  wireStateButton(btn, cls);
  // Extra wiring for app-rejected-btn: unlike like/toapply/applied it
  // needs the modal-opening handler on top of wireStateButton (which is
  // never actually called for it — see toggleAppRejected). But the way
  // wireStateButton is written, calling it on an app-rejected-btn only
  // attaches a no-op-ish click handler because there's no endpoints[cls].
  // Add the modal handler explicitly here.
  if (cls === 'app-rejected-btn' && !btn.__wired) {
    btn.__wired = true;
    btn.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      toggleAppRejected(btn);
    });
  }
  const priorClass = cls === 'toapply' ? 'like'
                  : cls === 'applied' ? 'toapply'
                  : cls === 'app-rejected-btn' ? 'applied'
                  : null;
  const anchor = (priorClass && container.querySelector('.' + priorClass))
    || container.querySelector('button.like')
    || container.querySelector('button.reject');
  // For regular jobs we insert before <details>; for spontaneous rows the
  // ✉ link plays the same role of "everything after the buttons".
  const tail = container.querySelector('details')
            || container.querySelector('.spontaneous-link');
  if (anchor) anchor.after(btn);
  else if (tail) container.insertBefore(btn, tail);
  return btn;
}

function moveLiToTop(li) {
  const ul = li.closest('ul');
  if (!ul) return;
  // Priority order: applied > toapply > liked > neither
  const rank = e => e.classList.contains('applied') ? 0
             : e.classList.contains('toapply') ? 1
             : e.classList.contains('liked')   ? 2 : 3;
  const my = rank(li);
  const peers = [...ul.querySelectorAll('li.job')];
  const before = peers.find(e => e !== li && rank(e) > my);
  if (before) ul.insertBefore(li, before);
  else ul.appendChild(li);
}

function wireStateButton(btn, cls) {
  // cls is one of 'like', 'toapply', 'applied'. Each maps to a pair of
  // endpoints (/like /unlike, /toapply /untoapply, /applied /unapplied).
  const endpoints = {
    like:    ['/like',    '/unlike'],
    toapply: ['/toapply', '/untoapply'],
    applied: ['/applied', '/unapplied'],
  }[cls];
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const li = btn.closest('li');
    const spontRow = btn.closest('.spontaneous-row');
    // The +1/TA/✓/R buttons on the ✉ Spontaneous line live in a <div>,
    // not an <li>. Treat that row as an alternate container.
    const container = li || spontRow;
    const isSpontaneous = !li && !!spontRow;
    const on = btn.dataset.state === 'on';
    // Removing a job from Applied should be a conscious decision — once
    // you've marked something as Applied, you almost never want to un-apply.
    // Ask for explicit confirmation so a stray click doesn't silently
    // undo the state.
    if (on && cls === 'applied') {
      if (!confirm("Really remove this job from 'Applied'? Normally you don't go back once you've applied.")) {
        return;
      }
    }
    btn.disabled = true;
    try {
      await apiPost(on ? endpoints[1] : endpoints[0], url);
      btn.dataset.state = on ? 'off' : 'on';
      // When you turn something ON, expose the next state's button too —
      // identical progressive-reveal for regular jobs and spontaneous rows.
      if (!on && cls === 'like') {
        ensureStateButton(container, 'toapply', 'TA', 'Mark as To apply');
      }
      if (!on && cls === 'toapply') {
        ensureStateButton(container, 'applied', '\u2713', 'Mark as Applied');
      }
      if (!on && cls === 'applied') {
        ensureStateButton(container, 'app-rejected-btn', 'R',
          'Mark this application as rejected by the company');
      }
      if (isSpontaneous) {
        refreshSpontaneousState(spontRow);
        // Nav pill count + section-empty marker depend on the spontaneous
        // row's state, so re-run the whole filter pass.
        applyFilters();
        return;
      }
      refreshLiState(li);
      moveLiToTop(li);
      refreshStateCounts();
    } catch (err) {
      alert(cls + ' toggle failed: ' + err.message);
    } finally {
      btn.disabled = false;
    }
  });
}

// Scope selectors to `button.` — the class names .toapply and .applied are
// ALSO used on <li> rows (li.toapply, li.applied). Without the button
// prefix, wireStateButton would attach a click handler to the entire row,
// and any click on the row (including the disclosure arrow to expand the
// description) would fire an /applied POST with dataset.url === undefined.
document.querySelectorAll('button.like').forEach(btn => wireStateButton(btn, 'like'));
document.querySelectorAll('button.toapply').forEach(btn => wireStateButton(btn, 'toapply'));
document.querySelectorAll('button.applied').forEach(btn => wireStateButton(btn, 'applied'));

/* --- Manual salary overrides (client-side, localStorage-only) ---------- */
// Small "$" button next to the ↗ link opens window.prompt(). Empty input
// clears the override (restores the LLM-extracted badge if any).
const MANUAL_SALARY_KEY = 'jobs:manual-salary:v1';
function loadManualSalaries() {
  try { return JSON.parse(localStorage.getItem(MANUAL_SALARY_KEY) || '{}') || {}; }
  catch (e) { return {}; }
}
function saveManualSalaries(m) {
  try { localStorage.setItem(MANUAL_SALARY_KEY, JSON.stringify(m)); } catch (e) {}
}
function renderSalaryOnLi(li, txt, isManual) {
  const summary = li.querySelector('summary');
  if (!summary) return;
  let badge = summary.querySelector('.badge.salary');
  if (txt) {
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'badge salary';
      // Insert after seniority badge if present, otherwise after the title.
      const anchor = summary.querySelector('.badge.seniority')
                  || summary.querySelector('.title');
      if (anchor) anchor.after(badge);
      else summary.appendChild(badge);
    }
    badge.classList.toggle('manual', !!isManual);
    badge.title = isManual
      ? 'Salary range you entered manually (click $ to edit)'
      : 'Salary range extracted from the description (verbatim, no conversion)';
    badge.textContent = '\U0001F4B0 ' + txt;
  } else if (badge) {
    const orig = badge.dataset.originalText;
    if (orig) {
      badge.textContent = orig;
      badge.classList.remove('manual');
      badge.title = 'Salary range extracted from the description (verbatim, no conversion)';
    } else {
      badge.remove();
    }
  }
}
(function hydrateManualSalaries() {
  const map = loadManualSalaries();
  document.querySelectorAll('li.job').forEach(li => {
    const url = li.querySelector('button.salary-edit')?.dataset.url;
    if (!url) return;
    // Preserve any existing LLM-extracted badge text so we can restore it
    // later if the manual override is cleared.
    const badge = li.querySelector('.badge.salary');
    if (badge && !badge.dataset.originalText) {
      badge.dataset.originalText = badge.textContent;
    }
    const manual = map[url];
    if (manual) renderSalaryOnLi(li, manual, true);
  });
})();
document.querySelectorAll('button.salary-edit').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const li = btn.closest('li');
    if (!li || !url) return;
    const map = loadManualSalaries();
    const current = map[url] || '';
    const val = window.prompt('Salary range for this job (leave empty to clear):', current);
    if (val === null) return;   // cancelled
    const trimmed = val.trim();
    if (trimmed) {
      map[url] = trimmed;
      renderSalaryOnLi(li, trimmed, true);
    } else {
      delete map[url];
      renderSalaryOnLi(li, '', true);
    }
    saveManualSalaries(map);
  });
});

/* --- "Ask Claude" helpers (single job + batch) --------------------------- */
// Build a French prompt that only ships the URL(s). Claude is expected to
// fetch the pages itself. Multiple URLs are numbered so Claude can refer
// back to them by index in its reply.
function buildClaudePromptForUrls(urls) {
  if (!urls || !urls.length) return '';
  const lang = _getClaudeLang();
  if (urls.length === 1) {
    if (lang === 'fr') {
      return (
        "Est-ce que ce job est bon pour mon profil ? Je te partagerai mon profil sur demande.\\n" +
        "Donne-moi un score de fit sur 10 et une justification de 2-3 phrases (missions, séniorité, techno, red flags).\\n\\n" +
        urls[0]
      );
    }
    return (
      "Is this job a good match for my profile? I'll share my profile on request.\\n" +
      "Give me a fit score out of 10 and a 2-3 sentence justification (missions, seniority, tech, red flags).\\n\\n" +
      urls[0]
    );
  }
  const numbered = urls.map((u, i) => (i + 1) + ". " + u).join('\\n');
  if (lang === 'fr') {
    return (
      "Est-ce que ces " + urls.length + " jobs sont bons pour mon profil ? Je te partagerai mon profil sur demande.\\n" +
      "Pour chaque job, donne-moi un score de fit sur 10 et une justification de 2-3 phrases (missions, séniorité, techno, red flags).\\n" +
      "Reprends les numéros ci-dessous (1 à " + urls.length + ") pour que je puisse faire le lien.\\n\\n" +
      numbered
    );
  }
  return (
    "Are these " + urls.length + " jobs a good match for my profile? I'll share my profile on request.\\n" +
    "For each job, give me a fit score out of 10 and a 2-3 sentence justification (missions, seniority, tech, red flags).\\n" +
    "Please reuse the numbers below (1 to " + urls.length + ") so I can map responses back to jobs.\\n\\n" +
    numbered
  );
}
// Open claude.ai/new in a new TAB — never a popup window. `window.open` is
// unreliable here because Chrome/Safari respect the modifier keys still
// held during the click handler (⇧ → new window, ⌥ → background tab, etc).
// Programmatic <a target="_blank">.click() produces a synthetic event with
// no modifiers, so the browser falls back to its "open in new adjacent tab"
// default regardless of what the user was holding.
function _openInTab(href) {
  // Chrome keeps tracking the user's held modifiers for the duration of
  // the triggering click event — so even a programmatic a.click() inside
  // a Shift-click handler can be interpreted as Shift+click → new window.
  // setTimeout(0) defers past the current event so modifier tracking has
  // moved on; the dispatched MouseEvent explicitly carries zero modifiers.
  setTimeout(() => {
    const a = document.createElement('a');
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.dispatchEvent(new MouseEvent('click', {
      bubbles: true, cancelable: true, view: window,
      shiftKey: false, ctrlKey: false, metaKey: false, altKey: false,
      button: 0,
    }));
    a.remove();
  }, 0);
}
// Pinned chat URL — set from the Settings page (/settings). When present,
// every AI click reuses THIS conversation (so previously granted fetch
// permissions carry over) and the prompt is copied to the clipboard.
const CLAUDE_CHAT_URL_KEY = 'jobs:claude-chat-url:v1';
function _getPinnedClaudeChatUrl() {
  try { return (localStorage.getItem(CLAUDE_CHAT_URL_KEY) || '').trim(); }
  catch (e) { return ''; }
}
// Response language for LLM output — "en" (default) or "fr". Affects
// prompt copy only (scores + justifications come back in that language).
// Does NOT translate the UI. Set from the Settings page.
const CLAUDE_LANG_KEY = 'jobs:claude-lang:v1';
function _getClaudeLang() {
  try {
    const v = (localStorage.getItem(CLAUDE_LANG_KEY) || '').trim().toLowerCase();
    return v === 'fr' ? 'fr' : 'en';
  } catch (e) { return 'en'; }
}
// Hydrate the gear's visual state on load — deeper-green when a chat
// URL is pinned, so the user sees at a glance which mode they're in.
(function _syncPinnedChatBtn() {
  const link = document.getElementById('settings-link');
  if (link && _getPinnedClaudeChatUrl()) link.classList.add('has-url');
})();

// The ⚙ gear now navigates to /settings (served by _render_settings_html).
// Nothing further to wire client-side — the <a> handles navigation, and
// Ctrl+, is routed below via the ACTION_SHORTCUTS map.

/* ------------------------------------------------------------------
   Edit-companies modal (🏢 button).

   Opens a wide modal that mirrors the onboarding wizard's company
   picker: 6 groups collapsible, "All in group" / "None in group"
   buttons, pre-checked from the user's current SOURCES, with a NEW
   tag on companies added since the last time this dialog was opened.
   Save → POST /write-user-config → reload. The server writes
   data/user_config.py (+ timestamped backup) and preserves the
   existing HIGHLIGHTS / TITLE_BLACKLIST / LOCATION_BLACKLIST.
   ------------------------------------------------------------------ */

const _CATALOG_SEEN_KEY = 'jobs:catalog-seen:v1';

function _getSeenCatalog() {
  try {
    const raw = localStorage.getItem(_CATALOG_SEEN_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch (e) { return new Set(); }
}
function _saveSeenCatalog(set) {
  try { localStorage.setItem(_CATALOG_SEEN_KEY, JSON.stringify([...set])); }
  catch (e) {}
}

// First page load (localStorage empty) means the user just finished
// onboarding OR hand-edited data/user_config.py. In both cases they've
// already reviewed the whole catalog as it currently exists — companies
// they declined aren't "new" to them. Seed `seen` with the full catalog
// so the badge only flags entries added to catalog.py in future
// releases. Persist so the one-shot seed survives reloads.
function _effectiveSeenCatalog() {
  let seen = _getSeenCatalog();
  if (seen.size === 0) {
    seen = new Set(CATALOG_FOR_EDIT.map(e => e.name));
    _saveSeenCatalog(seen);
  }
  return seen;
}

function _refreshNewCompaniesBadge() {
  const badge = document.getElementById('new-companies-badge');
  if (!badge) return;
  const effectiveSeen = _effectiveSeenCatalog();
  const n = CATALOG_FOR_EDIT.filter(e => !effectiveSeen.has(e.name)).length;
  if (n > 0) {
    badge.textContent = n;
    badge.style.display = '';
  } else {
    badge.style.display = 'none';
  }
}

function openEditCompaniesModal() {
  // Build the modal lazily on first open.
  let modal = document.getElementById('edit-sources-modal');
  const selected = new Set(SOURCES_NAMES);
  const effectiveSeen = _effectiveSeenCatalog();

  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'edit-sources-modal';
    modal.className = 'modal-backdrop wide';
    modal.innerHTML =
      '<div class="modal">' +
      '  <div class="modal-head">' +
      '    <h3 style="margin:0 0 0.3rem">Edit companies</h3>' +
      '    <div class="subtitle" style="color:var(--fg-muted); font-size:0.9rem; margin-bottom:0.8rem">' +
      '      Pick which companies you want to track. Your board rebuilds automatically after you save.' +
      '    </div>' +
      '    <div class="es-toolbar">' +
      '      <div class="es-mode" role="tablist" aria-label="Show">' +
      '        <button type="button" data-mode="all">All</button>' +
      '        <button type="button" data-mode="new" class="active">Only new</button>' +
      '        <button type="button" data-mode="missing">Only missing</button>' +
      '      </div>' +
      '      <input type="text" class="es-search" id="es-search" placeholder="Filter…">' +
      '    </div>' +
      '  </div>' +
      '  <div class="modal-body" id="es-body"></div>' +
      '  <div class="modal-foot">' +
      '    <span class="es-counter" id="es-counter"></span>' +
      '    <span class="spacer" style="flex:1"></span>' +
      '    <button type="button" id="es-cancel">Cancel</button>' +
      '    <button type="button" class="primary" id="es-save" style="background:var(--success); color:#fff; border-color:var(--success-emphasis)">Save</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(modal);
    _buildEditSourcesContent(modal, selected, effectiveSeen);
  } else {
    // Re-sync pre-checks + NEW tags each time (user may have refreshed
    // between opens and the config / catalog could have shifted).
    modal.querySelector('#es-body').innerHTML = '';
    _buildEditSourcesContent(modal, selected, effectiveSeen);
  }

  _esRefreshFooter();
  modal.classList.add('visible');

  modal.querySelector('#es-cancel').onclick = () => {
    modal.classList.remove('visible');
  };
  modal.querySelector('#es-save').onclick = async () => {
    await _esSave(modal);
  };
  modal.querySelector('#es-search').oninput = () => _esFilter(modal);
  modal.querySelectorAll('.es-mode button').forEach(b => {
    b.onclick = () => {
      modal.querySelectorAll('.es-mode button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      _esFilter(modal);
    };
  });
  // Apply the default "Only new" filter on first paint.
  _esFilter(modal);
  // NOTE: we do NOT touch the "seen catalog" watermark here. The badge
  // only resets after a successful Save (see _esSave) — Cancel means
  // the user still owes themselves a decision on the new companies,
  // so the (N) badge should stick around.
}

function _buildEditSourcesContent(modal, selected, effectiveSeen) {
  const body = modal.querySelector('#es-body');
  // Discovered-on-WTJ section FIRST — companies the Algolia probe
  // surfaced that are NOT already in the catalog or user's SOURCES.
  // Read-only (link to WTJ page) — adding is a manual follow-up for
  // now because each company needs a scraper-specific URL.
  const catalogNames = new Set(CATALOG_FOR_EDIT.map(e => e.name.toLowerCase()));
  const inSources = new Set([...selected].map(n => n.toLowerCase()));
  const discovered = (WTTJ_DISCOVERED || []).filter(c => {
    const nm = (c.name || '').toLowerCase();
    const sl = (c.slug || '').toLowerCase();
    return nm && !catalogNames.has(nm) && !inSources.has(nm) && !catalogNames.has(sl);
  });
  if (discovered.length) {
    const d = document.createElement('details');
    d.className = 'edit-sources-group edit-sources-discovered';
    d.open = false;
    const sum = document.createElement('summary');
    sum.innerHTML =
      '<span class="group-name">📡 Discovered on WTJ</span>' +
      '<span class="group-count"><span class="n-on">' + discovered.length +
      '</span> new</span>';
    d.appendChild(sum);
    const hint = document.createElement('p');
    hint.className = 'es-discovered-hint';
    hint.textContent =
      discovered.length + ' companies seen on Welcome to the Jungle but ' +
      'not yet tracked. Click to open the company page on WTJ; add to your ' +
      'config manually once you have a scrape URL.';
    d.appendChild(hint);
    const grid = document.createElement('div');
    grid.className = 'edit-sources-grid es-discovered-grid';
    for (const c of discovered.slice(0, 300)) {
      const row = document.createElement('a');
      row.className = 'es-discovered-row';
      row.href = c.website_url ||
        ('https://www.welcometothejungle.com/fr/companies/' + c.slug);
      row.target = '_blank';
      row.rel = 'noopener';
      const nm = document.createElement('div');
      nm.className = 'es-discovered-name';
      nm.textContent = c.name;
      row.appendChild(nm);
      if (c.description) {
        const dsc = document.createElement('div');
        dsc.className = 'es-discovered-desc';
        dsc.textContent = c.description;
        row.appendChild(dsc);
      }
      if (c.sectors && c.sectors.length) {
        const tags = document.createElement('div');
        tags.className = 'es-discovered-tags';
        tags.textContent = c.sectors.slice(0, 3).join(' · ');
        row.appendChild(tags);
      }
      grid.appendChild(row);
    }
    d.appendChild(grid);
    body.appendChild(d);
  }
  // Group by `group`, sort groups by size DESC (matches onboarding UX).
  const grouped = new Map();
  for (const e of CATALOG_FOR_EDIT) {
    if (!grouped.has(e.group)) grouped.set(e.group, []);
    grouped.get(e.group).push(e);
  }
  const sortedGroups = [...grouped.entries()].sort((a, b) => b[1].length - a[1].length);

  for (const [groupName, entries] of sortedGroups) {
    entries.sort((a, b) => a.name.localeCompare(b.name));
    const details = document.createElement('details');
    details.className = 'edit-sources-group';
    details.dataset.group = groupName;
    details.open = true;

    const summary = document.createElement('summary');
    summary.innerHTML =
      '<span class="group-name"></span>' +
      '<span class="group-count"><span class="n-on">0</span>/' + entries.length + '</span>';
    summary.querySelector('.group-name').textContent = groupName;
    details.appendChild(summary);

    const actions = document.createElement('div');
    actions.className = 'group-actions';
    actions.innerHTML =
      '<button type="button" data-act="all">All in group</button>' +
      '<button type="button" data-act="none">None in group</button>';
    details.appendChild(actions);

    const grid = document.createElement('div');
    grid.className = 'edit-sources-grid';
    for (const e of entries) {
      const label = document.createElement('label');
      label.dataset.name = e.name.toLowerCase();
      const isNew = !effectiveSeen.has(e.name);
      if (isNew) label.dataset.isNew = '1';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'es-cb';
      cb.dataset.name = e.name;
      if (selected.has(e.name)) cb.checked = true;
      cb.addEventListener('change', () => {
        _esRefreshGroup(details);
        // "Only missing" filter is dynamic — ticking a box should
        // hide it immediately. Only reflows if that mode is active.
        const modeInput = document.querySelector('input[name="es-mode"]:checked');
        if (modeInput && modeInput.value === 'missing') {
          const modal = document.getElementById('edit-sources-modal');
          if (modal) _esFilter(modal);
        }
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(' ' + e.name));
      if (isNew) {
        const tag = document.createElement('span');
        tag.className = 'new-tag';
        tag.textContent = 'NEW';
        label.appendChild(tag);
      }
      grid.appendChild(label);
    }
    details.appendChild(grid);

    actions.querySelector('[data-act="all"]').onclick = (ev) => {
      ev.preventDefault();
      details.querySelectorAll('.es-cb').forEach(cb => { cb.checked = true; });
      _esRefreshGroup(details);
    };
    actions.querySelector('[data-act="none"]').onclick = (ev) => {
      ev.preventDefault();
      details.querySelectorAll('.es-cb').forEach(cb => { cb.checked = false; });
      _esRefreshGroup(details);
    };

    body.appendChild(details);
    _esRefreshGroup(details);
  }
}

function _esRefreshGroup(details) {
  const on = details.querySelectorAll('.es-cb:checked').length;
  details.querySelector('.n-on').textContent = on;
  details.querySelector('.group-count').classList.toggle('has-picks', on > 0);
  _esRefreshFooter();
}

function _esRefreshFooter() {
  const modal = document.getElementById('edit-sources-modal');
  if (!modal) return;
  const nSel = modal.querySelectorAll('.es-cb:checked').length;
  const total = modal.querySelectorAll('.es-cb').length;
  const nNew = modal.querySelectorAll('.edit-sources-grid label[data-is-new="1"]').length;
  const nMissing = total - nSel;
  const mode = _currentEsMode(modal);
  const counter = modal.querySelector('#es-counter');
  if (counter) {
    if (mode === 'new') {
      counter.textContent = nNew + (nNew === 1 ? ' new' : ' new') +
        ' · ' + nSel + ' selected';
    } else if (mode === 'missing') {
      counter.textContent = nMissing + ' missing · ' + nSel + ' selected';
    } else {
      counter.textContent = nSel + ' / ' + total + ' selected';
    }
  }
  const saveBtn = modal.querySelector('#es-save');
  if (saveBtn) saveBtn.disabled = (nSel === 0);
}

function _currentEsMode(modal) {
  const active = modal.querySelector('.es-mode button.active');
  return (active && active.dataset.mode) || 'all';
}

function _esFilter(modal) {
  const q = (modal.querySelector('#es-search')?.value || '').trim().toLowerCase();
  const mode = _currentEsMode(modal);
  const anyFilter = !!q || mode !== 'all';
  for (const label of modal.querySelectorAll('.edit-sources-grid label')) {
    let visible = true;
    if (mode === 'new' && label.dataset.isNew !== '1') visible = false;
    if (mode === 'missing') {
      const cb = label.querySelector('.es-cb');
      if (!cb || cb.checked) visible = false;
    }
    if (visible && q && !(label.dataset.name || '').includes(q)) visible = false;
    label.classList.toggle('es-hide', !visible);
  }
  for (const g of modal.querySelectorAll('.edit-sources-group')) {
    const anyVisible = [...g.querySelectorAll('label')]
      .some(l => !l.classList.contains('es-hide'));
    g.classList.toggle('es-collapsed', anyFilter && !anyVisible);
    g.open = anyVisible || !anyFilter;
  }
  _esRefreshFooter();
}

async function _esSave(modal) {
  const names = [...modal.querySelectorAll('.es-cb:checked')].map(cb => cb.dataset.name);
  const saveBtn = modal.querySelector('#es-save');
  const originalText = saveBtn.textContent;
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving…';
  try {
    const base = location.protocol === 'file:' ? SERVER_URL : '';
    const r = await fetch(base + '/write-user-config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({names}),
    });
    if (!r.ok) throw new Error('http ' + r.status);
    await r.json();
    // Save succeeded → the user has acknowledged the current catalog
    // state (whether they added the new companies or chose not to).
    // Reset the badge watermark now.
    _saveSeenCatalog(new Set(CATALOG_FOR_EDIT.map(e => e.name)));
    _refreshNewCompaniesBadge();
    // Close the modal and trigger a refresh (same flow as clicking the
    // R button) so the board rebuilds against the new SOURCES. The
    // refresh handler polls /refresh-status and reloads the page when
    // done — no further user action needed.
    modal.classList.remove('visible');
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn && !refreshBtn.disabled) refreshBtn.click();
  } catch (e) {
    saveBtn.textContent = originalText;
    saveBtn.disabled = false;
    alert('Save failed: ' + e.message);
  }
}

document.getElementById('edit-sources-setup')?.addEventListener('click', openEditCompaniesModal);
_refreshNewCompaniesBadge();

/* --- Per-source query pills (inline edit) -----------------------------
 * Each company header has a .queries span with its current query words
 * (= substrings jobs.py matches against to decide which postings to keep
 * for that source). Clicking × on a pill removes it; clicking + pops an
 * inline input to add a new word. Every change POSTs to /update-queries
 * which rewrites data/user_config.py. The new filter applies on the
 * next refresh — we don't live-filter the DOM because queries are
 * applied server-side at fetch time.
 */
async function _saveQueries(sourceName, queries) {
  const base = location.protocol === 'file:' ? SERVER_URL : '';
  const res = await fetch(base + '/update-queries', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: sourceName, queries}),
  });
  if (!res.ok) {
    console.error('/update-queries failed', {sourceName, queries, status: res.status});
    throw new Error('http ' + res.status);
  }
}
function _readQueryWords(wrapper) {
  return [...wrapper.querySelectorAll('.query-pill')].map(p => p.dataset.q);
}
function _makeQueryPill(word) {
  const pill = document.createElement('span');
  pill.className = 'query-pill';
  pill.dataset.q = word;
  pill.textContent = word;
  const x = document.createElement('button');
  x.type = 'button';
  x.className = 'query-remove';
  x.title = 'Remove this query word';
  x.setAttribute('aria-label', 'Remove');
  x.textContent = '×';
  pill.appendChild(x);
  return pill;
}
document.addEventListener('click', async (ev) => {
  const removeBtn = ev.target.closest('.query-remove');
  if (removeBtn) {
    ev.preventDefault();
    const pill = removeBtn.closest('.query-pill');
    const wrapper = removeBtn.closest('.queries');
    if (!pill || !wrapper) return;
    pill.remove();
    try { await _saveQueries(wrapper.dataset.source, _readQueryWords(wrapper)); }
    catch (e) { /* already logged by _saveQueries */ }
    return;
  }
  const addBtn = ev.target.closest('.query-add');
  if (addBtn && !addBtn.dataset.editing) {
    ev.preventDefault();
    const wrapper = addBtn.closest('.queries');
    if (!wrapper) return;
    addBtn.dataset.editing = '1';
    addBtn.style.display = 'none';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'query-input';
    input.placeholder = 'word…';
    input.setAttribute('aria-label', 'New query word');
    addBtn.before(input);
    input.focus();
    let done = false;
    const close = () => {
      if (done) return;
      done = true;
      input.remove();
      addBtn.style.display = '';
      delete addBtn.dataset.editing;
    };
    input.addEventListener('keydown', async (kev) => {
      if (kev.key === 'Escape') { close(); return; }
      if (kev.key !== 'Enter') return;
      kev.preventDefault();
      const raw = input.value.trim();
      if (!raw) { close(); return; }
      const existing = _readQueryWords(wrapper).map(s => s.toLowerCase());
      if (existing.includes(raw.toLowerCase())) { close(); return; }
      addBtn.before(_makeQueryPill(raw));
      close();
      try { await _saveQueries(wrapper.dataset.source, _readQueryWords(wrapper)); }
      catch (e) { /* already logged */ }
    });
    // Blur-without-Enter cancels silently. Setting a tiny timeout lets
    // Enter's keydown-driven path finish first (otherwise blur fires and
    // close() wipes the input before we read it).
    input.addEventListener('blur', () => setTimeout(close, 50));
  }
});

// Open claude.ai with the prompt pre-filled when it fits in the URL,
// otherwise copy to clipboard and open a bare tab. If the user has pinned
// a chat URL (via ⚙), always open that chat (prompt copied — no ?q= on
// existing chats) UNLESS the caller passes {forceFreshChat:true}: the
// per-job "?" button is a one-shot question that benefits from a new chat
// (and the user never notices the clipboard copy because ?q= pre-fills
// everything). Returns "prefilled" / "copied" / "copied-to-pinned" /
// "failed" so callers can show the right instruction.
async function openClaudeWithPrompt(prompt, statusEl, opts) {
  if (!prompt) return 'failed';
  const forceFreshChat = !!(opts && opts.forceFreshChat);
  const pinned = forceFreshChat ? '' : _getPinnedClaudeChatUrl();
  if (pinned) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(prompt);
        _openInTab(pinned);
        return 'copied-to-pinned';
      } catch (e) {
        _openInTab(pinned);
        return 'failed';
      }
    }
    _openInTab(pinned);
    return 'failed';
  }
  const target = 'https://claude.ai/new?q=' + encodeURIComponent(prompt);
  if (target.length < 7500) {
    _openInTab(target);
    return 'prefilled';
  }
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(prompt);
      _openInTab('https://claude.ai/new');
      if (statusEl) {
        statusEl.textContent = 'Prompt copied — paste in the Claude tab.';
        setTimeout(() => { statusEl.textContent = ''; }, 4000);
      }
      return 'copied';
    } catch (e) {
      _openInTab('https://claude.ai/new');
      return 'failed';
    }
  }
  _openInTab('https://claude.ai/new');
  return 'failed';
}
// Per-job "?" button → single-URL prompt.
document.querySelectorAll('button.ask-claude').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url || '';
    if (!url) return;
    // URL-only — Claude fetches the page itself (fresh / complete info).
    const prompt = (_getClaudeLang() === 'fr')
      ? (
        "Est-ce que ce job est bon pour mon profil ? Je te partagerai mon profil sur demande.\\n" +
        "Va chercher la description sur le site, puis donne-moi un score de fit sur 10 et une justification de 2-3 phrases (missions, séniorité, techno, red flags).\\n\\n" +
        url
      )
      : (
        "Is this job a good match for my profile? I'll share my profile on request.\\n" +
        "Fetch the description from the site, then give me a fit score out of 10 and a 2-3 sentence justification (missions, seniority, tech, red flags).\\n\\n" +
        url
      );
    // Bypass any pinned chat URL — a one-shot per-job question works
    // better in a fresh conversation where ?q= pre-fills the prompt.
    openClaudeWithPrompt(prompt, null, {forceFreshChat: true});
  });
});

/* --- Application rejected by company: modal + toggle ------------------ */
function openAppRejectModal(prefill) {
  return new Promise((resolve) => {
    let modal = document.getElementById('app-reject-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'app-reject-modal';
      modal.className = 'modal-backdrop';
      modal.innerHTML =
        '<div class="modal">' +
        '  <h3>Application rejected — why?</h3>' +
        '  <label>Reason (short)<br>' +
        '    <input type="text" id="ar-reason" placeholder="e.g. no response, HR ghosted, bad fit">' +
        '  </label>' +
        '  <label>Feedback (details, optional)<br>' +
        '    <textarea id="ar-feedback" rows="5" placeholder="What did you learn? Interview notes? Recruiter said?"></textarea>' +
        '  </label>' +
        '  <div class="modal-actions">' +
        '    <button type="button" id="ar-cancel">Cancel</button>' +
        '    <button type="button" id="ar-save" class="primary">Save</button>' +
        '  </div>' +
        '</div>';
      document.body.appendChild(modal);
    }
    const reason = modal.querySelector('#ar-reason');
    const feedback = modal.querySelector('#ar-feedback');
    reason.value   = prefill?.reason   || '';
    feedback.value = prefill?.feedback || '';
    modal.classList.add('visible');
    setTimeout(() => reason.focus(), 50);
    const cleanup = (result) => {
      modal.classList.remove('visible');
      modal.querySelector('#ar-cancel').onclick = null;
      modal.querySelector('#ar-save').onclick = null;
      resolve(result);
    };
    modal.querySelector('#ar-cancel').onclick = () => cleanup(null);
    modal.querySelector('#ar-save').onclick = () => cleanup({
      reason: reason.value.trim(),
      feedback: feedback.value.trim(),
    });
  });
}

async function toggleAppRejected(btn) {
  const url = btn.dataset.url;
  const li = btn.closest('li');
  const spontRow = btn.closest('.spontaneous-row');
  const on = btn.dataset.state === 'on';
  // Removing a job from Rejected (application rejected by the company)
  // should also be a conscious decision. A rejection is factual history —
  // guard against stray clicks silently rewriting it.
  if (on) {
    if (!confirm("Really remove this job from 'Rejected'? A rejected application is a historical fact — you rarely take it back.")) {
      return;
    }
  }
  btn.disabled = true;
  try {
    if (on) {
      // Un-reject: confirmation already handled above.
      const base = location.protocol === 'file:' ? SERVER_URL : '';
      const res = await fetch(base + '/un-app-rejected', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url}),
      });
      if (!res.ok) throw new Error('http ' + res.status);
      btn.dataset.state = 'off';
    } else {
      // Open dialog first; cancel = do nothing.
      const answers = await openAppRejectModal();
      if (!answers) return;
      const base = location.protocol === 'file:' ? SERVER_URL : '';
      const res = await fetch(base + '/app-rejected', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url, ...answers}),
      });
      if (!res.ok) throw new Error('http ' + res.status);
      btn.dataset.state = 'on';
    }
    if (li) {
      refreshLiState(li);
      moveLiToTop(li);
      refreshStateCounts();
    } else if (spontRow) {
      refreshSpontaneousState(spontRow);
      applyFilters();
    }
  } catch (e) {
    alert('Application-rejected toggle failed: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

document.querySelectorAll('button.app-rejected-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleAppRejected(btn);
  });
});

/* --- Reject + Undo ----------------------------------------------------- */
const rejectUndoStack = [];   // {url, sid, li, next, ul}

function updateCounters(sid, deltaVisible, deltaRejected) {
  const h1 = document.getElementById(sid);
  if (h1) {
    const v = h1.querySelector('.counter .v');
    const r = h1.querySelector('.counter .r');
    if (v) v.textContent = parseInt(v.textContent) + deltaVisible;
    if (r) r.textContent = parseInt(r.textContent) + deltaRejected;
  }
  const navCount = document.querySelector('.nav-btn[href="#' + sid + '"] .nav-count');
  if (navCount) {
    const newVal = parseInt(navCount.textContent) + deltaVisible;
    navCount.textContent = newVal;
    const btn = navCount.closest('.nav-btn');
    if (btn) {
      const fetched = parseInt(btn.dataset.fetched) || 0;
      btn.classList.toggle('has-jobs',   newVal > 0);
      btn.classList.toggle('no-match',   newVal === 0 && fetched > 0);
      btn.classList.toggle('no-fetched', newVal === 0 && fetched === 0);
    }
  }
  const totalEl = document.getElementById('total-count');
  if (totalEl) totalEl.textContent = parseInt(totalEl.textContent) + deltaVisible;
  // Total NEW tracks visible .badge.new-badge rows — rejecting a NEW job
  // removes the <li>, so recompute from the DOM rather than track a delta
  // (we don't know up front whether the removed row carried the badge).
  const totalNewEl = document.getElementById('total-new-count');
  if (totalNewEl) {
    totalNewEl.textContent = document.querySelectorAll(
      'li.job:not(.hidden) .badge.new-badge'
    ).length;
  }
  refreshStateCounts();
  // If the section is now empty, mark it .empty so hide-empty-sections works.
  // We recompute across the affected section rather than trust the delta —
  // reject can push visible to 0 mid-page (Cmd-Z can bring it back).
  const ul = document.querySelector('ul[data-section="' + sid + '"]');
  if (ul) {
    const visible = ul.querySelectorAll('li.job:not(.hidden)').length;
    const section = ul.closest('.company-section');
    if (section) section.classList.toggle('empty', visible === 0);
  }
  // Then re-collapse any category row that lost its last hit.
  document.querySelectorAll('.nav-row').forEach(row => {
    const btns = row.querySelectorAll('.nav-btn');
    const anyHit = [...btns].some(b => b.classList.contains('has-jobs'));
    row.classList.toggle('empty', btns.length > 0 && !anyHit);
  });
  // Re-evaluate h2 group headings — a reject can empty the last company
  // section under a heading, and the heading's own .empty class is
  // JS-set (CSS :has() alone wouldn't catch the hide-empty-sections
  // mode). Without this, the heading stayed visible until the next tab
  // switch triggered applyFilters().
  if (typeof refreshGroupHeadings === 'function') refreshGroupHeadings();
}

let undoToastTimer = null;

function showUndoToast() {
  let toast = document.getElementById('undo-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'undo-toast';
    toast.className = 'undo-toast';
    document.body.appendChild(toast);
  }
  if (undoToastTimer) { clearTimeout(undoToastTimer); undoToastTimer = null; }
  const count = rejectUndoStack.length;
  if (count === 0) {
    toast.classList.remove('visible');
    return;
  }
  const last = rejectUndoStack[rejectUndoStack.length - 1];
  const title = last.li.querySelector('.title')?.textContent?.trim() || 'job';
  toast.innerHTML =
    '<span class="undo-msg">Rejected <em>' + title.slice(0, 60) + '</em></span>' +
    '<button id="undo-btn" class="undo-btn">Undo (' + count + ')</button>';
  toast.classList.add('visible');
  document.getElementById('undo-btn').addEventListener('click', undoLastReject);
  // Auto-hide after 5s. The undo stack itself stays alive so Cmd-Z still
  // works even after the toast has faded.
  undoToastTimer = setTimeout(() => {
    toast.classList.remove('visible');
    undoToastTimer = null;
  }, 5000);
}

async function undoLastReject() {
  const last = rejectUndoStack.pop();
  if (!last) return;
  // Route undo to the right endpoint depending on how the row was removed.
  const undoEndpoint = last.kind === 'history' ? '/unhistory' : '/unreject';
  try {
    await apiPost(undoEndpoint, last.url);
  } catch (err) {
    alert('Undo failed: ' + err.message);
    rejectUndoStack.push(last);
    return;
  }
  // Re-insert the <li> before its next sibling (or at the end of the ul).
  if (last.next && last.next.parentNode === last.ul) {
    last.ul.insertBefore(last.li, last.next);
  } else {
    last.ul.appendChild(last.li);
  }
  // Kill the "<li><em>none</em></li>" placeholder if we added one.
  last.ul.querySelectorAll('li').forEach(li => {
    if (!li.classList.contains('job') && li.textContent.trim() === 'none') li.remove();
  });
  // History undo doesn't move a rejected counter — the +1 visible/-1 rejected
  // math is only right for reject undo.
  if (last.kind === 'history') {
    updateCounters(last.sid, +1, 0);
  } else {
    updateCounters(last.sid, +1, -1);
  }
  showUndoToast();
}

document.querySelectorAll('.reject').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const li = btn.closest('li');
    const ul = li.closest('ul');
    const sid = ul.dataset.section;
    btn.disabled = true;
    li.style.opacity = '0.3';
    try {
      await apiPost('/reject', url);
      // Save enough state to restore this exact position.
      const next = li.nextElementSibling;
      rejectUndoStack.push({url, sid, li, next, ul});
      li.remove();
      updateCounters(sid, -1, +1);
      showUndoToast();
    } catch (err) {
      btn.disabled = false;
      li.style.opacity = '1';
      alert('Reject failed: ' + err.message);
    }
  });
});

// Section × — reject every untouched job (no state) in this company section
// in one click. Reuses the per-URL /reject endpoint sequentially so each
// rejection lands on the undo stack and Cmd+Z brings them back one at a
// time. Rows the user has already touched (liked / to-apply / applied /
// app-rejected) are skipped: the same CSS that hides the per-row × on
// those rows applies here.
document.querySelectorAll('.reject-section').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const sid = btn.dataset.sid;
    const name = btn.dataset.name || sid;
    const ul = document.querySelector('ul[data-section="' + sid + '"]');
    if (!ul) return;
    const rows = [...ul.querySelectorAll(
      'li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected)'
    )];
    if (rows.length === 0) return;
    // No confirm — Cmd+Z brings every reject back (see rejectUndoStack
    // + showUndoToast), so a misclick is cheap to undo.
    btn.disabled = true;
    for (const li of rows) {
      const rowBtn = li.querySelector('button.reject');
      const url = rowBtn?.dataset.url;
      if (!url) continue;
      li.style.opacity = '0.3';
      try {
        await apiPost('/reject', url);
        const next = li.nextElementSibling;
        rejectUndoStack.push({url, sid, li, next, ul});
        li.remove();
        updateCounters(sid, -1, +1);
      } catch (err) {
        li.style.opacity = '1';
        alert('Reject failed on ' + url + ': ' + err.message);
        break;
      }
    }
    btn.disabled = false;
    showUndoToast();
  });
});

// Unfollow: drop this company from data/user_config.py SOURCES. No confirm
// prompt — the on-disk backup is the recovery path if the click was a
// mistake. On success we hide the section immediately so the board
// reflects the new state without waiting for a refresh.
document.querySelectorAll('.unfollow-company').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const name = btn.dataset.name;
    const sid = btn.dataset.sid;
    if (!name) return;
    btn.disabled = true;
    try {
      const base = location.protocol === 'file:' ? SERVER_URL : '';
      const res = await fetch(base + '/unfollow', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name}),
      });
      if (!res.ok) throw new Error('http ' + res.status);
      const section = document.querySelector('.company-section[data-section="' + sid + '"]');
      if (section) section.remove();
      refreshGroupHeadings();
    } catch (err) {
      btn.disabled = false;
      alert('Unfollow failed: ' + err.message);
    }
  });
});

// Review button: like reject, but also POSTs the title to /to-review which
// appends it to planning/TOREVIEW.md. Non-undoable — the file append is not reversible.
document.querySelectorAll('button.review').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const title = btn.dataset.title || '';
    const li = btn.closest('li');
    const ul = li.closest('ul');
    const sid = ul?.dataset.section;
    btn.disabled = true;
    li.style.opacity = '0.3';
    try {
      const base = location.protocol === 'file:' ? SERVER_URL : '';
      const res = await fetch(base + '/to-review', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url, title}),
      });
      if (!res.ok) throw new Error('http ' + res.status);
      // Track this like a reject so the undo toast + Cmd-Z bring it back.
      // /to-review both rejects the URL and appends the title to
      // planning/TOREVIEW.md; the planning/TOREVIEW.md line is not auto-removed on undo
      // (user cleans up manually), but the /unreject call on undo pulls
      // the URL back out of rejected.json so the job re-appears next
      // render — which is what "undo" mostly needs to mean here.
      const next = li.nextElementSibling;
      rejectUndoStack.push({url, sid, li, next, ul});
      li.remove();
      if (sid) updateCounters(sid, -1, +1);
      showUndoToast();
    } catch (err) {
      btn.disabled = false;
      li.style.opacity = '1';
      alert('Review failed: ' + err.message);
    }
  });
});

// Keyboard shortcuts (all Cmd/Ctrl + <letter>, no Shift / Alt).
// Keep this comment in sync with the Shortcuts section on /settings.
//   Cmd+Z  undo last reject
//   Cmd+R  refresh
//   Cmd+I  AI — score every visible job with Claude
//   Cmd+U  AI — score only the visible jobs that don't have a score yet
//   Cmd+E  Entreprises (edit companies)
//   Cmd+,  Settings (macOS Preferences idiom)
// Shift must NOT be held so Cmd+Shift+R (hard-reload) and Cmd+Shift+I
// (devtools) stay available if the user wants the browser default.
// Cmd+U collides with the browser "view source" default — we accept
// that trade-off on this page because the rendered HTML isn't the
// interesting surface anyway (jobs come from an API).
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey
      && e.key === 'z' && rejectUndoStack.length > 0) {
    e.preventDefault();
    undoLastReject();
    return;
  }
  if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey
      && !e.repeat && e.key.toLowerCase() === 'u') {
    e.preventDefault();
    _runClaudeScoring(_collectUnscoredJobUrls(), 'No unscored jobs to rate.');
    return;
  }
  if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey || e.repeat) return;
  const map = {
    'r': 'refresh-btn',
    'i': 'claude-score-all',
    'e': 'edit-sources-setup',
    ',': 'settings-link',
  };
  const btnId = map[e.key.toLowerCase()] || map[e.key];
  if (!btnId) return;
  const el = document.getElementById(btnId);
  if (el && !el.disabled) {
    e.preventDefault();
    // <a> → navigate; <button> → click. Both do the right thing when we
    // call .click(), so a single branch covers the mixed element types.
    el.click();
  }
});

/* --- Tab digit shortcuts (1..9) ----------------------------------------- */
// Positional: `1` jumps to the first tab, `2` the second, …, matching
// the visual order rendered by render_html_tabs(). Guard against typing
// in filter inputs / the query-add box, and against any modifier so
// Cmd+1 (browser-reserved) and Shift+1 (= '!' typed in a field) stay
// untouched. activateTab() is defined earlier in this script, so by
// the time this listener fires it is in scope.
(() => {
  function _isTypingTarget(el) {
    if (!el) return false;
    const tag = (el.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (el.isContentEditable) return true;
    return false;
  }
  document.addEventListener('keydown', (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.repeat) return;
    if (_isTypingTarget(e.target)) return;
    const digit = parseInt(e.key, 10);
    if (!(digit >= 1 && digit <= 9)) return;
    const tabs = document.querySelectorAll('#tabs .tab[data-tab]');
    const btn = tabs[digit - 1];
    if (!btn) return;
    e.preventDefault();
    btn.click();
  });
})();

/* --- Keep in history: like reject but posts /history --------------------- */
// Factored wire function so client-created unkeep buttons behave exactly
// like server-rendered ones.
function _wireUnkeepButton(btn) {
  if (!btn || btn.__wired) return;
  btn.__wired = true;
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const li = btn.closest('li.history-job');
    const block = li?.closest('.history-block');
    btn.disabled = true;
    if (li) li.style.opacity = '0.4';
    try {
      await apiPost('/unhistory', url);
      li?.remove();
      const summary = block?.querySelector('summary');
      const remaining = block?.querySelectorAll('li.history-job').length ?? 0;
      if (summary) summary.textContent = remaining + ' kept in history — click to expand';
      if (remaining === 0 && block) block.remove();
      // Trigger a refresh so the row comes back into the main list.
      const rb = document.getElementById('refresh-btn');
      if (rb && !rb.disabled) rb.click();
    } catch (err) {
      btn.disabled = false;
      if (li) li.style.opacity = '1';
      alert('Restore failed: ' + err.message);
    }
  });
}

// Insert a job into (or create) the per-section History block, mirroring
// the server-side layout in render_html_section.
function _addToHistoryBlock(sid, data) {
  if (!sid) return;
  const section = document.querySelector('.company-section[data-section="' + sid + '"]');
  if (!section) return;
  let block = section.querySelector(':scope > .history-block[data-section="' + sid + '"]');
  if (!block) {
    block = document.createElement('details');
    block.className = 'history-block';
    block.dataset.section = sid;
    block.innerHTML =
      '<summary>0 kept in history — click to expand</summary>' +
      '<ul class="history-list"></ul>';
    // Insert BEFORE the main <ul data-section> (same slot as server render).
    const mainUl = section.querySelector(':scope > ul[data-section]');
    if (mainUl) section.insertBefore(block, mainUl);
    else section.appendChild(block);
  }
  const listUl = block.querySelector('.history-list');
  const li = document.createElement('li');
  li.className = 'history-job';
  const safeUrl   = (data.url || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  const safeTitle = (data.title || '(no title)').replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const safeLocs  = (data.locations || 'N/A').replace(/&/g, '&amp;').replace(/</g, '&lt;');
  li.innerHTML =
    '<button class="unkeep" data-url="' + safeUrl + '" title="Remove from history (bring back to the main list)">↩</button>' +
    '<a href="' + safeUrl + '" target="_blank" rel="noopener">' + safeTitle + '</a>' +
    (data.salaryHtml || '') +
    '<span class="locs"> — ' + safeLocs + '</span>';
  listUl.appendChild(li);
  const n = listUl.querySelectorAll('li.history-job').length;
  const summary = block.querySelector('summary');
  summary.textContent = n + ' kept in history — click to expand';
  _wireUnkeepButton(li.querySelector('.unkeep'));
}

document.querySelectorAll('button.keep').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const li = btn.closest('li');
    const ul = li.closest('ul');
    const sid = ul?.dataset.section;
    btn.disabled = true;
    li.style.opacity = '0.3';
    // Grab everything we need from the li BEFORE removing it.
    const title = (li.querySelector('.title')?.textContent || '').trim();
    const locations = (li.dataset.locations || '').trim();
    const salaryBadge = li.querySelector('.badge.salary');
    const salaryHtml = salaryBadge ? salaryBadge.outerHTML : '';
    try {
      await apiPost('/history', url);
      // Reuse the reject undo stack — the toast is identical semantics.
      const next = li.nextElementSibling;
      rejectUndoStack.push({url, sid, li, next, ul, kind: 'history'});
      li.remove();
      if (sid) updateCounters(sid, -1, 0);
      // Mirror the server-side render: move the row into the section's
      // history block so the user sees it right away without a refresh.
      _addToHistoryBlock(sid, {url, title, locations, salaryHtml});
      showUndoToast();
    } catch (err) {
      btn.disabled = false;
      li.style.opacity = '1';
      alert('Keep failed: ' + err.message);
    }
  });
});

/* --- Restore from the "Rejected in this section" list ---------------- */
document.querySelectorAll('.restore').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const li = btn.closest('li.rejected-job');
    const block = li.closest('.rejected-block');
    const sid = block?.dataset.section;
    btn.disabled = true;
    li.style.opacity = '0.4';
    try {
      await apiPost('/unreject', url);
      li.remove();
      // Update the counter of rejected items in this section's expando.
      const summary = block?.querySelector('summary');
      const remaining = block?.querySelectorAll('li.rejected-job').length ?? 0;
      if (summary) {
        summary.textContent = remaining + ' rejected in this section — click to expand';
      }
      if (remaining === 0 && block) block.remove();
      if (sid) updateCounters(sid, +1, -1);
      // The URL was just removed from rejected.json. The next full
      // refresh (R button) will re-promote it to the main list; we don't
      // auto-trigger a refresh since the user may want to batch restores.
      const status = document.getElementById('dump-status');
      if (status) status.textContent = 'Restored — click R to refresh and re-promote it to the list.';
    } catch (err) {
      btn.disabled = false;
      li.style.opacity = '1';
      alert('Restore failed: ' + err.message);
    }
  });
});

/* --- Restore from the "Kept in history" list --------------------------- */
// Wire all server-rendered unkeep buttons on page load — client-created
// ones get wired at creation time via _wireUnkeepButton.
document.querySelectorAll('.unkeep').forEach(_wireUnkeepButton);
</script>
</body>
</html>
"""


# Global refresh state, used by the in-browser refresh button. The server
# spawns `jobs.py --clear-cache list --no-serve --no-open` in a background
# thread and the client polls /refresh-status until "done".
_refresh_state = {"status": "idle", "started_at": None, "error": None, "log_tail": ""}
_refresh_lock = threading.Lock()


def _refresh_progress():
    """Mirror onboarding's _launch_progress: inspect LIST_CACHE_DIR for
    JSON files written since the refresh started, so the browser floater
    can show "N/M fetched · latest: X · working on: Y" instead of a bare
    elapsed-seconds counter. Each successful source fetch writes one
    JSON file, so file count = completed source count."""
    with _refresh_lock:
        started = _refresh_state["started_at"]
    total = sum(1 for s in SOURCES if s.get("name"))
    slug_to_name = {slug(s["name"]): s["name"] for s in SOURCES if s.get("name")}
    done = []
    if started is not None and os.path.isdir(LIST_CACHE_DIR):
        try:
            for name in os.listdir(LIST_CACHE_DIR):
                if not name.endswith(".json"):
                    continue
                try:
                    mtime = os.path.getmtime(os.path.join(LIST_CACHE_DIR, name))
                except OSError:
                    continue
                # Only count files written after the refresh kicked off —
                # defends against stale caches from a prior session being
                # mistaken for current-run progress.
                if mtime >= started:
                    done.append((name[:-5], mtime))
        except OSError:
            pass
    done.sort(key=lambda x: x[1])
    done_slugs = {s for s, _ in done}
    last_done = slug_to_name.get(done[-1][0], done[-1][0]) if done else None
    currently_working = None
    for s in SOURCES:
        nm = s.get("name")
        if nm and slug(nm) not in done_slugs:
            currently_working = nm
            break
    return {
        "done_count": len(done),
        "total": total,
        "last_done": last_done,
        "currently_working": currently_working,
    }


def _run_refresh_subprocess(mode="refresh"):
    """Regenerate jobs.html in a subprocess. Updates _refresh_state."""
    global _refresh_state
    extra = ["--clear-cache", "list", "--interactive-runaway"]
    try:
        proc = subprocess.run(
            [sys.executable, __file__, *extra, "--no-serve", "--no-open"],
            capture_output=True, text=True, timeout=900,
        )
        with _refresh_lock:
            tail = (proc.stdout or "")[-2000:]
            if proc.returncode == 0:
                _refresh_state["status"] = "done"
                _refresh_state["log_tail"] = tail
            else:
                _refresh_state["status"] = "failed"
                _refresh_state["error"] = (proc.stderr[-500:] or "unknown error").strip()
                _refresh_state["log_tail"] = tail
    except Exception as e:
        with _refresh_lock:
            _refresh_state["status"] = "failed"
            _refresh_state["error"] = str(e)[:500]


def _render_settings_html():
    """Load src/settings.html and inline __SERVER_URL__ + __RUNAWAY_THRESHOLD__.

    Rendered on every GET /settings (not cached) so a mid-session
    /set-settings POST shows the new value when the user reopens the
    page. The file is small (~10kB) — rebuilding costs microseconds."""
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "settings.html"), "r", encoding="utf-8") as f:
        html = f.read()
    server_url = f"http://{SERVE_HOST}:{SERVE_PORT}"
    import html as _html
    html = (
        html
        .replace("__SERVER_URL__", server_url)
        .replace("__RUNAWAY_THRESHOLD__", json.dumps(_cfg.RUNAWAY_THRESHOLD))
        .replace("__BOARD_TITLE__", _html.escape(_cfg.BOARD_TITLE))
    )
    return html.encode("utf-8")


class Handler(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(OUTPUT_HTML, "rb") as f:
                    data = f.read()
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path in ("/settings", "/settings.html"):
            try:
                data = _render_settings_html()
            except FileNotFoundError:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path not in (
            "/reject", "/unreject",
            "/like", "/unlike",
            "/toapply", "/untoapply",
            "/applied", "/unapplied",
            "/app-rejected", "/un-app-rejected",
            "/history", "/unhistory",
            "/to-review",
            "/refresh", "/refresh-status", "/refresh-decision",
            "/claude-fit-paste",
            "/write-user-config", "/update-queries", "/unfollow",
            "/save-probe", "/save-open-selected",
            "/set-settings",
        ):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length))
        except Exception:
            payload = {}
        if self.path == "/set-settings":
            # Settings page save. Each writable field is optional in the
            # payload; the handler accepts any subset. Each accepted field
            # updates _cfg in memory (so subsequent renders see the new
            # value) and rewrites data/user_config.py so the change
            # survives a restart.
            updates = []  # list of (varname, python_literal, log_repr)
            if "runaway_threshold" in payload:
                val = payload.get("runaway_threshold")
                if not isinstance(val, int) or val < 10 or val > 10000:
                    self.send_response(400); self._cors(); self.end_headers(); return
                _cfg.RUNAWAY_THRESHOLD = val
                updates.append(("RUNAWAY_THRESHOLD", str(val), str(val)))
            if "board_title" in payload:
                val = payload.get("board_title")
                if not isinstance(val, str) or not val.strip() or len(val) > 100:
                    self.send_response(400); self._cors(); self.end_headers(); return
                val = val.strip()
                _cfg.BOARD_TITLE = val
                updates.append(("BOARD_TITLE", repr(val), val))
            if not updates:
                self.send_response(400); self._cors(); self.end_headers(); return
            out_path = os.path.join(_cfg.DATA_DIR, "user_config.py")
            try:
                txt = ""
                if os.path.isfile(out_path):
                    with open(out_path, "r", encoding="utf-8") as f:
                        txt = f.read()
                    bak = f"{out_path}.bak.{time.strftime('%Y%m%d-%H%M%S')}"
                    with open(bak, "w", encoding="utf-8") as f:
                        f.write(txt)
                for name, literal, _ in updates:
                    new_line = f"{name} = {literal}"
                    pat = rf"^{re.escape(name)}\s*=\s*.*$"
                    if re.search(pat, txt, re.MULTILINE):
                        txt = re.sub(pat, new_line, txt, count=1, flags=re.MULTILINE)
                    else:
                        if txt and not txt.endswith("\n"):
                            txt += "\n"
                        txt += "\n" + new_line + "\n"
                os.makedirs(_cfg.DATA_DIR, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(txt)
                for name, _, log in updates:
                    sys.stdout.write(f"set-settings: {name} → {log}\n")
            except Exception as e:
                sys.stdout.write(f"set-settings: write failed: {e}\n")
                self.send_response(500); self._cors(); self.end_headers(); return
            self.send_response(204); self._cors(); self.end_headers(); return
        if self.path == "/save-probe":
            script = payload.get("script") or ""
            if not script:
                self.send_response(400); self._cors(); self.end_headers(); return
            try:
                os.makedirs("debug", exist_ok=True)
                path = os.path.join("debug", "probe_visible.py")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(script)
                os.chmod(path, 0o755)
                sys.stdout.write(f"probe:    wrote {path} ({len(script)} bytes)\n")
            except Exception as e:
                sys.stdout.write(f"probe:    save failed: {e}\n")
                self.send_response(500); self._cors(); self.end_headers(); return
            self.send_response(204); self._cors(); self.end_headers(); return
        if self.path == "/save-open-selected":
            script = payload.get("script") or ""
            # Sanitize filename — only [a-z0-9_.-], default to open_liked.sh.
            requested = payload.get("filename") or "open_liked.sh"
            safe = re.sub(r"[^a-z0-9_.-]+", "_", requested.lower())
            if not safe.endswith(".sh"):
                safe += ".sh"
            if not script:
                self.send_response(400); self._cors(); self.end_headers(); return
            try:
                os.makedirs("debug", exist_ok=True)
                path = os.path.join("debug", safe)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(script)
                os.chmod(path, 0o755)
                sys.stdout.write(f"open-sel: wrote {path} ({len(script)} bytes)\n")
            except Exception as e:
                sys.stdout.write(f"open-sel: save failed: {e}\n")
                self.send_response(500); self._cors(); self.end_headers(); return
            self.send_response(204); self._cors(); self.end_headers(); return
        # Refresh: kicks off jobs.py --clear-cache list --skip-llm in a
        # subprocess. Client polls /refresh-status until done, then reloads.
        if self.path == "/refresh":
            with _refresh_lock:
                already_running = _refresh_state["status"] == "running"
                if not already_running:
                    _refresh_state["status"] = "running"
                    _refresh_state["started_at"] = time.time()
                    _refresh_state["error"] = None
                    _refresh_state["log_tail"] = ""
                    threading.Thread(
                        target=_run_refresh_subprocess,
                        args=("refresh",),
                        daemon=True,
                    ).start()
                    sys.stdout.write("refresh: started\n")
                started = _refresh_state["started_at"]
            body = json.dumps({
                "status": "already-running" if already_running else "started",
                "elapsed": int(time.time() - started) if started else 0,
            }).encode()
            self.send_response(200); self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/write-user-config":
            # Edit-companies modal save: persist the new SOURCES list to
            # data/user_config.py (with a timestamped backup of the
            # existing file). HIGHLIGHTS / TITLE_BLACKLIST /
            # LOCATION_BLACKLIST are preserved from the current config —
            # the editor only changes companies.
            names = [str(n) for n in (payload.get("names") or [])]
            if not names:
                body = json.dumps({"error": "no company names"}).encode()
                self.send_response(400); self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            try:
                import onboarding  # lazy; keeps a plain run cheap
                data_dir = os.environ.get("JOBS_DATA_DIR", "data")
                out_path = os.path.join(data_dir, "user_config.py")
                # Preserve the user's existing filter lists so editing
                # companies doesn't wipe out blacklists / highlights.
                hl, tb, lb = HIGHLIGHTS[:], TITLE_BLACKLIST[:], LOCATION_BLACKLIST[:]
                # Also preserve per-source `queries` — the catalog
                # doesn't carry those (they're user-tunable), and
                # dropping them silently would unleash the full
                # unfiltered firehose of e.g. Salesforce (1500+ jobs).
                existing_q = {s["name"]: s.get("queries") or []
                              for s in SOURCES if s.get("name")}
                backup = None
                if os.path.isfile(out_path):
                    backup = onboarding._backup_path(out_path)
                    import shutil
                    shutil.copy2(out_path, backup)
                content = onboarding._build_user_config(
                    set(names),
                    highlights=hl,
                    title_blacklist=tb,
                    location_blacklist=lb,
                    existing_queries=existing_q,
                )
                os.makedirs(data_dir, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)
                sys.stdout.write(f"write-user-config: {len(names)} companies → {out_path}\n")
                body = json.dumps({
                    "ok": True, "path": out_path,
                    "backup": backup, "n": len(names),
                }).encode()
                self.send_response(200)
            except Exception as e:
                err(f"/write-user-config crashed: {e}")
                body = json.dumps({"error": str(e)[:300]}).encode()
                self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/update-queries":
            # Inline-edit a single source's `queries` list from the board
            # (× / + pills on each company header). We rebuild
            # data/user_config.py with the SAME companies and filter lists
            # as before, overriding `queries` just for the named source —
            # this reuses onboarding._build_user_config so the file stays
            # structurally identical to what the wizard emits. Changes
            # apply on the next refresh (queries filter runs server-side
            # at fetch time).
            name = (payload.get("name") or "").strip()
            raw_queries = payload.get("queries") or []
            if not name or not isinstance(raw_queries, list):
                body = json.dumps({"error": "name + queries list required"}).encode()
                self.send_response(400); self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            # Dedupe case-insensitively, strip whitespace, preserve order.
            cleaned, seen_lc = [], set()
            for q in raw_queries:
                qs = str(q).strip()
                if not qs:
                    continue
                k = qs.lower()
                if k in seen_lc:
                    continue
                seen_lc.add(k)
                cleaned.append(qs)
            try:
                import onboarding  # lazy; keeps a plain run cheap
                data_dir = os.environ.get("JOBS_DATA_DIR", "data")
                out_path = os.path.join(data_dir, "user_config.py")
                names = {s["name"] for s in SOURCES if s.get("name")}
                if name not in names:
                    body = json.dumps({"error": f"unknown source: {name}"}).encode()
                    self.send_response(400); self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers(); self.wfile.write(body); return
                existing_q = {s["name"]: list(s.get("queries") or [])
                              for s in SOURCES if s.get("name")}
                existing_q[name] = cleaned
                hl, tb, lb = HIGHLIGHTS[:], TITLE_BLACKLIST[:], LOCATION_BLACKLIST[:]
                backup = None
                if os.path.isfile(out_path):
                    backup = onboarding._backup_path(out_path)
                    import shutil
                    shutil.copy2(out_path, backup)
                content = onboarding._build_user_config(
                    names,
                    highlights=hl,
                    title_blacklist=tb,
                    location_blacklist=lb,
                    existing_queries=existing_q,
                )
                os.makedirs(data_dir, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)
                # Keep the running process's SOURCES in sync so if the
                # user clicks Refresh immediately, the new filter is used
                # by any code path that reads SOURCES before the
                # subprocess finishes reloading the file.
                for s in SOURCES:
                    if s.get("name") == name:
                        s["queries"] = list(cleaned)
                        break
                sys.stdout.write(
                    f"update-queries: {name} → {cleaned} ({out_path})\n"
                )
                body = json.dumps({
                    "ok": True, "name": name, "queries": cleaned,
                    "path": out_path, "backup": backup,
                }).encode()
                self.send_response(200)
            except Exception as e:
                err(f"/update-queries crashed: {e}")
                body = json.dumps({"error": str(e)[:300]}).encode()
                self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/unfollow":
            # Remove ONE source from data/user_config.py SOURCES. Reuses
            # the same _build_user_config path as /write-user-config and
            # /update-queries so the file stays structurally identical to
            # what the wizard emits — just with the named company gone.
            # Also drops the entry from in-memory SOURCES so the running
            # process won't try to re-fetch it on the next Refresh.
            name = (payload.get("name") or "").strip()
            if not name:
                body = json.dumps({"error": "name required"}).encode()
                self.send_response(400); self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            try:
                import onboarding  # lazy; keeps a plain run cheap
                data_dir = os.environ.get("JOBS_DATA_DIR", "data")
                out_path = os.path.join(data_dir, "user_config.py")
                names = {s["name"] for s in SOURCES if s.get("name")}
                if name not in names:
                    body = json.dumps({"error": f"unknown source: {name}"}).encode()
                    self.send_response(400); self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers(); self.wfile.write(body); return
                existing_q = {s["name"]: list(s.get("queries") or [])
                              for s in SOURCES if s.get("name") and s["name"] != name}
                names.discard(name)
                hl, tb, lb = HIGHLIGHTS[:], TITLE_BLACKLIST[:], LOCATION_BLACKLIST[:]
                backup = None
                if os.path.isfile(out_path):
                    backup = onboarding._backup_path(out_path)
                    import shutil
                    shutil.copy2(out_path, backup)
                content = onboarding._build_user_config(
                    names,
                    highlights=hl,
                    title_blacklist=tb,
                    location_blacklist=lb,
                    existing_queries=existing_q,
                )
                os.makedirs(data_dir, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)
                SOURCES[:] = [s for s in SOURCES if s.get("name") != name]
                sys.stdout.write(f"unfollow: {name} ({out_path})\n")
                body = json.dumps({
                    "ok": True, "name": name,
                    "path": out_path, "backup": backup,
                }).encode()
                self.send_response(200)
            except Exception as e:
                err(f"/unfollow crashed: {e}")
                body = json.dumps({"error": str(e)[:300]}).encode()
                self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/claude-fit-paste":
            # Persist scores parsed from the Claude paste bar into
            # claude_fit_cache.json so a refresh (or another browser) sees
            # the new score + reason, not whatever the API or an earlier
            # paste wrote. Payload: {"scores": {url: {score, reason, salary, ts}}}.
            # When Claude also returned a `salary`, write it into
            # score_cache.json so the badge survives a refresh / rescore.
            scores = payload.get("scores") or {}
            if not isinstance(scores, dict) or not scores:
                self.send_response(400); self._cors(); self.end_headers(); return
            try:
                cache = _load_claude_fit_cache()
                score_cache = _load_score_cache()
                saved = 0
                salaries_saved = 0
                for url, entry in scores.items():
                    if not isinstance(entry, dict):
                        continue
                    try:
                        n = int(entry.get("score"))
                    except (TypeError, ValueError):
                        continue
                    if not (0 <= n <= 10):
                        continue
                    cache[url] = {
                        "score": n,
                        "reason": str(entry.get("reason", ""))[:1000],
                        "ts": str(entry.get("ts") or ""),
                    }
                    saved += 1
                    sal = str(entry.get("salary") or "").strip()[:100]
                    if sal:
                        prev = score_cache.get(url) or {}
                        prev["salary"] = sal
                        score_cache[url] = prev
                        salaries_saved += 1
                _save_claude_fit_cache(cache)
                if salaries_saved:
                    _save_score_cache(score_cache)
                body = json.dumps({"saved": saved, "salaries": salaries_saved}).encode()
                self.send_response(200)
            except Exception as e:
                err(f"/claude-fit-paste crashed: {e}")
                body = json.dumps({"error": str(e)[:300]}).encode()
                self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/refresh-status":
            with _refresh_lock:
                st = dict(_refresh_state)
                # After a terminal state is READ once, reset to idle so a
                # subsequent /refresh call can start fresh.
                terminal = st["status"] in ("done", "failed")
                if terminal:
                    _refresh_state["status"] = "idle"
                    _refresh_state["started_at"] = None
                    _refresh_state["error"] = None
                    _refresh_state["log_tail"] = ""
            # Pending runaway prompts — one per source blocked on user
            # decision. Browser pops a modal when the list is non-empty.
            runaway = []
            try:
                d = os.path.join(DATA_DIR, ".runaway")
                if os.path.isdir(d):
                    for name in sorted(os.listdir(d)):
                        if not name.endswith(".pending.json"):
                            continue
                        try:
                            with open(os.path.join(d, name), encoding="utf-8") as f:
                                runaway.append(json.load(f))
                        except Exception:
                            pass
            except Exception:
                pass
            body = json.dumps({
                "status": st["status"],
                "elapsed": int(time.time() - st["started_at"]) if st["started_at"] else 0,
                "error": st["error"],
                "log_tail": st["log_tail"],
                "runaway": runaway,
                "progress": _refresh_progress(),
            }).encode()
            self.send_response(200); self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/refresh-decision":
            # Browser modal reports the user's pick. We just write the
            # decision file; the fetcher subprocess polls for it and
            # drops the pending flag once it reads a valid action.
            source = (payload.get("source") or "").strip()
            action = (payload.get("action") or "").strip()
            if not source or action not in ("stop", "continue"):
                body = json.dumps({"error": "source + action required"}).encode()
                self.send_response(400); self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            path = os.path.join(DATA_DIR, ".runaway",
                                f"{slug(source)}.decision.json")
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"action": action, "at": time.time()}, f)
                sys.stdout.write(f"refresh-decision: {source} → {action}\n")
                body = json.dumps({"ok": True}).encode()
                self.send_response(200)
            except Exception as e:
                err(f"/refresh-decision crashed: {e}")
                body = json.dumps({"error": str(e)[:300]}).encode()
                self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        url = (payload.get("url") or "").strip()
        if not url:
            self.send_response(400)
            self._cors()
            self.end_headers()
            return
        if self.path == "/reject":
            s = load_rejected(); s.add(url); save_rejected(s)
            sys.stdout.write(f"rejected: {url}\n")
        elif self.path == "/unreject":
            s = load_rejected(); s.discard(url); save_rejected(s)
            sys.stdout.write(f"unrejected: {url}\n")
        elif self.path == "/history":
            s = load_history(); s.add(url); save_history(s)
            sys.stdout.write(f"history+: {url}\n")
        elif self.path == "/unhistory":
            s = load_history(); s.discard(url); save_history(s)
            sys.stdout.write(f"history-: {url}\n")
        elif self.path == "/to-review":
            # Append title to planning/TOREVIEW.md AND reject the URL so
            # the job doesn't come back next run. User cleans up
            # planning/TOREVIEW.md later and reports back which patterns
            # to add to TITLE_BLACKLIST.
            title = (payload.get("title") or "").strip() or "(no title)"
            try:
                os.makedirs("planning", exist_ok=True)
                with open("planning/TOREVIEW.md", "a", encoding="utf-8") as f:
                    f.write(f"- {title}\n")
            except Exception as e:
                sys.stdout.write(f"toreview: append failed: {e}\n")
            s = load_rejected(); s.add(url); save_rejected(s)
            sys.stdout.write(f"toreview: {title!r} · rejected\n")
        elif self.path == "/like":
            s = load_liked(); s.add(url); save_liked(s)
            sys.stdout.write(f"liked:    {url}\n")
        elif self.path == "/unlike":
            s = load_liked(); s.discard(url); save_liked(s)
            sys.stdout.write(f"unliked:  {url}\n")
        elif self.path == "/toapply":
            s = load_to_apply(); s.add(url); save_to_apply(s)
            sys.stdout.write(f"toapply:  {url}\n")
        elif self.path == "/untoapply":
            s = load_to_apply(); s.discard(url); save_to_apply(s)
            sys.stdout.write(f"un-toapp: {url}\n")
        elif self.path == "/applied":
            d = load_applied()
            # Preserve existing timestamp if the entry already exists
            # (allows quick off/on toggling without losing the original date).
            if url not in d:
                d[url] = {"ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_applied(d)
            sys.stdout.write(f"applied:  {url} — ts={d[url]['ts']}\n")
        elif self.path == "/unapplied":
            d = load_applied(); d.pop(url, None); save_applied(d)
            sys.stdout.write(f"un-appl:  {url}\n")
        elif self.path == "/app-rejected":
            d = load_app_rejected()
            d[url] = {
                "reason":   (payload.get("reason") or "").strip(),
                "feedback": (payload.get("feedback") or "").strip(),
                "ts":       time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            save_app_rejected(d)
            sys.stdout.write(f"app-rej:  {url} — reason={d[url]['reason']!r}\n")
        elif self.path == "/un-app-rejected":
            d = load_app_rejected()
            d.pop(url, None)
            save_app_rejected(d)
            sys.stdout.write(f"un-appR:  {url}\n")
        self.send_response(204)
        self._cors()
        self.end_headers()

    def log_message(self, *a):
        pass


def _run_location_debug():
    """Dump every raw location string across all sources plus how we normalize
    them, so mismatches jump out. Reads directly from desc_cache-free sources."""
    print("=" * 70)
    print("LOCATION DEBUG — raw → normalized → group")
    print("=" * 70)
    all_raw = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:
        futures = {ex.submit(FETCHERS[s["kind"]], s): s for s in SOURCES}
        for fut in concurrent.futures.as_completed(futures):
            src = futures[fut]
            try:
                r = fut.result()
                for j in r.get("jobs", []):
                    for loc in j.get("locations") or []:
                        all_raw.append((src["name"], loc))
            except Exception as e:
                err(f"  [{src['name']}] fetch failed: {e}")
    seen = set()
    for company, raw in all_raw:
        if raw in seen:
            continue
        seen.add(raw)
        normalized = _flatten_locations([raw])
        print(f"  {company:14} raw={raw!r:60} → {normalized}")
    print()
    print("Grouping:")
    all_normalized = sorted({loc for _c, r in all_raw for loc in _flatten_locations([r])})
    for country, cities in _group_locations(all_normalized):
        print(f"  {country}: {cities}")


def _parse_cli():
    ap = argparse.ArgumentParser(
        prog="jobs.py",
        description="Aggregate job postings from many boards into a single HTML page.",
        epilog=(
            "Examples:\n"
            "  python3 jobs.py                              # full run\n"
            "  python3 jobs.py --only OpenAI,Anthropic      # just two boards\n"
            "  python3 jobs.py --skip Apple,Google,Meta     # skip these\n"
            "  python3 jobs.py --skip-playwright            # HTTP-only sources\n"
            "  python3 jobs.py --debug-locations            # dump location parsing\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--only", metavar="A,B,C",
                    help="Fetch only these board names (comma-separated).")
    ap.add_argument("--skip", metavar="A,B,C",
                    help="Skip these board names (comma-separated).")
    ap.add_argument("--skip-playwright", action="store_true",
                    help="Skip all Playwright-based boards (Apple/Google/MS/…).")
    ap.add_argument("--no-list-cache", action="store_true",
                    help="Ignore the per-source list cache and re-fetch everything.")
    ap.add_argument("--no-dump-descriptions", action="store_true",
                    help="Disable the automatic job-description dump under debug/descriptions/.")
    ap.add_argument("--clear-cache", metavar="WHAT",
                    help="Wipe caches before running. WHAT is a comma-separated "
                         "subset of {scores,descriptions,list,seen,all}. "
                         "Rejected / liked / raw_locations are always kept. "
                         "`seen` (used to mark NEW jobs) is only cleared when "
                         "explicitly listed — NOT included in `all`.")
    ap.add_argument("--debug-locations", action="store_true",
                    help="Dump raw→normalized locations and exit.")
    ap.add_argument("--no-open", action="store_true",
                    help="Don't auto-open the browser after starting the server.")
    ap.add_argument("--no-serve", action="store_true",
                    help="Skip the local HTTP server — exit after writing jobs.html. "
                         "Used by the in-browser refresh button so a subprocess can "
                         "regenerate the file without fighting for the serve port.")
    ap.add_argument("--port", type=int, default=None, metavar="N",
                    help=f"HTTP serve port (default: {SERVE_PORT}). Lets a second "
                         f"board — e.g. an onboarding sandbox — run alongside the "
                         f"main one on a different port.")
    ap.add_argument("--interactive-runaway", action="store_true",
                    help="When a per-query paginated fetcher hits >100 jobs on "
                         "one query, write a signal file and wait up to 60s for "
                         "the board's modal to decide stop vs. continue. Used by "
                         "/refresh so a 'broad word' query doesn't peg Playwright. "
                         "Outside refresh (initial make run), we hard-stop at the "
                         "same threshold with no dialog.")
    ap.add_argument("--list", action="store_true",
                    help="Print every configured board name (comma-separated) and exit.")
    ap.add_argument("--onboard", action="store_true",
                    help="Launch the interactive onboarding wizard that writes "
                         "data/user_config.py from a catalog of ~150 companies. "
                         "Honours $JOBS_DATA_DIR for sandbox testing.")
    return ap.parse_args()


def _port_holder():
    """Return (pid:int, command:str, full_cmdline:str) of the process
    bound to SERVE_PORT in LISTEN state, or (None, '', '') when we
    can't tell (lsof missing, nothing listening, permission denied)."""
    try:
        out = subprocess.run(
            ["lsof", "-nP", "-iTCP:" + str(SERVE_PORT), "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return (None, "", "")
    if out.returncode != 0 or not out.stdout:
        return (None, "", "")
    for line in out.stdout.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        cmd, pid_str = parts[0], parts[1]
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        full = ""
        try:
            ps = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True, text=True, timeout=3,
            )
            full = (ps.stdout or "").strip()
        except Exception:
            pass
        return (pid, cmd, full)
    return (None, "", "")


def _looks_like_our_jobs_py(full_cmdline):
    """Decide whether a given process cmdline is a prior instance of
    this very script. Being conservative here matters — we're about to
    SIGTERM the owner."""
    if not full_cmdline:
        return False
    cl = full_cmdline.lower()
    return ("jobs.py" in cl) and ("python" in cl)


def _check_serve_port_free():
    """Fail fast if the HTTP serve port is already in use. Called at the
    very top of main() so a stale previous server doesn't make us waste
    30-90 s on a fetch before the OSError surfaces during server bind.

    Auto-reclaim: when the port holder is a stale `jobs.py` subprocess
    (typical after `make onboarding → Save and launch` + closed tab),
    we SIGTERM it ourselves and continue. For any other process we
    print an actionable error with the PID and bail — safer than
    killing something we don't recognise.

    Skipped when --no-serve is set (that mode doesn't bind the port)."""
    import socket as _sock
    import signal as _signal

    def _try_bind():
        # Mirror what http.server.ThreadingHTTPServer does — otherwise
        # a stale TIME_WAIT socket from a just-killed server makes the
        # pre-flight bind fail even though the real server would reuse
        # the port fine.
        with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
            s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
            try:
                s.bind((SERVE_HOST, SERVE_PORT))
                return True
            except OSError:
                return False

    if _try_bind():
        return

    pid, cmd, full = _port_holder()
    if pid and _looks_like_our_jobs_py(full):
        sys.stdout.write(
            f"[preflight] port {SERVE_PORT} held by stale jobs.py (PID {pid}) "
            f"— sending SIGTERM.\n"
        )
        try:
            os.kill(pid, _signal.SIGTERM)
        except ProcessLookupError:
            pass  # already gone — probably won a race
        except PermissionError:
            err(
                f"\nPort {SERVE_PORT} is held by jobs.py PID {pid} but we "
                f"lack permission to kill it. Try:\n"
                f"\n    sudo kill {pid}\n"
            )
            sys.exit(1)
        # Wait up to 5 s for the socket to become free.
        for _ in range(50):
            time.sleep(0.1)
            if _try_bind():
                sys.stdout.write("[preflight] port reclaimed.\n")
                return
        # Escalate to SIGKILL as a last resort.
        try:
            os.kill(pid, _signal.SIGKILL)
            time.sleep(0.3)
        except Exception:
            pass
        if _try_bind():
            sys.stdout.write("[preflight] port reclaimed (after SIGKILL).\n")
            return

    # Either not our process, or we failed to free the port.
    err(f"\nPort {SERVE_PORT} is already in use.")
    if pid:
        err(f"Held by: {cmd} (PID {pid})")
        if full:
            err(f"         {full}")
        err("")
        if _looks_like_our_jobs_py(full):
            err("That's a stale jobs.py — we tried to free it but SIGTERM failed.")
        else:
            err("Not a jobs.py process — refusing to kill it blindly.")
    else:
        err("Something is listening on that port but lsof couldn't name it.")
    err("")
    err("Free it with:")
    if SERVE_PORT == 8765:
        err(f"    make kill            # kills whatever listens on {SERVE_PORT}")
    else:
        err(f"    make kill PORT={SERVE_PORT}  # kills whatever listens on {SERVE_PORT}")
    err(f"    lsof -ti:{SERVE_PORT} | xargs kill   # same thing, no make")
    err("")
    err("Then re-run  make run.")
    sys.exit(1)


def main():
    args = _parse_cli()
    if args.onboard:
        # Lazy import so a plain run doesn't pull in the catalog.
        import onboarding
        sys.exit(onboarding.run_wizard(
            os.environ.get("JOBS_DATA_DIR", "data"),
            port=args.port,
        ))

    # --port overrides the module-level SERVE_PORT so every downstream
    # helper (preflight, bind, error messages, server_url) picks it up
    # without threading an extra arg through each call. Lets a sandbox
    # board coexist with the main one on 8765.
    if args.port is not None:
        global SERVE_PORT
        SERVE_PORT = args.port

    # Flip the runaway guard into "ask the browser" mode when invoked
    # by /refresh. Also wipe any stale signal files from a previous
    # refresh so the modal doesn't pop with yesterday's prompt.
    global _interactive_runaway_enabled
    _interactive_runaway_enabled = args.interactive_runaway
    _clear_runaway_signals()

    # Pre-flight: refuse to start if the HTTP port is already taken.
    # Catches the common "forgot to kill the previous `make run`" case
    # before we spend 30-90 s re-fetching every source.
    if not args.no_serve:
        _check_serve_port_free()

    # Pre-flight: if SOURCES references Playwright-only kinds and
    # Playwright isn't importable, bail LOUDLY instead of silently
    # returning [] from every pw/apple/microsoft/… fetcher. That silent
    # failure was how the "Zama shows 0 jobs" bug hid for weeks when
    # make run used system python3 instead of the venv's.
    _PW_KINDS = frozenset({
        "pw", "apple", "google", "microsoft", "meta", "phenom", "wttj",
        "ableton", "lucca", "bose", "linkedin", "cisco", "ibm", "scale",
        "checkmarx", "pixee", "github",
    })
    if not HAS_PLAYWRIGHT:
        _pw_sources = [s["name"] for s in SOURCES
                       if s.get("kind") in _PW_KINDS]
        if _pw_sources:
            err("\nPlaywright is not installed in this Python but SOURCES "
                "contains Playwright-dependent companies:")
            err(f"    {', '.join(_pw_sources[:12])}"
                + (f" and {len(_pw_sources) - 12} more" if len(_pw_sources) > 12 else ""))
            err("")
            err(f"Current python: {sys.executable}")
            err("Fix: activate your venv (venv-macos or .venv-macos) and")
            err("re-run, or run `make install` to set it up.")
            err("")
            err("Refusing to proceed — every pw source would silently "
                "return 0 jobs and poison nothing-is-wrong UI.")
            sys.exit(1)

    if args.clear_cache:
        # Accept singular / plural / minor typos.
        _aliases = {
            "score": "scores", "scores": "scores",
            "description": "descriptions", "descriptions": "descriptions",
            "desc": "descriptions", "descs": "descriptions",
            "list": "list", "lists": "list",
            "seen": "seen",  # explicit only — `all` does NOT include seen.
            "all": "all",
        }
        wanted = set()
        unknown = []
        for x in args.clear_cache.split(","):
            k = x.strip().lower()
            if not k: continue
            if k in _aliases: wanted.add(_aliases[k])
            else: unknown.append(k)
        # Fail hard on any unknown part rather than silently clearing a subset
        # and moving on — the user asked to wipe something specific and got a
        # partial result last time because of a typo.
        if unknown:
            err(
                f"[clear-cache] unknown parts: {sorted(unknown)}. "
                "Accepted: scores, descriptions, list, seen, all. Aborting."
            )
            sys.exit(2)
        if "all" in wanted:
            wanted = {"scores", "descriptions", "list"}
        if "scores" in wanted:
            try: os.remove(SCORE_CACHE); print(f"[clear-cache] removed {SCORE_CACHE}")
            except FileNotFoundError: pass
        if "descriptions" in wanted:
            try: os.remove(DESC_CACHE); print(f"[clear-cache] removed {DESC_CACHE}")
            except FileNotFoundError: pass
        if "seen" in wanted:
            try: os.remove(SEEN_DB); print(f"[clear-cache] removed {SEEN_DB}")
            except FileNotFoundError: pass
        if "list" in wanted:
            import shutil
            if os.path.isdir(LIST_CACHE_DIR):
                shutil.rmtree(LIST_CACHE_DIR)
                print(f"[clear-cache] removed {LIST_CACHE_DIR}/")

    if args.no_list_cache:
        # Global override — see collect().
        global LIST_CACHE_TTL_HOURS
        LIST_CACHE_TTL_HOURS = 0

    dump_dir = None if args.no_dump_descriptions else "debug/descriptions"


    if args.list:
        print(",".join(s["name"] for s in SOURCES))
        return

    if args.debug_locations or os.environ.get("JOBS_DEBUG_LOCATIONS") == "1":
        _run_location_debug()
        return

    t0 = time.perf_counter()
    timing(f"[run] started at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # CLI flags win; env vars remain as a legacy fallback.
    def _split(s):
        return {x.strip() for x in (s or "").split(",") if x.strip()}
    only  = _split(args.only) or _split(os.environ.get("JOBS_ONLY", ""))
    skip  = _split(args.skip) or _split(os.environ.get("JOBS_SKIP", ""))
    skip_pw    = args.skip_playwright or os.environ.get("JOBS_SKIP_PLAYWRIGHT") == "1"
    pw_kinds = {"apple", "google", "microsoft", "meta", "phenom", "scale", "github", "checkmarx", "pixee", "ableton", "lucca", "pw"}
    active_sources = [
        s for s in SOURCES
        if (not only or s["name"] in only)
        and s["name"] not in skip
        and not (skip_pw and s["kind"] in pw_kinds)
    ]
    if len(active_sources) != len(SOURCES):
        skipped = [s["name"] for s in SOURCES if s not in active_sources]
        sys.stdout.write(f"[main] active: {[s['name'] for s in active_sources]} · skipped: {skipped}\n")

    rejected = load_rejected()
    liked = load_liked()
    to_apply = load_to_apply()
    applied = load_applied()
    app_rejected = load_app_rejected()
    history = load_history()
    seen = load_seen()
    job_index = load_job_index()
    # Loaded once and reused when building orphan job dicts — see the
    # per-source render loop below. Kept separate from the live scoring path.
    _score_cache_for_orphans = _load_score_cache()
    _desc_cache_for_orphans = _load_desc_cache()
    html_sections = []
    nav_entries = []
    all_visible = []

    print("=" * 70, file=sys.stdout)
    print("Step 1 — fetch: query every source in parallel (HTTP JSON APIs +", file=sys.stdout)
    print("               headless Chromium for SPAs like Apple/Google/MS)", file=sys.stdout)
    print("=" * 70, file=sys.stdout)
    t_fetch_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(active_sources))) as ex:
        futures = {ex.submit(collect, src): src for src in active_sources}
        results = {}
        for fut in concurrent.futures.as_completed(futures):
            src = futures[fut]
            try:
                results[src["name"]] = fut.result()
            except Exception as e:
                err(f"[{src['name']}] collect crashed: {e}")
                # Record the exception so the UI can flag this source as
                # "scraper broken" (distinct from "returned 0 jobs").
                results[src["name"]] = {
                    "jobs": [], "spontaneous_url": None,
                    "error": f"{type(e).__name__}: {e}"[:200],
                }
    t_fetch = time.perf_counter() - t_fetch_start
    timing(f"[timing] fetch (all sources, parallel) → {t_fetch:.1f}s")

    print("=" * 70, file=sys.stdout)
    print("Step 2 — hydrate cached scores: no LLM call. The AI button in the UI", file=sys.stdout)
    print("               writes to score_cache.json; we just re-attach the", file=sys.stdout)
    print("               cached `salary` field so the badge shows up.", file=sys.stdout)
    print("=" * 70, file=sys.stdout)
    t_score_start = time.perf_counter()
    all_visible_for_score = []
    for src in active_sources:
        result = results[src["name"]]
        all_visible_for_score.extend(
            j for j in result["jobs"] if j["url"] not in rejected
        )
    _cached_scores = _load_score_cache()
    _hits = 0

    def _extract_legacy_salary(entry):
        rl = entry.get("role_long") or ""
        if not rl:
            return ""
        m = re.search(r"\*\*Salary:\*\*\s*[\r\n]+((?:\s*-.*(?:\r?\n|$))+)", rl)
        if not m:
            return ""
        return m.group(1).splitlines()[0].lstrip("- \t").strip()[:100]

    for j in all_visible_for_score:
        cached = _cached_scores.get(j["url"])
        if cached:
            sal = cached.get("salary")
            if sal is None:
                sal = _extract_legacy_salary(cached)
            j["salary"] = sal
            _hits += 1
    t_score = time.perf_counter() - t_score_start
    timing(f"[timing] hydrated {_hits}/{len(all_visible_for_score)} cached salaries → {t_score:.1f}s")

    print("=" * 70, file=sys.stdout)
    print("Step 3 — render: build HTML section per source (sorted liked → score", file=sys.stdout)
    print("               → seniority) with badges, filters, spontaneous links", file=sys.stdout)
    print("=" * 70, file=sys.stdout)
    t_render_start = time.perf_counter()

    # Sort active_sources by group, then alphabetically inside each group so the
    # HTML sections render in the same order as the nav pills.
    def _sort_key(s):
        g = GROUP_OF.get(s["name"], "Autres")
        try:
            gi = GROUP_ORDER.index(g)
        except ValueError:
            gi = len(GROUP_ORDER)
        return (gi, s["name"].lower())
    active_sources.sort(key=_sort_key)

    current_group = None
    for src in active_sources:
        group = GROUP_OF.get(src["name"], "Autres")
        if group != current_group:
            html_sections.append(
                f'  <h2 class="group-heading" id="group-{slug(group)}">'
                f'{html.escape(group)}</h2>'
            )
            current_group = group
        result = results[src["name"]]
        all_jobs = result["jobs"]
        # A job is NEW when we haven't seen its URL in any previous run.
        # `seen` is only updated once per run below, so re-running twice in a
        # row doesn't cause postings to "un-new" mid-processing.
        # Guard: a job you already +1'd or rejected can NEVER be NEW — you
        # must have interacted with it in a prior run. This also gracefully
        # handles the first-run case where seen.json doesn't exist yet.
        #
        # Second guard: when a company was just added to SOURCES, EVERY
        # one of its URLs is "unseen" — flagging all of them as NEW turns
        # the next run into a wall of thousands of fake-new jobs. Detect
        # this per-source: if zero URLs from this source overlap with
        # `seen`, treat the whole batch as a baseline instead of new.
        source_urls = {j["url"] for j in all_jobs if j.get("url")}
        src_first_visit = (
            len(source_urls) >= 5
            and source_urls.isdisjoint(seen)
            and source_urls.isdisjoint(liked)
            and source_urls.isdisjoint(rejected)
        )
        if src_first_visit:
            sys.stdout.write(
                f"[{src['name']}] first visit — "
                f"{len(source_urls)} jobs added to baseline (no NEW badge)\n"
            )
        for j in all_jobs:
            u = j["url"]
            j["is_new"] = (
                not src_first_visit
                and u not in seen
                and u not in liked
                and u not in rejected
            )
            j["is_orphan"] = False
            # Remember this job in the persistent index so we can render it
            # later if it disappears from the board.
            job_index[u] = {
                "title": j.get("title", ""),
                "locations": j.get("locations") or [],
                "source": src["name"],
            }
        # Orphans: jobs the user cares about (liked / to_apply / applied) that
        # (a) used to belong to this source per job_index, (b) are NOT in this
        # run's result, and (c) are not rejected. Reconstruct them from the
        # index + desc/score caches and inject at the top of `visible`.
        fresh_urls = {j["url"] for j in all_jobs}
        # `applied` is now a dict {url: {ts}}; treat its keys as the set.
        cared = liked | to_apply | set(applied.keys() if isinstance(applied, dict) else applied)
        orphan_urls = [
            u for u in cared
            if u not in fresh_urls
            and u not in rejected
            and u not in history
            and job_index.get(u, {}).get("source") == src["name"]
        ]
        orphans = []
        # Only trusted fetcher kinds (full-board API) can reliably say a URL
        # has been removed. For query-based scrapers (Phenom/Playwright/etc.),
        # a missing URL might just be outside the current queries — we still
        # surface the job (so the user's liked entry doesn't vanish), but
        # without the REMOVED badge and without the "no longer on the board"
        # description fallback that would be a lie.
        _trust_removal = src["kind"] in _TRUSTED_REMOVAL_KINDS
        for u in orphan_urls:
            meta = job_index.get(u, {})
            score_entry = _score_cache_for_orphans.get(u, {})
            cached_desc = _desc_cache_for_orphans.get(u, "")
            if _trust_removal:
                desc_fallback = "<em>Original posting has been removed from this board.</em>"
            else:
                desc_fallback = "<em>Not returned by this run's search — job may still be on the board. Click ↗ to check.</em>"
            orphans.append({
                "title": meta.get("title", "(unknown)"),
                "locations": meta.get("locations") or [],
                "url": u,
                "description": cached_desc or desc_fallback,
                "salary": score_entry.get("salary", ""),
                "is_new": False,
                "is_orphan": _trust_removal,
            })
        # Hide any job whose title marks it as spontaneous — the ✉ Spontaneous
        # link already surfaces the same URL at the top of the section, so
        # showing it in the main list is a duplicate. Also route history
        # entries into their own block (below rejected).
        visible = orphans + [
            j for j in all_jobs
            if j["url"] not in rejected
            and j["url"] not in history
            and not is_spontaneous(j)
        ]
        rejected_jobs = [j for j in all_jobs if j["url"] in rejected]
        # History: jobs the user K'd. Some may still be in the current fetch
        # (visible pruning already routes them out of `visible`), others have
        # dropped off the board — reconstruct those from job_index + caches
        # like we do for orphans, so the History block always contains every
        # K'd URL that belongs to this source.
        history_in_fetch = [j for j in all_jobs if j["url"] in history]
        _history_fetched_urls = {j["url"] for j in history_in_fetch}
        history_from_index = []
        for u in history:
            if u in _history_fetched_urls:
                continue
            if job_index.get(u, {}).get("source") != src["name"]:
                continue
            meta = job_index.get(u, {})
            score_entry = _score_cache_for_orphans.get(u, {})
            history_from_index.append({
                "title": meta.get("title", "(unknown)"),
                "locations": meta.get("locations") or [],
                "url": u,
                "description": "",
                "salary": score_entry.get("salary", ""),
                "is_new": False,
                "is_orphan": True,
            })
        history_jobs_here = history_in_fetch + history_from_index
        # rejected_here = count of jobs from this run's fetch that were rejected.
        # Orphans don't count as rejected (they're just gone from the board).
        rejected_here = len(rejected_jobs)
        html_sections.append(render_html_section(
            src["name"], visible, rejected_here,
            board_url_for(src), result.get("spontaneous_url"),
            liked, src.get("queries", []),
            rejected_jobs=rejected_jobs,
            to_apply=to_apply, applied=applied, app_rejected=app_rejected,
            history=history, history_jobs=history_jobs_here,
            display_name=src.get("display_name"),
            # Only show "total" when the source can report the true board-wide
            # count (Ashby / Greenhouse / Workable — they return the full list
            # and we filter client-side). Playwright sources search per query
            # so len(all_jobs) is a query-filtered subset, not the real total;
            # showing that number would be misleading, so we hide it entirely.
            fetched_count=result.get("total_board"),
            kind=src.get("kind"),
        ))
        # (name, visible-after-rejects-and-orphans, fetched-from-source-this-run, error)
        # For the fetched count that drives the pill color (grey vs orange),
        # prefer total_board (raw board size from the fetcher) when available.
        # This way sources that returned N jobs but had all N filtered out by
        # TITLE/LOCATION_BLACKLIST get "no-match" (orange = check your
        # filters), not "no-fetched" (grey = scraper broken).
        _fetched_for_pill = result.get("total_board") or len(all_jobs)
        nav_entries.append((src["name"], len(visible), _fetched_for_pill, result.get("error") or "", src.get("display_name") or ""))
        all_visible.extend(visible)
        # Optional: dump this source's visible jobs' descriptions for audit.
        if dump_dir:
            src_dir = os.path.join(dump_dir, slug(src["name"]))
            try:
                os.makedirs(src_dir, exist_ok=True)
                for j in visible:
                    fname = re.sub(r"[^A-Za-z0-9._-]+", "_", j["title"])[:80] or "job"
                    fpath = os.path.join(src_dir, f"{fname}.txt")
                    body = (
                        f"# {j['title']}\n"
                        f"URL: {j.get('url', '')}\n"
                        f"Locations: {', '.join(j.get('locations') or []) or 'N/A'}\n"
                        f"\n---\n\n"
                        + re.sub(r"<[^>]+>", " ", j.get("description") or "").strip()
                    )
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(body)
            except OSError as e:
                err(f"[dump-descriptions] {src['name']}: {e}")
        extra = " · spontaneous✉" if result.get("spontaneous_url") else ""
        total_fetched = len(all_jobs) + rejected_here  # visible + rejected == fetched
        line = (
            f"{src['name']:22} fetched={len(all_jobs):4}  "
            f"visible={len(visible):4}  rejected={rejected_here:4}{extra}"
        )
        if len(all_jobs) == 0:
            err(line + "  (ZERO fetched!)")
        else:
            print(line, file=sys.stdout)

    canonical_order = [label for _, label in SENIORITY]
    found_labels = {detect_seniority(j["title"]) for j in all_visible}
    has_none = None in found_labels
    found_labels.discard(None)
    seniority_labels = [l for l in canonical_order if l in found_labels]
    # dedup while preserving order. CAREFUL: the local variable name
    # `seen` would shadow (actually mutate, since set is a reference)
    # the module-level `seen` loaded at the top of main() to track URLs.
    # Using a different name keeps our URL tracker intact — otherwise
    # we end up persisting seniority labels into seen.json alongside
    # the real job URLs.
    _dedup = set()
    seniority_labels = [l for l in seniority_labels if not (l in _dedup or _dedup.add(l))]
    # Jobs without a detected seniority are always visible (no "None"
    # checkbox in the filter bar). They can still be hidden via the title
    # or text filters if needed.

    server_url = f"http://{SERVE_HOST}:{SERVE_PORT}"
    # Run the global list of unique locations through the flattener one more
    # time so aliases apply across sources (e.g. "Remote-Friendly (Travel
    # Required)" from Anthropic merges with "Remote-Friendly US (Travel
    # Required)" from Anthropic even when they originate from different jobs).
    _raw_locs = list({loc for j in all_visible for loc in j["locations"] if loc})
    all_locations = sorted(_flatten_locations(_raw_locs))

    print(file=sys.stdout)
    print(f"[locations] {len(all_locations)} unique locations across {len(_raw_locs)} raw entries",
          file=sys.stdout)
    for country, cities in _group_locations(all_locations):
        marker = f"{_RED}{country}{_RESET}" if country == "Other" else country
        print(f"  {marker} ({len(cities)}): {', '.join(cities)}", file=sys.stdout)
    print(file=sys.stdout)

    # Dump every raw location string we saw across sources — used by
    # improve_locations.py to seed the audit workflow. Written each run so
    # newly-added companies get their locations in the file.
    raw_dump = []
    seen_raw = set()
    for src in active_sources:
        r = results.get(src["name"]) or {}
        for j in r.get("jobs") or []:
            # We can't easily recover the original pre-flatten string here;
            # each already-flattened location works as an "audit unit".
            for loc in j.get("locations") or []:
                if loc not in seen_raw:
                    seen_raw.add(loc)
                    raw_dump.append(loc)
    # Run the flattener once more across the union so cross-source variants
    # (Zurich vs Zürich, "Peru" alone vs "Peru, X", …) get deduped.
    raw_dump = sorted(_flatten_locations(raw_dump))
    try:
        os.makedirs(os.path.dirname(RAW_LOCATIONS_FILE) or ".", exist_ok=True)
        with open(RAW_LOCATIONS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(raw_dump) + "\n")
        print(f"[locations] wrote {len(raw_dump)} raw entries to {RAW_LOCATIONS_FILE}",
              file=sys.stdout)
    except Exception as e:
        err(f"[locations] failed to write {RAW_LOCATIONS_FILE}: {e}")
    total = len(all_visible)
    total_new = sum(1 for j in all_visible if j.get("is_new"))
    # Counters derived from the visible-across-all-sources list. The client
    # keeps them in sync when the user toggles a button — see updateCounters
    # below. The state check matches li.applied → applied > toapply > liked
    # so a job in "applied" doesn't get double-counted in liked.
    visible_urls = {j["url"] for j in all_visible}
    # Spontaneous URLs (one per source with a ✉ link) are ALSO likeable via
    # the +1 button next to the envelope. When liked, they should count as
    # +1 in the top-of-page "Open Liked" tally alongside job likes. Union
    # them into visible_urls so the intersect-with-liked math below picks
    # them up.
    spontaneous_urls = {
        r.get("spontaneous_url") for r in results.values()
        if r.get("spontaneous_url")
    }
    visible_urls = visible_urls | spontaneous_urls
    # `applied` is now a dict {url: {ts}} — treat keys as the set for math.
    applied_keys = set(applied.keys()) if isinstance(applied, dict) else set(applied)
    # app_rejected is dict too; count visible ones that stayed in Applied at
    # some point but got the company-rejection flag on top.
    app_rej_keys = set(app_rejected.keys()) if isinstance(app_rejected, dict) else set(app_rejected)
    n_liked        = len((liked & visible_urls) - to_apply - applied_keys - app_rej_keys)
    n_toapply      = len((to_apply & visible_urls) - applied_keys - app_rej_keys)
    # An applied+rejected job counts as Rejected, NOT Applied — mutually exclusive.
    n_applied      = len((applied_keys & visible_urls) - app_rej_keys)
    n_app_rejected = len(app_rej_keys & visible_urls)
    # All counts live on the tab labels; the R / AI / ⚙ actions live
    # inside the tabs nav. The top bar carries the async-action status
    # line + global settings (currently just the Highlight toggle) that
    # need to stay reachable on every tab (not only the All tab's
    # filters section).
    # The /settings page owns the row-element show/hide toggles (served
    # by _render_settings_html). The top bar carries only the async-
    # action status line.
    total_bar = (
        f'  <div class="top-bar top-bar-row2">\n'
        f'    <span class="dump-status" id="dump-status" aria-live="polite"></span>\n'
        f'  </div>\n'
        # Floating refresh indicator — stays visible no matter how far the
        # user has scrolled. The in-flow #dump-status is kept for the
        # non-refresh messages ("copied to clipboard", "opening N URLs")
        # that are tied to a specific action.
        f'  <div id="refresh-floater" role="status" aria-live="polite"></div>\n'
    )
    # Build a "sources with problems" banner so you can see at a glance
    # which scrapers crashed or returned nothing this run. Broken (red) →
    # code needs a fix. Empty (grey) → source likely blocked or URL moved.
    # Also compute per-source rejected counts across ALL history so we can
    # flag sources whose scraper never surfaced anything you cared enough
    # to reject (usually means: broken since day 1, or wrong queries).
    _reject_by_source = {}
    for u in rejected:
        src_name = job_index.get(u, {}).get("source")
        if src_name:
            _reject_by_source[src_name] = _reject_by_source.get(src_name, 0) + 1
    _broken = [
        (name, results[name].get("error") or "")
        for name in (s["name"] for s in active_sources)
        if results[name].get("error")
    ]
    _empty = [
        name for name in (s["name"] for s in active_sources)
        if not results[name].get("error")
        and not results[name].get("jobs")
        and not results[name].get("total_board")
    ]
    # Suspect: scraper did NOT crash and reported a total_board, but the
    # pre-blacklist raw count is far below that total. Signals a scraper
    # that only sees part of the board (broken pagination, wrong regex,
    # partial page load).
    #
    # Sources with `queries` set filter server-side by keyword, so raw
    # count vs total_board mismatch is EXPECTED (Anthropic returns 83 of
    # 627 = only jobs matching "security"/"cryptography"/etc.). Only
    # sources with queries=[] can be legitimately compared.
    _suspect = []
    for src in active_sources:
        if src.get("queries"):
            continue                        # keyword filter → mismatch is normal
        r = results[src["name"]] or {}
        if r.get("error") or not r.get("total_board"):
            continue
        total_board = r["total_board"]
        raw = r.get("raw_fetched")
        if raw is None:
            continue
        gap = total_board - raw
        if total_board >= 10 and gap >= 5 and raw < total_board * 0.5:
            _suspect.append((src["name"], raw, total_board))
    # "Never seen matching" — sources with 0 rejected across ALL history AND
    # 0 visible right now. Usually means the scraper works technically but
    # the queries are too narrow OR the source really has nothing matching
    # your profile. Excludes sources already listed in the "issues" banner
    # (broken / suspect / empty) so a company shows up in exactly ONE list.
    _issue_names = {n for n, _ in _broken} | {n for n, _, _ in _suspect} | set(_empty)
    _never_matched = []
    for src in active_sources:
        name = src["name"]
        if name in _issue_names:
            continue
        r = results[name] or {}
        has_visible = len(r.get("jobs") or []) > 0
        if has_visible:
            continue
        if _reject_by_source.get(name, 0) > 0:
            continue
        _never_matched.append(name)
    problems_banner = ""
    if _broken or _empty or _suspect:
        parts = []
        if _broken:
            broken_html = ", ".join(
                f'<a href="#{slug(n)}" title="{html.escape(err, quote=True)}">{html.escape(n)}</a>'
                for n, err in sorted(_broken, key=lambda x: x[0].lower())
            )
            parts.append(
                f'<div class="problems-line problems-broken">'
                f'<strong>⚠ Broken scrapers ({len(_broken)}):</strong> {broken_html}</div>'
            )
        if _suspect:
            suspect_html = ", ".join(
                f'<a href="#{slug(n)}" title="Scraper saw only {raw}/{total} jobs — likely missing pagination or wrong selector.">{html.escape(n)} ({raw}/{total})</a>'
                for n, raw, total in sorted(_suspect, key=lambda x: x[0].lower())
            )
            parts.append(
                f'<div class="problems-line problems-suspect">'
                f'<strong>🟡 Suspect scrapers ({len(_suspect)}):</strong> {suspect_html}</div>'
            )
        if _empty:
            empty_html = ", ".join(
                f'<a href="#{slug(n)}">{html.escape(n)}</a>'
                for n in sorted(_empty, key=lambda x: x.lower())
            )
            parts.append(
                f'<div class="problems-line problems-empty">'
                f'<strong>⚪ Sources with 0 jobs ({len(_empty)}):</strong> {empty_html}</div>'
            )
        _issue_total = len(_broken) + len(_suspect) + len(_empty)
        problems_banner = (
            '  <details class="problems-banner">\n'
            f'    <summary>Sources with issues this run ({_issue_total}) — click to expand</summary>\n'
            f'    {"".join(parts)}\n'
            '  </details>\n'
        )
    # Separate collapsible: "Never seen matching" — sources that have never
    # produced a job you rejected AND have 0 visible right now. Not an
    # "issue" per se (queries just don't hit), but worth surfacing so you
    # can prune the source list.
    never_matched_banner = ""
    if _never_matched:
        nm_html = ", ".join(
            f'<a href="#{slug(n)}">{html.escape(n)}</a>'
            for n in sorted(_never_matched, key=lambda x: x.lower())
        )
        never_matched_banner = (
            '  <details class="problems-banner never-matched-banner">\n'
            f'    <summary>Never seen matching ({len(_never_matched)}) — click to expand</summary>\n'
            f'    <div class="problems-line problems-never-matched">'
            f'<strong>🔍 No rejects, no matches — ever:</strong> {nm_html}</div>\n'
            '  </details>\n'
        )
    html_body = (
        # Tabs sit at the top so switching views is one glance away. Every
        # other section below reacts to the active body.tab-{name} class.
        render_html_tabs() + "\n"
        + total_bar + "\n"
        + problems_banner
        + never_matched_banner
        + render_html_nav(nav_entries) + "\n"
        + render_html_filters(seniority_labels, all_locations) + "\n"
        # Ranked tab destination — JS moves every <li.job> here on tab
        # activation (sorted by Claude fit DESC), and restores them to their
        # original company section on deactivation. The controls bar above
        # it hosts the "show spontaneous" checkbox; both are hidden on
        # every tab EXCEPT ranked via CSS.
        + '  <div id="ranked-controls" class="ranked-controls">\n'
        + '    <label class="filter-check"><input type="checkbox" id="ranked-show-spontaneous" checked> Show spontaneous</label>\n'
        + '    <label class="filter-check"><input type="checkbox" id="ranked-show-marks" checked> Show marks</label>\n'
        + '  </div>\n'
        + '  <ul id="ranked-list" class="ranked-list"></ul>\n'
        + "\n".join(html_sections)
    )
    # Inline the Claude fit cache so badges hydrate on page load without
    # waiting for a user click. Only visible URLs so the payload stays small.
    _fit_cache = _load_claude_fit_cache()
    _fit_subset = {j["url"]: _fit_cache[j["url"]] for j in all_visible if j["url"] in _fit_cache}
    # Edit-companies modal: the catalog + the user's currently-tracked
    # names are inlined so the dialog opens instantly, no round-trip.
    try:
        from catalog import CATALOG as _CATALOG_FOR_EDIT
    except Exception:
        _CATALOG_FOR_EDIT = []
    try:
        from wttj_discovery import load_candidates as _wttj_discovery_load
    except Exception:
        _wttj_discovery_load = lambda _p: {}
    _sources_names = sorted({s.get("name") for s in SOURCES if s.get("name")})
    html_output = (
        HTML_TEMPLATE
        .replace("__BODY__", html_body)
        .replace("__SERVER_URL__", server_url)
        .replace("__HIGHLIGHTS__", json.dumps(HIGHLIGHTS))
        .replace("__CLAUDE_FITS__", json.dumps(_fit_subset))
        .replace("__CATALOG_FOR_EDIT__", json.dumps(_CATALOG_FOR_EDIT))
        .replace("__SOURCES_NAMES__", json.dumps(_sources_names))
        .replace("__RUNAWAY_THRESHOLD__", json.dumps(_cfg.RUNAWAY_THRESHOLD))
        .replace("__BOARD_TITLE__", html.escape(_cfg.BOARD_TITLE))
        .replace("__WTTJ_DISCOVERED__", json.dumps(
            (_wttj_discovery_load(os.path.join(DATA_DIR, "wttj_discovered.json"))
             or {}).get("candidates", [])
        ))
    )

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_output)
    t_render = time.perf_counter() - t_render_start
    timing(f"[timing] render + write → {t_render:.1f}s")

    # Persist the union of "seen so far" ∪ "everything we surfaced this run".
    # Doing this AFTER the HTML render means the current run's NEW badges are
    # already baked in — the update only affects future runs.
    all_urls_this_run = {j["url"] for j in all_visible} | {
        j["url"] for src in active_sources for j in results[src["name"]]["jobs"]
    }
    new_this_run = all_urls_this_run - seen
    save_seen(seen | all_urls_this_run)
    save_job_index(job_index)

    elapsed = time.perf_counter() - t0
    timing(
        f"wrote {OUTPUT_HTML} · total {elapsed:.1f}s · "
        f"rejected DB: {REJECTED_DB} ({len(rejected)} entries) · "
        f"NEW this run: {len(new_this_run)}"
    )

    # All Playwright work is done — release the shared Chromium instance so
    # it doesn't leak memory while the HTTP server runs indefinitely.
    _close_shared_browser()

    # WTJ company discovery — one Algolia POST per refresh. Independent
    # of the fetchers loop (not a source), writes to
    # data/wttj_discovered.json so the Edit-companies modal can surface
    # companies not yet in the catalog. Isolated in a try so a WTJ
    # outage never breaks the render.
    try:
        import wttj_discovery
        candidates = wttj_discovery.fetch_candidates()
        wttj_discovery.cache_candidates(
            os.path.join(DATA_DIR, "wttj_discovered.json"),
            candidates,
        )
        timing(f"[wttj_discovery] cached {len(candidates)} candidates")
    except Exception as e:
        timing(f"[wttj_discovery] skipped: {e}")

    if args.no_serve:
        print("[main] --no-serve: exiting after render", file=sys.stdout)
        return
    print("=" * 70, file=sys.stdout)
    print("Step 4 — serve: local HTTP server + auto-open browser; handles", file=sys.stdout)
    print("               POST /reject and POST /like for live persistence", file=sys.stdout)
    print("=" * 70, file=sys.stdout)
    try:
        server = http.server.ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    except OSError as e:
        # EADDRINUSE = 48 on macOS, 98 on Linux. Common cause: a prior
        # `make onboarding` left its spawned board subprocess running.
        if getattr(e, "errno", None) in (48, 98):
            err(f"\nPort {SERVE_PORT} is already in use.")
            err("Another jobs server (or make onboarding → launch) is probably")
            err("still running. Kill it with:")
            err("")
            err(f"    lsof -ti:{SERVE_PORT} | xargs kill")
            err("")
            err("Then re-run  make run.")
            sys.exit(1)
        raise
    print(f"serving on {server_url} — Ctrl-C to stop", file=sys.stdout)
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(server_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("bye", file=sys.stdout)


if __name__ == "__main__":
    main()
