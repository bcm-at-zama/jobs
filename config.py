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
TO_APPLY_DB         = "to_apply.json"
APPLIED_DB          = "applied.json"
# {url: {reason, feedback, ts}} — jobs where I applied and the company
# rejected me. Kept even after the job is removed from the board.
APP_REJECTED_DB     = "app_rejected.json"
# History: jobs you want to remember even though you're not applying and
# not rejecting them. Typically clicked via the K button once you've read
# the description and want to archive it out of the main list.
HISTORY_DB          = "history.json"
SEEN_DB             = "seen.json"
# {url: {title, locations, source}} — used to render orphans (jobs the user
# +1'd / marked but no longer returned by the source board).
JOB_INDEX_DB        = "job_index.json"
PROFILE_FILE        = "PROFILE.md"
SCORE_CACHE         = "llm_cache.json"
DESC_CACHE          = "desc_cache.json"
RAW_LOCATIONS_FILE  = "debug/raw_locations.txt"
LIST_CACHE_DIR      = "list_cache"

# TTL for the per-source list cache. On a re-run within this window we skip
# Playwright entirely for that source (huge speed-up when descriptions and
# scores are already cached). Set to 0 to always re-fetch.
LIST_CACHE_TTL_HOURS = 6

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
OLLAMA_MODEL     = "qwen2.5:7b"
SCORE_BATCH_SIZE = 1      # 1 = 100% coverage; higher = faster but may drop scores
SCORE_DESC_CHARS = 15000  # description chars sent to the LLM per job. Set high
                          # enough to include Salary/Compensation/Benefits which
                          # usually sit near the end of a posting. Very few jobs
                          # exceed this; on the current model + laptop the extra
                          # latency is negligible for ~150 jobs.
SCORE_PARALLEL   = 6      # concurrent calls to Ollama/Claude
SCORE_LONG_ROLES = True   # role_long (structured markdown) is the only role output now

# =============================================================================
# Highlights — words drawn with a marker style in titles + descriptions
# =============================================================================

