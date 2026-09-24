"""
config.py — your personal setup for jobs.py.

Everything here is safe to tweak. The engine (jobs.py) never has to change
just because you want to add a company, filter out a title, highlight a
different word, or change your LLM backend.

Copy this file to a personal fork, then run `python3 jobs.py` as usual —
the engine reads whatever is in *this* file.
"""

# =============================================================================
# Storage locations (one file per concern; edit only if the defaults collide)
# =============================================================================

OUTPUT_HTML         = "jobs.html"
REJECTED_DB         = "rejected.json"
LIKED_DB            = "liked.json"
PROFILE_FILE        = "PROFILE.md"
SCORE_CACHE         = "score_cache.json"
DESC_CACHE          = "desc_cache.json"
RAW_LOCATIONS_FILE  = "raw_locations.txt"

# Local HTTP server the browser talks to (× reject / +1 like).
SERVE_HOST = "127.0.0.1"
SERVE_PORT = 8765

# =============================================================================
# Scoring backend — how each job is rated against PROFILE.md
# =============================================================================
#   "claude" — Anthropic API (needs ANTHROPIC_API_KEY env var, `pip install anthropic`).
#   "ollama" — local Ollama server at OLLAMA_URL.
#   "none"   — disable scoring.
SCORER           = "ollama"
CLAUDE_MODEL     = "claude-sonnet-4-6"
OLLAMA_URL       = "http://localhost:11434/api/chat"
OLLAMA_MODEL     = "llama3.2:latest"
SCORE_BATCH_SIZE = 1     # 1 = 100% coverage; higher = faster but may drop scores
SCORE_DESC_CHARS = 400   # description chars sent to the LLM per job
SCORE_PARALLEL   = 6     # concurrent calls to Ollama/Claude

# =============================================================================
# Highlights — words drawn with a marker style in titles + descriptions
# =============================================================================

HIGHLIGHTS = ["Security", "Manager", "Codex", "Codemender", "Cyber",
              "CyberSecurity", "SEAR", "DeepMind", "Researcher"]

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
    # Roman numerals I..X
    "i": "I", "ii": "II", "iii": "III", "iv": "IV", "v": "V",
    "vi": "VI", "vii": "VII", "viii": "VIII", "ix": "IX", "x": "X",
}

# =============================================================================
# Blacklists
# =============================================================================
# If any of these substrings appear in a job title (case-insensitive), hide.
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
    "Public Sector",
    "Healthcare",
    "Billing",
    "Media Manager",
    "Design Engineer",
    "Field Engineer",
    "Recruiting",
    "Account Manager",
    "General Manager",
    "Events Lead",
    "Post-Production Lead",
    "Freelance",
    "Brand design",
    "Customer Success",
    "Marketer",
    "Martech Engineer",
    "Payroll",
    "Translator",
    "Regional Director",
    "Deal Desk",
    "Partners",
    "Data Analyst",
    "Integrated Campaigns",
    "Events",
    "Community",
    "Procurement",
    "Office Assistant",
    "Language Specialist",
    "Accounts Payable Specialist",
    "Creative Producer",
    "Analyst Relations",
    "APAC Communications",
    "Compensation",
    "Counsel",
    "Technical Customer",
    "Workplace Operations",
    "Partner Director",
    "Account Director",
    "Country Leader",
    "Business Operations",
    "Deployed Engineer",
    "Facility Security Officer",
    "IT Support Engineer",
    "Partner Deployed Engineer",
    "People Operations",
    "Workplace & Engagement Coordinator",
    "Executive Business Partner",
    "Global Public Policy",
    "HR Business Partner",
    "Product Policy",
    "Technical Recruiter",
    "Technical Sourcer",
    "Senior Hardware Security Engineer",
    "Community Manager",
    "Motion Designer",
    "SEO Outreach",
    "Recruiter",
    "Finance",
    "New Grad",
    "Technical Writer",
    "DevOps",
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

