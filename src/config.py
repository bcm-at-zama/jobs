"""
config.py — framework defaults for jobs.py.

This file ships only neutral framework configuration: storage paths,
scoring backend knobs, seniority bands, spontaneous-application patterns,
company-blurb metadata, group taxonomy. Everything here is safe to open
source — zero personal data.

Personal preferences (SOURCES, HIGHLIGHTS, TITLE_BLACKLIST,
LOCATION_BLACKLIST) live in `data/user_config.py`, loaded at the bottom
of this file. New installs: copy `src/user_config.example.py` to
`data/user_config.py` and edit.
"""

# =============================================================================
# Storage locations
#
# The engine code (jobs.py) and all per-user state are now separated:
#   - Engine → repository code (jobs.py, config.py, tests/, …)
#   - State  → the `data/` directory, created automatically on first run
#
# To relocate your state (e.g. to a Dropbox-synced folder), set
# JOBS_DATA_DIR in your environment to an absolute path.
# =============================================================================
import os as _os

DATA_DIR            = _os.environ.get("JOBS_DATA_DIR", "data")
# Ensure data/ exists so writers never fail on a fresh clone. idempotent.
_os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_HTML         = _os.path.join(DATA_DIR, "jobs.html")
REJECTED_DB         = _os.path.join(DATA_DIR, "rejected.json")
LIKED_DB            = _os.path.join(DATA_DIR, "liked.json")
TO_APPLY_DB         = _os.path.join(DATA_DIR, "to_apply.json")
APPLIED_DB          = _os.path.join(DATA_DIR, "applied.json")
# {url: {reason, feedback, ts}} — jobs where I applied and the company
# rejected me. Kept even after the job is removed from the board.
APP_REJECTED_DB     = _os.path.join(DATA_DIR, "app_rejected.json")
# History: jobs you want to remember even though you're not applying and
# not rejecting them. Typically clicked via the K button once you've read
# the description and want to archive it out of the main list.
HISTORY_DB          = _os.path.join(DATA_DIR, "history.json")
SEEN_DB             = _os.path.join(DATA_DIR, "seen.json")
# {url: {title, locations, source}} — used to render orphans (jobs the user
# +1'd / marked but no longer returned by the source board).
JOB_INDEX_DB        = _os.path.join(DATA_DIR, "job_index.json")
SCORE_CACHE         = _os.path.join(DATA_DIR, "llm_cache.json")
DESC_CACHE          = _os.path.join(DATA_DIR, "desc_cache.json")
# {url: {score: int 0-10, reason: str, ts: ISO}} — Claude fit scores from
# the "C" button. Keyed by URL. Written per-URL as scoring progresses so
# interrupted runs don't lose work.
CLAUDE_FIT_CACHE    = _os.path.join(DATA_DIR, "claude_fit_cache.json")
RAW_LOCATIONS_FILE  = "debug/raw_locations.txt"
LIST_CACHE_DIR      = _os.path.join(DATA_DIR, "list_cache")

# TTL for the per-source list cache. On a re-run within this window we skip
# Playwright entirely for that source (huge speed-up when descriptions and
# scores are already cached). Set to 0 to always re-fetch.
LIST_CACHE_TTL_HOURS = 6

# Local HTTP server the browser talks to (× reject / +1 like).
SERVE_HOST = "127.0.0.1"
SERVE_PORT = 8765

# Scoring is handled manually via the "C" button in the UI (Claude.ai
# web paste flow — zero API cost, uses your Claude.ai subscription). No
# auto-scorer, no API key needed.

# =============================================================================
# Highlights — words drawn with a marker style in titles + descriptions
# =============================================================================

# Framework default — empty so an open-source clone has no personal
# bias. Your real list lives in data/user_config.py (loaded at the end
# of this file).
HIGHLIGHTS = []

# When titles come from a URL slug (Apple, Google, Ableton, …), each dash is
# split and each word .capitalize()'d. Add anything here to preserve custom
# casing (compared case-insensitively).
TITLE_CASE_OVERRIDES = {
    "sear": "SEAR",
    "ios": "iOS", "ipad": "iPad", "iphone": "iPhone",
    "macos": "macOS", "watchos": "watchOS", "tvos": "tvOS", "visionos": "visionOS",
    "ai": "AI", "ml": "ML", "llm": "LLM", "api": "API", "sdk": "SDK",
    "ui": "UI", "ux": "UX", "os": "OS", "gpu": "GPU", "cpu": "CPU",
    "ci": "CI", "cd": "CD", "sre": "SRE", "qa": "QA", "saas": "SaaS",
    "vp": "VP", "hr": "HR", "it": "IT", "grc": "GRC",
    "ssd": "SSD", "aiml": "AIML", "ciso": "CISO",
    "cto": "CTO", "cso": "CSO", "csi": "CSI",
    "ceo": "CEO", "cfo": "CFO", "coo": "COO", "cmo": "CMO", "cro": "CRO",
    "cpo": "CPO", "cdo": "CDO", "cio": "CIO",
    # Roman numerals I..X
    "i": "I", "ii": "II", "iii": "III", "iv": "IV", "v": "V",
    "vi": "VI", "vii": "VII", "viii": "VIII", "ix": "IX", "x": "X",
}

# =============================================================================
# Blacklists
# =============================================================================
# If any of these substrings appear in a job title (case-insensitive), hide.
TITLE_BLACKLIST = []  # loaded from data/user_config.py

# If ALL of a job's locations contain one of these substrings, hide.
LOCATION_BLACKLIST = []  # loaded from data/user_config.py

# =============================================================================
# Seniority — how the badge, filter, and sort work
# =============================================================================
# Groups shown as separate rows in the seniority filter bar. Order also
# drives the "most senior first" sort inside each section.
SENIORITY_GROUPS = [
    ("Management", ["VP", "Director", "Senior Manager", "Manager", "Head", "Lead"]),
    ("IC",         ["Senior Staff", "Staff", "Principal", "Senior"]),
]
SENIORITY_RANK = [lbl for _, group in SENIORITY_GROUPS for lbl in group] + [
    "Distinguished", "Associate", "Junior", "Intern",
]
# Substring → label. First match wins, so put more specific keywords first.
SENIORITY = [
    ("Senior Staff", "Senior Staff"),
    ("Staff", "Staff"),
    ("Principal", "Principal"),
    ("Distinguished", "Distinguished"),
    ("Head of", "Head"),
    ("Director", "Director"),
    ("Vice President", "VP"),
    (" VP ", "VP"),
    ("VP,", "VP"),
    ("VP of ", "VP"),
    ("SVP", "VP"),
    ("Senior Manager", "Senior Manager"),
    ("Sr. Manager", "Senior Manager"),
    ("Sr Manager", "Senior Manager"),
    ("Manager", "Manager"),
    # "Sr " / "Sr. " catch-all for IC titles (CrowdStrike uses "Sr Engineer",
    # etc.). Placed AFTER manager entries so "Sr Manager" still → Senior Manager.
    ("Sr. ", "Senior"),
    ("Sr ", "Senior"),
    ("Lead", "Lead"),
    ("Senior", "Senior"),
    ("Associate", "Associate"),
    ("Junior", "Junior"),
    ("Intern", "Intern"),
]
# Seniority toggles rendered ON by default at the top of the filter bar.
SENIORITY_TOGGLES = ["Manager", "Director"]

# =============================================================================
# Typical years-of-experience per (company, seniority label)
# =============================================================================
# Purple badge shown to the LEFT of the salary badge when we know the
# company's leveling grid. Values are indicative — real ranges vary and
# atypical profiles (founders, PhDs) enter higher. Sources: levels.fyi,
# published pay grids, engineering blog posts.
#
# Keyed by company name → seniority label (as produced by detect_seniority
# in config.SENIORITY). Missing entries just show no badge.
SENIORITY_XP = {
    "Google": {
        "Senior":       "~5y (L5)",
        "Staff":        "~10y (L6)",
        "Senior Staff": "~13y (L7)",
        "Principal":    "~15y+ (L8)",
        "Distinguished":"~20y+ (L9)",
    },
    "Meta": {
        "Senior":       "~6y (E5)",
        "Staff":        "~9y (E6)",
        "Senior Staff": "~12y (E7)",
        "Principal":    "~15y+ (E8)",
        "Distinguished":"~20y+ (E9)",
    },
    "Microsoft": {
        "Senior":       "~6-8y (63-64)",
        "Principal":    "~10-12y (65-66)",
    },
    "Apple": {
        "Senior":       "~5-7y (ICT4)",
        "Staff":        "~8-10y (ICT5)",
        "Principal":    "~12y+ (ICT6)",
    },
    "NVIDIA": {
        "Senior":       "~5-8y",
        "Staff":        "~10-12y",
        "Principal":    "~14y+",
        "Distinguished":"~18y+",
    },
    "OpenAI": {
        "Senior":       "~5y",
        "Staff":        "~10y",
        "Principal":    "~13y+",
    },
    "Anthropic": {
        "Senior":       "~5y (L4)",
        "Staff":        "~9y (L5)",
        "Senior Staff": "~12y (L6)",
    },
    "Stripe": {
        "Senior":       "~5y (L3)",
        "Staff":        "~8y (L4)",
        "Principal":    "~12y+ (L5)",
    },
    "Databricks": {
        "Senior":       "~5y",
        "Staff":        "~9y",
        "Principal":    "~13y+",
    },
    "Airbnb": {
        "Senior":       "~6y (L5)",
        "Staff":        "~9y (L6)",
        "Principal":    "~12y+ (L7)",
    },
    "Pinterest": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Roblox": {
        "Senior":       "~5y",
        "Principal":    "~10y+",
    },
    "Dropbox": {
        "Senior":       "~5y (IC4)",
        "Staff":        "~8y (IC5)",
        "Principal":    "~12y+ (IC6)",
    },
    "GitHub": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "GitLab": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Snowflake": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Cloudflare": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Datadog": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Discord": {
        "Senior":       "~5y",
        "Staff":        "~8y",
    },
    "Block": {
        "Senior":       "~5y (L4)",
        "Staff":        "~8y (L5)",
        "Principal":    "~12y+ (L6)",
    },
    "Robinhood": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Twilio": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Elastic": {
        "Senior":       "~5y",
        "Principal":    "~10y+",
    },
    "Cursor": {
        "Senior":       "~5y",
        "Staff":        "~8y",
    },
    "Perplexity": {
        "Senior":       "~5y",
        "Staff":        "~8y",
    },
    # --- Wave 6 additions ---
    "Adobe": {
        "Senior":       "~5y",
        "Staff":        "~9y",
        "Principal":    "~13y+",
    },
    "Salesforce": {
        "Senior":       "~5y",
        "Lead":         "~7y",
        "Principal":    "~10-12y",
    },
    "Intel": {
        "Senior":       "~5-8y",
        "Staff":        "~10y",
        "Principal":    "~13y+",
    },
    "PayPal": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "SAP": {
        "Senior":       "~5-7y",
        "Principal":    "~10y+",
    },
    "GitGuardian": {
        "Senior":       "~5y",
        "Staff":        "~8y",
    },
    # --- Wave 7 (2026-10-02) — big companies with public leveling grids ---
    "Cisco": {
        "Senior":       "~4y (G9)",
        "Lead":         "~7y (G10 Technical Leader)",
        "Staff":        "~8y (G10-11)",
        "Principal":    "~12y+ (G11-12)",
        "Distinguished":"~15y+ (G13)",
    },
    "LinkedIn": {
        "Senior":       "~5y (IC3)",
        "Staff":        "~8y (IC4)",
        "Senior Staff": "~11y (IC5)",
        "Principal":    "~15y+ (IC6)",
        "Distinguished":"~18y+ (IC7)",
    },
    "IBM": {
        "Senior":       "~5-7y (Band 8)",
        "Principal":    "~10-12y (STSM, Band 9)",
        "Distinguished":"~15y+ (Band 10)",
    },
    "Palantir": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
    "Qualcomm": {
        "Senior":       "~4y",
        "Staff":        "~7y",
        "Senior Staff": "~10y",
        "Principal":    "~14y+",
    },
    "CrowdStrike": {
        "Senior":       "~5y",
        "Staff":        "~8y",
        "Principal":    "~12y+",
    },
}

