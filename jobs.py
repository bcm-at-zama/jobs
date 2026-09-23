#!/usr/bin/env python3
"""
jobs.py — aggregate job postings from multiple career boards into a single
HTML page with reject/persistence and client-side filters.

Everything you may want to tweak lives in the CONFIG section below.
"""

# =============================================================================
# CONFIG — tweak these
# =============================================================================

OUTPUT_HTML = "jobs.html"
REJECTED_DB = "rejected.json"
LIKED_DB = "liked.json"
PROFILE_FILE = "PROFILE.md"
SCORE_CACHE = "score_cache.json"

SERVE_HOST = "127.0.0.1"
SERVE_PORT = 8765

# Scoring backend for ranking jobs against PROFILE.md.
#   "claude" — Anthropic API (needs ANTHROPIC_API_KEY env var, `pip install anthropic`).
#   "ollama" — local Ollama server at OLLAMA_URL.
#   "none"   — disable scoring.
SCORER = "ollama"
CLAUDE_MODEL = "claude-sonnet-4-6"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:7b"
SCORE_BATCH_SIZE = 20
SCORE_DESC_CHARS = 800

# Words highlighted in titles and descriptions (case-insensitive).
HIGHLIGHTS = ["Security", "Manager", "Codex", "Codemender", "Cyber", "SEAR", "DeepMind", "Researcher"]

# When titles are derived from a URL slug (Apple, Google, Ableton, …), each
# dash-separated word is capitalized. Keys here override the default
# .capitalize() to preserve custom casing (compared case-insensitively).
TITLE_CASE_OVERRIDES = {
    "sear": "SEAR",
    "ios": "iOS",
    "ipad": "iPad",
    "iphone": "iPhone",
    "macos": "macOS",
    "watchos": "watchOS",
    "tvos": "tvOS",
    "visionos": "visionOS",
    "ai": "AI",
    "ml": "ML",
    "llm": "LLM",
    "api": "API",
    "sdk": "SDK",
    "ui": "UI",
    "ux": "UX",
    "os": "OS",
    "gpu": "GPU",
    "cpu": "CPU",
    "ci": "CI",
    "cd": "CD",
    "sre": "SRE",
    "qa": "QA",
    "saas": "SaaS",
    "vp": "VP",
    "hr": "HR",
    "it": "IT",
    "grc": "GRC",
    "ssd": "SSD",
    "aiml": "AIML",
    "ciso": "CISO",
    "i": "I",
    "ii": "II",
    "iii": "III",
    "iv": "IV",
    "v": "V",
    "vi": "VI",
    "vii": "VII",
    "viii": "VIII",
    "ix": "IX",
    "x": "X",
}

# If any of these substrings appear in a job title (case-insensitive), the
# job is hidden.
TITLE_BLACKLIST = [
    "Data Scientist",
    "Developper Experience",
    "Developer Experience",
    "Federal",
    "GRC",
    "Forward",
    "Network Engineer",
    "Compliance",
    "Strategist",
    "Program Manager",
    "Product Manager",
    "Product Marketing Manager",
    "Security Operations Manager",
    "Growth",
    "Reliability",
    "Incident Manager",
    "Business Systems Analyst",
    "Hardware Platform Security Architect",
    "Platform Hardware Security",
    "Tech Events Manager",
    "Account Executive",
    "Business Development",
    "Forward Deployed Engineer",
    "GTM",
    "Technical Support Engineer",
    "Gotomarket",
    "Stage",
    "Product Designer",
    "Sales",
    "Marketing",
    "AV Engineer",
    "Partnership",
    "Talent",
    "ASIC Design",
    "SoC Security",
    "Revenue",
    "Commercial",
    "Logistics",
    "Intelligence",
    "Lawfull",
    "Lawful",
    "Legal",
    "Travel",
    "Intern",
]

# If ALL of a job's locations contain one of these substrings, the job is
# hidden. Example: ["Tokyo", "Bangalore"].
LOCATION_BLACKLIST = []

# Seniority filter groups shown in the filter bar. Order within groups also
# drives the "most senior jobs first" sort. Labels not listed here go last.
SENIORITY_GROUPS = [
    ("Management", ["VP", "Director", "Manager", "Head", "Lead"]),
    ("IC",         ["Senior Staff", "Staff", "Principal", "Senior"]),
]

