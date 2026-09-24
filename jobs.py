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
# CONFIG — tweak these
# =============================================================================

OUTPUT_HTML = "jobs.html"
REJECTED_DB = "rejected.json"
LIKED_DB = "liked.json"
PROFILE_FILE = "PROFILE.md"
SCORE_CACHE = "score_cache.json"
DESC_CACHE = "desc_cache.json"

SERVE_HOST = "127.0.0.1"
SERVE_PORT = 8765

# Scoring backend for ranking jobs against PROFILE.md.
#   "claude" — Anthropic API (needs ANTHROPIC_API_KEY env var, `pip install anthropic`).
#   "ollama" — local Ollama server at OLLAMA_URL.
#   "none"   — disable scoring.
SCORER = "ollama"
CLAUDE_MODEL = "claude-sonnet-4-6"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:latest"
SCORE_BATCH_SIZE = 1   # qwen consistently outputs 1 object per call; batch=1 = 100% coverage
SCORE_DESC_CHARS = 400
SCORE_PARALLEL = 6     # concurrent calls to Ollama/Claude

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
LOCATION_BLACKLIST = ["Israel", "India", "Romania", "Brazil", "Mexico"]

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

# Group labels shown as separators in the nav. Order defines the section order.
GROUP_ORDER = [
    "Acteurs de l'AI",
    "Grosses compagnies",
    "Acteurs de la sécurité",
    "Compagnies de musique",
    "Autres",
]