# Internal level codes (L4, L5, E5, IC5...) → years-of-experience, per company.
# Used as a FALLBACK when the title contains a level code but no seniority
# keyword (e.g. Netflix "Security Engineer (L5)" — detect_seniority returns
# nothing because "Senior" / "Staff" aren't in the title). Keyed by company
# name → uppercased level code (as produced by detect_ic_level). Values are
# the same free-text format as SENIORITY_XP.
IC_LEVEL_XP = {
    "Netflix": {
        # Netflix is famous for a flat IC ladder — L4 is the entry level
        # (no L1-L3), and multiple tiers of "Senior" exist. Source: levels.fyi.
        "L4": "~3y (entry IC)",
        "L5": "~6y (Senior)",
        "L6": "~9y (Staff)",
        "L7": "~12y+ (Principal)",
        "L8": "~15y+ (Distinguished)",
    },
    "Google": {
        "L3": "~1y (SWE II)",
        "L4": "~3y (SWE III)",
        "L5": "~5y (Senior)",
        "L6": "~10y (Staff)",
        "L7": "~13y (Senior Staff)",
        "L8": "~15y+ (Principal)",
        "L9": "~20y+ (Distinguished)",
    },
    "Meta": {
        "E3": "~1y",
        "E4": "~3y",
        "E5": "~6y (Senior)",
        "E6": "~9y (Staff)",
        "E7": "~12y (Senior Staff)",
        "E8": "~15y+ (Principal)",
        "E9": "~20y+ (Distinguished)",
    },
    "LinkedIn": {
        "IC3": "~5y (Senior)",
        "IC4": "~8y (Staff)",
        "IC5": "~11y (Senior Staff)",
        "IC6": "~15y+ (Principal)",
        "IC7": "~18y+ (Distinguished)",
    },
}

# Fallback used when a company isn't listed above (typical startup leveling).
# Rendered with a slightly different tooltip so the user knows it's generic.
# Keep this short — it's a last resort for small companies without published
# grids. Big-tech companies with real leveling grids should always get an
# explicit entry in SENIORITY_XP above.
SENIORITY_XP_DEFAULT = {
    "Senior":    "~5y",
    "Staff":     "~8y",
    "Principal": "~12y+",
}

# NOTE for future maintenance (also in CLAUDE.md):
# When adding a new source to SOURCES, consider whether its company has a
# known leveling grid (Cisco grades, IBM bands, Google L-levels, Meta
# E-levels, LinkedIn IC-levels, etc). If so, add an explicit SENIORITY_XP
# entry so the 🎓 badge shows the right numbers. Otherwise the generic
# SENIORITY_XP_DEFAULT fallback kicks in (~5y Senior / ~8y Staff / ~12y+
# Principal) — fine for startups, misleading for big companies with
# atypical bands.

# =============================================================================
# Sources — the boards to fetch
# =============================================================================
# Each entry is a dict:
#   name:     display name (shown in nav + section headings)
#   kind:     picks the fetcher (ashby, greenhouse, workable, phenom, apple,
#             google, microsoft, meta, ableton, lucca, pw)
#   slug:     ATS-specific slug or short identifier
#   queries:  list of search terms; empty [] = show everything
#   board:    (optional) public URL of the company's own careers page
#   search_url, link_re, origin, wait_selector: extra fields for `kind=pw`
#             (generic Playwright link scraper)

SOURCES = []  # loaded from data/user_config.py