# Flat ordered rank derived from SENIORITY_GROUPS + any extra label at the end.
SENIORITY_RANK = [lbl for _, group in SENIORITY_GROUPS for lbl in group] + [
    "Distinguished", "Associate", "Junior", "Intern",
]

# Seniority labels extracted from job title. First match wins, so put more
# specific keywords first.
SENIORITY = [
    ("Senior Staff", "Senior Staff"),
    ("Staff", "Staff"),
    ("Principal", "Principal"),
    ("Distinguished", "Distinguished"),
    ("Head of", "Head"),
    ("Director", "Director"),
    ("Vice President", "VP"),
    (" VP ", "VP"),
    ("Manager", "Manager"),
    ("Lead", "Lead"),
    ("Senior", "Senior"),
    ("Associate", "Associate"),
    ("Junior", "Junior"),
    ("Intern", "Intern"),
]

# One entry per company. `kind` picks the fetcher (see FETCHERS below).
# `queries` is the per-board search terms.
# Optional `board`: URL to that company's public job board (defaults auto-derived).
SOURCES = [
    {"name": "OpenAI",    "kind": "ashby",      "slug": "openai",     "queries": ["security", "codex"]},
    {"name": "Anthropic", "kind": "greenhouse", "slug": "anthropic",  "queries": ["security"]},
    {"name": "Mistral",   "kind": "ashby",      "slug": "mistral.ai", "queries": ["security"]},
    {"name": "Cohere",    "kind": "ashby",      "slug": "cohere",     "queries": ["security"]},
    {"name": "H",         "kind": "ashby",      "slug": "hcompany",   "queries": []},
    {"name": "AMI",       "kind": "ashby",      "slug": "ami",        "queries": []},
    {"name": "Apple",     "kind": "apple",      "slug": "apple",      "queries": ["security", "Logic"],
     "board": "https://jobs.apple.com/en-us/search?search=security"},
    {"name": "Microsoft", "kind": "microsoft",  "slug": "microsoft",  "queries": ["security"],
     "board": "https://apply.careers.microsoft.com/careers?query=Security&pid=1970393556942260&sort_by=relevance"},
    {"name": "Google",    "kind": "google",     "slug": "google",     "queries": ["security", "codemender", "DeepMind"],
     "board": "https://www.google.com/about/careers/applications/jobs/results/?q=security&hl=en_US",
     "search_url": "https://www.google.com/about/careers/applications/jobs/results?hl=en_US&target_level=DIRECTOR_PLUS&target_level=ADVANCED&employment_type=FULL_TIME"},
    {"name": "Ableton",    "kind": "ableton", "slug": "ableton",       "queries": [],
     "board": "https://www.ableton.com/en/jobs/"},
    {"name": "Arturia",    "kind": "lucca",   "slug": "arturia-france", "queries": [],
     "board": "https://jobs.world.luccasoftware.com/arturia-france"},
    {"name": "Neural DSP", "kind": "pw",      "slug": "neuraldsp",     "queries": [],
     "board": "https://careers.neuraldsp.com/",
     "search_url": "https://careers.neuraldsp.com/",
     "link_re": r'href="(https?://careers\.neuraldsp\.com/[^"#?]+|/(?:jobs|positions|openings)/[^"#?]+)"',
     "origin": "https://careers.neuraldsp.com"},
    {"name": "Steinberg",  "kind": "pw",      "slug": "steinberg",     "queries": [],
     "board": "https://www.steinberg.net/careers/vacancies/",
     "search_url": "https://www.steinberg.net/careers/vacancies/",
     "link_re": r'href="(https?://www\.steinberg\.net/careers/[^"#?]+|/careers/[^"#?/]+/[^"#?]+)"',
     "origin": "https://www.steinberg.net"},
    # TODO: need job board URLs for Native Instruments and Bitwig.
    # Paste their careers page URL and I'll wire them up.
]

# Title patterns marking a job as a "spontaneous application" entry
# (case-insensitive substring match).
SPONTANEOUS_PATTERNS = [
    "spontaneous",
    "speculative",
    "general application",
    "don't see the right role",
    "prospective application",
    "candidature spontan",
]

# Seniority filter toggles shown at the top of the page.
# Values must match labels produced by detect_seniority(). Default state is ON.
SENIORITY_TOGGLES = ["Manager", "Director"]

