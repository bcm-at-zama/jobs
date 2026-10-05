"""user_config.example.py — minimal starter config for a new user.

This file is a TEMPLATE. The engine reads `data/user_config.py`
(gitignored for an open-source clone). To onboard:

    1. Copy this file to `data/user_config.py`.
    2. Edit the four lists below to reflect YOUR job hunt.
    3. Run `python3 src/jobs.py`.

Framework defaults (seniority bands, ATS fetchers, scoring settings,
company blurbs) live in `src/config.py`. Personal preferences stay in
`data/user_config.py` so src/ can be shared as open source without
leaking private taste.

NOTE: this example is intentionally small (3 sources, 3-5 entries per
list) so new users have something that runs end-to-end in <10s on a
first fetch. Grow it as you discover sources you care about.
"""

# =============================================================================
# 1. SOURCES — which career boards to scrape
#
# `kind` must map to a FETCHERS entry in jobs.py (greenhouse, ashby,
# workday, phenom, pw, …). `slug` is the ATS board identifier (the
# segment after the ATS domain). `queries` filters titles client-side
# — start with [] and tighten later.
# =============================================================================

SOURCES = [
    # Greenhouse ATS — slug is whatever follows boards.greenhouse.io/
    {"name": "Example GH Co",     "kind": "greenhouse", "slug": "exampleghco",    "queries": []},
    # Ashby ATS
    {"name": "Example Ashby Co",  "kind": "ashby",      "slug": "exampleashbyco", "queries": []},
    # Workday needs the full board URL
    {"name": "Example Workday Co","kind": "workday",    "slug": "wdco",           "queries": [],
     "board": "https://wdco.wd1.myworkdayjobs.com/External"},
]

# =============================================================================
# 2. TITLE_BLACKLIST — substrings (case-insensitive) that disqualify a
# posting even if its company is on your SOURCES list. Useful to filter
# out junior roles, non-engineering positions, etc.
# =============================================================================

TITLE_BLACKLIST = [
    "Intern",
    "Junior",
    "Associate",       # usually consultant / investment-bank levels
    "Marketing",
    "Sales",
]

# =============================================================================
# 3. LOCATION_BLACKLIST — countries, cities, or regions you don't want.
# Matched substring on the location field (case-insensitive).
# =============================================================================

LOCATION_BLACKLIST = [
    "India",
    "Philippines",
    "Vietnam",
]

# =============================================================================
# 4. HIGHLIGHT_WORDS — words highlighted (<mark>) in job descriptions
# so you can skim postings fast. Case-insensitive, whole-word.
# =============================================================================

HIGHLIGHT_WORDS = [
    "Rust",
    "Go",
    "Kubernetes",
    "security",
    "cryptography",
]