# =============================================================================
# Company descriptions — small blurb + headcount + revenue shown next to the
# company header. Data from public sources (Crunchbase, LinkedIn, press,
# Wikipedia) as of end-2025 / early-2026 unless noted. Estimates are approx.
# Format: name → {"blurb": short one-liner, "employees": str, "revenue": str}
# Use "n/a" for missing data. Keep employees / revenue as strings — some are
# ranges ("~500"), some are ARR vs GAAP, mix as you find them.
# =============================================================================
COMPANY_INFO = {
    # --- Major AI Companies ---
    "OpenAI":      {"blurb": "Frontier AI lab, ChatGPT / GPT / Codex",              "employees": "~3,500",  "revenue": "$12B ARR (2025)"},
    "Anthropic":   {"blurb": "Frontier AI lab, Claude — safety-focused",             "employees": "~1,500",  "revenue": "$5B ARR (2025)"},
    "Mistral":     {"blurb": "European frontier AI lab (Paris)",                     "employees": "~250",    "revenue": "~$100M ARR"},
    "Cohere":      {"blurb": "Enterprise LLMs — RAG, embeddings",                    "employees": "~500",    "revenue": "~$100M ARR"},
    "HF":          {"blurb": "Hugging Face — open-source ML hub",                    "employees": "~500",    "revenue": "~$80M"},
    "Scale AI":    {"blurb": "Data-labeling for foundation models",                  "employees": "~1,000",  "revenue": "~$1B"},
    "DeepL":       {"blurb": "Machine translation (Cologne, DE)",                    "employees": "~1,000",  "revenue": "~$200M"},
    "Eleven Labs": {"blurb": "Voice AI / TTS",                                       "employees": "~200",    "revenue": "~$100M ARR"},
    "Sony AI":     {"blurb": "Sony's AI research org (music, imaging, gaming)",      "employees": "~200",    "revenue": "part of Sony ~$85B"},
    "Cursor":      {"blurb": "AI-native code editor (Anysphere)",                    "employees": "~100",    "revenue": "~$500M ARR"},

    # --- AI Startups ---
    "H":                     {"blurb": "H Company — Paris agent lab (ex-DeepMind founders)", "employees": "~50",     "revenue": "pre-revenue"},
    "AMI":                   {"blurb": "AMI Automation — no public info",                    "employees": "n/a",     "revenue": "n/a"},
    "SSI":                   {"blurb": "Safe Superintelligence (Ilya Sutskever)",            "employees": "~20",     "revenue": "pre-revenue"},
    "Thinking Machines":     {"blurb": "Mira Murati's lab (ex-OpenAI CTO)",                  "employees": "~50",     "revenue": "pre-revenue"},
    "Poolside":              {"blurb": "Code generation / dev tools AI",                    "employees": "~100",    "revenue": "pre-revenue"},
    "Black Forest Labs":     {"blurb": "Flux image models (ex-Stable Diffusion team)",       "employees": "~30",     "revenue": "n/a"},
    "Cognition":             {"blurb": "Devin — autonomous SWE agent",                       "employees": "~50",     "revenue": "~$50M ARR"},
    "Perplexity":            {"blurb": "AI-native search engine",                            "employees": "~200",    "revenue": "~$100M ARR"},
    "Modal":                 {"blurb": "Serverless GPU platform for AI",                     "employees": "~50",     "revenue": "~$20M ARR"},
    "Together AI":           {"blurb": "GPU inference cloud + open-source models",           "employees": "~100",    "revenue": "~$100M ARR"},
    "Fireworks AI":          {"blurb": "Fast LLM inference API",                             "employees": "~70",     "revenue": "~$40M ARR"},
    "Sakana AI":             {"blurb": "Tokyo AI lab — nature-inspired research",            "employees": "~30",     "revenue": "n/a"},
    "Prime Intellect":       {"blurb": "Distributed AI training",                            "employees": "~30",     "revenue": "n/a"},
    "Physical Intelligence": {"blurb": "Foundation models for robotics",                     "employees": "~70",     "revenue": "pre-revenue"},
    "Voyage AI":             {"blurb": "Retrieval embeddings (acquired by MongoDB 2025)",    "employees": "~30",     "revenue": "n/a"},
    "Rewind AI":             {"blurb": "Personal AI memory / assistant",                     "employees": "~30",     "revenue": "n/a"},
    "Replit":                {"blurb": "Browser-based coding + AI agent",                    "employees": "~150",    "revenue": "~$100M ARR"},
    "LangChain":             {"blurb": "LLM orchestration framework + LangSmith",            "employees": "~90",     "revenue": "~$20M ARR"},
    "Runway":                {"blurb": "Generative video (Gen-3)",                           "employees": "~120",    "revenue": "~$100M ARR"},
    "Pika":                  {"blurb": "Video generation from text/image",                    "employees": "~30",     "revenue": "n/a"},
    "Character AI":          {"blurb": "Character chatbots (Google licensed 2024)",           "employees": "~50",     "revenue": "~$30M ARR"},
    "Cerebras":              {"blurb": "Wafer-scale AI accelerators",                        "employees": "~500",    "revenue": "~$500M"},
    "Etched":                {"blurb": "Transformer ASIC chips (Sohu)",                      "employees": "~40",     "revenue": "pre-revenue"},
    "Tenstorrent":           {"blurb": "RISC-V AI chips (Jim Keller)",                       "employees": "~500",    "revenue": "~$150M"},
    "MatX":                  {"blurb": "LLM-optimized ASICs",                                "employees": "~40",     "revenue": "pre-revenue"},
    "Rain":                  {"blurb": "Neuromorphic AI chips",                              "employees": "~50",     "revenue": "n/a"},
    "Anyscale":              {"blurb": "Ray / distributed compute for AI",                   "employees": "~200",    "revenue": "~$60M ARR"},
    "Baseten":               {"blurb": "Model serving infra",                                "employees": "~100",    "revenue": "~$25M ARR"},
    "Coreweave":             {"blurb": "GPU cloud for AI (IPO'd 2025)",                     "employees": "~1,000",  "revenue": "$2B (2025)"},
    "Nebius":                {"blurb": "GPU cloud (ex-Yandex NBIS)",                        "employees": "~700",    "revenue": "~$500M"},
    "Crusoe":                {"blurb": "GPU cloud + gas-powered data centers",              "employees": "~600",    "revenue": "~$500M"},
    "Lambda":                {"blurb": "GPU cloud + on-prem workstations",                  "employees": "~400",    "revenue": "~$400M"},
    "Braintrust":            {"blurb": "LLM evaluation platform",                            "employees": "~40",     "revenue": "n/a"},
    "LlamaIndex":            {"blurb": "RAG framework for LLMs",                             "employees": "~30",     "revenue": "n/a"},
    "Nomic":                 {"blurb": "Nomic Embed + Atlas visualization",                  "employees": "~20",     "revenue": "n/a"},
    "Weaviate":              {"blurb": "Vector database (Amsterdam)",                        "employees": "~150",    "revenue": "~$20M ARR"},
    "Pinecone":              {"blurb": "Vector database SaaS",                               "employees": "~200",    "revenue": "~$50M ARR"},
    "Deepgram":              {"blurb": "Speech-to-text API",                                 "employees": "~250",    "revenue": "~$50M ARR"},
    "AssemblyAI":            {"blurb": "Speech understanding API",                           "employees": "~80",     "revenue": "~$25M ARR"},
    "Zed":                   {"blurb": "High-perf code editor (ex-Atom team)",              "employees": "~20",     "revenue": "n/a"},
    "Cline":                 {"blurb": "AI coding agent in VS Code",                        "employees": "~15",     "revenue": "n/a"},

    # --- Big Tech ---
    "Apple":     {"blurb": "iPhone, macOS, Logic Pro — Cupertino",                 "employees": "~164,000", "revenue": "$391B (2024)"},
    "Microsoft": {"blurb": "Azure, Windows, Office, GitHub, OpenAI investor",      "employees": "~228,000", "revenue": "$245B (2024)"},
    "Google":    {"blurb": "Search, Gemini, DeepMind, Cloud, Android",             "employees": "~183,000", "revenue": "$350B (2024)"},
    "Meta":      {"blurb": "Facebook, Instagram, WhatsApp, Reality Labs, Llama",   "employees": "~74,000",  "revenue": "$164B (2024)"},
    "NVIDIA":    {"blurb": "GPUs, CUDA, AI infrastructure",                        "employees": "~30,000",  "revenue": "$130B (FY25)"},
    "GitHub":    {"blurb": "Code hosting, Copilot (Microsoft subsidiary)",         "employees": "~3,000",   "revenue": "~$2B ARR"},
    "Proton":    {"blurb": "Privacy-first email/VPN/drive (Geneva)",               "employees": "~500",     "revenue": "~$150M"},
    "Airbnb":    {"blurb": "Short-term rentals marketplace",                       "employees": "~7,000",   "revenue": "$11B (2024)"},
    "LinkedIn":  {"blurb": "Professional network (Microsoft subsidiary)",          "employees": "~19,000",  "revenue": "$17B (2024)"},
    "Pinterest": {"blurb": "Visual discovery / social bookmarking",                "employees": "~4,500",   "revenue": "$3.6B (2024)"},
    "Discord":   {"blurb": "Voice/text chat platform (gaming/communities)",        "employees": "~1,000",   "revenue": "~$700M"},
    "Roblox":    {"blurb": "UGC gaming platform",                                  "employees": "~2,500",   "revenue": "$3.6B (2024)"},
    "Stripe":    {"blurb": "Payments infrastructure",                              "employees": "~8,500",   "revenue": "$4.5B (2024)"},
    "Twilio":    {"blurb": "Communications APIs (SMS, voice, email)",              "employees": "~5,500",   "revenue": "$4.4B (2024)"},
    "Dropbox":   {"blurb": "File storage / collaboration",                         "employees": "~2,500",   "revenue": "$2.5B (2024)"},
    "Block":     {"blurb": "Square, Cash App, Bitcoin (Jack Dorsey)",              "employees": "~13,000",  "revenue": "$24B (2024)"},
    "Robinhood": {"blurb": "Retail trading + crypto",                              "employees": "~2,300",   "revenue": "$2.8B (2024)"},

    # --- Security Companies ---
    "DepthFirst":      {"blurb": "AI-driven pentest / red-team automation",         "employees": "~30",     "revenue": "n/a"},
    "XBOW":            {"blurb": "AI pentesting agent",                             "employees": "~30",     "revenue": "n/a"},
    "Aisle":           {"blurb": "AI-native appsec (Y Combinator)",                 "employees": "~15",     "revenue": "n/a"},
    "ZeroPath":        {"blurb": "AI SAST / code security",                         "employees": "~15",     "revenue": "n/a"},
    "Pixee":           {"blurb": "Automated code fixes for vulns",                  "employees": "~30",     "revenue": "n/a"},
    "Corgea":          {"blurb": "AI vulnerability triage & fix",                   "employees": "~20",     "revenue": "n/a"},
    "CrowdStrike":     {"blurb": "Endpoint security (Falcon)",                      "employees": "~10,000", "revenue": "$3.9B (FY25)"},
    "Snyk":            {"blurb": "Developer-first appsec (SCA/SAST)",               "employees": "~1,200",  "revenue": "~$300M ARR"},
    "Semgrep":         {"blurb": "Static analysis / secrets scanning",              "employees": "~250",    "revenue": "~$50M ARR"},
    "Checkmarx":       {"blurb": "Enterprise appsec / SAST",                        "employees": "~1,000",  "revenue": "~$300M"},
    "Chainguard":      {"blurb": "Container / supply-chain security",               "employees": "~300",    "revenue": "~$100M ARR"},
    "Endor Labs":      {"blurb": "SCA / open-source dep security",                  "employees": "~150",    "revenue": "~$30M ARR"},
    "Socket":          {"blurb": "npm/pypi supply-chain security",                  "employees": "~50",     "revenue": "n/a"},
    "Wiz":             {"blurb": "Cloud security posture (~$32B valuation, ex-Google acq.)", "employees": "~1,600", "revenue": "$900M ARR"},
    "1Password":       {"blurb": "Password manager for enterprise/consumer",        "employees": "~1,200",  "revenue": "~$250M ARR"},
    "Okta":            {"blurb": "Identity / SSO enterprise",                       "employees": "~6,000",  "revenue": "$2.5B (FY25)"},
    "Cybereason":      {"blurb": "XDR endpoint defense",                            "employees": "~1,300",  "revenue": "~$200M"},
    "Elastic":         {"blurb": "Elasticsearch + Elastic Security SIEM",           "employees": "~3,700",  "revenue": "$1.3B (FY25)"},
    "Doppler":         {"blurb": "Secrets management for devs",                     "employees": "~30",     "revenue": "n/a"},
    "BeyondTrust":     {"blurb": "Privileged access management",                    "employees": "~1,500",  "revenue": "~$400M"},
    "Nord Security":   {"blurb": "NordVPN / NordPass",                              "employees": "~1,600",  "revenue": "~$400M"},
    "Bitwarden":       {"blurb": "Open-source password manager",                    "employees": "~250",    "revenue": "~$100M"},
    "Yubico":          {"blurb": "YubiKey hardware auth (Stockholm/US)",            "employees": "~500",    "revenue": "~$220M"},
    "SandboxAQ":       {"blurb": "Post-quantum crypto + AI/quantum simulation (ex-Alphabet)", "employees": "~500", "revenue": "n/a"},
    "Cape Privacy":    {"blurb": "FHE / privacy-preserving ML",                     "employees": "~30",     "revenue": "n/a"},
    "Cloudflare":      {"blurb": "CDN, DDoS, Zero Trust, Workers",                  "employees": "~4,000",  "revenue": "$1.7B (2024)"},

    # --- Other (dev tools / data / enterprise / FR-EU) ---
    "HashiCorp":  {"blurb": "Terraform, Vault, Nomad (IBM acquired 2025)",           "employees": "~2,300",  "revenue": "$650M"},
    "GitLab":     {"blurb": "DevOps platform, all-remote",                           "employees": "~2,000",  "revenue": "$760M (FY25)"},
    "Databricks": {"blurb": "Lakehouse + AI/ML platform",                            "employees": "~7,500",  "revenue": "$3B ARR"},
    "Snowflake":  {"blurb": "Cloud data warehouse",                                  "employees": "~7,600",  "revenue": "$3.6B (FY25)"},
    "Alan":       {"blurb": "Health insurance disruptor (Paris)",                    "employees": "~600",    "revenue": "~$450M"},
    "Datadog":    {"blurb": "Observability / APM / logs",                            "employees": "~7,700",  "revenue": "$2.7B (2024)"},
    "Dataiku":    {"blurb": "Enterprise data science / ML platform (Paris/NYC)",     "employees": "~1,200",  "revenue": "~$300M"},
    "Doctolib":   {"blurb": "Healthcare booking platform (FR/DE)",                   "employees": "~2,800",  "revenue": "~$300M"},
    "Fastly":     {"blurb": "Edge CDN / compute",                                    "employees": "~1,100",  "revenue": "$544M (2024)"},
    "Owkin":      {"blurb": "Federated ML for pharma / biotech (Paris/NY)",          "employees": "~250",    "revenue": "n/a"},
    "Qonto":      {"blurb": "SME neo-bank (Paris)",                                  "employees": "~1,600",  "revenue": "~$250M"},

    # --- Music Companies ---
    "Ableton":         {"blurb": "Ableton Live DAW (Berlin)",                         "employees": "~350",    "revenue": "~$100M"},
    "Arturia":         {"blurb": "Synth software/hardware (Grenoble)",                "employees": "~100",    "revenue": "~$50M"},
    "Neural DSP":      {"blurb": "Guitar amp modelling (Helsinki)",                   "employees": "~90",     "revenue": "~$40M"},
    "Steinberg":       {"blurb": "Cubase, Nuendo, VST (Hamburg, Yamaha subsidiary)",  "employees": "~250",    "revenue": "n/a"},
    "Suno":            {"blurb": "AI music generation",                                "employees": "~50",     "revenue": "~$120M ARR"},
    "Udio":            {"blurb": "AI music generation (ex-DeepMind team)",             "employees": "~30",     "revenue": "n/a"},
    "Fender":          {"blurb": "Guitars, amps, apps (Scottsdale AZ)",               "employees": "~2,000",  "revenue": "~$900M"},
    "Universal Audio": {"blurb": "Studio audio interfaces + plugins",                  "employees": "~350",    "revenue": "~$150M"},
    "Slate Digital":   {"blurb": "Audio plugins + hardware",                           "employees": "~50",     "revenue": "n/a"},
    "Output":          {"blurb": "Sample libraries + AI music tools (LA)",             "employees": "~80",     "revenue": "n/a"},
    "Pioneer DJ":      {"blurb": "DJ hardware / software (AlphaTheta)",                "employees": "~500",    "revenue": "~$300M"},
    "Spitfire Audio":  {"blurb": "Cinematic sample libraries (London)",                "employees": "~100",    "revenue": "~$40M"},
    "Splice":          {"blurb": "Music sample subscription platform",                 "employees": "~200",    "revenue": "~$80M"},

    # --- Wave 5 (music hardware, 2026-09-28) ---
    "Softube":              {"blurb": "Swedish audio plugin developer — physical modelling of vintage analog gear + Console 1 controller.", "employees": "~80",  "revenue": "~$30M"},
    "inMusic Brands":       {"blurb": "Music-tech conglomerate (Numark, Denon DJ, Rane, Alesis, M-Audio, Marantz Pro, Moog Music). US HQ, aggressive M&A strategy in DJ/production hardware.", "employees": "~1,000", "revenue": "~$400M"},
    "Yamaha":               {"blurb": "Japanese conglomerate — pianos, synths, guitars, PA, motorcycles, semiconductors. Umantis-hosted German recruiting portal covers the corporate music side.", "employees": "~20,000", "revenue": "$16B (FY24)"},
    "Sonos":                {"blurb": "Wireless multi-room speakers and home audio ecosystem. Santa Barbara CA HQ. Strong DSP + firmware + iOS/Android team. Public (Nasdaq).", "employees": "~1,500", "revenue": "$1.5B (FY24)"},
    "Sennheiser":           {"blurb": "German premium audio — microphones, headphones, wireless mics. Consumer division sold to Sonova 2021; pro audio + business stayed independent. Wedemark HQ.", "employees": "~2,500", "revenue": "~$900M"},
    "Bose":                 {"blurb": "US audio manufacturer — noise-cancelling headphones, home audio, automotive. Framingham MA HQ. Private, owned by MIT (founder's donation).", "employees": "~7,000", "revenue": "~$3.5B"},
    "Roland":               {"blurb": "Japanese electronic music instruments — synths, DAWs, drum machines, e-drums. TR-808, TB-303, Juno legacy. Public (TSE).", "employees": "~2,900", "revenue": "~$700M"},
    "Marshall":             {"blurb": "British guitar amp icon (Marshall stacks). Plus Marshall Headphones spin-off. Bletchley HQ.", "employees": "~800", "revenue": "~$200M"},
    "Elektron":             {"blurb": "Swedish groovebox / synth maker (Digitakt, Digitone, Analog series). Gothenburg HQ. ~90 people. Cult following among electronic producers.", "employees": "~90", "revenue": "~$30M"},
    "Seymour Duncan":       {"blurb": "US pickup + pedal maker (JB, '59, humbuckers). Santa Barbara CA HQ. Family-run since 1978.", "employees": "~150", "revenue": "~$40M"},
    "Dolby":                {"blurb": "US audio/video technology powerhouse — Dolby Atmos, Dolby Vision, Dolby Digital codecs. San Francisco HQ. Public (Nyse). Heavy DSP + video codec research.", "employees": "~2,500", "revenue": "$1.3B (FY24)"},
    "MOTU":                 {"blurb": "Mark of the Unicorn — Digital Performer DAW + audio interfaces (Ultralite, 828). Cambridge MA HQ. Small, deep DAW/DSP culture.", "employees": "~50", "revenue": "n/a"},
    "Boris FX / iZotope":   {"blurb": "Boris FX group — video/audio VFX tools including Continuum, Sapphire, Mocha (VFX) + iZotope RX/Ozone/Neutron (audio ML). Boston HQ. Iconic post-prod names.", "employees": "~200", "revenue": "n/a"},
    "Boss":                 {"blurb": "Roland's guitar pedal / effects brand — DS-1, Metal Zone, RC-series loopers. Job listings on the shared employment_opportunities page.", "employees": "part of Roland", "revenue": "part of Roland"},

    # --- Wave 6: Big Tech / GAFAM-adjacent (verified working) ---
    "Adobe":                {"blurb": "Creative Cloud, Photoshop, Premiere, Firefly. Public — San Jose HQ. Big focus on generative AI integration since 2024.", "employees": "~30,000", "revenue": "$21B (FY24)"},
    "Salesforce":           {"blurb": "CRM giant — plus Slack, Tableau, MuleSoft. San Francisco HQ. Agentforce / Einstein AI push since 2024.", "employees": "~75,000", "revenue": "$35B (FY25)"},
    "Intel":                {"blurb": "US chip giant — CPUs (Core, Xeon), foundry push. Santa Clara HQ. Ongoing turnaround vs TSMC / AMD.", "employees": "~110,000", "revenue": "$54B (FY24)"},
    "PayPal":               {"blurb": "Payments / Braintrust / Venmo. San Jose HQ. Big fintech security + fraud focus.", "employees": "~24,000", "revenue": "$32B (FY24)"},
    "SAP":                  {"blurb": "German enterprise ERP giant — S/4HANA, SuccessFactors, Ariba. Walldorf HQ. Strong security + crypto team.", "employees": "~110,000", "revenue": "€34B (FY24)"},
    "GitGuardian":          {"blurb": "French secrets-scanning + non-human identity security — scans GitHub / GitLab / Bitbucket for leaked credentials. Paris HQ.", "employees": "~150", "revenue": "~$30M ARR"},
    "Palantir":             {"blurb": "Foundry (government + enterprise analytics) + AIP. Denver HQ. Public — NYSE. Classified / defense work.", "employees": "~4,000", "revenue": "$2.9B (FY24)"},
    "Netflix":              {"blurb": "Streaming + original content + gaming. Los Gatos CA HQ. Very strong security + ML infra teams.", "employees": "~14,000", "revenue": "$39B (FY24)"},
    "Cisco":                {"blurb": "Networking + security giant — Catalyst, Umbrella, Duo, Splunk (post-acquisition). San Jose HQ.", "employees": "~85,000", "revenue": "$54B (FY24)"},
    "Unity":                {"blurb": "Game engine (Unity3D) + ad / live-ops / Weta Digital VFX. San Francisco HQ. Public — Nasdaq.", "employees": "~5,500", "revenue": "~$1.8B"},
    "Qualcomm":             {"blurb": "Mobile SoC leader (Snapdragon), 5G modems, auto AI. San Diego HQ. Strong IP licensing engine.", "employees": "~50,000", "revenue": "$38B (FY24)"},
    "IBM":                  {"blurb": "Hybrid cloud (Red Hat), AI (watsonx), consulting, mainframes. Armonk NY HQ. Deep security + crypto practice.", "employees": "~280,000", "revenue": "$62B (FY24)"},
    "VMware (Broadcom)":    {"blurb": "VMware (vSphere, NSX, Carbon Black) under Broadcom since late 2023. Palo Alto HQ. Heavy virt / networking / security.", "employees": "~30,000", "revenue": "n/a (part of Broadcom's $52B)"},
    "Avid":                 {"blurb": "Pro Tools DAW + Media Composer NLE — the pro-audio / film-editing standard. Burlington MA HQ.", "employees": "~1,400", "revenue": "~$400M"},

    # --- Added via catalog expansion 2026-10-06 ---------------------------
    # AI Startups
    "Imbue":            {"blurb": "Reasoning agents for software (ex-Generally Intelligent). SF HQ.",                                                    "employees": "~40",  "revenue": "pre-revenue"},
    # Security Companies
    "Netskope":         {"blurb": "Cloud security — SASE / SSE / CASB. Santa Clara HQ. Public filing on hold; late-stage.",                              "employees": "~3,000", "revenue": "~$500M ARR"},
    "PQShield":         {"blurb": "Post-quantum cryptography IP + libraries (NIST PQC standards). Oxford, UK HQ.",                                       "employees": "~80",    "revenue": "n/a"},
    "Tailscale":        {"blurb": "WireGuard-based mesh VPN / zero-trust networking. Toronto HQ.",                                                       "employees": "~150",   "revenue": "~$50M ARR"},
    # Other — dev tools / SaaS / fintech
    "Brex":             {"blurb": "Corporate cards + banking / expense mgmt for startups. SF HQ.",                                                        "employees": "~1,000", "revenue": "~$400M"},
    "Figma":            {"blurb": "Collaborative design & prototyping. SF HQ. Public (IPO 2025).",                                                        "employees": "~1,500", "revenue": "~$900M ARR"},
    "Grafana Labs":     {"blurb": "Observability — Grafana, Loki, Mimir, Tempo, Pyroscope. NYC + remote-first.",                                           "employees": "~1,100", "revenue": "~$300M ARR"},
    "Hex":              {"blurb": "Collaborative data notebooks (SQL + Python + viz). SF HQ.",                                                             "employees": "~250",   "revenue": "~$40M ARR"},
    "Linear":           {"blurb": "Issue tracking + project mgmt for software teams. Remote-first (Europe heavy).",                                        "employees": "~70",    "revenue": "~$50M ARR"},
    "Mercury":          {"blurb": "Banking + treasury for startups. SF HQ.",                                                                               "employees": "~800",   "revenue": "~$500M"},
    "Vercel":           {"blurb": "Hosting + edge network built around Next.js. SF HQ.",                                                                   "employees": "~500",   "revenue": "~$200M ARR"},
    # --- Added 2026-10-06 (batch 2) ---------------------------------------
    # AI Startups
    "Reka":             {"blurb": "Multimodal frontier models (Reka Core, Flash). SF HQ, ex-DeepMind founders.",                                            "employees": "~50",    "revenue": "pre-revenue"},
    "Lightning AI":     {"blurb": "PyTorch Lightning + Lightning Studio IDE for AI. NYC HQ.",                                                               "employees": "~80",    "revenue": "~$15M ARR"},
    "Observe AI":       {"blurb": "AI-powered conversation intelligence for contact centers. SF HQ.",                                                       "employees": "~500",   "revenue": "~$60M ARR"},
    # Security Companies
    "Drata":            {"blurb": "Compliance automation + continuous monitoring. San Diego HQ.",                                                           "employees": "~500",   "revenue": "~$80M ARR"},
    # Other
    "Fivetran":         {"blurb": "Automated data pipelines (ELT) into data warehouses. Oakland HQ.",                                                       "employees": "~1,300", "revenue": "~$350M ARR"},
    "MongoDB":          {"blurb": "Document database + Atlas managed service. NYC HQ. Public (MDB).",                                                       "employees": "~5,500", "revenue": "~$1.9B"},
    "Reddit":           {"blurb": "Social news + discussion platform. SF HQ. Public (RDDT).",                                                               "employees": "~2,000", "revenue": "~$1.3B"},
}