# =============================================================================
# END CONFIG
# =============================================================================

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
    escaped = html.escape(text)
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
        out.append({
            "title": j.get("title", ""),
            "locations": locs,
            "url": j.get("jobUrl") or j.get("applyUrl") or "",
            "description": desc_html or desc_plain,
            "blob": " ".join([j.get("title", ""), j.get("department", ""), j.get("team", "")]),
        })
    return out


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
    url = f"https://api.ashbyhq.com/posting-api/job-board/{source['slug']}"
    try:
        raw = http_get_json(url)
    except Exception as e:
        sys.stderr.write(f"[{source['name']}] Ashby fetch failed: {e}\n")
        return {"jobs": [], "spontaneous_url": None}
    all_jobs = normalize_ashby(raw)
    matched = [j for j in all_jobs if matches(j, source["queries"])]
    if not matched and all_jobs:
        sys.stderr.write(
            f"[{source['name']}] Ashby returned {len(all_jobs)} jobs but 0 matched "
            f"queries {source['queries']!r}. Set queries=[] to see them all.\n"
        )
    return {"jobs": matched, "spontaneous_url": _pick_spontaneous(all_jobs)}


def fetch_greenhouse(source):
    url = f"https://boards-api.greenhouse.io/v1/boards/{source['slug']}/jobs?content=true"
    try:
        raw = http_get_json(url)
    except Exception as e:
        sys.stderr.write(f"{source['name']} fetch failed: {e}\n")
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


def _open_browser():
    """Start Playwright + Chromium. Returns (playwright, browser, page)."""
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
    page = ctx.new_page()
    # Hide navigator.webdriver flag
    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
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


def _fetch_descriptions(page, jobs, source_name):
    n = len(jobs)
    if not n:
        return
    for i, j in enumerate(jobs, 1):
        j["description"] = _fetch_description_via_page(page, j.get("url", ""))
        if i % 10 == 0 or i == n:
            sys.stderr.write(f"[{source_name}] fetched {i}/{n} descriptions\n")


