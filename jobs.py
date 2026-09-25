#!/usr/bin/env python3
"""
jobs.py — aggregate job postings from multiple career boards into a single
HTML page with reject/persistence and client-side filters.

Everything you may want to tweak lives in the CONFIG section below.

Pipeline
--------
Step 1 — Load state
    Read `rejected.json`, `liked.json`, `score_cache.json`, `desc_cache.json`,
    `PROFILE.md`. Parse env-var knobs (JOBS_ONLY / JOBS_SKIP /
    JOBS_SKIP_PLAYWRIGHT / JOBS_SKIP_SCORING) to decide which sources run.

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

Step 4 — Score against PROFILE.md
    All non-rejected jobs are batched (SCORE_BATCH_SIZE) and sent to the LLM
    (Ollama local by default, or Anthropic Claude). Results cached to
    `score_cache.json`. Failed batches split recursively down to size 1.

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
    OUTPUT_HTML, REJECTED_DB, LIKED_DB, TO_APPLY_DB, APPLIED_DB, SEEN_DB, JOB_INDEX_DB, PROFILE_FILE,
    SCORE_CACHE, DESC_CACHE, RAW_LOCATIONS_FILE,
    LIST_CACHE_DIR, LIST_CACHE_TTL_HOURS,
    SERVE_HOST, SERVE_PORT,
    SCORER, CLAUDE_MODEL, OLLAMA_URL, OLLAMA_MODEL,
    SCORE_BATCH_SIZE, SCORE_DESC_CHARS, SCORE_PARALLEL, SCORE_LONG_ROLES,
    HIGHLIGHTS, TITLE_CASE_OVERRIDES,
    TITLE_BLACKLIST, LOCATION_BLACKLIST,
    SENIORITY_GROUPS, SENIORITY_RANK, SENIORITY, SENIORITY_TOGGLES,
    SOURCES, SPONTANEOUS_PATTERNS,
    GROUP_ORDER, GROUP_OF,
)


import argparse
import concurrent.futures
import html
import http.server
import json
import re
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

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

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
def load_applied():    return _load_set(APPLIED_DB)
def save_applied(s):   _save_set(APPLIED_DB, s)


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
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(all_jobs)}


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
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(all_jobs)}


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


def fetch_apple(source):
    if not HAS_PLAYWRIGHT:
        sys.stdout.write(
            "[Apple] Playwright not installed. Run:\n"
            "  pip install playwright && playwright install chromium\n"
        )
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        for q in source["queries"]:
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
                if not jobs:
                    break
                added = 0
                for j in jobs:
                    if not j["url"] or j["url"] in seen:
                        continue
                    seen.add(j["url"])
                    out.append(j)
                    added += 1
                if added == 0:
                    break
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, "Apple")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


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


def fetch_google(source):
    if not HAS_PLAYWRIGHT:
        sys.stdout.write(
            "[Google] Playwright not installed. Run:\n"
            "  pip install playwright && playwright install chromium\n"
        )
        return {"jobs": [], "spontaneous_url": None}
    base = source.get("search_url") or "https://www.google.com/about/careers/applications/jobs/results/?hl=en_US"
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
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
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


_MICROSOFT_JOB_RE = re.compile(
    r'href="/careers/job/(\d+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def fetch_microsoft(source):
    if not HAS_PLAYWRIGHT:
        sys.stdout.write(
            "[Microsoft] Playwright not installed. Run:\n"
            "  pip install playwright && playwright install chromium\n"
        )
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        for q in source["queries"]:
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
                if added == 0:
                    break
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, "Microsoft")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


def _pw_scrape_links(source_name, url, link_re_pattern, origin, wait_selector="a"):
    """Render `url` with Playwright, then extract hrefs matching `link_re_pattern`.
    Titles are derived from the last URL segment. Returns list of job dicts."""
    if not HAS_PLAYWRIGHT:
        err(f"[{source_name}] Playwright not installed")
        return []
    debug = f"debug/debug-{slug(source_name)}-1.html"
    p, browser, page = _open_browser()
    try:
        text = _render(page, url, wait_selector=wait_selector, debug_path=debug)
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


def fetch_pw_generic(source):
    """Generic Playwright link scraper. Requires `search_url`, `link_re`, `origin` on source."""
    if not source.get("search_url") or not source.get("link_re"):
        err(f"[{source['name']}] missing search_url/link_re")
        return {"jobs": [], "spontaneous_url": None}
    jobs = _pw_scrape_links(
        source["name"],
        source["search_url"],
        source["link_re"],
        source.get("origin") or source["search_url"].rsplit("/", 1)[0],
        wait_selector=source.get("wait_selector", "a"),
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


def fetch_github(source):
    """GitHub careers page — anchors carry the title as text; the generic
    scraper would use the URL slug instead which loses the title."""
    if not HAS_PLAYWRIGHT:
        err("[GitHub] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
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
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


def fetch_scale(source):
    """Scale AI careers page — job cards have title + location inside the
    anchor body, so we can extract both at once."""
    if not HAS_PLAYWRIGHT:
        err("[Scale AI] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        url = source.get("search_url") or "https://scale.com/careers"
        debug = "debug/debug-scale-ai-1.html"
        text = _render(page, url, wait_selector='a[href*="/careers/"]', debug_path=debug)
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
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


_META_JOB_RE = re.compile(r'/profile/job_details/(\d{5,})', re.IGNORECASE)


def fetch_meta(source):
    if not HAS_PLAYWRIGHT:
        err("[Meta] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
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
                locs = parts[1:] if len(parts) > 1 else []
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
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


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
    origin = source.get("search_url", "").split("/careers")[0] or "https://jobs.example.com"
    try:
        for q in source["queries"]:
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
                if added == 0:
                    break
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, source["name"])
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


_WTTJ_JOB_RE = re.compile(
    r'href="(/[a-z]{2}/companies/[^"#]+/jobs/[^"#?]+)"',
    re.IGNORECASE,
)


def fetch_wttj(source):
    if not HAS_PLAYWRIGHT:
        err("[Welcome to the Jungle] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        for q in source["queries"]:
            base = source.get("search_url") or f"https://www.welcometothejungle.com/fr/pages/emploi?query={urllib.parse.quote(q)}"
            for pnum in range(1, 6):
                sep = "&" if "?" in base else "?"
                url = f"{base}{sep}page={pnum}"
                debug = f"debug/debug-wttj-{q}-{pnum}.html" if pnum == 1 else None
                text = _render(
                    page, url,
                    wait_selector='a[href*="/companies/"][href*="/jobs/"]',
                    debug_path=debug,
                )
                paths = list(dict.fromkeys(_WTTJ_JOB_RE.findall(text)))
                if pnum == 1:
                    sys.stdout.write(
                        f"[Welcome to the Jungle] q='{q}' rendered {len(text)}B, urls={len(paths)}\n"
                    )
                if not paths:
                    break
                added = 0
                for path in paths:
                    if path in seen:
                        continue
                    seen.add(path)
                    tail = path.rstrip("/").rsplit("/", 1)[-1]
                    title = _title_from_slug(tail)
                    out.append({
                        "title": title,
                        "locations": [],
                        "url": f"https://www.welcometothejungle.com{path}",
                        "description": "",
                        "blob": title,
                    })
                    added += 1
                if added == 0:
                    break
        filtered = [j for j in out if matches(j, source["queries"])]
        _fetch_descriptions(page, filtered, "Welcome to the Jungle")
    finally:
        browser.close()
        p.stop()
    return {"jobs": filtered, "spontaneous_url": _pick_spontaneous(out)}


FETCHERS = {
    "ashby": fetch_ashby,
    "greenhouse": fetch_greenhouse,
    "workable": fetch_workable,
    "apple": fetch_apple,
    "google": fetch_google,
    "microsoft": fetch_microsoft,
    "meta": fetch_meta,
    "phenom": fetch_phenom,
    "scale": fetch_scale,
    "github": fetch_github,
    "checkmarx": fetch_checkmarx,
    "pixee": fetch_pixee,
    "ableton": fetch_ableton,
    "lucca": fetch_lucca,
    "pw": fetch_pw_generic,
    "wttj": fetch_wttj,
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


SCORING_SYSTEM_BASE = """You score job postings against a candidate profile.