# Merge in the long-form blurbs kept in config_blurbs.py. Any name present in
# BLURBS overrides the short blurb above; other entries keep the short version.
try:
    from config_blurbs import BLURBS as _LONG_BLURBS
    for _name, _long in _LONG_BLURBS.items():
        if _name in COMPANY_INFO:
            COMPANY_INFO[_name]["blurb"] = _long
        else:
            COMPANY_INFO[_name] = {"blurb": _long, "employees": "n/a", "revenue": "n/a"}
except ImportError:
    pass


# =============================================================================
# Grouping — sections in the nav and HTML
# =============================================================================
GROUP_ORDER = [
    "Big Tech",
    "Major AI Companies",
    "AI Startups",
    "Startups",
    "Security Companies",
    "FHE",
    "Blockchain",
    "Cars",
    "Media",
    "Welcome to the Jungle",
    "Other",
    "Music Companies",
]
# name → group. Missing entries fall back to "Other".
GROUP_OF = {
    # Welcome to the Jungle (via api.welcometothejungle.com/api/v3)
    # 2026-10-07 — 14 verified (via debug/probe_wttj_slug_fixer.py),
    # 7 with wrong slug still searching for the real one (via
    # debug/probe_wttj_slug_find.py). Per CLAUDE.md, non-working
    # entries are KEPT (with TODO comment in catalog.py), not removed.
    "Zama": "FHE",
    "Aircall": "Welcome to the Jungle",
    "Back Market": "Welcome to the Jungle",
    "BlaBlaCar": "Welcome to the Jungle",
    "Contentsquare": "Welcome to the Jungle",
    "Deezer": "Welcome to the Jungle",
    "Getaround": "Welcome to the Jungle",
    "Spendesk": "Welcome to the Jungle",
    "PayFit": "Welcome to the Jungle",
    "Swile": "Welcome to the Jungle",
    "Malt": "Welcome to the Jungle",
    "Mirakl": "Welcome to the Jungle",
    "OpenClassrooms": "Welcome to the Jungle",
    "Pigment": "Welcome to the Jungle",
    "360Learning": "Welcome to the Jungle",
    "Shift Technology": "Welcome to the Jungle",
    "Vestiaire Collective": "Welcome to the Jungle",
    "Withings": "Welcome to the Jungle",
    "Yousign": "Welcome to the Jungle",
    "Lifen": "Welcome to the Jungle",
    "Lydia": "Welcome to the Jungle",
    '6sense': "Welcome to the Jungle",
    'ABBYY': "Welcome to the Jungle",
    'AbCellera Biologics': "Welcome to the Jungle",
    'Abnormal Security': "Welcome to the Jungle",
    'Abridge': "Welcome to the Jungle",
    'Acadenice': "Welcome to the Jungle",
    'ACAI Travel': "Welcome to the Jungle",
    'acceldata': "Welcome to the Jungle",
    'Achievers': "Welcome to the Jungle",
    'ActiveCampaign': "Welcome to the Jungle",
    'Ada': "Welcome to the Jungle",
    'Adthena': "Welcome to the Jungle",
    'Aera Technology': "Welcome to the Jungle",
    'Aeva': "Welcome to the Jungle",
    'Agility Robotics': "Welcome to the Jungle",
    'AiDash': "Welcome to the Jungle",
    'Aidence': "Welcome to the Jungle",
    'Aily Labs': "Welcome to the Jungle",
    'Air Space Intelligence': "Welcome to the Jungle",
    'AirDNA': "Welcome to the Jungle",
    'AISI': "Welcome to the Jungle",
    'AKASA': "Welcome to the Jungle",
    'akirolabs': "Welcome to the Jungle",
    'AKUR8': "Welcome to the Jungle",
    'Alation': "Welcome to the Jungle",
    'AlayaCare': "Welcome to the Jungle",
    'ALCYCONIE': "Welcome to the Jungle",
    'Alethea': "Welcome to the Jungle",
    'Alluxio': "Welcome to the Jungle",
    'Altana': "Welcome to the Jungle",
    'Alteryx': "Welcome to the Jungle",
    'Ambience Healthcare': "Welcome to the Jungle",
    'AMP': "Welcome to the Jungle",
    'Amperity': "Welcome to the Jungle",
    'Amplemarket': "Welcome to the Jungle",
    'Anomali': "Welcome to the Jungle",
    'Anvilogic': "Welcome to the Jungle",
    'Apheris': "Welcome to the Jungle",
    'Applied Intuition': "Welcome to the Jungle",
    'Applovin': "Welcome to the Jungle",
    'AppZen': "Welcome to the Jungle",
    'Aqemia': "Welcome to the Jungle",
    'Aqua Security': "Welcome to the Jungle",
    'Arctic Wolf': "Welcome to the Jungle",
    'Argile': "Welcome to the Jungle",
    'Arista': "Welcome to the Jungle",
    'Arondite': "Welcome to the Jungle",
    'ASAPP': "Welcome to the Jungle",
    'Ask for the moon': "Welcome to the Jungle",
    'AssetWatch': "Welcome to the Jungle",
    'Astera Labs': "Welcome to the Jungle",
    'Ataccama': "Welcome to the Jungle",
    'Atomic AI': "Welcome to the Jungle",
    'AutogenAI': "Welcome to the Jungle",
    'AutoLeadStar': "Welcome to the Jungle",
    'Automation Anywhere': "Welcome to the Jungle",
    'AVEVA': "Welcome to the Jungle",
    'Axelera AI': "Welcome to the Jungle",
    'Axion Ray': "Welcome to the Jungle",
    'Axuall': "Welcome to the Jungle",
    'AZmed': "Welcome to the Jungle",
    'Babbar': "Welcome to the Jungle",
    'Banz-Ai': "Welcome to the Jungle",
    'Basetwo': "Welcome to the Jungle",
    'Beacon Biosignals': "Welcome to the Jungle",
    'Beam': "Welcome to the Jungle",
    'Bear Robotics': "Welcome to the Jungle",
    'Berkshire Grey': "Welcome to the Jungle",
    'BigHat Biosciences': "Welcome to the Jungle",
    'Billy Grace': "Welcome to the Jungle",
    'Bizzdesign': "Welcome to the Jungle",
    'Blackbird AI': "Welcome to the Jungle",
    'BlackSky Global': "Welcome to the Jungle",
    'Blend': "Welcome to the Jungle",
    'Blue J Legal': "Welcome to the Jungle",
    'Blue River Technology': "Welcome to the Jungle",
    'Breek': "Welcome to the Jungle",
    'Brighter AI': "Welcome to the Jungle",
    'BrightHire': "Welcome to the Jungle",
    'BulQ': "Welcome to the Jungle",
    'Burq': "Welcome to the Jungle",
    'Bynder': "Welcome to the Jungle",
    'C3.ai': "Welcome to the Jungle",
    'CAiDENN': "Welcome to the Jungle",
    'Campus Cyber': "Welcome to the Jungle",
    'Candid Health': "Welcome to the Jungle",
    'Canoe': "Welcome to the Jungle",
    'Capmo': "Welcome to the Jungle",
    'Caspar Health': "Welcome to the Jungle",
    'CAST AI': "Welcome to the Jungle",
    'CB Insights': "Welcome to the Jungle",
    'Chalk': "Welcome to the Jungle",
    'Chance': "Welcome to the Jungle",
    'Character.ai': "Welcome to the Jungle",
    'Checkr': "Welcome to the Jungle",
    'CI&T': "Welcome to the Jungle",
    'Circus Group': "Welcome to the Jungle",
    'Citizen Health': "Welcome to the Jungle",
    'Citylitics': "Welcome to the Jungle",
    'Cleerly': "Welcome to the Jungle",
    'Cloudera': "Welcome to the Jungle",
    'CO2 AI': "Welcome to the Jungle",
    'Code Metal': "Welcome to the Jungle",
    'Cognism': "Welcome to the Jungle",
    'Cohere Health': "Welcome to the Jungle",
    'CommerceIQ': "Welcome to the Jungle",
    'Connectly.ai': "Welcome to the Jungle",
    'Coralogix': "Welcome to the Jungle",
    'Corelight': "Welcome to the Jungle",
    'Counsel Health': "Welcome to the Jungle",
    'Coupa': "Welcome to the Jungle",
    'Co–Star Astrology': "Welcome to the Jungle",
    'Creative Fabrica': "Welcome to the Jungle",
    'Credo AI': "Welcome to the Jungle",
    'Cresta': "Welcome to the Jungle",
    'CrewAI': "Welcome to the Jungle",
    'Current AI': "Welcome to the Jungle",
    'Cyberhaven': "Welcome to the Jungle",
    'd-Matrix': "Welcome to the Jungle",
    'Darktrace': "Welcome to the Jungle",
    'Dashmote': "Welcome to the Jungle",
    'DataRobot': "Welcome to the Jungle",
    'Datasnipper': "Welcome to the Jungle",
    'DealHub.io': "Welcome to the Jungle",
    'DEFCON AI': "Welcome to the Jungle",
    'Defense Unicorns': "Welcome to the Jungle",
    'Delphina': "Welcome to the Jungle",
    'Descript': "Welcome to the Jungle",
    'DevRev': "Welcome to the Jungle",
    'Dext France': "Welcome to the Jungle",
    'Dexterity': "Welcome to the Jungle",
    'Diligent Robotics': "Welcome to the Jungle",
    'DISCO': "Welcome to the Jungle",
    'Distyl': "Welcome to the Jungle",
    'Doma': "Welcome to the Jungle",
    'Domino Data Lab': "Welcome to the Jungle",
    'Doppel': "Welcome to the Jungle",
    'Doxel': "Welcome to the Jungle",
    'Drips': "Welcome to the Jungle",
    'DXC Technology': "Welcome to the Jungle",
    'Ed.ai': "Welcome to the Jungle",
    'EGYM': "Welcome to the Jungle",
    'Eleos Health': "Welcome to the Jungle",
    'Elixirr': "Welcome to the Jungle",
    'Ello': "Welcome to the Jungle",
    'Ema': "Welcome to the Jungle",
    'Emburse': "Welcome to the Jungle",
    'EnergyHub': "Welcome to the Jungle",
    'Enova': "Welcome to the Jungle",
    'Entera': "Welcome to the Jungle",
    'Enterpret': "Welcome to the Jungle",
    'Ethyca': "Welcome to the Jungle",
    'eToro': "Welcome to the Jungle",
    'EVA.AI': "Welcome to the Jungle",
    'EvenUp': "Welcome to the Jungle",
    'ever-T': "Welcome to the Jungle",
    'EvolutionIQ': "Welcome to the Jungle",
    'Evolv Technology': "Welcome to the Jungle",
    'Exa': "Welcome to the Jungle",
    'Exiger': "Welcome to the Jungle",
    'Expat-U': "Welcome to the Jungle",
    'ExtraHop': "Welcome to the Jungle",
    'Fairmarkit': "Welcome to the Jungle",
    'Fiddler AI': "Welcome to the Jungle",
    'Figure': "Welcome to the Jungle",
    'FinQuery': "Welcome to the Jungle",
    'Firsthand': "Welcome to the Jungle",
    'Flo': "Welcome to the Jungle",
    'Flock': "Welcome to the Jungle",
    'Flock Safety': "Welcome to the Jungle",
    'FlowX.AI': "Welcome to the Jungle",
    'Fonio.ai': "Welcome to the Jungle",
    'Forma.ai': "Welcome to the Jungle",
    'Forter': "Welcome to the Jungle",
    'Fourth': "Welcome to the Jungle",
    'FRANCE IA': "Welcome to the Jungle",
    'French Tech Grand Paris': "Welcome to the Jungle",
    'Front': "Welcome to the Jungle",
    'GIC': "Welcome to the Jungle",
    'Glia': "Welcome to the Jungle",
    'Globality': "Welcome to the Jungle",
    'GoDaddy': "Welcome to the Jungle",
    'GoGuardian': "Welcome to the Jungle",
    'Govini': "Welcome to the Jungle",
    'GPTZero': "Welcome to the Jungle",
    'Graphcore': "Welcome to the Jungle",
    'Grayce': "Welcome to the Jungle",
    'H2O.ai': "Welcome to the Jungle",
    'HackerRank': "Welcome to the Jungle",
    'Hadrian': "Welcome to the Jungle",
    'Halcyon': "Welcome to the Jungle",
    'HarfangLab': "Welcome to the Jungle",
    'Hayden AI': "Welcome to the Jungle",
    'Healx': "Welcome to the Jungle",
    'Hedra': "Welcome to the Jungle",
    'Hippocratic AI': "Welcome to the Jungle",
    'HOLENEK INGENIERIE': "Welcome to the Jungle",
    'honeysales': "Welcome to the Jungle",
    'Hopper': "Welcome to the Jungle",
    'Horizon Surgical Systems': "Welcome to the Jungle",
    'Horizon3': "Welcome to the Jungle",
    'HP Enterprise': "Welcome to the Jungle",
    'Hugging Face': "Welcome to the Jungle",
    'Humanoid': "Welcome to the Jungle",
    'HumanSignal': "Welcome to the Jungle",
    'Hume AI': "Welcome to the Jungle",
    'Hypatos': "Welcome to the Jungle",
    'Hyperbolic': "Welcome to the Jungle",
    'Hyperscience': "Welcome to the Jungle",
    'Icertis': "Welcome to the Jungle",
    'Ideogram': "Welcome to the Jungle",
    'IEX': "Welcome to the Jungle",
    'Illuma Technology': "Welcome to the Jungle",
    'Imagen Technologies': "Welcome to the Jungle",
    'Incode Technologies': "Welcome to the Jungle",
    'Innovapptive': "Welcome to the Jungle",
    'Insurify': "Welcome to the Jungle",
    'Intenseye': "Welcome to the Jungle",
    'Intent HQ': "Welcome to the Jungle",
    'Intrinsic': "Welcome to the Jungle",
    'IoT Valley': "Welcome to the Jungle",
    'IQVIA': "Welcome to the Jungle",
    'Ironclad': "Welcome to the Jungle",
    'Iterative Health': "Welcome to the Jungle",
    'Ivo AI Inc': "Welcome to the Jungle",
    'Jacobian': "Welcome to the Jungle",
    'Jampp': "Welcome to the Jungle",
    'January': "Welcome to the Jungle",
    'Jellyfish': "Welcome to the Jungle",
    'Jumio': "Welcome to the Jungle",
    'K Health': "Welcome to the Jungle",
    'Kalepa': "Welcome to the Jungle",
    'Kayrros': "Welcome to the Jungle",
    'kea': "Welcome to the Jungle",
    'Ketryx': "Welcome to the Jungle",
    'Kinetic': "Welcome to the Jungle",
    'KINEXON': "Welcome to the Jungle",
    'KNIME': "Welcome to the Jungle",
    'Kodiak Robotics': "Welcome to the Jungle",
    'Kody': "Welcome to the Jungle",
    'Kontakt.io': "Welcome to the Jungle",
    'Labelbox': "Welcome to the Jungle",
    'Landbot': "Welcome to the Jungle",
    'LanguageWire': "Welcome to the Jungle",
    'Leah AI': "Welcome to the Jungle",
    'LeanDNA': "Welcome to the Jungle",
    'Lendbuzz': "Welcome to the Jungle",
    'Levelpath': "Welcome to the Jungle",
    'Lexroom': "Welcome to the Jungle",
    'Lightmatter': "Welcome to the Jungle",
    'LogicMonitor': "Welcome to the Jungle",
    'Loopio': "Welcome to the Jungle",
    'LoopMe': "Welcome to the Jungle",
    'mabl': "Welcome to the Jungle",
    'MadHive': "Welcome to the Jungle",
    'Magic': "Welcome to the Jungle",
    'Mapp': "Welcome to the Jungle",
    'Mashgin': "Welcome to the Jungle",
    'Matic': "Welcome to the Jungle",
    'Matroid': "Welcome to the Jungle",
    'Mechanical Orchard': "Welcome to the Jungle",
    'Merantix': "Welcome to the Jungle",
    'Mercanis': "Welcome to the Jungle",
    'Merlin Labs': "Welcome to the Jungle",
    'Metropolis': "Welcome to the Jungle",
    'Mintlify': "Welcome to the Jungle",
    'Mirage': "Welcome to the Jungle",
    'Mithril': "Welcome to the Jungle",
    'Modular': "Welcome to the Jungle",
    'Moloco': "Welcome to the Jungle",
    'MotherDuck': "Welcome to the Jungle",
    'Motive': "Welcome to the Jungle",
    'MRI Software': "Welcome to the Jungle",
    'Multiverse': "Welcome to the Jungle",
    'Multiverse Computing': "Welcome to the Jungle",
    'Music World Media': "Welcome to the Jungle",
    'Mutiny': "Welcome to the Jungle",
    'Naratis': "Welcome to the Jungle",
    'NavVis': "Welcome to the Jungle",
    'Nayya': "Welcome to the Jungle",
    'NEC Software Solutions': "Welcome to the Jungle",
    'Netomi': "Welcome to the Jungle",
    'Netradyne': "Welcome to the Jungle",
    'NewsBreak': "Welcome to the Jungle",
    'NewtonX': "Welcome to the Jungle",
    'NextRoll': "Welcome to the Jungle",
    'Nooks': "Welcome to the Jungle",
    'Norm AI': "Welcome to the Jungle",
    'Normal Computing': "Welcome to the Jungle",
    'Northbeam': "Welcome to the Jungle",
    'Nosto': "Welcome to the Jungle",
    'nuvo': "Welcome to the Jungle",
    'Obligo': "Welcome to the Jungle",
    'Observe.AI': "Welcome to the Jungle",
    'ODAIA': "Welcome to the Jungle",
    'OLX Group': "Welcome to the Jungle",
    'Omaha Insights': "Welcome to the Jungle",
    'Omnea': "Welcome to the Jungle",
    'Omnidian': "Welcome to the Jungle",
    'OnCorps AI': "Welcome to the Jungle",
    'Onebrief': "Welcome to the Jungle",
    'Ontra': "Welcome to the Jungle",
    'Open Cosmos': "Welcome to the Jungle",
    'OpenText': "Welcome to the Jungle",
    'Oportun': "Welcome to the Jungle",
    'Optimove': "Welcome to the Jungle",
    'Orasio': "Welcome to the Jungle",
    'Orum': "Welcome to the Jungle",
    'Osaro': "Welcome to the Jungle",
    'OTERIA': "Welcome to the Jungle",
    'Otter.ai': "Welcome to the Jungle",
    'Outreach': "Welcome to the Jungle",
    'Overstory': "Welcome to the Jungle",
    'Owl Labs': "Welcome to the Jungle",
    'Pagaya Investments': "Welcome to the Jungle",
    'PagerDuty': "Welcome to the Jungle",
    'PAIR Finance': "Welcome to the Jungle",
    'Pallet': "Welcome to the Jungle",
    'Panaya': "Welcome to the Jungle",
    'Pano AI': "Welcome to the Jungle",
    'Papaya': "Welcome to the Jungle",
    'Parloa': "Welcome to the Jungle",
    'Partnerize': "Welcome to the Jungle",
    'PathAI': "Welcome to the Jungle",
    'Pathway': "Welcome to the Jungle",
    'Pattern Bioscience': "Welcome to the Jungle",
    'PayZen': "Welcome to the Jungle",
    'Pearl': "Welcome to the Jungle",
    'Pentera': "Welcome to the Jungle",
    'People.ai': "Welcome to the Jungle",
    'PermitFlow': "Welcome to the Jungle",
    'Perplexity AI': "Welcome to the Jungle",
    'Personalis': "Welcome to the Jungle",
    'Phagos': "Welcome to the Jungle",
    'Phaidra': "Welcome to the Jungle",
    'Pimloc': "Welcome to the Jungle",
    'Pinewood.AI': "Welcome to the Jungle",
    'Plain Concepts': "Welcome to the Jungle",
    'Plume Design': "Welcome to the Jungle",
    'PlusAI': "Welcome to the Jungle",
    'Pony.ai': "Welcome to the Jungle",
    'Praktika.ai': "Welcome to the Jungle",
    'Procurement Sciences AI': "Welcome to the Jungle",
    'Protex AI': "Welcome to the Jungle",
    'Proton.ai': "Welcome to the Jungle",
    'Proximie': "Welcome to the Jungle",
    'PulsePoint': "Welcome to the Jungle",
    'Pyl.tech': "Welcome to the Jungle",
    'Pôle Sud': "Welcome to the Jungle",
    'Quantexa': "Welcome to the Jungle",
    'quantilope': "Welcome to the Jungle",
    'Quantinuum': "Welcome to the Jungle",
    'Quinyx': "Welcome to the Jungle",
    'Quora': "Welcome to the Jungle",
    'Rad AI': "Welcome to the Jungle",
    'Radar': "Welcome to the Jungle",
    'Range': "Welcome to the Jungle",
    'RapidAI': "Welcome to the Jungle",
    'Reach Security': "Welcome to the Jungle",
    'RealAdvisor': "Welcome to the Jungle",
    'Reality Defender': "Welcome to the Jungle",
    'Relativity Space': "Welcome to the Jungle",
    'Relay Therapeutics': "Welcome to the Jungle",
    'Relex': "Welcome to the Jungle",
    'Replicant': "Welcome to the Jungle",
    'Replika': "Welcome to the Jungle",
    'Resolver': "Welcome to the Jungle",
    'Revenue': "Welcome to the Jungle",
    'Revv': "Welcome to the Jungle",
    'Rigetti Computing': "Welcome to the Jungle",
    'Right-Hand': "Welcome to the Jungle",
    'Ripjar': "Welcome to the Jungle",
    'Riskified': "Welcome to the Jungle",
    'Rivercell': "Welcome to the Jungle",
    'Rokt': "Welcome to the Jungle",
    'Root Global': "Welcome to the Jungle",
    'Rootly': "Welcome to the Jungle",
    'Rotageek': "Welcome to the Jungle",
    'Safe Security': "Welcome to the Jungle",
    'Sahara AI': "Welcome to the Jungle",
    'Salt Security': "Welcome to the Jungle",
    'Samaya': "Welcome to the Jungle",
    'Samba TV': "Welcome to the Jungle",
    'SambaNova Systems': "Welcome to the Jungle",
    'Sancare': "Welcome to the Jungle",
    'Sardine': "Welcome to the Jungle",
    'Saronic': "Welcome to the Jungle",
    'Scandit': "Welcome to the Jungle",
    'SchooLinks': "Welcome to the Jungle",
    'Sea Machines Robotics': "Welcome to the Jungle",
    'SeeChange Technologies': "Welcome to the Jungle",
    'Sense': "Welcome to the Jungle",
    'Sensi.AI': "Welcome to the Jungle",
    'SentinelOne': "Welcome to the Jungle",
    'SEON': "Welcome to the Jungle",
    'Shield AI': "Welcome to the Jungle",
    'Siena': "Welcome to the Jungle",
    'Sift': "Welcome to the Jungle",
    'Simbe': "Welcome to the Jungle",
    'Simple Machines': "Welcome to the Jungle",
    'Sinch': "Welcome to the Jungle",
    'Siro': "Welcome to the Jungle",
    'SkinVision': "Welcome to the Jungle",
    'Skydio': "Welcome to the Jungle",
    'Skyral': "Welcome to the Jungle",
    'SkySpecs': "Welcome to the Jungle",
    'Skyways': "Welcome to the Jungle",
    'Slingshot Aerospace': "Welcome to the Jungle",
    'Smartly.io': "Welcome to the Jungle",
    'SnapLogic': "Welcome to the Jungle",
    'Snapsheet': "Welcome to the Jungle",
    'Snorkel AI': "Welcome to the Jungle",
    'SOCi': "Welcome to the Jungle",
    'Socure': "Welcome to the Jungle",
    'Solidus Labs': "Welcome to the Jungle",
    'SOPHiA GENETICS': "Welcome to the Jungle",
    'Sophos': "Welcome to the Jungle",
    'SoundHound AI': "Welcome to the Jungle",
    'Speak': "Welcome to the Jungle",
    'Speechify': "Welcome to the Jungle",
    'SponsorUnited': "Welcome to the Jungle",
    'Spot AI': "Welcome to the Jungle",
    'SPREAD AI': "Welcome to the Jungle",
    'Sprig': "Welcome to the Jungle",
    'Square Enix': "Welcome to the Jungle",
    'Stability AI': "Welcome to the Jungle",
    'Standard Bots': "Welcome to the Jungle",
    'SuiteSpot': "Welcome to the Jungle",
    'Suki': "Welcome to the Jungle",
    'Super Annotate': "Welcome to the Jungle",
    'super.AI': "Welcome to the Jungle",
    'Swapcard': "Welcome to the Jungle",
    'Swayable': "Welcome to the Jungle",
    'System': "Welcome to the Jungle",
    'Tabs': "Welcome to the Jungle",
    'tacton': "Welcome to the Jungle",
    'Taktile': "Welcome to the Jungle",
    'Tandem Health': "Welcome to the Jungle",
    'Tavus': "Welcome to the Jungle",
    'TBAuctions': "Welcome to the Jungle",
    'TEAMWAY': "Welcome to the Jungle",
    'Techspert': "Welcome to the Jungle",
    'Tenable': "Welcome to the Jungle",
    'Tennr': "Welcome to the Jungle",
    'Tensordyne': "Welcome to the Jungle",
    'TetraScience': "Welcome to the Jungle",
    'text.cortex': "Welcome to the Jungle",
    'Textio': "Welcome to the Jungle",
    'Thread AI': "Welcome to the Jungle",
    'TIFIN': "Welcome to the Jungle",
    'Tiger Data': "Welcome to the Jungle",
    'Tipalti': "Welcome to the Jungle",
    'Tome': "Welcome to the Jungle",
    'Topline Pro': "Welcome to the Jungle",
    'Topsort': "Welcome to the Jungle",
    'Torq': "Welcome to the Jungle",
    'traide': "Welcome to the Jungle",
    'TribalScale': "Welcome to the Jungle",
    'Trullion': "Welcome to the Jungle",
    'Trunk Tools': "Welcome to the Jungle",
    'Twelve Labs': "Welcome to the Jungle",
    'Twin Health': "Welcome to the Jungle",
    'uberall': "Welcome to the Jungle",
    'UJET': "Welcome to the Jungle",
    'UltraEdge': "Welcome to the Jungle",
    'unitQ': "Welcome to the Jungle",
    'Unzer': "Welcome to the Jungle",
    'Updraft': "Welcome to the Jungle",
    'Urbint': "Welcome to the Jungle",
    'UVeye': "Welcome to the Jungle",
    'Valdera': "Welcome to the Jungle",
    'Vectara': "Welcome to the Jungle",
    'Vectra AI': "Welcome to the Jungle",
    'Vendelux': "Welcome to the Jungle",
    'Veriff': "Welcome to the Jungle",
    'Vic.ai': "Welcome to the Jungle",
    'VideaHealth': "Welcome to the Jungle",
    'Vise': "Welcome to the Jungle",
    'Visian': "Welcome to the Jungle",
    'Viz': "Welcome to the Jungle",
    'Vocca': "Welcome to the Jungle",
    'Volta software': "Welcome to the Jungle",
    'Voxel': "Welcome to the Jungle",
    'Voxie Inc': "Welcome to the Jungle",
    'Voyado': "Welcome to the Jungle",
    'Waiv, formerly Owkin Dx': "Welcome to the Jungle",
    'Wealth.com': "Welcome to the Jungle",
    'webAI': "Welcome to the Jungle",
    'WEKA': "Welcome to the Jungle",
    'WellSaid Labs': "Welcome to the Jungle",
    'Wilgo': "Welcome to the Jungle",
    'Windfall': "Welcome to the Jungle",
    'WireScreen': "Welcome to the Jungle",
    'Workato': "Welcome to the Jungle",
    'Writer': "Welcome to the Jungle",
    'xAI': "Welcome to the Jungle",
    'YESWEHACK': "Welcome to the Jungle",
    'Yext': "Welcome to the Jungle",
    'you.com': "Welcome to the Jungle",
    'Yourban': "Welcome to the Jungle",
    'Yxir': "Welcome to the Jungle",
    'zaizi': "Welcome to the Jungle",
    'Zefir': "Welcome to the Jungle",
    'Zeitview': "Welcome to the Jungle",
    'Zendar': "Welcome to the Jungle",
    'Zenika': "Welcome to the Jungle",
    'Zilliz': "Welcome to the Jungle",
    'ZILO': "Welcome to the Jungle",
    'ZoomInfo': "Welcome to the Jungle",
    'Zum': "Welcome to the Jungle",
    # Major AI Companies — well-funded frontier labs and category leaders
    "OpenAI": "Major AI Companies",
    "Anthropic": "Major AI Companies",
    "Mistral": "Major AI Companies",
    "Cohere": "Major AI Companies",
    "HF": "Major AI Companies",
    "Scale AI": "Major AI Companies",
    "DeepL": "Major AI Companies",
    "Eleven Labs": "Major AI Companies",
    "Sony AI": "Major AI Companies",
    "Cursor": "Major AI Companies",
    # AI Startups — smaller / earlier-stage
    "H": "AI Startups",
    "AMI": "AI Startups",
    "SSI": "AI Startups",
    "Thinking Machines": "AI Startups",
    "Poolside": "AI Startups",
    "Black Forest Labs": "AI Startups",
    "Cognition": "AI Startups",
    # Big Tech
    "Apple": "Big Tech",
    "Microsoft": "Big Tech",
    "Google": "Big Tech",
    "Meta": "Big Tech",
    "NVIDIA": "Big Tech",
    "GitHub": "Big Tech",
    "Proton": "Big Tech",
    # Security Companies
    "DepthFirst": "Security Companies",
    "XBOW": "Security Companies",
    "Aisle": "Security Companies",
    "ZeroPath": "Security Companies",
    "Pixee": "Security Companies",
    "Corgea": "Security Companies",
    "CrowdStrike": "Security Companies",
    "Snyk": "Security Companies",
    "Semgrep": "Security Companies",
    "Checkmarx": "Security Companies",
    # Music Companies
    "Ableton": "Music Companies",
    "Arturia": "Music Companies",
    "Neural DSP": "Music Companies",
    "Steinberg": "Music Companies",

    # --- Added via debug/ats_probe.py 2026-09-25 ---------------------------
    # AI Startups (Manager-or-Security filter applied)
    "Perplexity":            "AI Startups",
    "Modal":                 "AI Startups",
    "Together AI":           "AI Startups",
    "Fireworks AI":          "AI Startups",
    "Sakana AI":             "AI Startups",
    "Prime Intellect":       "AI Startups",
    "Physical Intelligence": "AI Startups",
    "Voyage AI":             "AI Startups",
    "Rewind AI":             "AI Startups",
    "Replit":                "AI Startups",
    "LangChain":             "AI Startups",
    "Runway":                "AI Startups",
    "Pika":                  "AI Startups",
    "Character AI":          "AI Startups",
    # Music
    "Suno":                  "Music Companies",
    "Udio":                  "Music Companies",
    # Security
    "Chainguard":            "Security Companies",
    "Endor Labs":            "Security Companies",
    "Socket":                "Security Companies",
    "Wiz":                   "Security Companies",
    "Cloudflare":            "Security Companies",
    "1Password":             "Security Companies",
    "Okta":                  "Security Companies",
    "Cybereason":            "Security Companies",
    "Elastic":               "Security Companies",
    # Other
    "HashiCorp":             "Other",
    "GitLab":                "Other",
    "Databricks":            "Other",
    "Snowflake":             "Other",

    # --- Wave 2 (2026-09-25) -----------------------------------------------
    # AI Startups (infra / chips / inference / evals / vector DBs / voice)
    "SandboxAQ":             "Security Companies",  # PQC/crypto
    "Cape Privacy":          "Security Companies",  # FHE
    "Cerebras":              "AI Startups",
    "Etched":                "AI Startups",
    "Tenstorrent":           "AI Startups",
    "MatX":                  "AI Startups",
    "Rain":                  "AI Startups",
    "Anyscale":              "AI Startups",
    "Baseten":               "AI Startups",
    "Coreweave":             "AI Startups",
    "Nebius":                "AI Startups",
    "Crusoe":                "AI Startups",
    "Lambda":                "AI Startups",
    "Braintrust":            "AI Startups",
    "LlamaIndex":            "AI Startups",
    "Nomic":                 "AI Startups",
    "Weaviate":              "AI Startups",
    "Pinecone":              "AI Startups",
    "Deepgram":              "AI Startups",
    "AssemblyAI":            "AI Startups",
    "Zed":                   "AI Startups",
    "Cline":                 "AI Startups",
    # Security (Wave 2)
    "Doppler":               "Security Companies",
    "BeyondTrust":           "Security Companies",
    "Nord Security":         "Security Companies",
    "Bitwarden":             "Security Companies",
    "Yubico":                "Security Companies",
    # Music
    "Spitfire Audio":        "Music Companies",
    "Splice":                "Music Companies",
    # Wave 5 (verified 2026-09-28)
    "Softube":               "Music Companies",
    "inMusic Brands":        "Music Companies",
    "Yamaha":                "Music Companies",
    "Sonos":                 "Music Companies",
    "Sennheiser":            "Music Companies",
    "Bose":                  "Music Companies",
    "Roland":                "Music Companies",
    "Marshall":              "Music Companies",
    "Elektron":              "Music Companies",
    "Dolby":                 "Music Companies",
    "MOTU":                  "Music Companies",
    "Boris FX / iZotope":    "Music Companies",
    "Seymour Duncan":        "Music Companies",
    "Boss":                  "Music Companies",
    # Other (French / EU / infra)
    "Doctolib":              "Other",
    "Alan":                  "Other",
    "Qonto":                 "Other",
    "Dataiku":               "Other",
    "Owkin":                 "Other",
    "Fastly":                "Other",
    "Datadog":               "Other",

    # --- Wave 3 (2026-09-25) — quasi-GAFAM / hyperscalers ------------------
    "Airbnb":                "Big Tech",
    "LinkedIn":              "Big Tech",
    "Pinterest":             "Big Tech",
    "Discord":               "Big Tech",
    "Roblox":                "Big Tech",
    "Stripe":                "Big Tech",
    "Twilio":                "Big Tech",
    "Dropbox":               "Big Tech",
    "Block":                 "Big Tech",
    "Robinhood":             "Big Tech",

    # --- Wave 4 (2026-09-25) — music / audio -------------------------------
    "Fender":                "Music Companies",
    "Universal Audio":       "Music Companies",
    "Slate Digital":         "Music Companies",
    "Output":                "Music Companies",
    "Pioneer DJ":            "Music Companies",

    # --- Wave 6: Big Tech / GAFAM-adjacent (verified working) ---
    "Adobe":                 "Big Tech",
    "Salesforce":            "Big Tech",
    "Intel":                 "Big Tech",
    "PayPal":                "Big Tech",
    "SAP":                   "Big Tech",
    "GitGuardian":           "Security Companies",
    "Palantir":              "Big Tech",
    "Netflix":               "Big Tech",
    "Cisco":                 "Big Tech",
    "Unity":                 "Big Tech",
    "Qualcomm":              "Big Tech",
    "IBM":                   "Big Tech",
    "VMware (Broadcom)":     "Big Tech",
    "Avid":                  "Music Companies",

    # --- Added via catalog expansion 2026-10-06 -------------------------
    # AI Startups
    "Imbue":               "AI Startups",
    # Security Companies
    "Netskope":            "Security Companies",
    "PQShield":            "Security Companies",
    "Tailscale":           "Security Companies",
    # Other (dev-tools / SaaS / fintech)
    "Brex":                "Other",
    "Figma":               "Other",
    "Grafana Labs":        "Other",
    "Hex":                 "Other",
    "Linear":              "Other",
    "Mercury":             "Other",
    "Vercel":              "Other",
    # --- Added 2026-10-06 (batch 2) --------------------------------------
    # AI Startups
    "Reka":                "AI Startups",
    "Lightning AI":        "AI Startups",
    "Observe AI":          "AI Startups",
    # Security Companies
    "Drata":               "Security Companies",
    # Other
    "Fivetran":            "Other",
    "MongoDB":             "Other",
    "Reddit":              "Other",
}