# name → group. Every source name should appear here. Missing entries fall
# back to "Autres".
GROUP_OF = {
    # Acteurs de l'AI
    "OpenAI": "Acteurs de l'AI",
    "Anthropic": "Acteurs de l'AI",
    "Mistral": "Acteurs de l'AI",
    "Cohere": "Acteurs de l'AI",
    "H": "Acteurs de l'AI",
    "AMI": "Acteurs de l'AI",
    "HF": "Acteurs de l'AI",
    "SSI": "Acteurs de l'AI",
    "Thinking Machines": "Acteurs de l'AI",
    "Scale AI": "Acteurs de l'AI",
    "DeepL": "Acteurs de l'AI",
    "Eleven Labs": "Acteurs de l'AI",
    "Poolside": "Acteurs de l'AI",
    "Black Forest Labs": "Acteurs de l'AI",
    "Sony AI": "Acteurs de l'AI",
    "Cursor": "Acteurs de l'AI",
    "Cognition": "Acteurs de l'AI",
    # Grosses compagnies
    "Apple": "Grosses compagnies",
    "Microsoft": "Grosses compagnies",
    "Google": "Grosses compagnies",
    "Meta": "Grosses compagnies",
    "NVIDIA": "Grosses compagnies",
    "GitHub": "Grosses compagnies",
    "Proton": "Grosses compagnies",
    # Acteurs de la sécurité
    "DepthFirst": "Acteurs de la sécurité",
    "XBOW": "Acteurs de la sécurité",
    "Aisle": "Acteurs de la sécurité",
    "ZeroPath": "Acteurs de la sécurité",
    "Pixee": "Acteurs de la sécurité",
    "Corgea": "Acteurs de la sécurité",
    "CrowdStrike": "Acteurs de la sécurité",
    "Snyk": "Acteurs de la sécurité",
    "Semgrep": "Acteurs de la sécurité",
    "Checkmarx": "Acteurs de la sécurité",
    # Compagnies de musique
    "Ableton": "Compagnies de musique",
    "Arturia": "Compagnies de musique",
    "Neural DSP": "Compagnies de musique",
    "Steinberg": "Compagnies de musique",
    # Autres
    "Welcome to the Jungle": "Autres",
}

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
    {"name": "HF",        "kind": "workable",   "slug": "huggingface","queries": [],
     "board": "https://apply.workable.com/huggingface/"},
    {"name": "SSI",       "kind": "ashby",      "slug": "ssi",        "queries": []},
    {"name": "Thinking Machines", "kind": "ashby", "slug": "ThinkingMachines", "queries": []},
    {"name": "Scale AI",  "kind": "pw",         "slug": "scale",      "queries": [],
     "board": "https://scale.com/careers",
     "search_url": "https://scale.com/careers",
     "link_re": r'href="(/careers/[^"#?]+)"',
     "origin": "https://scale.com"},
    {"name": "DeepL",     "kind": "ashby",      "slug": "DeepL",      "queries": []},
    {"name": "Eleven Labs", "kind": "ashby",    "slug": "elevenlabs", "queries": []},
    {"name": "Poolside", "kind": "ashby",       "slug": "poolside",   "queries": []},
    {"name": "Black Forest Labs", "kind": "pw", "slug": "blackforestlabs", "queries": [],
     "board": "https://job-boards.greenhouse.io/blackforestlabs",
     "search_url": "https://job-boards.greenhouse.io/blackforestlabs",
     "link_re": r'href="(/blackforestlabs/jobs/\d+|https?://job-boards\.greenhouse\.io/blackforestlabs/jobs/\d+)"',
     "origin": "https://job-boards.greenhouse.io"},
    {"name": "Proton",   "kind": "greenhouse",  "slug": "proton",    "queries": [],
     "board": "https://proton.me/careers"},
    {"name": "Sony AI",  "kind": "pw",          "slug": "sonyai",    "queries": [],
     "board": "https://ai.sony/join-us",
     "search_url": "https://ai.sony/join-us",
     "link_re": r'href="(https?://[^"]*(?:jobs|careers|job-postings|apply)[^"]*|/(?:jobs|careers|open-roles)/[^"#?]+)"',
     "origin": "https://ai.sony"},
    {"name": "Cursor",   "kind": "ashby",       "slug": "cursor",    "queries": [],
     "board": "https://cursor.com/careers"},
    {"name": "Cognition","kind": "ashby",       "slug": "cognition", "queries": [],
     "board": "https://cognition.com/careers"},
    {"name": "DepthFirst","kind": "ashby",      "slug": "depthfirst","queries": []},
    {"name": "XBOW",      "kind": "ashby",      "slug": "xbowcareers","queries": []},
    {"name": "Aisle",     "kind": "pw",         "slug": "aisle",     "queries": [],
     "board": "https://aisle.com/careers",
     "search_url": "https://aisle.com/careers",
     "link_re": r'href="(https?://jobs\.ashbyhq\.com/[^"#?]+/[a-f0-9-]{20,}|/careers/[^"#?]+|https?://[^"]*(?:greenhouse|lever|workable|ashby)[^"]*)"',
     "origin": "https://aisle.com"},
    {"name": "ZeroPath",  "kind": "pw",         "slug": "zeropath",  "queries": [],
     "board": "https://zeropath.com/careers",
     "search_url": "https://zeropath.com/careers",
     "link_re": r'href="(https?://jobs\.ashbyhq\.com/[^"#?]+/[a-f0-9-]{20,}|/careers/[^"#?]+|https?://[^"]*(?:greenhouse|lever|workable|ashby)[^"]*)"',
     "origin": "https://zeropath.com"},
    {"name": "Pixee",     "kind": "pw",         "slug": "pixee",     "queries": [],
     "board": "https://app.dover.com/jobs/pixee",
     "search_url": "https://app.dover.com/jobs/pixee",
     "link_re": r'href="(/jobs/pixee/[^"#?]+|https?://app\.dover\.com/jobs/pixee/[^"#?]+)"',
     "origin": "https://app.dover.com"},
    {"name": "Corgea",    "kind": "pw",         "slug": "corgea",    "queries": [],
     "board": "https://www.ycombinator.com/companies/corgea/jobs",
     "search_url": "https://www.ycombinator.com/companies/corgea/jobs",
     "link_re": r'href="(/companies/corgea/jobs/[^"#?]+)"',
     "origin": "https://www.ycombinator.com"},
    {"name": "CrowdStrike","kind": "pw",        "slug": "crowdstrike","queries": ["security"],
     "board": "https://crowdstrike.wd5.myworkdayjobs.com/en-US/crowdstrikecareers",
     "search_url": "https://crowdstrike.wd5.myworkdayjobs.com/en-US/crowdstrikecareers",
     "link_re": r'href="(/en-US/crowdstrikecareers/job/[^"#?]+)"',
     "origin": "https://crowdstrike.wd5.myworkdayjobs.com"},
    {"name": "Snyk",       "kind": "pw",         "slug": "snyk",       "queries": [],
     "board": "https://job-boards.greenhouse.io/snyk",
     "search_url": "https://job-boards.greenhouse.io/snyk",
     "link_re": r'href="(/snyk/jobs/\d+|https?://job-boards\.greenhouse\.io/snyk/jobs/\d+)"',
     "origin": "https://job-boards.greenhouse.io"},
    {"name": "Semgrep",    "kind": "pw",         "slug": "semgrep",    "queries": [],
     "board": "https://job-boards.greenhouse.io/semgrep",
     "search_url": "https://job-boards.greenhouse.io/semgrep",
     "link_re": r'href="(/semgrep/jobs/\d+|https?://job-boards\.greenhouse\.io/semgrep/jobs/\d+)"',
     "origin": "https://job-boards.greenhouse.io"},
    {"name": "Checkmarx",  "kind": "pw",         "slug": "checkmarx",  "queries": [],
     "board": "https://checkmarx.com/company/careers/",
     "search_url": "https://checkmarx.com/company/careers/",
     "link_re": r'href="(https?://[^"]*(?:greenhouse|lever|workable|ashby|workday|smartrecruiters)[^"]*)"',
     "origin": "https://checkmarx.com"},
    {"name": "NVIDIA",    "kind": "phenom",     "slug": "nvidia",     "queries": ["security"],
     "board": "https://jobs.nvidia.com/careers?query=Security&pid=893394830937&sort_by=relevance",
     "search_url": "https://jobs.nvidia.com/careers?query=Security&sort_by=relevance"},
    {"name": "GitHub",    "kind": "pw",         "slug": "github",    "queries": ["security"],
     "board": "https://www.github.careers/careers-home/jobs?keywords=security",
     "search_url": "https://www.github.careers/careers-home/jobs?keywords=security",
     "link_re": r'href="(https?://www\.github\.careers/careers-home/jobs/\d+[^"#?]*|/careers-home/jobs/\d+[^"#?]*)"',
     "origin": "https://www.github.careers"},
    {"name": "Apple",     "kind": "apple",      "slug": "apple",      "queries": ["security", "Logic"],
     "board": "https://jobs.apple.com/en-us/search?search=security"},
    {"name": "Microsoft", "kind": "microsoft",  "slug": "microsoft",  "queries": ["security"],
     "board": "https://apply.careers.microsoft.com/careers?query=Security&pid=1970393556942260&sort_by=relevance"},
    {"name": "Google",    "kind": "google",     "slug": "google",     "queries": ["security", "codemender", "DeepMind", "Big Sleep"],
     "board": "https://www.google.com/about/careers/applications/jobs/results/?q=security&hl=en_US",
     "search_url": "https://www.google.com/about/careers/applications/jobs/results?hl=en_US&target_level=DIRECTOR_PLUS&target_level=ADVANCED&employment_type=FULL_TIME"},
    {"name": "Meta",      "kind": "meta",       "slug": "meta",       "queries": ["security"],
     "board": "https://www.metacareers.com/jobsearch/?q=security"},
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
    {"name": "Welcome to the Jungle", "kind": "wttj", "slug": "wttj", "queries": ["security"],
     "board": "https://www.welcometothejungle.com/fr/pages/emploi?query=security",
     "search_url": "https://www.welcometothejungle.com/fr/pages/emploi?query=security&refinementList[contract_type][0]=full_time"},
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
_RED = "\033[31m" if _USE_COLOR else ""
_RESET = "\033[0m" if _USE_COLOR else ""