def _render(page, url, wait_selector=None, timeout=12000, debug_path=None):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception as e:
        sys.stderr.write(f"[render] {url} nav failed: {e}\n")
    selector_ok = False
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=5000)
            selector_ok = True
        except Exception:
            pass
    if not selector_ok:
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
    try:
        content = page.content()
    except Exception as e:
        sys.stderr.write(f"[render] content read failed: {e}\n")
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
        sys.stderr.write(
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
                debug = f"debug-apple-{q}-{pnum}.html" if pnum == 1 else None
                text = _render(page, url, wait_selector="a[href*='/details/']", debug_path=debug)
                from_json = _apple_extract_from_json(text)
                from_links = _apple_extract_from_links(text, source["queries"])
                jobs = from_json or from_links
                if pnum == 1:
                    sys.stderr.write(
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
        sys.stderr.write(
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
            for pnum in range(1, 11):
                url = base
                if q:
                    sep = "&" if "?" in url else "?"
                    url += f"{sep}q={urllib.parse.quote(q)}"
                sep = "&" if "?" in url else "?"
                url += f"{sep}page={pnum}"
                debug = f"debug-google-{q or 'nofilter'}-{pnum}.html" if pnum == 1 else None
                text = _render(page, url, wait_selector="a[href*='/jobs/results/']", debug_path=debug)
                ld = _google_extract_from_ld(text)
                urls = set(_GOOGLE_JOB_RE.findall(text))
                if pnum == 1:
                    sys.stderr.write(
                        f"[Google] q='{q}' rendered {len(text)}B, "
                        f"ld={len(ld)}, urls={len(urls)} "
                        f"(HTML dumped to {debug})\n"
                    )
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
        sys.stderr.write(
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
                debug = f"debug-microsoft-{q}-{pnum}.html" if pnum == 0 else None
                text = _render(
                    page, url,
                    wait_selector='a[id^="job-card-"][id$="-job-list"]',
                    debug_path=debug,
                )
                urls = _MICROSOFT_JOB_RE.findall(text)
                if pnum == 0:
                    sys.stderr.write(
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
                        "url": f"https://jobs.careers.microsoft.com/global/en/job/{jid}",
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
        sys.stderr.write(f"[{source_name}] Playwright not installed\n")
        return []
    debug = f"debug-{slug(source_name)}-1.html"
    p, browser, page = _open_browser()
    try:
        text = _render(page, url, wait_selector=wait_selector, debug_path=debug)
    finally:
        browser.close()
        p.stop()
    sys.stderr.write(f"[{source_name}] rendered {len(text)}B (dumped {debug})\n")
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
        sys.stderr.write("[Ableton] Playwright not installed\n")
        return {"jobs": [], "spontaneous_url": None}
    url = source.get("search_url") or "https://www.ableton.com/en/jobs/"
    debug = "debug-ableton-1.html"
    p, browser, page = _open_browser()
    try:
        text = _render(page, url, wait_selector="a[href*='/jobs/apply/']", debug_path=debug)
    finally:
        browser.close()
        p.stop()
    sys.stderr.write(f"[Ableton] rendered {len(text)}B (dumped {debug})\n")
    pattern = re.compile(
        r'<a[^>]+href="(/[a-z]{2}/jobs/apply/\d+/?)"[^>]*>'
        r'(?:\s*<span[^>]*>)?\s*([^<]+?)\s*(?:</span>)?\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )
    out, seen = [], set()
    for path, title in pattern.findall(text):
        if path in seen:
            continue
        seen.add(path)
        out.append({
            "title": title.strip(),
            "locations": [],
            "url": f"https://www.ableton.com{path}",
            "description": "",
            "blob": title,
        })
    return {"jobs": out, "spontaneous_url": _pick_spontaneous(out)}


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
        sys.stderr.write(f"[{source['name']}] missing search_url/link_re\n")
        return {"jobs": [], "spontaneous_url": None}
    jobs = _pw_scrape_links(
        source["name"],
        source["search_url"],
        source["link_re"],
        source.get("origin") or source["search_url"].rsplit("/", 1)[0],
    )
    return {"jobs": jobs, "spontaneous_url": _pick_spontaneous(jobs)}


FETCHERS = {
    "ashby": fetch_ashby,
    "greenhouse": fetch_greenhouse,
    "apple": fetch_apple,
    "google": fetch_google,
    "microsoft": fetch_microsoft,
    "ableton": fetch_ableton,
    "lucca": fetch_lucca,
    "pw": fetch_pw_generic,
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
    if kind == "apple":
        return "https://jobs.apple.com/en-us/search"
    if kind == "google":
        return "https://www.google.com/about/careers/applications/jobs/results/"
    return ""


SCORING_SYSTEM = """You score job postings against a candidate profile.
Return ONLY a JSON array — no prose, no markdown fences. Each element:
{"url": "<exact url provided>", "score": <integer 0-10>, "reason": "<one short sentence>"}

Scoring guidance:
- 9-10: strong match to top-priority interests (see profile rubric)
- 6-8: solid fit, some priority interests
- 3-5: partial fit
- 0-2: weak/no fit
Use the rubric in the profile. Preserve URLs exactly. Do not invent jobs."""


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
    lines = ["Score these jobs (return JSON array only):", ""]
    for i, j in enumerate(batch, 1):
        desc = re.sub(r"<[^>]+>", " ", j.get("description") or "")
        desc = re.sub(r"\s+", " ", desc).strip()[:SCORE_DESC_CHARS]
        locs = ", ".join(j.get("locations") or []) or "N/A"
        lines.append(f"[{i}]")
        lines.append(f"url: {j['url']}")
        lines.append(f"title: {j['title']}")
        lines.append(f"location: {locs}")
        if desc:
            lines.append(f"description: {desc}")
        lines.append("")
    return "\n".join(lines)


def _parse_score_response(text, url_set):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except Exception:
            return {}
    out = {}
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        u = item.get("url", "")
        if u not in url_set:
            continue
        try:
            out[u] = {"score": int(item.get("score", 0)), "reason": str(item.get("reason", ""))[:280]}
        except Exception:
            continue
    return out


def _score_batch_claude(batch, profile_text, client):
    urls = {j["url"] for j in batch}
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
    return _parse_score_response(text, urls)


def _score_batch_ollama(batch, profile_text):
    urls = {j["url"] for j in batch}
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM + "\n\n" + profile_text},
            {"role": "user", "content": _make_batch_prompt(batch)},
        ],
        "format": "json",
    }
    req = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code}: {body}") from None
    text = data.get("message", {}).get("content", "") or data.get("response", "")
    return _parse_score_response(text, urls)


def score_jobs(jobs):
    """Attach `score` and `score_reason` to each job in place. Uses SCORE_CACHE
    to avoid re-scoring URLs we already know about."""
    if SCORER == "none" or not jobs:
        return
    profile = _load_profile()
    if not profile:
        sys.stderr.write(f"[score] no {PROFILE_FILE} — skipping\n")
        return
    cache = _load_score_cache()
    todo = [j for j in jobs if j["url"] and j["url"] not in cache]
    for j in jobs:
        cached = cache.get(j["url"])
        if cached:
            j["score"] = cached.get("score", 0)
            j["score_reason"] = cached.get("reason", "")
    if not todo:
        return

    client = None
    if SCORER == "claude":
        if not HAS_ANTHROPIC:
            sys.stderr.write("[score] anthropic SDK missing. pip install anthropic\n")
            return
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.stderr.write("[score] ANTHROPIC_API_KEY not set\n")
            return
        client = anthropic.Anthropic()

    sys.stderr.write(f"[score] {SCORER}: {len(todo)} jobs to rate\n")
    for i in range(0, len(todo), SCORE_BATCH_SIZE):
        batch = todo[i:i + SCORE_BATCH_SIZE]
        try:
            if SCORER == "claude":
                results = _score_batch_claude(batch, profile, client)
            elif SCORER == "ollama":
                results = _score_batch_ollama(batch, profile)
            else:
                results = {}
        except Exception as e:
            sys.stderr.write(f"[score] batch {i//SCORE_BATCH_SIZE} failed: {e}\n")
            continue
        for j in batch:
            r = results.get(j["url"])
            if r:
                j["score"] = r["score"]
                j["score_reason"] = r["reason"]
                cache[j["url"]] = r
        sys.stderr.write(f"[score] batch {i//SCORE_BATCH_SIZE + 1}/{(len(todo)-1)//SCORE_BATCH_SIZE + 1} done\n")
    _save_score_cache(cache)


def dedup_by_url(jobs):
    seen = {}
    for j in jobs:
        key = j["url"] or f"{j['title']}|{','.join(j['locations'])}"
        seen.setdefault(key, j)
    return list(seen.values())


def is_title_blacklisted(job):
    if not TITLE_BLACKLIST:
        return False
    title = job["title"].lower()
    return any(w.lower() in title for w in TITLE_BLACKLIST)


def is_location_blacklisted(job):
    if not LOCATION_BLACKLIST or not job["locations"]:
        return False
    bl = [b.lower() for b in LOCATION_BLACKLIST]
    return all(any(b in loc.lower() for b in bl) for loc in job["locations"])


def collect(source):
    result = FETCHERS[source["kind"]](source)
    jobs = [
        j for j in result["jobs"]
        if not is_title_blacklisted(j) and not is_location_blacklisted(j)
    ]
    jobs = dedup_by_url(jobs)
    jobs.sort(key=lambda j: j["title"].lower())
    return {"jobs": jobs, "spontaneous_url": result.get("spontaneous_url")}


def slug(name):
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")


def _cap_word(w):
    return TITLE_CASE_OVERRIDES.get(w.lower(), w.capitalize())


def _title_from_slug(s):
    return " ".join(_cap_word(w) for w in re.split(r"[-_]", s) if w)


def _seniority_rank(label):
    if label and label in SENIORITY_RANK:
        return SENIORITY_RANK.index(label)
    return len(SENIORITY_RANK)


def render_html_section(name, visible, rejected_count, board_url, spontaneous_url, liked, queries):
    sid = slug(name)
    ordered = sorted(
        visible,
        key=lambda j: (
            0 if j["url"] in liked else 1,
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
        score = j.get("score")
        score_reason = j.get("score_reason") or ""
        if score is not None:
            score_cls = "score-hi" if score >= 8 else "score-mid" if score >= 5 else "score-lo"
            score_html = (
                f'<span class="badge score {score_cls}" '
                f'title="{html.escape(score_reason, quote=True)}">'
                f'{int(score)}</span>'
            )
        else:
            score_html = ""
        desc = sanitize_html(j["description"])
        desc_html = desc if desc else '<em>No description available.</em>'
        is_liked = url in liked
        like_state = "on" if is_liked else "off"
        like_btn = (
            f'<button class="like" data-url="{url_esc}" data-state="{like_state}" title="Like">+1</button>'
            if url else ""
        )
        reject_btn = (
            f'<button class="reject" data-url="{url_esc}" title="Reject">×</button>'
            if url else ""
        )
        open_link = (
            f'<a href="{url_esc}" target="_blank" rel="noopener">Open original ↗</a>'
            if url else ""
        )
        li_class = "job liked" if is_liked else "job"
        items.append(
            f'    <li class="{li_class}" data-seniority="{seniority_attr}" '
            f'data-locations="{locs_attr}">'
            f'{reject_btn}{like_btn}<details>\n'
            f'      <summary title="{title_attr} — {locs_attr}">'
            f'{score_html}'
            f'<span class="title">{title_html}</span>'
            f'{seniority_html}'
            f'<span class="locs"> — {locs}</span>'
            f'</summary>\n'
            f'      <div class="description">\n'
            f'        <div class="desc-actions">{open_link}</div>\n'
            f'        <div class="desc-body">{desc_html}</div>\n'
            f'      </div>\n'
            f'    </details></li>'
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
    return (
        f'  <h1 id="{sid}">{board_link} {query_pills} {counter}</h1>\n'
        f'{spontaneous_row}'
        f'  <ul data-section="{sid}">\n{ul_content}\n  </ul>'
    )


NAV_BREAK_BEFORE = {"Apple", "Ableton"}


def render_html_nav(entries):
    buttons = []
    for name, visible_count in entries:
        if name in NAV_BREAK_BEFORE and buttons:
            buttons.append('    <div class="nav-break"></div>')
        buttons.append(
            f'    <a class="nav-btn" href="#{slug(name)}">{html.escape(name)} '
            f'(<span class="nav-count">{visible_count}</span>)</a>'
        )
    return '  <nav class="nav">\n' + "\n".join(buttons) + "\n  </nav>"


def _group_locations(locations):
    groups = {}
    for loc in locations:
        if "," in loc:
            country = loc.rsplit(",", 1)[1].strip()
        else:
            country = "Other"
        groups.setdefault(country, []).append(loc)
    for k in groups:
        groups[k] = sorted(set(groups[k]))
    return sorted(groups.items(), key=lambda kv: (kv[0] == "Other", kv[0].lower()))


def _render_location_picker(locations):
    if not locations:
        return ""
    blocks = []
    for country, locs in _group_locations(locations):
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
    .nav-count { color: var(--severe); font-weight: 600; }
    .total-count {
      font-size: 1rem;
      font-weight: 600;
      color: var(--fg);
      padding: 0.5rem 0.9rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: 6px;
      display: inline-block;
      margin-bottom: 1rem;
    }
    #total-count { color: var(--severe); }
    .nav-break { flex-basis: 100%; height: 0; }

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
      align-items: baseline;
      gap: 0.6rem;
      margin: 0.4rem 0;
    }
    li.hidden { display: none; }
    li > details { flex: 1; min-width: 0; }
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
    .badge.score {
      font-weight: 700;
      min-width: 1.3rem;
      text-align: center;
      cursor: help;
    }
    .badge.score-hi  { color: #ffffff;         background: var(--success); border-color: var(--success); }
    .badge.score-mid { color: var(--attention);background: #fff8c5;         border-color: rgba(154,103,0,0.4); }
    .badge.score-lo  { color: var(--fg-muted); background: var(--bg-subtle);border-color: var(--border); }

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
    if (navCount) navCount.textContent = visible;
    const v = document.querySelector('#' + sid + ' .counter .v');
    if (v) v.textContent = visible;
  });
  const totalEl = document.getElementById('total-count');
  if (totalEl) totalEl.textContent = total;
  saveFilters();
}

loadFilters();
applyFilters();

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

document.querySelectorAll('.like').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const url = btn.dataset.url;
    const li = btn.closest('li');
    const ul = li.closest('ul');
    const on = btn.dataset.state === 'on';
    btn.disabled = true;
    try {
      await apiPost(on ? '/unlike' : '/like', url);
      btn.dataset.state = on ? 'off' : 'on';
      if (on) {
        li.classList.remove('liked');
      } else {
        li.classList.add('liked');
        // move to top of the ul, after any already-liked entries
        const firstUnliked = ul.querySelector('li.job:not(.liked)');
        if (firstUnliked && firstUnliked !== li) ul.insertBefore(li, firstUnliked);
        else ul.insertBefore(li, ul.firstElementChild);
      }
    } catch (err) {
      alert('Like failed: ' + err.message);
    } finally {
      btn.disabled = false;
    }
  });
});

