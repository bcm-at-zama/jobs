"""data/user_config.py — your personal preferences.

Lives outside src/ so personal data stays out of source code. Loaded
by src/config.py at import time if present. Copy src/user_config.example.py
→ data/user_config.py on first install and edit to taste.
"""

# =============================================================================
# HIGHLIGHTS — words drawn with a marker style in titles + descriptions
# =============================================================================

HIGHLIGHTS = ["Security", "Codex", "Codemender", "Cyber",
              "CyberSecurity", "SEAR", "DeepMind", "Researcher", "Logic",
              "Codex Security", "Claude Security"]

# =============================================================================
# TITLE_BLACKLIST — case-insensitive title substrings to hide
# =============================================================================

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
    # Batch-added from planning/TOREVIEW.md
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

# =============================================================================
# LOCATION_BLACKLIST — if ALL of a job's locations contain one of these,
# the job is hidden.
# =============================================================================

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
    "Vietnam", "Ho Chi Minh",
    "Philippines", "Manila",
    "Thailand", "Bangkok",
]

# =============================================================================
# SOURCES — company career boards to scrape. One entry per ATS board.
# Framework-neutral metadata (blurbs, employees, revenue, group) lives in
# src/config.py — only the per-user selection lives here.
# =============================================================================

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
    # Snyk uses Ashby under the hood (jobs.ashbyhq.com/<workspace-uuid>/…
    # on snyk.io/careers/all-jobs/). Friendly slug "snyk" works on the Ashby
    # posting API — verified 2026-10-02 via probe_broken_sources.py (13 jobs
    # returned). The previous pw-based scraper never matched any href because
    # Snyk doesn't publish greenhouse URLs nor /fr/careers/<slug> pages.
    {"name": "Snyk",       "kind": "ashby",      "slug": "snyk",       "queries": []},
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
    {"name": "Pinecone",             "kind": "ashby",      "slug": "pinecone",             "queries": []},
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
    {"name": "Dataiku",              "kind": "greenhouse", "slug": "dataiku",              "queries": []},
    {"name": "Owkin",                "kind": "ashby",      "slug": "owkin",                "queries": []},
    # Adjacent
    {"name": "Fastly",               "kind": "greenhouse", "slug": "fastly",               "queries": ["security", "manager", "CTO", "VP"]},
    {"name": "Datadog",              "kind": "greenhouse", "slug": "datadog",              "queries": ["security", "manager", "CTO", "VP"]},

    # --- Wave 3 via debug/ats_probe.py 2026-09-25 (quasi-GAFAM) ------------
    # Big consumer tech
    {"name": "Airbnb",               "kind": "greenhouse", "slug": "airbnb",               "queries": []},
    # LinkedIn: no public ATS; scraped from the guest /jobs/search/ pages.
    # Pagination doesn't work (verified: &start=N ignored), so we union three
    # filter variants to widen coverage from 60 → ~110 jobs:
    #   - strict: f_C=1337 + geoId=US + f_TPR=7d + salary bands
    #   - medium: same, f_TPR=30d (gets different top-60)
    #   - loose:  no time/salary filter (the 200-roles headline page)
    # f_C=1337 = LinkedIn-the-company; geoId=103644278 = United States.
    # Note: /jobs/search-results/ (logged-in UI) returns a login wall;
    # /jobs/search/ (guest) renders cards server-side.
    {"name": "LinkedIn",             "kind": "linkedin",   "slug": "linkedin",             "queries": [],
     "board": "https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278",
     "urls": [
         "https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278&f_TPR=r604800&f_SAL=f_SA_id_227001%3A278001%2C272003%2C279001%24f_SA_id_226001%3A272015&keywords=jobs",
         "https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278&f_TPR=r2592000&f_SAL=f_SA_id_227001%3A278001%2C272003%2C279001%24f_SA_id_226001%3A272015&keywords=jobs",
         "https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278",
     ]},
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
     "display_name": "inMusic Brands (including Native Instruments)",
     "board": "https://inmusicbrands.pinpointhq.com/"},
    {"name": "Yamaha",               "kind": "umantis",    "slug": "yamaha",               "queries": [],
     "board": "https://recruitingapp-5230.de.umantis.com/Jobs/All",
     "search_url": "https://recruitingapp-5230.de.umantis.com/Jobs/All"},
    {"name": "Sonos",                "kind": "workday",    "slug": "sonos",                "queries": ["security", "manager", "CTO", "VP"],
     "board": "https://sonos.wd1.myworkdayjobs.com/Sonos"},
    {"name": "Sennheiser",           "kind": "successfactors", "slug": "sennheiser",       "queries": [],
     "board": "https://jobs.sennheiser.com/search/?q=&locationsearch=&locale=en_US&searchResultView=LIST"},
    {"name": "Bose",                 "kind": "bose",       "slug": "bose",                 "queries": [],
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
     "link_re": r'href="(https?://yoursmartsource\.hiringthing\.com/job/\d+/[a-z0-9-]+|https?://(?:www\.)?seymourduncan\.com/[a-z0-9-]+-job-posting|/[a-z0-9-]+-job-posting)"',
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
    # --- Wave 6: Big Tech + GAFAM-adjacent — VERIFIED WORKING ---
    {"name": "Adobe",                "kind": "workday",    "slug": "adobe",                "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://adobe.wd5.myworkdayjobs.com/external_experienced"},
    {"name": "Salesforce",           "kind": "workday",    "slug": "salesforce",           "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"},
    {"name": "Intel",                "kind": "workday",    "slug": "intel",                "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://intel.wd1.myworkdayjobs.com/External"},
    {"name": "PayPal",               "kind": "workday",    "slug": "paypal",               "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://paypal.wd1.myworkdayjobs.com/jobs"},
    # SAP uses their own jobs.sap.com portal with URL pattern
    #   https://jobs.sap.com/en/jobs/<id>/<slug>/
    # Verified 2026-10-01: regex pulls 12 jobs from the rendered dump. We use
    # the same search URL that successfully rendered before (SF endpoint
    # happens to serve the same listings page).
    {"name": "SAP",                  "kind": "pw",         "slug": "sap",                  "queries": [],
     "board": "https://jobs.sap.com/search/?q=&locationsearch=&searchResultView=LIST",
     "search_url": "https://jobs.sap.com/search/?q=&locationsearch=&searchResultView=LIST",
     "link_re": r'href="(/en/jobs/\d+/[^"#?]+)"',
     "origin": "https://jobs.sap.com"},
    # Avid on Workday. Verified 2026-10-01: wd5 (not wd1), board=AVID (uppercase).
    {"name": "Avid",                 "kind": "workday",    "slug": "avid",                 "queries": [],
     "board": "https://avid.wd5.myworkdayjobs.com/AVID"},

    # VMware (now Broadcom) on Workday. Verified 2026-10-01.
    # Board: External_Career (not External_Career_Site as initially guessed).
    {"name": "VMware (Broadcom)",    "kind": "workday",    "slug": "broadcom",             "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://broadcom.wd1.myworkdayjobs.com/External_Career"},

    # IBM uses their own careers portal (NOT Workday). Search page is on
    # ibm.com, job detail URLs are on careers.ibm.com subdomain.
    # Verified 2026-10-01 via https://careers.ibm.com/en_US/careers/JobDetail?jobId=<id>
    # IBM: generic pw scraper derived titles from URL tail (/JobDetail?jobId=…)
    # so every job came out titled "Jobdetail". Dedicated fetch_ibm parses the
    # Carbon-Design cards and pulls the real title from aria-label.
    {"name": "IBM",                  "kind": "ibm",        "slug": "ibm",                  "queries": [],
     "board": "https://www.ibm.com/careers/search?q=security",
     "search_url": "https://www.ibm.com/careers/search?q=security"},

    # Qualcomm uses Phenom (same ATS as NVIDIA, Microsoft, Dolby, Bose).
    # Verified 2026-10-01 via https://careers.qualcomm.com/careers?pid=<id>
    {"name": "Qualcomm",             "kind": "phenom",     "slug": "qualcomm",             "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://careers.qualcomm.com/careers",
     "search_url": "https://careers.qualcomm.com/careers?query=security&sort_by=relevance"},

    # Unity on Workday. Tenant: unitytech, board_id: Unity. Verified 2026-10-01.
    {"name": "Unity",                "kind": "workday",    "slug": "unity",                "queries": ["security", "cryptography", "CTO", "VP"],
     "board": "https://unitytech.wd1.myworkdayjobs.com/Unity"},

    # Cisco uses Phenom People under the hood (tenant CISCISGLOBAL), BUT its
    # frontend ignores URL query params for search AND exposes a different
    # DOM shape (<a id="job-link">) + pagination param (?from=N instead of
    # ?start=N). Dedicated fetch_cisco paginates each category page.
    # Scope: Product & Engineering + Business Development & Strategy (VP
    # roles) + Other (catch-all). Remaining 5 categories (sales, business-
    # ops, supply-chain, etc.) excluded as not relevant to security/crypto/
    # CTO/VP profile.
    {"name": "Cisco",                "kind": "cisco",      "slug": "cisco",                "queries": [],
     "board": "https://careers.cisco.com/global/en",
     "categories": [
         "/global/en/c/product-and-engineering-jobs",
         "/global/en/c/business-development-and-strategy-jobs",
         "/global/en/c/other-jobs",
     ]},

    # Netflix uses Eightfold.ai with a vanity host. Verified 2026-10-01 via
    # https://explore.jobs.netflix.net/careers?pid=<id>&domain=netflix.com
    {"name": "Netflix",              "kind": "eightfold",  "slug": "netflix",              "queries": ["security", "cryptography", "CTO", "VP"],
     "host": "https://explore.jobs.netflix.net",
     "domain": "netflix.com"},

    # Palantir uses Lever. Verified 2026-10-01 via sample URL
    #   https://jobs.lever.co/palantir/<uuid>
    {"name": "Palantir",             "kind": "lever",      "slug": "palantir",             "queries": ["security", "cryptography", "CTO", "VP"]},

    # GitGuardian — careers page serves job cards directly on their own
    # domain (not an iframe). URL pattern verified 2026-10-01:
    #   https://www.gitguardian.com/job-openings/<id>-<title-slug>
    {"name": "GitGuardian",          "kind": "pw",         "slug": "gitguardian",          "queries": [],
     "board": "https://www.gitguardian.com/careers",
     "search_url": "https://www.gitguardian.com/careers",
     "link_re": r'href="(/job-openings/\d+-[a-z0-9-]+)"',
     "origin": "https://www.gitguardian.com"},

    # --- Removed on 2026-10-01 (first run returned 404 / 422 / 0 matches) ---
    # The URLs I guessed were wrong. Pending user to probe real URLs on their Mac
    # and send them to me — see planning/open/11-companies-backlog.md
    # (section "Probing a broken source") for the probe instructions. Specifically:
    #   Qualcomm, IBM, Unity, Cisco, VMware (Broadcom), Avid  — Workday board_id wrong
    #   Groq, Palantir, GitGuardian, Beatport                 — Greenhouse slug wrong
    #   Native Instruments, Netflix, Bitwig, Sequential       — Playwright pages don't
    #                                                           expose job URLs as HTML
    #                                                           links (JS-rendered).

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
    # See planning/open/11-companies-backlog.md for follow-up options.
]