def err(msg):
    """Print an error line in red to stdout."""
    print(f"{_RED}{msg}{_RESET}", file=sys.stdout)


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


def normalize_workable(raw):
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
        out.append({
            "title": _flat(j.get("title")),
            "locations": [loc_str] if loc_str else [],
            "url": j.get("url") or f"https://apply.workable.com/{j.get('shortcode', '')}",
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
    all_jobs = normalize_workable(raw)
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
    url = f"https://api.ashbyhq.com/posting-api/job-board/{source['slug']}"
    try:
        raw = http_get_json(url)
    except Exception as e:
        err(f"[{source['name']}] Ashby fetch failed: {e}")
        return {"jobs": [], "spontaneous_url": None}
    all_jobs = normalize_ashby(raw)
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
            sys.stdout.write(
                f"[{source_name}] {i}/{n} ({fetched} fetched, {i - fetched} cached)\n"
            )
            # Incremental save so a Ctrl-C mid-source doesn't lose everything.
            if new_entries:
                _save_desc_cache_merge(new_entries)
                new_entries = {}
    if new_entries:
        _save_desc_cache_merge(new_entries)


def _render(page, url, wait_selector=None, timeout=12000, debug_path=None):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception as e:
        err(f"[render] {url} nav failed: {e}")
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
                debug = f"debug-apple-{q}-{pnum}.html" if pnum == 1 else None
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
                    sys.stdout.write(
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
                debug = f"debug-microsoft-{q}-{pnum}.html" if pnum == 0 else None
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
        err(f"[{source_name}] Playwright not installed")
        return []
    debug = f"debug-{slug(source_name)}-1.html"
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
    debug = "debug-ableton-1.html"
    p, browser, page = _open_browser()
    try:
        text = _render(page, url, wait_selector="a[href*='/jobs/apply/']", debug_path=debug)
    finally:
        browser.close()
        p.stop()
    sys.stdout.write(f"[Ableton] rendered {len(text)}B (dumped {debug})\n")
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
        err(f"[{source['name']}] missing search_url/link_re")
        return {"jobs": [], "spontaneous_url": None}
    jobs = _pw_scrape_links(
        source["name"],
        source["search_url"],
        source["link_re"],
        source.get("origin") or source["search_url"].rsplit("/", 1)[0],
    )
    return {"jobs": jobs, "spontaneous_url": _pick_spontaneous(jobs)}


_META_JOB_RE = re.compile(r'/jobs/(\d{5,})/?', re.IGNORECASE)


def fetch_meta(source):
    if not HAS_PLAYWRIGHT:
        err("[Meta] Playwright not installed")
        return {"jobs": [], "spontaneous_url": None}
    out, seen = [], set()
    p, browser, page = _open_browser()
    try:
        for q in source["queries"]:
            url = f"https://www.metacareers.com/jobsearch/?q={urllib.parse.quote(q)}"
            debug = f"debug-meta-{q}-1.html"
            text = _render(page, url, wait_selector="a[href*='/jobs/']", debug_path=debug)
            # Meta renders job cards as <a href="/jobs/<id>/">…title…locations…</a>
            pattern = re.compile(
                r'<a[^>]+href="(/jobs/\d+/?)"[^>]*>(.*?)</a>',
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
                debug = f"debug-{slug(source['name'])}-{q}-{pnum}.html" if pnum == 0 else None
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
                debug = f"debug-wttj-{q}-{pnum}.html" if pnum == 1 else None
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


SCORING_SYSTEM = """You score job postings against a candidate profile.

Return ONLY a JSON array with ONE ELEMENT PER JOB you were given. If 5 jobs are
provided, the array MUST contain 5 elements. Never merge, summarize, or skip.

Each element:
  {"i": <index from the numbered list>, "score": <integer 0-10>,
   "reason": "<detailed reason: 2-3 sentences, ~100-400 characters, "
             "say what fits or doesn't per the rubric>"}

Example (for 3 jobs):
  [
    {"i": 1, "score": 8, "reason": "Directly matches the AI-powered vulnerability remediation interest (Codex-style role at OpenAI, US-based). No management scope but strong IC track and applied crypto adjacency via secure code analysis."},
    {"i": 2, "score": 3, "reason": "Sales/GTM role, not technical. Team focuses on account expansion rather than security engineering; location fits but domain doesn't align with the rubric priorities."},
    {"i": 3, "score": 6, "reason": "Model security research at DeepMind is close to the AI safety interest; description emphasizes red-teaming and adversarial ML which matches priority 3, though it's more research-only with fewer engineering hooks."}
  ]

Scoring rubric: 9-10 top-priority match, 6-8 solid, 3-5 partial, 0-2 weak.
The reason field is critical: it's what the user reads to decide whether to
open the posting, so be specific about which rubric items match and which don't."""


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
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        idx = item.get("i") or item.get("index") or item.get("id")
        try:
            idx = int(idx) - 1
        except Exception:
            continue
        if not (0 <= idx < len(batch)):
            continue
        url = batch[idx]["url"]
        try:
            out[url] = {"score": int(item.get("score", 0)), "reason": str(item.get("reason", ""))[:400]}
        except Exception:
            continue
    if not out:
        # Always dump when a batch produces zero scores. Rotated file so
        # we can inspect multiple failures side by side.
        try:
            n = _SCORE_DEBUG.setdefault("n", 0) + 1
            _SCORE_DEBUG["n"] = n
            with open(f"debug-score-response-{n}.txt", "w", encoding="utf-8") as f:
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


def _score_batch_ollama(batch, profile_text):
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
    sys.stdout.write(
        f"[score] {SCORER}: {len(todo)} jobs / {n_batches} batches "
        f"(parallel={SCORE_PARALLEL})\n"
    )
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

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=SCORE_PARALLEL) as ex:
            for i, batch in enumerate(batches):
                ex.submit(_process, batch, i)
    finally:
        _save_score_cache(cache)


_LOC_SPLIT_RE = re.compile(r"\s*[;|]\s*")
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


def _clean_loc(part):
    """Strip UI artifacts like ' + N more' suffixes and work-mode prefixes
    (Hybrid, Remote, Onsite …)."""
    s = _PLUS_MORE_RE.sub("", part).strip()
    s = _WORK_MODE_PREFIX_RE.sub("", s).strip()
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
            city, country, display = _parse_loc(part)
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
            display = f"{city}, {country}"
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
    raw_jobs = result["jobs"]
    for j in raw_jobs:
        j["locations"] = _flatten_locations(j.get("locations"))
    jobs = [
        j for j in raw_jobs
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


def render_html_nav(entries):
    """Groups nav buttons per GROUP_ORDER, with a labelled row per group."""
    by_group = {g: [] for g in GROUP_ORDER}
    for name, visible_count in entries:
        group = GROUP_OF.get(name, "Autres")
        by_group.setdefault(group, []).append((name, visible_count))
    rows = []
    for group in GROUP_ORDER + [g for g in by_group if g not in GROUP_ORDER]:
        items = by_group.get(group) or []
        if not items:
            continue
        items.sort(key=lambda kv: kv[0].lower())
        buttons = "".join(
            f'<a class="nav-btn" href="#{slug(name)}">{html.escape(name)} '
            f'(<span class="nav-count">{visible_count}</span>)</a>'
            for name, visible_count in items
        )
        rows.append(
            '    <div class="nav-row">'
            f'<span class="nav-group-label">{html.escape(group)}</span>'
            f'{buttons}'
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
    blocks = []
    for country, locs in _group_locations(locations):
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
    .nav-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.4rem;
      width: 100%;
    }
    .nav-group-label {
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--fg-muted);
      text-transform: uppercase;
      letter-spacing: 0.03em;
      min-width: 10rem;
      padding-right: 0.4rem;
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
            sys.stdout.write(f"rejected: {url}\n")
        elif self.path == "/like":
            s = load_liked(); s.add(url); save_liked(s)
            sys.stdout.write(f"liked:    {url}\n")
        elif self.path == "/unlike":
            s = load_liked(); s.discard(url); save_liked(s)
            sys.stdout.write(f"unliked:  {url}\n")
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
    ap.add_argument("--debug-locations", action="store_true",
                    help="Dump raw→normalized locations and exit.")
    ap.add_argument("--no-open", action="store_true",
                    help="Don't auto-open the browser after starting the server.")
    ap.add_argument("--list", action="store_true",
                    help="Print every configured board name (comma-separated) and exit.")
    return ap.parse_args()


def main():
    args = _parse_cli()

    if args.list:
        print(",".join(s["name"] for s in SOURCES))
        return

    if args.debug_locations or os.environ.get("JOBS_DEBUG_LOCATIONS") == "1":
        _run_location_debug()
        return

    t0 = time.perf_counter()

    # CLI flags win; env vars remain as a legacy fallback.
    def _split(s):
        return {x.strip() for x in (s or "").split(",") if x.strip()}
    only  = _split(args.only) or _split(os.environ.get("JOBS_ONLY", ""))
    skip  = _split(args.skip) or _split(os.environ.get("JOBS_SKIP", ""))
    skip_pw    = args.skip_playwright or os.environ.get("JOBS_SKIP_PLAYWRIGHT") == "1"
    skip_score = args.skip_scoring    or os.environ.get("JOBS_SKIP_SCORING") == "1"
    pw_kinds = {"apple", "google", "microsoft", "meta", "phenom", "ableton", "lucca", "pw", "wttj"}
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
    sys.stdout.write(f"[timing] fetch (all sources, parallel) → {t_fetch:.1f}s\n")

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
        sys.stdout.write("[timing] scoring SKIPPED (JOBS_SKIP_SCORING=1)\n")
    t_score = time.perf_counter() - t_score_start
    sys.stdout.write(f"[timing] score ({len(all_visible_for_score)} jobs) → {t_score:.1f}s\n")

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
    t_render = time.perf_counter() - t_render_start
    sys.stdout.write(f"[timing] render + write → {t_render:.1f}s\n")
    elapsed = time.perf_counter() - t0
    print(
        f"wrote {OUTPUT_HTML} · total {elapsed:.1f}s · "
        f"rejected DB: {REJECTED_DB} ({len(rejected)} entries)",
        file=sys.stdout,
    )

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