# =============================================================================
# Spontaneous applications
# =============================================================================
# Title patterns marking a job as a "spontaneous / general application" entry.
# When any of these substrings appear in a job title (case-insensitive), that
# job becomes the "✉ Spontaneous" link at the top of its section.
SPONTANEOUS_PATTERNS = [
    "spontaneous",
    "speculative",
    "general application",
    "don't see the right role",
    "don't see a role that fits",
    "looking for something else",
    "wild card",
    "wildcard",
    "prospective application",
    "candidature spontan",
    "candidatures spontan",
    "open application",
    "unsolicited application",
    "introduce yourself",
]


# =============================================================================
# Per-query runaway guard — stop paginating a single query at a source
# once it has yielded this many matching jobs. Protects the engine from
# a pathological keyword (e.g. "engineer" at Apple) that would otherwise
# hit the hard 10-page cap on every single query in the config.
# Overridable per-user via data/user_config.py; also tunable from the ⚙
# Settings modal (CMD+,) which writes back to user_config.py.
RUNAWAY_THRESHOLD = 300

# User overrides — load personal preferences from data/user_config.py
#
# This keeps src/ free of personal data (per CLAUDE.md). The user's SOURCES,
# HIGHLIGHTS, TITLE_BLACKLIST and LOCATION_BLACKLIST live in data/user_config.py
# (gitignored for an open-source clone) and override the empty defaults above.
# =============================================================================
import importlib.util as _ilu
import sys as _sys