HIGHLIGHTS = ["Security", "Manager", "Codex", "Codemender", "Cyber",
              "CyberSecurity", "SEAR", "DeepMind", "Researcher", "Logic",
              "MDASH", "Codex Security", "Claude Security"]

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
TITLE_BLACKLIST = [
    "Creative Director, Investment",
    "Global Event",
    "Junior",
    "Associate",
    "Intern",
    "Detection & Response",
    "Detection and Response",
    "Corporate Security",
    "Global Security Operation",
    "Cloud Security",
    "Capacity Manager",
    "Accounting Manager",
    "IT Support",
    "Regional",
    "Network Security",
    "Supply Chain",
    "Infrastructure Engineer",
    "Facilities",
    "Projects Manager",
    "Global Security",
    "Project Manager",
    "Tax",
    "Financial",
    "Data Center Manager",
    "Sourcing Manager",
    "Construction Manager",
    "Content Manager",
    "Category Manager",
    "Workplace Change Manager",
    "Service Desk",
    "Center Manager",
    "Deal Strategy",
    "Administrative",
    "IT Manager",
    "IR Risks",
    "Site Manager",
    "Expansion Manager",
    "Alliance Analyst",
    "Partner Manager",
    "Retention",
    "Data Engineer",
    "Customer Support",
    "Security Administrator",
    "Capture Manager",
    "Rewards",
    "Consulting Architect",
    "Technical Success Architect",
    "Product Owner",
    "Windows Engineer",
    "Investigator",
    "Operations Specialist",
    "Firmware Engineer",
    "Curriculum Manager",
    "Biologist",
    "Customer Care",
    "CRM Manager",
    "Human Resources",
    "Electrical Engineer",
    "Demand Planner",
    "Sourcing Specialist",
    "Designer",
    "Office Manager",
    "IT Risk & Controls Manager",
    "IT Risk and Controls Manager",
    "Student",
    "Engagement Manager",
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
    "Creative Director",
    "Quota & Capacity",
    "Media Strategy",
    "Paid Media",
    "Government Affairs",
    "Public Policy",
    "Customer Director",
    "Developer Relations",
    "Intellectual Property",
    "Technical Program Management",
    "Accounting",
    "Benefits",
    "Communications Director",
    "Investor Relations",
    "Treasury Director",
    "Corporate Communications",
    "PR Director",
    "HR Director",
    "Field CTO",
    "Executive Assistant",
    "People Success",
    "Quality Technician",
    "Lab Technician",
    "Contractor",
    "Pricing",
    "Litigation",
    "Brand",
    "Art Director",
    "Post-Doctoral",
    "Fixed-Term",
    "Teilzeit",
    "Part-Time", "Part Time",
    "temps partiel",
    # Batch-added from TOREVIEW.md
    "Technical Support",
    "Workplace",
    "Merchandising",
    "HR generalist",
    "QA Manager",
    "Localization Manager",
    "eLearning",
    "Partner Ecosystems",
    "Strategic Initiatives",
    "Post-Silicon",
    "Event Support",
    "Technician",
    "IP Engineer",
    "Strategy & Operations",
    "Field Chief Information Security Officer",
    "Incident Response",
    "Delivery Operations",
    "Market Adoption",
    "Social Media",
    "Controller",
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
    "Belgium", "Brussels",
    "Canada",
    "Ireland", "Dublin",
    "Japan", "Tokyo",
    "Armenia", "Yerevan",
    "Poland", "Warsaw", "Krakow",
    "Senegal", "Dakar",
    "Serbia", "Belgrade",
    "South Korea", "Korea", "Seoul",
    "Sweden", "Stockholm",
    "Africa",
    "Netherlands", "Amsterdam",
    "South America", "Latin America", "LATAM",
]

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
}

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
    {"name": "OpenAI",    "kind": "ashby",      "slug": "openai",     "queries": ["security", "codex", "cryptography", "CTO", "VP"]},
    {"name": "Anthropic", "kind": "greenhouse", "slug": "anthropic",  "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Mistral",   "kind": "ashby",      "slug": "mistral.ai", "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Cohere",    "kind": "ashby",      "slug": "cohere",     "queries": ["security", "cryptography", "CTO", "VP"]},
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
    {"name": "CrowdStrike","kind": "pw",        "slug": "crowdstrike","queries": ["security", "cryptography", "CTO", "VP"],
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
    {"name": "NVIDIA",    "kind": "phenom",     "slug": "nvidia",     "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://jobs.nvidia.com/careers?query=Security&pid=893394830937&sort_by=relevance",
     "search_url": "https://jobs.nvidia.com/careers?query=Security&sort_by=relevance"},
    {"name": "GitHub",    "kind": "github",     "slug": "github",    "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://www.github.careers/careers-home/jobs?keywords=security",
     "search_url": "https://www.github.careers/careers-home/jobs?keywords=security"},
    {"name": "Apple",     "kind": "apple",      "slug": "apple",      "queries": ["security", "Logic", "Creative", "cryptography", "CTO", "VP"],
     "board": "https://jobs.apple.com/en-us/search?search=security"},
    {"name": "Microsoft", "kind": "microsoft",  "slug": "microsoft",  "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://apply.careers.microsoft.com/careers?query=Security&pid=1970393556942260&sort_by=relevance"},
    {"name": "Google",    "kind": "google",     "slug": "google",     "queries": ["security", "codemender", "DeepMind", "Big Sleep", "Gemini", "cryptography", "CTO", "VP"],
     "board": "https://www.google.com/about/careers/applications/jobs/results/?q=security&hl=en_US",
     "search_url": "https://www.google.com/about/careers/applications/jobs/results?hl=en_US&target_level=DIRECTOR_PLUS&target_level=ADVANCED&employment_type=FULL_TIME"},
    {"name": "Meta",      "kind": "meta",       "slug": "meta",       "queries": ["security", "cryptography", "CTO", "VP"],
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
    {"name": "Welcome to the Jungle", "kind": "wttj", "slug": "wttj", "queries": ["security", "CTO", "VP"],
     "board": "https://www.welcometothejungle.com/fr/jobs?query=security",
     "search_url": "https://www.welcometothejungle.com/fr/jobs?query=security"},

    # --- Added via debug/ats_probe.py 2026-09-25 ---------------------------
    # AI Startups — filtered on Security or Manager to keep the list scoped.
    {"name": "Perplexity",           "kind": "ashby",      "slug": "perplexity",           "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Modal",                "kind": "ashby",      "slug": "modal",                "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Together AI",          "kind": "greenhouse", "slug": "togetherai",           "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Fireworks AI",         "kind": "ashby",      "slug": "fireworks",            "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Sakana AI",            "kind": "workable",   "slug": "sakana-ai",            "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Prime Intellect",      "kind": "ashby",      "slug": "primeintellect",       "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Physical Intelligence","kind": "ashby",      "slug": "physicalintelligence", "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Voyage AI",            "kind": "workable",   "slug": "voyage",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Rewind AI",            "kind": "ashby",      "slug": "rewind",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Replit",               "kind": "ashby",      "slug": "replit",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "LangChain",            "kind": "ashby",      "slug": "langchain",            "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Runway",               "kind": "ashby",      "slug": "runway",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Pika",                 "kind": "ashby",      "slug": "pika",                 "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Character AI",         "kind": "ashby",      "slug": "character",            "queries": ["security", "manager", "CTO", "VP"]},
    # Music
    {"name": "Suno",                 "kind": "ashby",      "slug": "suno",                 "queries": []},
    {"name": "Udio",                 "kind": "greenhouse", "slug": "udio",                 "queries": []},
    # Security
    {"name": "Chainguard",           "kind": "greenhouse", "slug": "chainguard",           "queries": []},
    {"name": "Endor Labs",           "kind": "greenhouse", "slug": "endorlabs",            "queries": []},
    {"name": "Socket",               "kind": "ashby",      "slug": "socket",               "queries": []},
    {"name": "Wiz",                  "kind": "ashby",      "slug": "wiz",                  "queries": []},
    {"name": "Cloudflare",           "kind": "greenhouse", "slug": "cloudflare",           "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "1Password",            "kind": "ashby",      "slug": "1password",            "queries": []},
    {"name": "Okta",                 "kind": "greenhouse", "slug": "okta",                 "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Cybereason",           "kind": "greenhouse", "slug": "cybereason",           "queries": []},
    {"name": "Elastic",              "kind": "greenhouse", "slug": "elastic",              "queries": ["security", "cryptography", "CTO", "VP"]},
    # Other (dev tools / data)
    {"name": "HashiCorp",            "kind": "workable",   "slug": "hashicorp",            "queries": []},
    {"name": "GitLab",               "kind": "greenhouse", "slug": "gitlab",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Databricks",           "kind": "greenhouse", "slug": "databricks",           "queries": ["security", "CTO", "VP"]},
    {"name": "Snowflake",            "kind": "ashby",      "slug": "snowflake",            "queries": ["security", "CTO", "VP"]},

    # --- Wave 2 via debug/ats_probe.py 2026-09-25 --------------------------
    # FHE / PQC / privacy-preserving crypto (Zama-adjacent, top interest)
    {"name": "SandboxAQ",            "kind": "ashby",      "slug": "sandboxaq",            "queries": []},
    {"name": "Cape Privacy",         "kind": "ashby",      "slug": "cape",                 "queries": []},
    # AI chips
    {"name": "Cerebras",             "kind": "ashby",      "slug": "cerebras",             "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Etched",               "kind": "ashby",      "slug": "etched",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Tenstorrent",          "kind": "greenhouse", "slug": "tenstorrent",          "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "MatX",                 "kind": "ashby",      "slug": "matx",                 "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Rain",                 "kind": "ashby",      "slug": "rain",                 "queries": ["security", "manager", "CTO", "VP"]},
    # AI infra / compute / inference
    {"name": "Anyscale",             "kind": "ashby",      "slug": "anyscale",             "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Baseten",              "kind": "ashby",      "slug": "baseten",              "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Coreweave",            "kind": "greenhouse", "slug": "coreweave",            "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Nebius",               "kind": "greenhouse", "slug": "nebius",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Crusoe",               "kind": "ashby",      "slug": "crusoe",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Lambda",               "kind": "ashby",      "slug": "lambda",               "queries": ["security", "manager", "CTO", "VP"]},
    # AI dev tools / evals / embeddings / vector DBs
    {"name": "Braintrust",           "kind": "ashby",      "slug": "braintrust",           "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "LlamaIndex",           "kind": "ashby",      "slug": "llamaindex",           "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Nomic",                "kind": "ashby",      "slug": "nomic",                "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Weaviate",             "kind": "ashby",      "slug": "weaviate",             "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Pinecone",             "kind": "ashby",      "slug": "pinecone",             "queries": ["security", "manager", "CTO", "VP"]},
    # Voice / audio AI
    {"name": "Deepgram",             "kind": "ashby",      "slug": "deepgram",             "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "AssemblyAI",           "kind": "greenhouse", "slug": "assemblyai",           "queries": ["security", "manager", "CTO", "VP"]},
    # Code / dev tools
    {"name": "Zed",                  "kind": "ashby",      "slug": "zed",                  "queries": []},
    {"name": "Cline",                "kind": "greenhouse", "slug": "cline",                "queries": []},
    # Security (Wave 2)
    {"name": "Doppler",              "kind": "ashby",      "slug": "doppler",              "queries": []},
    {"name": "BeyondTrust",          "kind": "greenhouse", "slug": "beyondtrust",          "queries": []},
    {"name": "Nord Security",        "kind": "ashby",      "slug": "nord-security",        "queries": []},
    {"name": "Bitwarden",            "kind": "greenhouse", "slug": "bitwarden",            "queries": []},
    {"name": "Yubico",               "kind": "greenhouse", "slug": "yubico",               "queries": []},
    # Music
    {"name": "Spitfire Audio",       "kind": "greenhouse", "slug": "spitfire",             "queries": []},
    {"name": "Splice",               "kind": "greenhouse", "slug": "splice",               "queries": []},
    # France / EU
    {"name": "Doctolib",             "kind": "ashby",      "slug": "doctolib",             "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Alan",                 "kind": "ashby",      "slug": "alan",                 "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Qonto",                "kind": "ashby",      "slug": "qonto",                "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Dataiku",              "kind": "greenhouse", "slug": "dataiku",              "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Owkin",                "kind": "ashby",      "slug": "owkin",                "queries": []},
    # Adjacent
    {"name": "Fastly",               "kind": "greenhouse", "slug": "fastly",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Datadog",              "kind": "greenhouse", "slug": "datadog",              "queries": ["security", "manager", "CTO", "VP"]},

    # --- Wave 3 via debug/ats_probe.py 2026-09-25 (quasi-GAFAM) ------------
    # Big consumer tech
    {"name": "Airbnb",               "kind": "greenhouse", "slug": "airbnb",               "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "LinkedIn",             "kind": "greenhouse", "slug": "linkedin",             "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Pinterest",            "kind": "greenhouse", "slug": "pinterest",            "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Discord",              "kind": "greenhouse", "slug": "discord",              "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Roblox",               "kind": "greenhouse", "slug": "roblox",               "queries": ["security", "cryptography", "CTO", "VP"]},
    # Enterprise / infra
    {"name": "Stripe",               "kind": "greenhouse", "slug": "stripe",               "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Twilio",               "kind": "greenhouse", "slug": "twilio",               "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Dropbox",              "kind": "greenhouse", "slug": "dropbox",              "queries": ["security", "cryptography", "CTO", "VP"]},
    # Fintech (crypto/trading — relevant to Benoit's crypto background)
    {"name": "Block",                "kind": "greenhouse", "slug": "block",                "queries": ["security", "cryptography", "CTO", "VP"]},
    {"name": "Robinhood",            "kind": "greenhouse", "slug": "robinhood",            "queries": ["security", "cryptography", "CTO", "VP"]},

    # --- Wave 4 via debug/ats_probe.py 2026-09-25 (music/audio) ------------
    {"name": "Fender",               "kind": "greenhouse", "slug": "fender",               "queries": []},
    {"name": "Universal Audio",      "kind": "greenhouse", "slug": "universalaudio",       "queries": []},
    {"name": "Slate Digital",        "kind": "ashby",      "slug": "slate",                "queries": []},
    {"name": "Output",               "kind": "ashby",      "slug": "output",               "queries": []},
    {"name": "Pioneer DJ",           "kind": "ashby",      "slug": "pioneer",              "queries": []},

    # --- Wave 5 via debug/music_url_probe.sh 2026-09-28 (music hardware) ---
    # ATS-supported (JSON APIs, fast fetchers)
    {"name": "Softube",              "kind": "bamboohr",   "slug": "softube",              "queries": [],
     "board": "https://softube.bamboohr.com/careers"},
    {"name": "inMusic Brands",       "kind": "pinpoint",   "slug": "inmusicbrands",        "queries": [],
     "board": "https://inmusicbrands.pinpointhq.com/"},
    {"name": "Yamaha",               "kind": "umantis",    "slug": "yamaha",               "queries": [],
     "board": "https://recruitingapp-5230.de.umantis.com/Jobs/All",
     "search_url": "https://recruitingapp-5230.de.umantis.com/Jobs/All"},
    {"name": "Sonos",                "kind": "workday",    "slug": "sonos",                "queries": ["security", "manager", "CTO", "VP"],
     "board": "https://sonos.wd1.myworkdayjobs.com/Sonos"},
    {"name": "Sennheiser",           "kind": "successfactors", "slug": "sennheiser",       "queries": [],
     "board": "https://jobs.sennheiser.com/search/?q=&locationsearch=&locale=en_US&searchResultView=LIST"},
    {"name": "Bose",                 "kind": "phenom",     "slug": "bose",                 "queries": ["security", "manager", "CTO", "VP"],
     "board": "https://careers.bose.com/us/en",
     "search_url": "https://careers.bose.com/us/en?query=&sort_by=relevance"},

    # --- Wave 5 Playwright custom scrapers (verified 2026-09-28) ---
    # Teamtailor: standard hosted careers with anchor pattern /jobs/<id>-<slug>
    {"name": "Roland",               "kind": "teamtailor", "slug": "roland",               "queries": [],
     "board": "https://www.rolandcareers.com/jobs"},
    {"name": "Marshall",             "kind": "teamtailor", "slug": "marshall",             "queries": [],
     "board": "https://careers.marshall.com/jobs"},
    {"name": "Elektron",             "kind": "teamtailor", "slug": "elektron",             "queries": [],
     "board": "https://careers.elektron.se/jobs"},
    # Phenom: same fetcher as Microsoft/NVIDIA
    {"name": "Dolby",                "kind": "phenom",     "slug": "dolby",                "queries": ["security", "manager", "CTO", "VP"],
     "board": "https://jobs.dolby.com/careers",
     "search_url": "https://jobs.dolby.com/careers?query=&sort_by=relevance"},
    # BorisFX (parent of iZotope group post-2024 restructure — same careers portal)
    {"name": "Boris FX / iZotope",   "kind": "pw",         "slug": "borisfx",              "queries": [],
     "board": "https://borisfx.com/company/careers/",
     "search_url": "https://borisfx.com/company/careers/",
     "link_re": r'href="(/company/careers/#[a-z0-9-]+)"',
     "origin": "https://borisfx.com"},
    # HiringThing (Seymour Duncan)
    {"name": "Seymour Duncan",       "kind": "pw",         "slug": "seymour",              "queries": [],
     "board": "https://www.seymourduncan.com/company/join-our-team",
     "search_url": "https://www.seymourduncan.com/company/join-our-team",
     "link_re": r'href="(https?://yoursmartsource\.hiringthing\.com/job/\d+/[a-z0-9-]+|/[a-z0-9-]+-job-posting)"',
     "origin": "https://www.seymourduncan.com"},
    # Direct HTML scrapers with proper regexes
    {"name": "MOTU",                 "kind": "pw",         "slug": "motu",                 "queries": [],
     "board": "https://motu.com/en-us/company/careers/",
     "search_url": "https://motu.com/en-us/company/careers/",
     "link_re": r'href="(/en-us/company/careers/(?!$)[a-z0-9-]+/?)"',
     "origin": "https://motu.com"},
    # Boss: single page with all listings inline as <h3> — custom fetcher.
    {"name": "Boss",                 "kind": "boss",       "slug": "boss",                 "queries": [],
     "board": "https://www.boss.info/uk/company/employment_opportunities/employment_opportunities/"},
    # NOTE: These sites had static career pages with no scrapable listings.
    # Removed from SOURCES rather than shipping broken/empty entries.
    # Focusrite   — WordPress marketing page, no listings visible
    # Fractal     — WordPress marketing page, mailto only
    # Antares     — Static single-page, no listings
    # Korg        — 16KB page, no listings visible
    # Ibanez      — Marketing page with images, no listings
    # PRS Guitars — Marketing page, no listings visible
    # PreSonus    — Marketing page with only link to Fender
    # Gibson      — ADP behind heavy JS bundle (needs deeper investigation)
    # Yamaha Guitar Group — AppOne iframe (would need iframe navigation)
    # Boss        — Marketing page (only self-links in tests)
    # See TODO.txt for follow-up options.
]

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
    "Welcome to the Jungle": {"blurb": "French job board / media",                    "employees": "~350",    "revenue": "~$50M"},

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
    "Security Companies",
    "Other",
    "Music Companies",
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
    "SandboxAQ":             "Security Companies",  # PQC/crypto — Benoit's specialty
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
    "open application",
    "unsolicited application",
]