/* --- Reject ------------------------------------------------------------ */
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
      const base = location.protocol === 'file:' ? SERVER_URL : '';
      const res = await fetch(base + '/reject', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url})
      });
      if (!res.ok) throw new Error('http ' + res.status);
      li.remove();
      const h1 = document.getElementById(sid);
      if (h1) {
        const v = h1.querySelector('.counter .v');
        const r = h1.querySelector('.counter .r');
        if (v) v.textContent = parseInt(v.textContent) - 1;
        if (r) r.textContent = parseInt(r.textContent) + 1;
      }
      const navCount = document.querySelector('.nav-btn[href="#' + sid + '"] .nav-count');
      if (navCount) navCount.textContent = parseInt(navCount.textContent) - 1;
      if (ul.querySelectorAll('li').length === 0) {
        ul.insertAdjacentHTML('beforeend', '    <li><em>none</em></li>');
      }
    } catch (err) {
      btn.disabled = false;
      li.style.opacity = '1';
      alert('Reject failed: ' + err.message);
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
        if self.path not in ("/reject", "/like", "/unlike"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length))
            url = (payload.get("url") or "").strip()
        except Exception:
            url = ""
        if not url:
            self.send_response(400)
            self._cors()
            self.end_headers()
            return
        if self.path == "/reject":
            s = load_rejected(); s.add(url); save_rejected(s)
            sys.stderr.write(f"rejected: {url}\n")
        elif self.path == "/like":
            s = load_liked(); s.add(url); save_liked(s)
            sys.stderr.write(f"liked:    {url}\n")
        elif self.path == "/unlike":
            s = load_liked(); s.discard(url); save_liked(s)
            sys.stderr.write(f"unliked:  {url}\n")
        self.send_response(204)
        self._cors()
        self.end_headers()

    def log_message(self, *a):
        pass