_USER_CONFIG_PATH = _os.path.join(DATA_DIR, "user_config.py")
if _os.path.isfile(_USER_CONFIG_PATH):
    _spec = _ilu.spec_from_file_location("_jobs_user_config", _USER_CONFIG_PATH)
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    for _name in ("HIGHLIGHTS", "TITLE_BLACKLIST", "LOCATION_BLACKLIST", "SOURCES",
                  "RUNAWAY_THRESHOLD"):
        if hasattr(_mod, _name):
            globals()[_name] = getattr(_mod, _name)
else:
    _sys.stderr.write(
        f"[config] no {_USER_CONFIG_PATH} — using empty SOURCES/HIGHLIGHTS/"
        "BLACKLIST defaults. Copy src/user_config.example.py to {} and edit "
        "to see any jobs.\n".format(_USER_CONFIG_PATH)
    )

# Auto-fill GROUP_OF from the catalog so new companies land in their
# declared group without a parallel edit here. Explicit entries above
# win (lets a user override a catalog default). This fixed the "I added
# Zama but it shows in Other and the FHE heading is empty" bug — before,
# adding `'group': 'FHE'` to catalog.py did nothing at render time.
try:
    from catalog import CATALOG as _CATALOG
except ImportError:
    _CATALOG = []
for _entry in _CATALOG:
    _n, _g = _entry.get("name"), _entry.get("group")
    if _n and _g and _n not in GROUP_OF:
        GROUP_OF[_n] = _g