Return ONLY a JSON array with ONE ELEMENT PER JOB you were given. If 5 jobs are
provided, the array MUST contain 5 elements. Never merge, summarize, or skip.

Each element:
  {"i": <index from the numbered list>, "score": <integer 0-10>,
   "reason": "<why this score — 2-3 sentences, ~100-400 chars, cite rubric>"__EXTRA_FIELDS__}

Example (for 2 jobs):
  [
    {"i": 1, "score": 8,
     "reason": "Directly matches the AI-powered vulnerability remediation interest (Codex-style role at OpenAI, US-based). No management scope but strong IC track and applied crypto adjacency via secure code analysis."__EXAMPLE_EXTRA__},
    {"i": 2, "score": 3,
     "reason": "Sales/GTM role, not technical. Team focuses on account expansion rather than security engineering; location fits but domain doesn't align with the rubric priorities."__EXAMPLE_EXTRA_2__}
  ]

Scoring rubric: 9-10 top-priority match, 6-8 solid, 3-5 partial, 0-2 weak.
The reason field explains the SCORE. The role_long field describes the job."""


def _scoring_system():
    if SCORE_LONG_ROLES:
        return (
            SCORING_SYSTEM_BASE
            .replace(
                "__EXTRA_FIELDS__",
                ',\n   "role_long": "<STRICT RULE: the reader already knows the company. Do NOT copy or paraphrase any \\"About us\\" / \\"Our mission\\" / \\"We are a company that\\" content. If the description opens with a company blurb, SKIP IT and start from the actual role. Detailed version of the ROLE, using markdown bullet points under section headers **Missions:**, **Key responsibilities:**, **Team:**, **Tech:**, **Seniority:**, **Minimal profile:**, **Preferred profile:**, **Salary:** in that exact order. Be as thorough as the job description supports — aim for 1500-3500 characters when the source material is rich. Cover: (Missions) the high-level mission of the role — what this position exists to achieve, 2-3 bullets; (Key responsibilities) the concrete day-to-day duties as stated in the description (variants: \\"you will…\\", \\"your responsibilities include…\\", \\"what you will do\\", \\"what you will be doing\\", \\"in this role you will\\", \\"about the role\\") — quote verbatim when possible, 4-6 bullets; (Team) size and structure of the team the person will be part of, reporting line, cross-functional partners; (Tech) READ THE WHOLE DESCRIPTION and extract EVERY technical hint — programming languages, frameworks, cloud providers (AWS/GCP/Azure), databases, ML tooling (PyTorch, JAX, HuggingFace, ONNX), cryptography protocols (FHE, MPC, TLS, PKI, ZK), reverse-engineering tools, operating systems, compilers (LLVM, MLIR), CI/CD, container tech. Also infer from the domain: an FHE role implies homomorphic encryption; a browser-security role implies V8/JS/DOM; a Codex role implies LLM inference stack. Only say \\"not stated\\" if the description is truly non-technical (e.g. Sales); (Seniority) explicit level in the title (Staff, Senior, Principal, etc.) AND any internal IC-level band mentioned anywhere in the description — quote verbatim (e.g. \\"IC5\\", \\"IC6\\", \\"L5\\", \\"L6\\", \\"E5\\", \\"M2\\", \\"Level 5\\", \\"Staff (IC5)\\", \\"Principal (IC6)\\") — these usually appear in the compensation table or a levels breakdown; AND years-of-experience requirement quoted verbatim from the description (e.g. \\"7+ years of experience in security engineering\\") AND any manager-vs-IC signal AND required qualifications like PhD or specific certifications; (Minimal profile) EVERYTHING labeled as required / must-have / \\"you have\\" / \\"required qualifications\\" / \\"basic qualifications\\" / \\"good fit if\\" — the hard bar. Quote verbatim; (Preferred profile) EVERYTHING labeled as preferred / nice-to-have / bonus / \\"you might also have\\" / \\"preferred qualifications\\" / \\"strong candidates if\\" / \\"you could be a strong candidate if\\" / \\"about you\\" / \\"you will thrive in this role if you\\" — the soft bar. Quote verbatim; (Salary) FIRST bullet MUST be a compensation range in USD only, using one of these two exact formats: \\"$MIN - $MAX USD\\" (when the description gives both a floor and a ceiling) or \\"> $MIN USD\\" (when the description only gives a floor, or wording like \\"starting at\\", \\"from\\", \\"minimum\\"). Numbers formatted with commas (e.g. \\"$405,000 - $485,000 USD\\"). If the description quotes the salary in another currency (EUR, GBP, CHF, CAD), convert to USD using the approximate rates 1 EUR = 1.08 USD, 1 GBP = 1.27 USD, 1 CHF = 1.13 USD, 1 CAD = 0.73 USD and round to the nearest 1,000. Never emit two currencies, never add prose like \\"which is roughly …\\", \\"equivalent to …\\", \\"exceeds …\\". If the description states NO salary at all, the FIRST bullet MUST be exactly \\"no information on salaries\\". Then, on separate bullets, add any equity / bonus / benefits / location constraints / travel / visa info stated. No company boilerplate."'
            )
            .replace(
                "__EXAMPLE_EXTRA__",
                ',\n     "role_long": "**Missions:**\\n- Scale Codex to production developer workflows.\\n- Own end-to-end the model-to-PR pipeline used by design partners.\\n\\n**Key responsibilities:**\\n- \\"Design and implement prompt strategies for code-generation tasks\\".\\n- \\"Build and maintain the evaluation harness for auto-PR quality\\".\\n- \\"Ship weekly improvements based on design-partner telemetry\\".\\n- \\"Run post-generation static analysis to catch regressions before merge\\".\\n\\n**Team:**\\n- 8 IC engineers, one Staff TL, embedded PM and applied researcher.\\n\\n**Tech:**\\n- Python (backend), TypeScript (developer-facing surfaces).\\n- Runs on internal Kubernetes; model serving on GPU clusters.\\n- Cryptography: TLS-terminating proxies and signed webhook payloads; no low-level crypto work.\\n\\n**Seniority:**\\n- Title: Member of Technical Staff.\\n- Experience: \\"7+ years shipping production ML systems\\" (quoted).\\n- IC role, no direct reports.\\n\\n**Minimal profile:**\\n- \\"BS in CS or equivalent experience\\".\\n- \\"7+ years shipping production ML systems\\".\\n- \\"Fluency in Python and modern JS\\".\\n\\n**Preferred profile:**\\n- \\"Prior experience with LLM inference stacks (vLLM, TGI)\\".\\n- \\"Contributions to open-source developer tools\\".\\n- \\"Prior work on evaluation harnesses\\".\\n\\n**Salary:**\\n- $405,000 - $485,000 USD.\\n- Equity refresh yearly."'
            )
            .replace(
                "__EXAMPLE_EXTRA_2__",
                ',\n     "role_long": "**Missions:**\\n- Run quarterly quota on financial-services logos across EMEA (60% new logo, 40% expansion).\\n- Lead technical qualification before handoff to solutions engineering.\\n- Own executive relationships at named accounts.\\n\\n**Team:**\\n- Reports to Regional Sales Director; sits alongside 5 other AEs, supported by 2 SEs and 1 SDR.\\n\\n**Tech:**\\n- Not stated in the description (non-engineering role).\\n\\n**Seniority:**\\n- Experience: \\"5+ years selling enterprise SaaS\\" (quoted).\\n- IC quota-carrying role, no direct reports.\\n\\n**Salary:**\\n- $250,000 - $350,000 USD.\\n- Travel required to customer sites."'
            )
        )
    return (
        SCORING_SYSTEM_BASE
        .replace("__EXTRA_FIELDS__", "")
        .replace("__EXAMPLE_EXTRA__", "")
        .replace("__EXAMPLE_EXTRA_2__", "")
    )


SCORING_SYSTEM = _scoring_system()


def _load_profile():
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
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


def _make_batch_prompt(batch):
    lines = ["Score these jobs (return JSON array only, one entry per job):", ""]
    for i, j in enumerate(batch, 1):
        desc = re.sub(r"<[^>]+>", " ", j.get("description") or "")
        desc = re.sub(r"\s+", " ", desc).strip()[:SCORE_DESC_CHARS]
        locs = ", ".join(j.get("locations") or []) or "N/A"
        lines.append(f"[{i}]")
        lines.append(f"title: {j['title']}")
        lines.append(f"location: {locs}")
        if desc:
            lines.append(f"description: {desc}")
        lines.append("")
    return "\n".join(lines)


_SCORE_DEBUG = {"first": True}


def _extract_first_object(text):
    """Given a possibly-truncated JSON payload (e.g. `[{...},{...},<cut>`),
    return the first complete top-level object as a dict, or None. Used as a
    fallback when the LLM loops on itself and blows past the token budget."""
    # Find the first '{' after optional array bracket.
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def _parse_score_response(text, batch):
    orig = text
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    data = None
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                pass
    # Recovery path: LLM went into a repetition loop and the payload is a
    # sequence of duplicated objects with the tail truncated mid-string. Pull
    # the first complete `{...}` object out and score that one job only.
    if data is None:
        first = _extract_first_object(text)
        if first is not None:
            data = [first]
    if isinstance(data, dict):
        for k in ("scores", "results", "jobs", "data"):
            if k in data and isinstance(data[k], list):
                data = data[k]
                break
        else:
            # Single-object response (qwen sometimes returns one JSON object per
            # call instead of an array). Wrap so the loop below handles it.
            if any(k in data for k in ("i", "index", "id", "score")):
                data = [data]
    out = {}
    items_list = data if isinstance(data, list) else []
    for pos, item in enumerate(items_list):
        if not isinstance(item, dict):
            continue
        idx = item.get("i") or item.get("index") or item.get("id")
        try:
            idx = int(idx) - 1
        except Exception:
            idx = None
        # Fallback 1: when there's no explicit index but positions align with
        # the batch (small models often skip or invent the "i" field).
        if (idx is None or not (0 <= idx < len(batch))) and pos < len(batch):
            idx = pos
        # Fallback 2: for size-1 batches, the item is unambiguously the job
        # (some models emit i=-1, i=0, i=99, etc.; use the only slot we have).
        if (idx is None or not (0 <= idx < len(batch))) and len(batch) == 1:
            idx = 0
        if idx is None or not (0 <= idx < len(batch)):
            continue
        url = batch[idx]["url"]
        try:
            def _clean(s, maxlen=400):
                s = str(s or "")
                # Normalize exotic Unicode spaces (EM QUAD, EN SPACE, etc.).
                s = re.sub(r"[\u2000-\u200a\u202f\u205f\u3000]", " ", s)
                s = re.sub(r"\s+", " ", s).strip()
                return s[:maxlen]
            raw_score = int(item.get("score", 0))
            # Small models sometimes return scores outside the 0-10 bounds.
            score = max(0, min(10, raw_score))
            role_long_raw = item.get("role_long", "")
            role_long_md = _role_long_to_markdown(role_long_raw)
            out[url] = {
                "score":     score,
                "reason":    _clean(item.get("reason", "")),
                "role_long": _clean(role_long_md, maxlen=6000),
            }
        except Exception:
            continue
    if not out:
        # Always dump when a batch produces zero scores. Rotated file so
        # we can inspect multiple failures side by side.
        try:
            _ensure_debug_dir()
            n = _SCORE_DEBUG.setdefault("n", 0) + 1
            _SCORE_DEBUG["n"] = n
            with open(f"debug/debug-score-response-{n}.txt", "w", encoding="utf-8") as f:
                f.write(orig)
            sys.stdout.write(
                f"[score] batch parsed 0 items → dumped raw response to "
                f"debug-score-response-{n}.txt ({len(orig)} chars)\n"
            )
        except Exception:
            pass
    return out


def _score_batch_claude(batch, profile_text, client):
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=[
            {"type": "text", "text": SCORING_SYSTEM},
            {"type": "text", "text": profile_text, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": _make_batch_prompt(batch)}],
    )
    text = resp.content[0].text if resp.content else ""
    return _parse_score_response(text, batch)


_LONG_ROLE_SECTIONS = [
    "missions", "key_responsibilities", "team", "tech", "seniority",
    "minimal_profile", "preferred_profile", "salary",
]


def _ollama_json_schema():
    """Build a strict JSON schema that forces the model to produce every field
    we need. Ollama honours this via structured outputs (v0.5+)."""
    item_props = {
        "i":      {"type": "integer"},
        "score":  {"type": "integer", "minimum": 0, "maximum": 10},
        "reason": {"type": "string",  "minLength": 30},
    }
    required = ["i", "score", "reason"]
    if SCORE_LONG_ROLES:
        # role_long is an OBJECT with one array-of-bullets per section. That
        # way the model is forced to fill each section separately — it can't
        # just dump a blob of prose that ignores the structure we asked for.
        section_schema = {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 10},
        }
        item_props["role_long"] = {
            "type": "object",
            "properties": {name: section_schema for name in _LONG_ROLE_SECTIONS},
            "required": _LONG_ROLE_SECTIONS,
        }
        required.append("role_long")
    return {
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "properties": item_props,
            "required": required,
        },
    }


_SECTION_LABELS = {
    "missions":            "Missions",
    "key_responsibilities":"Key responsibilities",
    "team":                "Team",
    "tech":                "Tech",
    "seniority":           "Seniority",
    "minimal_profile":     "Minimal profile",
    "preferred_profile":   "Preferred profile",
    "salary":              "Salary",
}


def _role_long_to_markdown(role_long_value):
    """Turn an object {missions: [...], team: [...], ...} into the markdown
    string that the rest of the code expects. If it's already a string,
    pass through."""
    if isinstance(role_long_value, str):
        return role_long_value
    if not isinstance(role_long_value, dict):
        return ""
    parts = []
    for key in _LONG_ROLE_SECTIONS:
        bullets = role_long_value.get(key) or []
        if not isinstance(bullets, list):
            continue
        clean = [b.strip() for b in bullets if isinstance(b, str) and b.strip()]
        if not clean:
            clean = ["not stated in the description"]
        label = _SECTION_LABELS.get(key, key.replace("_", " ").title())
        parts.append(f"**{label}:**\n" + "\n".join(f"- {b}" for b in clean))
    return "\n\n".join(parts)


def _score_batch_ollama(batch, profile_text):
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM + "\n\n" + profile_text},
            {"role": "user", "content": _make_batch_prompt(batch)},
        ],
        # Use a JSON schema (Ollama structured outputs) instead of "json"
        # so the model MUST fill in every required field, not just "score".
        "format": _ollama_json_schema(),
        "options": {
            # Curb "token repeat limit reached" 500s from Ollama when the model
            # falls into a repetition loop generating long role_long payloads.
            # 1.35 is aggressive but this repo has seen the LLM emit the same
            # JSON object 4+ times in a row until num_predict runs out (see
            # debug/debug-score-response-*.txt). A stronger penalty over a
            # longer lookback breaks the loop before it wastes the whole budget.
            "repeat_penalty": 1.35,
            "repeat_last_n": 512,
            # Cap the number of tokens generated per response.
            "num_predict": 3000 if SCORE_LONG_ROLES else 800,
        },
    }
    req = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    # Long-role prompts generate ~2x more tokens; give the LLM more headroom.
    ollama_timeout = 600 if SCORE_LONG_ROLES else 300
    try:
        with urllib.request.urlopen(req, timeout=ollama_timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code}: {body}") from None
    text = data.get("message", {}).get("content", "") or data.get("response", "")
    return _parse_score_response(text, batch)


def score_jobs(jobs):
    """Attach `score` and `score_reason` to each job in place. Uses SCORE_CACHE
    to avoid re-scoring URLs we already know about."""
    if SCORER == "none" or not jobs:
        return
    profile = _load_profile()
    if not profile:
        sys.stdout.write(f"[score] no {PROFILE_FILE} — skipping\n")
        return
    cache = _load_score_cache()
    # Rescore jobs that lack fields we now want. When SCORE_LONG_ROLES is on,
    # any cached entry that predates the long-role feature is missing
    # `role_long` and gets re-scored automatically.
    def _needs_rescore(url):
        entry = cache.get(url)
        if entry is None:
            return True
        if SCORE_LONG_ROLES and not entry.get("role_long"):
            return True
        return False
    todo = [j for j in jobs if j["url"] and _needs_rescore(j["url"])]
    for j in jobs:
        cached = cache.get(j["url"])
        if cached:
            j["score"] = cached.get("score", 0)
            j["score_reason"] = cached.get("reason", "")
            j["role_long"] = cached.get("role_long", "")
    if not todo:
        return

    client = None
    if SCORER == "claude":
        if not HAS_ANTHROPIC:
            sys.stdout.write("[score] anthropic SDK missing. pip install anthropic\n")
            return
        if not os.environ.get("ANTHROPIC_API_KEY"):
            err("[score] ANTHROPIC_API_KEY not set")
            return
        client = anthropic.Anthropic()

    def _score(batch):
        if SCORER == "claude":
            return _score_batch_claude(batch, profile, client)
        if SCORER == "ollama":
            return _score_batch_ollama(batch, profile)
        return {}

    def _score_safely(batch):
        """Score a batch; on exception split in half, on partial result retry
        the missing jobs individually."""
        try:
            results = _score(batch)
        except Exception as e:
            if len(batch) <= 1:
                err(f"[score] gave up on 1 job ({batch[0]['url']}): {e}")
                return {}
            err(f"[score] batch of {len(batch)} failed ({e}); splitting")
            mid = len(batch) // 2
            return {**_score_safely(batch[:mid]), **_score_safely(batch[mid:])}
        missing = [j for j in batch if j["url"] not in results]
        if 0 < len(missing) < len(batch):
            # qwen often returns 1 object instead of an array; retry the rest 1 by 1.
            for j in missing:
                more = _score_safely([j])
                results.update(more)
        return results

    batches = [todo[i:i + SCORE_BATCH_SIZE] for i in range(0, len(todo), SCORE_BATCH_SIZE)]
    n_batches = len(batches)
    total_seen = len(jobs)
    miss_ratio = len(todo) / max(1, total_seen)
    header = (
        f"[score] {SCORER}: {len(todo)} jobs / {n_batches} batches "
        f"(parallel={SCORE_PARALLEL}) — {miss_ratio:.0%} cache miss"
    )
    # Threshold: if we're re-scoring more than half the jobs, that's expensive
    # and probably means the cache was invalidated.
    if total_seen >= 20 and miss_ratio >= 0.5:
        warn(header)
    else:
        sys.stdout.write(header + "\n")
    cache_lock = threading.Lock()
    completed = [0]

    def _process(batch, idx):
        results = _score_safely(batch)
        with cache_lock:
            new_entries = False
            for j in batch:
                r = results.get(j["url"])
                if r:
                    j["score"] = r["score"]
                    j["score_reason"] = r["reason"]
                    j["role_long"] = r.get("role_long", "")
                    cache[j["url"]] = r
                    new_entries = True
            completed[0] += 1
            got = sum(1 for j in batch if j["url"] in results)
            sys.stdout.write(
                f"[score] batch {completed[0]}/{n_batches}: {got}/{len(batch)} scored\n"
            )
            # Incremental save every 5 batches (or every batch if serial) so
            # Ctrl-C doesn't lose everything.
            if new_entries and completed[0] % max(1, SCORE_PARALLEL) == 0:
                _save_score_cache(cache)

    # Long-role responses need ~2x more compute per request; halve the
    # concurrency to avoid Ollama backpressure and per-request timeouts.
    parallel = max(1, SCORE_PARALLEL // 2) if SCORE_LONG_ROLES else SCORE_PARALLEL
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as ex:
            for i, batch in enumerate(batches):
                ex.submit(_process, batch, i)
    finally:
        _save_score_cache(cache)


_LOC_SPLIT_RE = re.compile(r"\s*[;|]\s*")

# "CH - Geneva", "FR, Paris", "GB - London" → strip the country-code prefix.
# Accept both dash and comma separators.
_CC_PREFIX_RE = re.compile(
    r"^([A-Z]{2}|[A-Z]{3})\s*[-–—:,]\s*",
    re.IGNORECASE,
)

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
_PLUS_MORE_RE = re.compile(r"\s*\+\s*\d+\s*more\s*$", re.IGNORECASE)

# City aliases used to collapse "NYC", "New York City", "New York" to one entry.
_CITY_ALIASES = {
    "nyc": "new york",
    "new york city": "new york",
    "new york, ny": "new york",
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
    "united states", "usa", "us", "u.s.", "u.s.a.",
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
    return True


_TRAILING_REMOTE_RE = re.compile(
    r"\s*[\(\[]?\s*remote\s*[\)\]]?\s*$",
    re.IGNORECASE,
)


def _clean_loc(part):
    """Strip UI artifacts like ' + N more' suffixes and work-mode prefixes
    (Hybrid, Remote, Onsite …)."""
    s = _PLUS_MORE_RE.sub("", part).strip()
    s = _WORK_MODE_PREFIX_RE.sub("", s).strip()
    # "(Baltimore, MD)" → "Baltimore, MD"
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    # "Austria (Remote)" / "Denmark(Remote)" / "Canada remote" → strip suffix.
    # We keep the country so the entry is grouped correctly; anything without
    # a country is left alone (the Remote group will still catch it).
    stripped = _TRAILING_REMOTE_RE.sub("", s).strip()
    if stripped and stripped.lower() != s.lower():
        # Only apply if what's left looks like a real place.
        if _looks_like_location(stripped):
            s = stripped
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
    segments = [s.strip() for s in cleaned.split(",") if s.strip()]
    if not segments:
        return "", "", cleaned
    if len(segments) == 1:
        s = segments[0]
        if s.lower() in _KNOWN_COUNTRIES:
            c = _normalize_country(s)
            return c, c, c
        # Known city → pin to its country and canonicalize the display name.
        s_key = _city_key(s)
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
    return [best[k][1] for k in order]


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


def is_location_blacklisted(job):
    if not LOCATION_BLACKLIST or not job["locations"]:
        return False
    bl = [b.lower() for b in LOCATION_BLACKLIST]
    return all(any(b in loc.lower() for b in bl) for loc in job["locations"])


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
    raw_jobs = result["jobs"]
    for j in raw_jobs:
        j["locations"] = _flatten_locations(j.get("locations"))
    jobs = [
        j for j in raw_jobs
        if not is_title_blacklisted(j) and not is_location_blacklisted(j)
    ]
    jobs = dedup_by_url(jobs)
    jobs.sort(key=lambda j: j["title"].lower())
    final = {"jobs": jobs, "spontaneous_url": result.get("spontaneous_url")}
    if source_kind == "fresh":
        _save_list_cache(source, {"jobs": raw_jobs, "spontaneous_url": result.get("spontaneous_url")})
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


def render_html_section(name, visible, rejected_count, board_url, spontaneous_url, liked, queries, rejected_jobs=None, to_apply=None, applied=None):
    to_apply = to_apply or set()
    applied = applied or set()
    sid = slug(name)
    def _state_rank(u):
        # Lower rank = higher on the page.
        if u in applied:  return 0
        if u in to_apply: return 1
        if u in liked:    return 2
        return 3
    ordered = sorted(
        visible,
        key=lambda j: (
            _state_rank(j["url"]),
            0 if j.get("is_new") else 1,
            -int(j.get("score") or 0),
            _seniority_rank(detect_seniority(j["title"])),
            j["title"].lower(),
        ),
    )
    items = []
    for j in ordered:
        title_html = highlight_title(j["title"])
        title_attr = html.escape(j["title"], quote=True)
        locs_txt = ", ".join(j["locations"]) if j["locations"] else "N/A"
        locs = html.escape(locs_txt)
        locs_attr = html.escape(locs_txt, quote=True)
        url = j["url"]
        url_esc = html.escape(url, quote=True)
        seniority = detect_seniority(j["title"]) or ""
        seniority_attr = html.escape(seniority, quote=True)
        seniority_html = (
            f'<span class="badge seniority">{html.escape(seniority)}</span>' if seniority else ""
        )
        role_long = j.get("role_long") or ""
        # IC/L/E/M level from the LLM's role_long output first (which quotes
        # the compensation table verbatim), then the raw description as backup.
        ic_level = detect_ic_level(role_long, j.get("description", ""))
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
        # takes precedence over "Codex" alone when both would match.
        highlight_hits = []
        _search_blob = " ".join([
            j.get("title") or "", j.get("description") or "", role_long,
        ])
        for kw in sorted(HIGHLIGHTS, key=lambda s: -len(s)):
            if re.search(rf"\b{re.escape(kw)}\b", _search_blob, re.I):
                highlight_hits.append(kw)
        highlight_html = "".join(
            f'<span class="badge highlight-badge" title="Match on '
            f'{html.escape(kw, quote=True)}">{html.escape(kw)}</span>'
            for kw in highlight_hits
        )
        score = j.get("score")
        score_reason = j.get("score_reason") or ""
        if score is not None:
            score_cls = "score-hi" if score >= 8 else "score-mid" if score >= 5 else "score-lo"
            score_html = (
                f'<span class="badge score {score_cls}" '
                f'title="{html.escape(score_reason, quote=True)}">'
                f'{int(score)}</span>'
            )
            summary_parts = []
            if role_long:
                summary_parts.append(
                    f'<div class="role-summary"><strong>Role</strong>'
                    f'<div class="role-long">{_render_role_long(role_long)}</div>'
                    f'</div>'
                )
            if score_reason:
                summary_parts.append(
                    f'<div class="score-summary {score_cls}"><strong>Score</strong> '
                    f'<span>{html.escape(score_reason)}</span></div>'
                )
            score_summary_html = "".join(summary_parts)
        else:
            score_html = ""
            score_summary_html = ""
        desc = sanitize_html(j["description"])
        desc_html = desc if desc else '<em>No description available.</em>'
        is_liked = url in liked
        is_toapply = url in to_apply
        is_applied = url in applied
        like_state = "on" if is_liked else "off"
        like_btn = (
            f'<button class="like" data-url="{url_esc}" data-state="{like_state}" title="Like">+1</button>'
            if url else ""
        )
        reject_btn = (
            f'<button class="reject" data-url="{url_esc}" title="Reject">×</button>'
            if url else ""
        )
        # "To apply" button: only shown when the job is +1 or already in a
        # later state. Click toggles the to-apply flag. Applied jobs still
        # show it (in case user wants to demote back).
        toapply_state = "on" if is_toapply else "off"
        toapply_btn = (
            f'<button class="toapply" data-url="{url_esc}" data-state="{toapply_state}" '
            f'title="Mark as To apply">TA</button>'
            if url and (is_liked or is_toapply or is_applied) else ""
        )
        # "Applied" button: only shown once the job is at least in To apply.
        applied_state = "on" if is_applied else "off"
        applied_btn = (
            f'<button class="applied" data-url="{url_esc}" data-state="{applied_state}" '
            f'title="Mark as Applied">✓</button>'
            if url and (is_toapply or is_applied) else ""
        )
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
        # Highest state wins for the <li> visual class (used to move to top).
        state_class = ""
        if is_applied:
            state_class = "applied"
        elif is_toapply:
            state_class = "toapply"
        elif is_liked:
            state_class = "liked"
        li_class = ("job " + state_class).strip()
        items.append(
            f'    <li class="{li_class}" data-seniority="{seniority_attr}" '
            f'data-locations="{locs_attr}">'
            f'{reject_btn}{like_btn}{toapply_btn}{applied_btn}<details>\n'
            f'      <summary title="{title_attr} — {locs_attr}">'
            f'{score_html}'
            f'<span class="title">{title_html}</span>'
            f'{new_html}{orphan_html}{seniority_html}{ic_html}{highlight_html}'
            f'{summary_link}'
            f'<span class="locs"> — {locs}</span>'
            f'</summary>\n'
            f'      <div class="description">\n'
            f'        <div class="desc-actions">{open_link}</div>\n'
            f'        <div class="desc-body">{desc_html}</div>\n'
            f'      </div>\n'
            f'    </details>{score_summary_html}</li>'
        )
    ul_content = "\n".join(items) if items else "    <li><em>none</em></li>"
    visible_count = len(visible)
    counter = (
        f'<span class="counter">'
        f'<span class="v">{visible_count}</span> visible · '
        f'<span class="r">{rejected_count}</span> rejected'
        f'</span>'
    )
    board_link = (
        f'<a class="board-link" href="{html.escape(board_url, quote=True)}" '
        f'target="_blank" rel="noopener">{html.escape(name)}</a>'
        if board_url else html.escape(name)
    )
    spontaneous = (
        f'<a class="spontaneous-link" href="{html.escape(spontaneous_url, quote=True)}" '
        f'target="_blank" rel="noopener" title="Spontaneous application">'
        f'✉ Spontaneous</a>'
        if spontaneous_url else ""
    )
    query_pills = ""
    if queries:
        pills = "".join(
            f'<span class="query-pill">{html.escape(q)}</span>' for q in queries
        )
        query_pills = f'<span class="queries" title="Board-side search queries">{pills}</span>'
    spontaneous_row = f'  <div class="spontaneous-row">{spontaneous}</div>\n' if spontaneous else ""

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
            rej_items.append(
                f'      <li class="rejected-job">'
                f'<button class="restore" data-url="{url_esc}" title="Restore">↩</button>'
                f'<a href="{url_esc}" target="_blank" rel="noopener">{title_esc}</a>'
                f'<span class="locs"> — {locs_esc}</span></li>'
            )
        rejected_block = (
            f'  <details class="rejected-block" data-section="{sid}">\n'
            f'    <summary>{len(rejected_jobs)} rejected in this section — click to expand</summary>\n'
            f'    <ul class="rejected-list">\n' + "\n".join(rej_items) + '\n'
            f'    </ul>\n'
            f'  </details>\n'
        )

    return (
        f'  <section class="company-section" data-section="{sid}">\n'
        f'  <h1 id="{sid}">{board_link} {query_pills} {counter}</h1>\n'
        f'{spontaneous_row}'
        f'  <ul data-section="{sid}">\n{ul_content}\n  </ul>\n'
        f'{rejected_block}'
        f'  </section>'
    )


def render_html_nav(entries):
    """Groups nav buttons per GROUP_ORDER, with a labelled row per group."""
    by_group = {g: [] for g in GROUP_ORDER}
    for name, visible_count in entries:
        group = GROUP_OF.get(name, "Other")
        by_group.setdefault(group, []).append((name, visible_count))
    rows = []
    for group in GROUP_ORDER + [g for g in by_group if g not in GROUP_ORDER]:
        items = by_group.get(group) or []
        if not items:
            continue
        items.sort(key=lambda kv: kv[0].lower())
        buttons = "".join(
            f'<a class="nav-btn {"has-jobs" if visible_count > 0 else "no-jobs"}" '
            f'href="#{slug(name)}">{html.escape(name)} '
            f'(<span class="nav-count">{visible_count}</span>)</a>'
            for name, visible_count in items
        )
        rows.append(
            '    <div class="nav-row">'
            f'<span class="nav-group-label">{html.escape(group)}</span>'
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
            f'<span class="loc-country">{html.escape(country)}</span>{checks}</div>'
        )
    return (
        '      <div class="loc-panel">\n'
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
    found = set(seniority_labels)
    blocks = []
    for group_name, group_labels in SENIORITY_GROUPS:
        items = [_seniority_check(l) for l in group_labels if l in found]
        if not items:
            continue
        blocks.append(
            '    <div class="filter-group">\n'
            f'      <span class="filter-label">{html.escape(group_name)}:</span>\n'
            + "\n".join(items) + "\n"
            '    </div>'
        )
    known = {l for _, g in SENIORITY_GROUPS for l in g}
    other = [l for l in seniority_labels if l not in known]
    if other:
        items = [_seniority_check(l) for l in other]
        blocks.append(
            '    <div class="filter-group">\n'
            '      <span class="filter-label">Other:</span>\n'
            + "\n".join(items) + "\n"
            '    </div>'
        )
    return (
        '  <section class="filters">\n'
        + "\n".join(blocks) + "\n"
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
        '      <label class="filter-check"><input type="checkbox" id="highlight-toggle" checked> Highlight</label>\n'
        '      <label class="filter-check"><input type="checkbox" id="role-summary-toggle" checked> Show role details</label>\n'
        '      <label class="filter-check"><input type="checkbox" id="score-summary-toggle" checked> Show score reason</label>\n'
        '      <label class="filter-check"><input type="checkbox" id="hide-empty-toggle"> Hide sections with no matching jobs</label>\n'
        '    </div>\n'
        '  </section>'
    )


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Jobs</title>
  <style>
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
    html { scroll-behavior: smooth; }
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
    }
    .spontaneous-row { margin: 0.4rem 0 0.8rem; }
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
    .nav-btn.no-jobs {
      color: var(--fg-muted);
      opacity: 0.7;
    }
    .nav-count { font-weight: 600; }
    .nav-btn.has-jobs .nav-count { color: var(--success); }
    .nav-btn.no-jobs .nav-count { color: var(--fg-muted); }
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
    .filter-label { color: var(--fg-muted); font-weight: 700; }
    .filter-check { display: flex; align-items: center; gap: 0.3rem; cursor: pointer; }
    .filter-check input { accent-color: var(--accent-emphasis); }
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
    .loc-group {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.4rem 0.8rem;
      padding: 0.3rem 0;
      border-bottom: 1px dashed var(--border-muted);
    }
    .loc-group:last-child { border-bottom: none; }
    .loc-country {
      font-weight: 700;
      color: var(--severe);
      min-width: 8rem;
      font-size: 0.85rem;
    }
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
    li.liked .reject { display: none; }

    /* To apply — red pill, "TA" glyph */
    .toapply {
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
    .toapply:hover { background: var(--danger); color: #ffffff; border-color: var(--danger-emphasis); }
    .toapply[data-state="on"] { background: var(--danger); color: #ffffff; }
    li.toapply {
      background: rgba(209, 36, 47, 0.10);
      border-left: 3px solid var(--danger);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    li.toapply .reject { display: none; }

    /* Applied — purple pill, "✓" glyph */
    .applied {
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
    .applied:hover { background: #8250df; color: #ffffff; border-color: #6639ba; }
    .applied[data-state="on"] { background: #8250df; color: #ffffff; }
    li.applied {
      background: rgba(130, 80, 223, 0.10);
      border-left: 3px solid #8250df;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    li.applied .reject { display: none; }

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
    body.hide-empty-sections .company-section.empty { display: none; }

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
const SERVER_URL = '__SERVER_URL__';

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

/* --- Persistence: filter state survives page refreshes ----------------- */
const STORAGE_KEY = 'jobs:filters:v1';

function saveFilters() {
  const state = {
    seniorityOff: [...document.querySelectorAll('.seniority-toggle')]
      .filter(cb => !cb.checked)
      .map(cb => cb.dataset.seniority),
    locChecks: [...document.querySelectorAll('.loc-cb:checked')]
      .map(cb => cb.dataset.value),
    loc:   (document.getElementById('loc-filter')?.value)   || '',
    title: (document.getElementById('title-filter')?.value) || '',
    text:  (document.getElementById('text-filter')?.value)  || '',
    highlight: document.getElementById('highlight-toggle')?.checked ?? true,
    scoreSummary: document.getElementById('score-summary-toggle')?.checked ?? true,
    roleSummary: document.getElementById('role-summary-toggle')?.checked ?? true,
    hideEmpty: document.getElementById('hide-empty-toggle')?.checked ?? false,
  };
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) {}
}

function loadFilters() {
  let s;
  try { s = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch (e) { s = null; }
  if (!s) return;
  const off = new Set(s.seniorityOff || []);
  document.querySelectorAll('.seniority-toggle').forEach(cb => {
    cb.checked = !off.has(cb.dataset.seniority);
  });
  const loc = new Set(s.locChecks || []);
  document.querySelectorAll('.loc-cb').forEach(cb => {
    cb.checked = loc.has(cb.dataset.value);
  });
  const li = document.getElementById('loc-filter');   if (li) li.value = s.loc   || '';
  const ti = document.getElementById('title-filter'); if (ti) ti.value = s.title || '';
  const tx = document.getElementById('text-filter');  if (tx) tx.value = s.text  || '';
  const hl = document.getElementById('highlight-toggle');
  if (hl && s.highlight === false) {
    hl.checked = false;
    document.body.classList.add('no-highlights');
  }
  const ss = document.getElementById('score-summary-toggle');
  if (ss && s.scoreSummary === false) {
    ss.checked = false;
    document.body.classList.add('hide-score-summary');
  }
  const rs = document.getElementById('role-summary-toggle');
  if (rs && s.roleSummary === false) {
    rs.checked = false;
    document.body.classList.add('hide-role-summary');
  }
  const he = document.getElementById('hide-empty-toggle');
  if (he && s.hideEmpty === true) {
    he.checked = true;
    document.body.classList.add('hide-empty-sections');
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
  const seniorityOff = new Set();
  document.querySelectorAll('.seniority-toggle').forEach(cb => {
    if (!cb.checked) seniorityOff.add(cb.dataset.seniority.toLowerCase());
  });
  const locQ   = parseQuery('loc-filter');
  const titleQ = parseQuery('title-filter');
  const textQ  = parseQuery('text-filter');

  document.querySelectorAll('li[data-seniority]').forEach(li => {
    let hide = false;
    const sen = ((li.dataset.seniority || '').trim() || 'None').toLowerCase();
    if (seniorityOff.has(sen)) hide = true;
    if (!hide && locQ.length) {
      if (!matchQuery((li.dataset.locations || '').toLowerCase(), locQ)) hide = true;
    }
    if (!hide && titleQ.length) {
      if (!matchQuery((li.querySelector('.title')?.textContent || '').toLowerCase(), titleQ)) hide = true;
    }
    if (!hide && textQ.length) {
      if (!matchQuery((li.querySelector('.desc-body')?.textContent || '').toLowerCase(), textQ)) hide = true;
    }
    li.classList.toggle('hidden', hide);
  });
  let total = 0;
  document.querySelectorAll('ul[data-section]').forEach(ul => {
    const sid = ul.dataset.section;
    const visible = ul.querySelectorAll('li.job:not(.hidden)').length;
    total += visible;
    const navCount = document.querySelector('.nav-btn[href="#' + sid + '"] .nav-count');
    if (navCount) {
      navCount.textContent = visible;
      const btn = navCount.closest('.nav-btn');
      if (btn) {
        btn.classList.toggle('has-jobs', visible > 0);
        btn.classList.toggle('no-jobs',  visible === 0);
      }
    }
    const v = document.querySelector('#' + sid + ' .counter .v');
    if (v) v.textContent = visible;
    // Mark the parent .company-section empty when there's nothing visible.
    const section = ul.closest('.company-section');
    if (section) section.classList.toggle('empty', visible === 0);
  });
  const totalEl = document.getElementById('total-count');
  if (totalEl) totalEl.textContent = total;
  // Hide a nav-row (category label + all its company buttons) when every
  // button inside it has zero visible jobs. Runs after per-btn counts are
  // updated above so we react to filters, not just the initial render.
  document.querySelectorAll('.nav-row').forEach(row => {
    const btns = row.querySelectorAll('.nav-btn');
    const anyHit = [...btns].some(b => b.classList.contains('has-jobs'));
    row.classList.toggle('empty', btns.length > 0 && !anyHit);
  });
  saveFilters();
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
document.getElementById('open-selected-sh')?.addEventListener('click', async () => {
  const urls = collectUrls('li.job.liked:not(.hidden), li.job.toapply:not(.hidden), li.job.applied:not(.hidden)');
  const status = document.getElementById('dump-status');
  if (!urls.length) { status.textContent = 'No +1 jobs visible.'; setTimeout(() => status.textContent = '', 3000); return; }
  const script = buildOpenSelectedScript(urls);
  try {
    const base = location.protocol === 'file:' ? SERVER_URL : '';
    const res = await fetch(base + '/save-open-selected', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({script})
    });
    if (!res.ok) throw new Error('http ' + res.status);
    status.textContent = 'Wrote debug/open_selected.sh (' + urls.length + ' URLs) — run: bash debug/open_selected.sh';
  } catch (e) {
    status.textContent = 'Save failed (' + e.message + ') — falling back to clipboard.';
    copyToClipboard(script, status, 'Copied open script (' + urls.length + ' URLs) — paste into debug/open_selected.sh');
    return;
  }
  setTimeout(() => { status.textContent = ''; }, 5000);
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

const hlToggle = document.getElementById('highlight-toggle');
if (hlToggle) {
  hlToggle.addEventListener('change', () => {
    document.body.classList.toggle('no-highlights', !hlToggle.checked);
    saveFilters();
  });
}

const ssToggle = document.getElementById('score-summary-toggle');
if (ssToggle) {
  ssToggle.addEventListener('change', () => {
    document.body.classList.toggle('hide-score-summary', !ssToggle.checked);
    saveFilters();
  });
}

const rsToggle = document.getElementById('role-summary-toggle');
if (rsToggle) {
  rsToggle.addEventListener('change', () => {
    document.body.classList.toggle('hide-role-summary', !rsToggle.checked);
    saveFilters();
  });
}

const heToggle = document.getElementById('hide-empty-toggle');
if (heToggle) {
  heToggle.addEventListener('change', () => {
    document.body.classList.toggle('hide-empty-sections', heToggle.checked);
    applyFilters();  // recompute .empty markers below
    saveFilters();
  });
}

/* --- Like -------------------------------------------------------------- */
async function apiPost(path, url) {
  const base = location.protocol === 'file:' ? SERVER_URL : '';
  const res = await fetch(base + path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({url})
  });
  if (!res.ok) throw new Error('http ' + res.status);
}

/* --- Like / To apply / Applied state machine -------------------------- */
// Highest-priority active class on <li>. The trio is mutually exclusive
// from a visual standpoint (li can only be in one bucket) but the
// underlying stores are independent so we don't lose state when demoting.
function refreshLiState(li) {
  li.classList.remove('liked', 'toapply', 'applied');
  const likeOn = li.querySelector('.like')?.dataset.state === 'on';
  const taOn   = li.querySelector('.toapply')?.dataset.state === 'on';
  const apOn   = li.querySelector('.applied')?.dataset.state === 'on';
  if (apOn)      li.classList.add('applied');
  else if (taOn) li.classList.add('toapply');
  else if (likeOn) li.classList.add('liked');
}

// Insert a button into the action bar (right after existing .reject/.like)
// if it isn't already there. Reused when a job becomes liked/toapply and
// the server hadn't rendered the follow-up buttons.
function ensureStateButton(li, cls, glyph, title) {
  if (li.querySelector('.' + cls)) return li.querySelector('.' + cls);
  const url = li.querySelector('.like')?.dataset.url
    || li.querySelector('.reject')?.dataset.url;
  if (!url) return null;
  const btn = document.createElement('button');
  btn.className = cls;
  btn.dataset.url = url;
  btn.dataset.state = 'off';
  btn.title = title;
  btn.textContent = glyph;
  wireStateButton(btn, cls);
  // Insert after the .like button (or after .reject if no .like).
  const anchor = li.querySelector('.like') || li.querySelector('.reject');
  const details = li.querySelector('details');
  if (anchor) anchor.after(btn);
  else if (details) li.insertBefore(btn, details);
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
    const on = btn.dataset.state === 'on';
    btn.disabled = true;
    try {
      await apiPost(on ? endpoints[1] : endpoints[0], url);
      btn.dataset.state = on ? 'off' : 'on';
      // When you turn something ON, expose the next state's button too.
      if (!on && cls === 'like') {
        ensureStateButton(li, 'toapply', 'TA', 'Mark as To apply');
      }
      if (!on && cls === 'toapply') {
        ensureStateButton(li, 'applied', '\u2713', 'Mark as Applied');
      }
      refreshLiState(li);
      moveLiToTop(li);
    } catch (err) {
      alert(cls + ' toggle failed: ' + err.message);
    } finally {
      btn.disabled = false;
    }
  });
}

document.querySelectorAll('.like').forEach(btn => wireStateButton(btn, 'like'));
document.querySelectorAll('.toapply').forEach(btn => wireStateButton(btn, 'toapply'));
document.querySelectorAll('.applied').forEach(btn => wireStateButton(btn, 'applied'));

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
      btn.classList.toggle('has-jobs', newVal > 0);
      btn.classList.toggle('no-jobs',  newVal === 0);
    }
  }
  const totalEl = document.getElementById('total-count');
  if (totalEl) totalEl.textContent = parseInt(totalEl.textContent) + deltaVisible;
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
  try {
    await apiPost('/unreject', last.url);
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
  updateCounters(last.sid, +1, -1);
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
      if (ul.querySelectorAll('li').length === 0) {
        ul.insertAdjacentHTML('beforeend', '    <li><em>none</em></li>');
      }
      showUndoToast();
    } catch (err) {
      btn.disabled = false;
      li.style.opacity = '1';
      alert('Reject failed: ' + err.message);
    }
  });
});

// Keyboard shortcut: Cmd/Ctrl-Z anywhere on the page.
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'z' && rejectUndoStack.length > 0) {
    e.preventDefault();
    undoLastReject();
  }
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
      // Note: the restored job won't appear in the visible list until the
      // page is refreshed / re-fetched, because we don't have the fresh
      // job data client-side. Show a small note.
      alert('Restored. Refresh the page (or re-run jobs.py) to see it back in the main list.');
    } catch (err) {
      btn.disabled = false;
      li.style.opacity = '1';
      alert('Restore failed: ' + err.message);
    }
  });
});
</script>
</body>
</html>
"""


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
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path not in (
            "/reject", "/unreject",
            "/like", "/unlike",
            "/toapply", "/untoapply",
            "/applied", "/unapplied",
            "/save-probe", "/save-open-selected",
        ):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length))
        except Exception:
            payload = {}
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
            if not script:
                self.send_response(400); self._cors(); self.end_headers(); return
            try:
                os.makedirs("debug", exist_ok=True)
                path = os.path.join("debug", "open_selected.sh")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(script)
                os.chmod(path, 0o755)
                sys.stdout.write(f"open-sel: wrote {path} ({len(script)} bytes)\n")
            except Exception as e:
                sys.stdout.write(f"open-sel: save failed: {e}\n")
                self.send_response(500); self._cors(); self.end_headers(); return
            self.send_response(204); self._cors(); self.end_headers(); return
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
            s = load_applied(); s.add(url); save_applied(s)
            sys.stdout.write(f"applied:  {url}\n")
        elif self.path == "/unapplied":
            s = load_applied(); s.discard(url); save_applied(s)
            sys.stdout.write(f"un-appl:  {url}\n")
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
            "  python3 jobs.py --skip-scoring               # fetch only, no LLM\n"
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
    ap.add_argument("--skip-scoring", action="store_true",
                    help="Don't call the LLM for scoring (uses cached scores only).")
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
    ap.add_argument("--list", action="store_true",
                    help="Print every configured board name (comma-separated) and exit.")
    return ap.parse_args()