def main():
    t0 = time.perf_counter()
    rejected = load_rejected()
    liked = load_liked()
    html_sections = []
    nav_entries = []
    all_visible = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:
        futures = {ex.submit(collect, src): src for src in SOURCES}
        results = {}
        for fut in concurrent.futures.as_completed(futures):
            src = futures[fut]
            try:
                results[src["name"]] = fut.result()
            except Exception as e:
                sys.stderr.write(f"[{src['name']}] collect crashed: {e}\n")
                results[src["name"]] = {"jobs": [], "spontaneous_url": None}

    # Score all visible jobs against PROFILE.md before rendering.
    all_visible_for_score = []
    for src in SOURCES:
        result = results[src["name"]]
        all_visible_for_score.extend(
            j for j in result["jobs"] if j["url"] not in rejected
        )
    score_jobs(all_visible_for_score)

    for src in SOURCES:
        result = results[src["name"]]
        all_jobs = result["jobs"]
        visible = [j for j in all_jobs if j["url"] not in rejected]
        rejected_here = len(all_jobs) - len(visible)
        html_sections.append(render_html_section(
            src["name"], visible, rejected_here,
            board_url_for(src), result.get("spontaneous_url"),
            liked, src.get("queries", []),
        ))
        nav_entries.append((src["name"], len(visible)))
        all_visible.extend(visible)
        extra = " · spontaneous✉" if result.get("spontaneous_url") else ""
        print(f"{src['name']}: {len(visible)} visible, {rejected_here} rejected{extra}", file=sys.stderr)

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
    all_locations = sorted({loc for j in all_visible for loc in j["locations"] if loc})
    total = len(all_visible)
    total_bar = (
        f'  <div class="total-count">Total: '
        f'<span id="total-count">{total}</span> jobs visible</div>'
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
    elapsed = time.perf_counter() - t0
    print(
        f"wrote {OUTPUT_HTML} in {elapsed:.1f}s · "
        f"rejected DB: {REJECTED_DB} ({len(rejected)} entries)",
        file=sys.stderr,
    )

    server = http.server.ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    print(f"serving on {server_url} — Ctrl-C to stop", file=sys.stderr)
    threading.Timer(0.4, lambda: webbrowser.open(server_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("bye", file=sys.stderr)


if __name__ == "__main__":
    main()