# If ALL of a job's locations contain one of these substrings, hide.
LOCATION_BLACKLIST = [
    "Israel", "India", "Romania", "Brazil", "Mexico",
    "Bulgaria", "Lithuania", "North Macedonia", "Macedonia",
    "Qatar", "Saudi Arabia", "UAE", "Dubai",
    "Portugal", "Braga",
    "Czech Republic", "Czechia", "Prague",
    "Denmark", "Copenhagen",
    "Hungary", "Budapest",
    "Pune", "Ramat Gan",
]

# =============================================================================
# Seniority — how the badge, filter, and sort work
# =============================================================================
# Groups shown as separate rows in the seniority filter bar. Order also
# drives the "most senior first" sort inside each section.
SENIORITY_GROUPS = [
    ("Management", ["VP", "Director", "Manager", "Head", "Lead"]),
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
    ("Manager", "Manager"),
    ("Lead", "Lead"),
    ("Senior", "Senior"),
    ("Associate", "Associate"),
    ("Junior", "Junior"),
    ("Intern", "Intern"),
]
# Seniority toggles rendered ON by default at the top of the filter bar.
SENIORITY_TOGGLES = ["Manager", "Director"]

# =============================================================================
# Sources — the boards to fetch
# =============================================================================
# Each entry is a dict:
#   name:     display name (shown in nav + section headings)
#   kind:     picks the fetcher (ashby, greenhouse, workable, phenom, apple,
#             google, microsoft, meta, ableton, lucca, wttj, pw)
#   slug:     ATS-specific slug or short identifier
#   queries:  list of search terms; empty [] = show everything
#   board:    (optional) public URL of the company's own careers page
#   search_url, link_re, origin, wait_selector: extra fields for `kind=pw`
#             (generic Playwright link scraper)

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
    {"name": "Scale AI",  "kind": "scale",      "slug": "scale",      "queries": [],
     "board": "https://scale.com/careers",
     "search_url": "https://scale.com/careers"},
    {"name": "DeepL",     "kind": "ashby",      "slug": "DeepL",      "queries": []},
    {"name": "Eleven Labs", "kind": "ashby",    "slug": "elevenlabs", "queries": []},
    {"name": "Poolside", "kind": "ashby",       "slug": "poolside",   "queries": []},
    {"name": "Black Forest Labs", "kind": "pw", "slug": "blackforestlabs", "queries": [],
     "board": "https://bfl.ai/careers",
     "search_url": "https://bfl.ai/careers",
     "link_re": r'href="(https?://[^"]*greenhouse[^"]*/blackforestlabs[^"]*|/careers/[^"#?/]+/?)"',
     "origin": "https://bfl.ai",
     "wait_selector": "a[href*='greenhouse'], a[href*='/careers/']"},
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
    {"name": "Aisle",     "kind": "ashby",      "slug": "aisle",     "queries": [],
     "board": "https://aisle.com/careers"},
    {"name": "ZeroPath",  "kind": "pw",         "slug": "zeropath",  "queries": [],
     "board": "https://zeropath.com/careers",
     "search_url": "https://zeropath.com/careers",
     "link_re": r'href="(https?://jobs\.ashbyhq\.com/[^"#?]+/[a-f0-9-]{20,}|/careers/[^"#?]+|https?://[^"]*(?:greenhouse|lever|workable|ashby)[^"]*)"',
     "origin": "https://zeropath.com"},
    {"name": "Pixee",     "kind": "pixee",      "slug": "pixee",     "queries": [],
     "board": "https://app.dover.com/jobs/pixee",
     "search_url": "https://app.dover.com/jobs/pixee"},
    {"name": "Corgea",    "kind": "pw",         "slug": "corgea",    "queries": [],
     "board": "https://www.ycombinator.com/companies/corgea/jobs",
     "search_url": "https://www.ycombinator.com/companies/corgea/jobs",
     "link_re": r'href="(/companies/corgea/jobs/[^"#?]+)"',
     "origin": "https://www.ycombinator.com"},
    {"name": "CrowdStrike","kind": "pw",        "slug": "crowdstrike","queries": ["security"],
     "board": "https://crowdstrike.wd5.myworkdayjobs.com/en-US/crowdstrikecareers?q=security",
     "search_url": "https://crowdstrike.wd5.myworkdayjobs.com/en-US/crowdstrikecareers?q=security",
     "link_re": r'href="(/en-US/crowdstrikecareers/job/[^"]+)"',
     "origin": "https://crowdstrike.wd5.myworkdayjobs.com",
     "wait_selector": "a[href*='/crowdstrikecareers/job/']"},
    {"name": "Snyk",       "kind": "pw",         "slug": "snyk",       "queries": [],
     "board": "https://snyk.io/fr/careers/all-jobs/",
     "search_url": "https://snyk.io/fr/careers/all-jobs/",
     "link_re": r'href="(https?://[^"]*greenhouse[^"]*/snyk/jobs/\d+[^"]*|/fr/careers/[^"#?/]+/[^"#?/]+/?)"',
     "origin": "https://snyk.io",
     "wait_selector": "a[href*='/jobs/'], a[href*='/careers/']"},
    {"name": "Semgrep",    "kind": "pw",         "slug": "semgrep",    "queries": [],
     "board": "https://semgrep.dev/about/careers/",
     "search_url": "https://semgrep.dev/about/careers/",
     "link_re": r'href="(https?://[^"]*greenhouse[^"]*/semgrep/jobs/\d+[^"]*|/about/careers/[^"#?/]+/?)"',
     "origin": "https://semgrep.dev",
     "wait_selector": "a[href*='/jobs/'], a[href*='/careers/']"},
    {"name": "Checkmarx",  "kind": "checkmarx",  "slug": "checkmarx",  "queries": [],
     "board": "https://checkmarx.com/company/careers/",
     "search_url": "https://checkmarx.com/company/careers/"},
    {"name": "NVIDIA",    "kind": "phenom",     "slug": "nvidia",     "queries": ["security"],
     "board": "https://jobs.nvidia.com/careers?query=Security&pid=893394830937&sort_by=relevance",
     "search_url": "https://jobs.nvidia.com/careers?query=Security&sort_by=relevance"},
    {"name": "GitHub",    "kind": "github",     "slug": "github",    "queries": ["security"],
     "board": "https://www.github.careers/careers-home/jobs?keywords=security",
     "search_url": "https://www.github.careers/careers-home/jobs?keywords=security"},
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
     "search_url": "https://revolutpeople.com/neural-dsp/public/careers/",
     "link_re": r'href="(/neural-dsp/public/careers/[^"#?]+|https?://revolutpeople\.com/neural-dsp/public/careers/[^"#?]+)"',
     "origin": "https://revolutpeople.com"},
    {"name": "Steinberg",  "kind": "pw",      "slug": "steinberg",     "queries": [],
     "board": "https://www.steinberg.net/careers/vacancies/",
     "search_url": "https://www.steinberg.net/careers/vacancies/",
     "link_re": r'href="(https?://www\.steinberg\.net/careers/[^"#?]+|/careers/[^"#?/]+/[^"#?]+)"',
     "origin": "https://www.steinberg.net"},
    {"name": "Welcome to the Jungle", "kind": "wttj", "slug": "wttj", "queries": ["security"],
     "board": "https://www.welcometothejungle.com/fr/jobs?query=security",
     "search_url": "https://www.welcometothejungle.com/fr/jobs?query=security"},
]

# =============================================================================
# Grouping — sections in the nav and HTML
# =============================================================================
GROUP_ORDER = [
    "Major AI Companies",
    "AI Startups",
    "Big Tech",
    "Security Companies",
    "Music Companies",
    "Other",
]
# name → group. Missing entries fall back to "Other".
GROUP_OF = {
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
    # Other
    "Welcome to the Jungle": "Other",
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
    "prospective application",
    "candidature spontan",
]