def main():
    args = _parse_cli()

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
    skip_score = args.skip_scoring    or os.environ.get("JOBS_SKIP_SCORING") == "1"
    pw_kinds = {"apple", "google", "microsoft", "meta", "phenom", "scale", "github", "checkmarx", "pixee", "ableton", "lucca", "pw", "wttj"}
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
    seen = load_seen()
    job_index = load_job_index()
    # Loaded once and reused when building orphan job dicts — see the
    # per-source render loop below. Kept separate from the live scoring path.
    _score_cache_for_orphans = _load_score_cache()
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
                results[src["name"]] = {"jobs": [], "spontaneous_url": None}
    t_fetch = time.perf_counter() - t_fetch_start
    timing(f"[timing] fetch (all sources, parallel) → {t_fetch:.1f}s")

    print("=" * 70, file=sys.stdout)
    print("Step 2 — score: send visible jobs to the LLM (per PROFILE.md rubric),", file=sys.stdout)
    print("               batched with cache-hits reused from score_cache.json", file=sys.stdout)
    print("=" * 70, file=sys.stdout)
    t_score_start = time.perf_counter()
    all_visible_for_score = []
    for src in active_sources:
        result = results[src["name"]]
        all_visible_for_score.extend(
            j for j in result["jobs"] if j["url"] not in rejected
        )
    if not skip_score:
        score_jobs(all_visible_for_score)
    else:
        timing("[timing] scoring SKIPPED (JOBS_SKIP_SCORING=1)")
    t_score = time.perf_counter() - t_score_start
    timing(f"[timing] score ({len(all_visible_for_score)} jobs) → {t_score:.1f}s")

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
        for j in all_jobs:
            u = j["url"]
            j["is_new"] = u not in seen and u not in liked and u not in rejected
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
        cared = (liked | to_apply | applied)
        orphan_urls = [
            u for u in cared
            if u not in fresh_urls
            and u not in rejected
            and job_index.get(u, {}).get("source") == src["name"]
        ]
        orphans = []
        for u in orphan_urls:
            meta = job_index.get(u, {})
            score_entry = _score_cache_for_orphans.get(u, {})
            orphans.append({
                "title": meta.get("title", "(unknown)"),
                "locations": meta.get("locations") or [],
                "url": u,
                "description": "<em>Original posting has been removed from this board. Cached score / role data may be shown below.</em>",
                "score": score_entry.get("score"),
                "score_reason": score_entry.get("reason", ""),
                "role_long": score_entry.get("role_long", ""),
                "is_new": False,
                "is_orphan": True,
            })
        visible = orphans + [j for j in all_jobs if j["url"] not in rejected]
        rejected_jobs = [j for j in all_jobs if j["url"] in rejected]
        # rejected_here = count of jobs from this run's fetch that were rejected.
        # Orphans don't count as rejected (they're just gone from the board).
        rejected_here = len(rejected_jobs)
        html_sections.append(render_html_section(
            src["name"], visible, rejected_here,
            board_url_for(src), result.get("spontaneous_url"),
            liked, src.get("queries", []),
            rejected_jobs=rejected_jobs,
            to_apply=to_apply, applied=applied,
        ))
        nav_entries.append((src["name"], len(visible)))
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
    # dedup while preserving order
    seen = set()
    seniority_labels = [l for l in seniority_labels if not (l in seen or seen.add(l))]
    if has_none:
        seniority_labels.append("None")

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
    total_bar = (
        f'  <div class="top-bar">\n'
        f'    <div class="total-count">Total: '
        f'<span id="total-count">{total}</span> jobs visible</div>\n'
        f'    <button type="button" class="dump-btn" id="dump-all" title="Copy every visible job URL to the clipboard, one per line">Dump all</button>\n'
        f'    <button type="button" class="dump-btn" id="dump-selected" title="Copy the URLs of jobs you +1&#39;d (still visible), one per line">Dump selected</button>\n'
        f'    <button type="button" class="dump-btn" id="dump-sh" title="Save a Python+Playwright script to debug/probe_visible.py that renders each visible URL in real Chromium and flags the broken ones">Save probe .py for debugging links</button>\n'
        f'    <button type="button" class="dump-btn" id="open-selected-sh" title="Save a bash script to debug/open_selected.sh that opens every +1 URL in your default browser">Open selected in .sh</button>\n'
        f'    <span class="dump-status" id="dump-status" aria-live="polite"></span>\n'
        f'  </div>'
    )
    html_body = (
        total_bar + "\n"
        + render_html_nav(nav_entries) + "\n"
        + render_html_filters(seniority_labels, all_locations) + "\n"
        + "\n".join(html_sections)
    )
    html_output = (
        HTML_TEMPLATE
        .replace("__BODY__", html_body)
        .replace("__SERVER_URL__", server_url)
        .replace("__HIGHLIGHTS__", json.dumps(HIGHLIGHTS))
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

    print("=" * 70, file=sys.stdout)
    print("Step 4 — serve: local HTTP server + auto-open browser; handles", file=sys.stdout)
    print("               POST /reject and POST /like for live persistence", file=sys.stdout)
    print("=" * 70, file=sys.stdout)
    server = http.server.ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    print(f"serving on {server_url} — Ctrl-C to stop", file=sys.stdout)
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(server_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("bye", file=sys.stdout)


if __name__ == "__main__":
    main()
