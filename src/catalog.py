"""catalog.py — the full set of companies this engine can scrape.

This is the "menu" the onboarding wizard shows. Each entry carries just
enough plumbing (kind + slug + any ATS-specific extras like `board`,
`search_url`, `link_re`, `wait_selector`, `host`, `domain`, `urls`,
`origin`, `display_name`, `categories`) for the wizard to generate a
valid SOURCES entry in data/user_config.py.

User-tunable fields (`queries`) are intentionally NOT here — those are
personal and belong in data/user_config.py only.

Generated from data/user_config.py; see tooling/build_catalog.py if we
ever want a repeatable rebuild. For now, hand-maintained + re-run the
extraction when adding a new company.
"""

CATALOG = [{'name': 'AMI', 'kind': 'ashby', 'slug': 'ami', 'group': 'AI Startups'},
 {'name': 'Anyscale', 'kind': 'ashby', 'slug': 'anyscale', 'group': 'AI Startups'},
 {'name': 'AssemblyAI', 'kind': 'greenhouse', 'slug': 'assemblyai', 'group': 'AI Startups'},
 {'name': 'Baseten', 'kind': 'ashby', 'slug': 'baseten', 'group': 'AI Startups'},
 {'name': 'Black Forest Labs',
  'kind': 'pw',
  'slug': 'blackforestlabs',
  'board': 'https://bfl.ai/careers',
  'search_url': 'https://bfl.ai/careers',
  'link_re': 'href="(https?://[^"]*greenhouse[^"]*/blackforestlabs[^"]*|/careers/[^"#?/]+/?)"',
  'origin': 'https://bfl.ai',
  'wait_selector': "a[href*='greenhouse'], a[href*='/careers/']",
  'group': 'AI Startups'},
 {'name': 'Braintrust', 'kind': 'ashby', 'slug': 'braintrust', 'group': 'AI Startups'},
 {'name': 'Cerebras', 'kind': 'ashby', 'slug': 'cerebras', 'group': 'AI Startups'},
 {'name': 'Character AI', 'kind': 'ashby', 'slug': 'character', 'group': 'AI Startups'},
 {'name': 'Cline', 'kind': 'greenhouse', 'slug': 'cline', 'group': 'AI Startups'},
 {'name': 'Cognition',
  'kind': 'ashby',
  'slug': 'cognition',
  'board': 'https://cognition.com/careers',
  'group': 'AI Startups'},
 {'name': 'Coreweave', 'kind': 'greenhouse', 'slug': 'coreweave', 'group': 'AI Startups'},
 {'name': 'Crusoe', 'kind': 'ashby', 'slug': 'crusoe', 'group': 'AI Startups'},
 {'name': 'Deepgram', 'kind': 'ashby', 'slug': 'deepgram', 'group': 'AI Startups'},
 {'name': 'Etched', 'kind': 'ashby', 'slug': 'etched', 'group': 'AI Startups'},
 {'name': 'Fireworks AI', 'kind': 'ashby', 'slug': 'fireworks', 'group': 'AI Startups'},
 {'name': 'H', 'kind': 'ashby', 'slug': 'hcompany', 'group': 'AI Startups'},
 {'name': 'Imbue', 'kind': 'greenhouse', 'slug': 'imbue', 'group': 'AI Startups'},
 {'name': 'Lambda', 'kind': 'ashby', 'slug': 'lambda', 'group': 'AI Startups'},
 {'name': 'LangChain', 'kind': 'ashby', 'slug': 'langchain', 'group': 'AI Startups'},
 {'name': 'Lightning AI', 'kind': 'greenhouse', 'slug': 'lightningai', 'group': 'AI Startups'},
 {'name': 'LlamaIndex', 'kind': 'ashby', 'slug': 'llamaindex', 'group': 'AI Startups'},
 {'name': 'MatX', 'kind': 'ashby', 'slug': 'matx', 'group': 'AI Startups'},
 {'name': 'Modal', 'kind': 'ashby', 'slug': 'modal', 'group': 'AI Startups'},
 {'name': 'Nebius', 'kind': 'greenhouse', 'slug': 'nebius', 'group': 'AI Startups'},
 {'name': 'Nomic', 'kind': 'ashby', 'slug': 'nomic', 'group': 'AI Startups'},
 {'name': 'Observe AI', 'kind': 'greenhouse', 'slug': 'observeai', 'group': 'AI Startups'},
 {'name': 'Perplexity', 'kind': 'ashby', 'slug': 'perplexity', 'group': 'AI Startups'},
 {'name': 'Physical Intelligence', 'kind': 'ashby', 'slug': 'physicalintelligence', 'group': 'AI Startups'},
 {'name': 'Pika', 'kind': 'ashby', 'slug': 'pika', 'group': 'AI Startups'},
 {'name': 'Pinecone', 'kind': 'ashby', 'slug': 'pinecone', 'group': 'AI Startups'},
 {'name': 'Poolside', 'kind': 'ashby', 'slug': 'poolside', 'group': 'AI Startups'},
 {'name': 'Prime Intellect', 'kind': 'ashby', 'slug': 'primeintellect', 'group': 'AI Startups'},
 {'name': 'Rain', 'kind': 'ashby', 'slug': 'rain', 'group': 'AI Startups'},
 {'name': 'Reka', 'kind': 'ashby', 'slug': 'reka', 'group': 'AI Startups'},
 {'name': 'Replit', 'kind': 'ashby', 'slug': 'replit', 'group': 'AI Startups'},
 {'name': 'Rewind AI', 'kind': 'ashby', 'slug': 'rewind', 'group': 'AI Startups'},
 {'name': 'Runway', 'kind': 'ashby', 'slug': 'runway', 'group': 'AI Startups'},
 {'name': 'Sakana AI', 'kind': 'workable', 'slug': 'sakana-ai', 'group': 'AI Startups'},
 {'name': 'SSI', 'kind': 'ashby', 'slug': 'ssi', 'group': 'AI Startups'},
 {'name': 'Tenstorrent', 'kind': 'greenhouse', 'slug': 'tenstorrent', 'group': 'AI Startups'},
 {'name': 'Thinking Machines', 'kind': 'ashby', 'slug': 'ThinkingMachines', 'group': 'AI Startups'},
 {'name': 'Together AI', 'kind': 'greenhouse', 'slug': 'togetherai', 'group': 'AI Startups'},
 {'name': 'Voyage AI', 'kind': 'workable', 'slug': 'voyage', 'group': 'AI Startups'},
 {'name': 'Weaviate', 'kind': 'ashby', 'slug': 'weaviate', 'group': 'AI Startups'},
 {'name': 'Zed', 'kind': 'ashby', 'slug': 'zed', 'group': 'AI Startups'},
 {'name': 'Adobe',
  'kind': 'workday',
  'slug': 'adobe',
  'board': 'https://adobe.wd5.myworkdayjobs.com/external_experienced',
  'group': 'Big Tech'},
 {'name': 'Airbnb', 'kind': 'greenhouse', 'slug': 'airbnb', 'group': 'Big Tech'},
 {'name': 'Apple',
  'kind': 'apple',
  'slug': 'apple',
  'board': 'https://jobs.apple.com/en-us/search?search=security',
  'group': 'Big Tech'},
 {'name': 'Block', 'kind': 'greenhouse', 'slug': 'block', 'group': 'Big Tech'},
 {'name': 'Cisco',
  'kind': 'cisco',
  'slug': 'cisco',
  'board': 'https://careers.cisco.com/global/en',
  'categories': ['/global/en/c/product-and-engineering-jobs',
                 '/global/en/c/business-development-and-strategy-jobs',
                 '/global/en/c/other-jobs'],
  'group': 'Big Tech'},
 {'name': 'Discord', 'kind': 'greenhouse', 'slug': 'discord', 'group': 'Big Tech'},
 {'name': 'Dropbox', 'kind': 'greenhouse', 'slug': 'dropbox', 'group': 'Big Tech'},
 {'name': 'GitHub',
  'kind': 'github',
  'slug': 'github',
  'board': 'https://www.github.careers/careers-home/jobs?keywords=security',
  'search_url': 'https://www.github.careers/careers-home/jobs?keywords=security',
  'group': 'Big Tech'},
 {'name': 'Google',
  'kind': 'google',
  'slug': 'google',
  'board': 'https://www.google.com/about/careers/applications/jobs/results/?q=security&hl=en_US',
  'search_url': 'https://www.google.com/about/careers/applications/jobs/results?hl=en_US&target_level=DIRECTOR_PLUS&target_level=ADVANCED&employment_type=FULL_TIME',
  'group': 'Big Tech'},
 {'name': 'IBM',
  'kind': 'ibm',
  'slug': 'ibm',
  'board': 'https://www.ibm.com/careers/search?q=security',
  'search_url': 'https://www.ibm.com/careers/search?q=security',
  'group': 'Big Tech'},
 {'name': 'Intel',
  'kind': 'workday',
  'slug': 'intel',
  'board': 'https://intel.wd1.myworkdayjobs.com/External',
  'group': 'Big Tech'},
 {'name': 'LinkedIn',
  'kind': 'linkedin',
  'slug': 'linkedin',
  'board': 'https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278',
  'urls': ['https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278&f_TPR=r604800&f_SAL=f_SA_id_227001%3A278001%2C272003%2C279001%24f_SA_id_226001%3A272015&keywords=jobs',
           'https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278&f_TPR=r2592000&f_SAL=f_SA_id_227001%3A278001%2C272003%2C279001%24f_SA_id_226001%3A272015&keywords=jobs',
           'https://www.linkedin.com/jobs/search/?f_C=1337&geoId=103644278'],
  'group': 'Big Tech'},
 {'name': 'Meta',
  'kind': 'meta',
  'slug': 'meta',
  'board': 'https://www.metacareers.com/jobsearch/?q=security',
  'group': 'Big Tech'},
 {'name': 'Microsoft',
  'kind': 'microsoft',
  'slug': 'microsoft',
  'board': 'https://apply.careers.microsoft.com/careers?query=Security&pid=1970393556942260&sort_by=relevance',
  'group': 'Big Tech'},
 {'name': 'Netflix',
  'kind': 'eightfold',
  'slug': 'netflix',
  'host': 'https://explore.jobs.netflix.net',
  'domain': 'netflix.com',
  'group': 'Big Tech'},
 {'name': 'NVIDIA',
  'kind': 'phenom',
  'slug': 'nvidia',
  'board': 'https://jobs.nvidia.com/careers?query=Security&pid=893394830937&sort_by=relevance',
  'search_url': 'https://jobs.nvidia.com/careers?query=Security&sort_by=relevance',
  'group': 'Big Tech'},
 {'name': 'Palantir', 'kind': 'lever', 'slug': 'palantir', 'group': 'Big Tech'},
 {'name': 'PayPal',
  'kind': 'workday',
  'slug': 'paypal',
  'board': 'https://paypal.wd1.myworkdayjobs.com/jobs',
  'group': 'Big Tech'},
 {'name': 'Pinterest', 'kind': 'greenhouse', 'slug': 'pinterest', 'group': 'Big Tech'},
 {'name': 'Proton', 'kind': 'greenhouse', 'slug': 'proton', 'board': 'https://proton.me/careers', 'group': 'Big Tech'},
 {'name': 'Qualcomm',
  'kind': 'phenom',
  'slug': 'qualcomm',
  'board': 'https://careers.qualcomm.com/careers',
  'search_url': 'https://careers.qualcomm.com/careers?query=security&sort_by=relevance',
  'group': 'Big Tech'},
 {'name': 'Robinhood', 'kind': 'greenhouse', 'slug': 'robinhood', 'group': 'Big Tech'},
 {'name': 'Roblox', 'kind': 'greenhouse', 'slug': 'roblox', 'group': 'Big Tech'},
 {'name': 'Salesforce',
  'kind': 'workday',
  'slug': 'salesforce',
  'board': 'https://salesforce.wd12.myworkdayjobs.com/External_Career_Site',
  'group': 'Big Tech'},
 {'name': 'SAP',
  'kind': 'pw',
  'slug': 'sap',
  'board': 'https://jobs.sap.com/search/?q=&locationsearch=&searchResultView=LIST',
  'search_url': 'https://jobs.sap.com/search/?q=&locationsearch=&searchResultView=LIST',
  'link_re': 'href="(/en/jobs/\\d+/[^"#?]+)"',
  'origin': 'https://jobs.sap.com',
  'group': 'Big Tech'},
 {'name': 'Stripe', 'kind': 'greenhouse', 'slug': 'stripe', 'group': 'Big Tech'},
 {'name': 'Twilio', 'kind': 'greenhouse', 'slug': 'twilio', 'group': 'Big Tech'},
 {'name': 'Unity',
  'kind': 'workday',
  'slug': 'unity',
  'board': 'https://unitytech.wd1.myworkdayjobs.com/Unity',
  'group': 'Big Tech'},
 {'name': 'VMware (Broadcom)',
  'kind': 'workday',
  'slug': 'broadcom',
  'board': 'https://broadcom.wd1.myworkdayjobs.com/External_Career',
  'group': 'Big Tech'},
 {'name': 'Anthropic', 'kind': 'greenhouse', 'slug': 'anthropic', 'group': 'Major AI Companies'},
 {'name': 'Cohere', 'kind': 'ashby', 'slug': 'cohere', 'group': 'Major AI Companies'},
 {'name': 'Cursor',
  'kind': 'ashby',
  'slug': 'cursor',
  'board': 'https://cursor.com/careers',
  'group': 'Major AI Companies'},
 {'name': 'DeepL', 'kind': 'ashby', 'slug': 'DeepL', 'group': 'Major AI Companies'},
 {'name': 'Eleven Labs', 'kind': 'ashby', 'slug': 'elevenlabs', 'group': 'Major AI Companies'},
 {'name': 'HF',
  'kind': 'workable',
  'slug': 'huggingface',
  'board': 'https://apply.workable.com/huggingface/',
  'group': 'Major AI Companies'},
 {'name': 'Mistral', 'kind': 'ashby', 'slug': 'mistral.ai', 'group': 'Major AI Companies'},
 {'name': 'OpenAI', 'kind': 'ashby', 'slug': 'openai', 'group': 'Major AI Companies'},
 {'name': 'Scale AI',
  'kind': 'scale',
  'slug': 'scale',
  'board': 'https://scale.com/careers',
  'search_url': 'https://scale.com/careers',
  'group': 'Major AI Companies'},
 {'name': 'Sony AI',
  'kind': 'pw',
  'slug': 'sonyai',
  'board': 'https://ai.sony/join-us',
  'search_url': 'https://ai.sony/join-us',
  'link_re': 'href="(https?://[^"]*(?:jobs|careers|job-postings|apply)[^"]*|/(?:jobs|careers|open-roles)/[^"#?]+)"',
  'origin': 'https://ai.sony',
  'group': 'Major AI Companies'},
 {'name': 'Ableton',
  'kind': 'ableton',
  'slug': 'ableton',
  'board': 'https://www.ableton.com/en/jobs/',
  'group': 'Music Companies'},
 {'name': 'Arturia',
  'kind': 'lucca',
  'slug': 'arturia-france',
  'board': 'https://jobs.world.luccasoftware.com/arturia-france',
  'group': 'Music Companies'},
 {'name': 'Avid',
  'kind': 'workday',
  'slug': 'avid',
  'board': 'https://avid.wd5.myworkdayjobs.com/AVID',
  'group': 'Music Companies'},
 {'name': 'Boris FX / iZotope',
  'kind': 'pw',
  'slug': 'borisfx',
  'board': 'https://borisfx.com/company/careers/',
  'search_url': 'https://borisfx.com/company/careers/',
  'link_re': 'href="(/company/careers/#[a-z0-9-]+)"',
  'origin': 'https://borisfx.com',
  'group': 'Music Companies'},
 {'name': 'Bose',
  'kind': 'bose',
  'slug': 'bose',
  'board': 'https://careers.bose.com/us/en',
  'search_url': 'https://careers.bose.com/us/en?query=&sort_by=relevance',
  'group': 'Music Companies'},
 {'name': 'Boss',
  'kind': 'boss',
  'slug': 'boss',
  'board': 'https://www.boss.info/uk/company/employment_opportunities/employment_opportunities/',
  'group': 'Music Companies'},
 {'name': 'Dolby',
  'kind': 'phenom',
  'slug': 'dolby',
  'board': 'https://jobs.dolby.com/careers',
  'search_url': 'https://jobs.dolby.com/careers?query=&sort_by=relevance',
  'group': 'Music Companies'},
 {'name': 'Elektron',
  'kind': 'teamtailor',
  'slug': 'elektron',
  'board': 'https://careers.elektron.se/jobs',
  'group': 'Music Companies'},
 {'name': 'Fender', 'kind': 'greenhouse', 'slug': 'fender', 'group': 'Music Companies'},
 {'name': 'inMusic Brands',
  'kind': 'pinpoint',
  'slug': 'inmusicbrands',
  'display_name': 'inMusic Brands (including Native Instruments)',
  'board': 'https://inmusicbrands.pinpointhq.com/',
  'group': 'Music Companies'},
 {'name': 'Marshall',
  'kind': 'teamtailor',
  'slug': 'marshall',
  'board': 'https://careers.marshall.com/jobs',
  'group': 'Music Companies'},
 {'name': 'MOTU',
  'kind': 'pw',
  'slug': 'motu',
  'board': 'https://motu.com/en-us/company/careers/',
  'search_url': 'https://motu.com/en-us/company/careers/',
  'link_re': 'href="(/en-us/company/careers/(?!$)[a-z0-9-]+/?)"',
  'origin': 'https://motu.com',
  'group': 'Music Companies'},
 {'name': 'Neural DSP',
  'kind': 'pw',
  'slug': 'neuraldsp',
  'board': 'https://careers.neuraldsp.com/',
  'search_url': 'https://revolutpeople.com/neural-dsp/public/careers/',
  'link_re': 'href="(/neural-dsp/public/careers/[^"#?]+|https?://revolutpeople\\.com/neural-dsp/public/careers/[^"#?]+)"',
  'origin': 'https://revolutpeople.com',
  'group': 'Music Companies'},
 {'name': 'Output', 'kind': 'ashby', 'slug': 'output', 'group': 'Music Companies'},
 {'name': 'Pioneer DJ', 'kind': 'ashby', 'slug': 'pioneer', 'group': 'Music Companies'},
 {'name': 'Roland',
  'kind': 'teamtailor',
  'slug': 'roland',
  'board': 'https://www.rolandcareers.com/jobs',
  'group': 'Music Companies'},
 {'name': 'Sennheiser',
  'kind': 'successfactors',
  'slug': 'sennheiser',
  'board': 'https://jobs.sennheiser.com/search/?q=&locationsearch=&locale=en_US&searchResultView=LIST',
  'group': 'Music Companies'},
 {'name': 'Seymour Duncan',
  'kind': 'pw',
  'slug': 'seymour',
  'board': 'https://www.seymourduncan.com/company/join-our-team',
  'search_url': 'https://www.seymourduncan.com/company/join-our-team',
  'link_re': 'href="(https?://yoursmartsource\\.hiringthing\\.com/job/\\d+/[a-z0-9-]+|https?://(?:www\\.)?seymourduncan\\.com/[a-z0-9-]+-job-posting|/[a-z0-9-]+-job-posting)"',
  'origin': 'https://www.seymourduncan.com',
  'group': 'Music Companies'},
 {'name': 'Slate Digital', 'kind': 'ashby', 'slug': 'slate', 'group': 'Music Companies'},
 {'name': 'Softube',
  'kind': 'bamboohr',
  'slug': 'softube',
  'board': 'https://softube.bamboohr.com/careers',
  'group': 'Music Companies'},
 {'name': 'Sonos',
  'kind': 'workday',
  'slug': 'sonos',
  'board': 'https://sonos.wd1.myworkdayjobs.com/Sonos',
  'group': 'Music Companies'},
 {'name': 'Spitfire Audio', 'kind': 'greenhouse', 'slug': 'spitfire', 'group': 'Music Companies'},
 {'name': 'Splice', 'kind': 'greenhouse', 'slug': 'splice', 'group': 'Music Companies'},
 {'name': 'Steinberg',
  'kind': 'pw',
  'slug': 'steinberg',
  'board': 'https://www.steinberg.net/careers/vacancies/',
  'search_url': 'https://www.steinberg.net/careers/vacancies/',
  'link_re': 'href="(https?://www\\.steinberg\\.net/careers/[^"#?]+|/careers/[^"#?/]+/[^"#?]+)"',
  'origin': 'https://www.steinberg.net',
  'group': 'Music Companies'},
 {'name': 'Suno', 'kind': 'ashby', 'slug': 'suno', 'group': 'Music Companies'},
 {'name': 'Udio', 'kind': 'greenhouse', 'slug': 'udio', 'group': 'Music Companies'},
 {'name': 'Universal Audio', 'kind': 'greenhouse', 'slug': 'universalaudio', 'group': 'Music Companies'},
 {'name': 'Yamaha',
  'kind': 'umantis',
  'slug': 'yamaha',
  'board': 'https://recruitingapp-5230.de.umantis.com/Jobs/All',
  'search_url': 'https://recruitingapp-5230.de.umantis.com/Jobs/All',
  'group': 'Music Companies'},
 {'name': 'Alan', 'kind': 'ashby', 'slug': 'alan', 'group': 'Other'},
 {'name': 'Brex', 'kind': 'greenhouse', 'slug': 'brex', 'group': 'Other'},
 {'name': 'Databricks', 'kind': 'greenhouse', 'slug': 'databricks', 'group': 'Other'},
 {'name': 'Datadog', 'kind': 'greenhouse', 'slug': 'datadog', 'group': 'Other'},
 {'name': 'Dataiku', 'kind': 'greenhouse', 'slug': 'dataiku', 'group': 'Other'},
 {'name': 'Doctolib', 'kind': 'ashby', 'slug': 'doctolib', 'group': 'Other'},
 {'name': 'Fastly', 'kind': 'greenhouse', 'slug': 'fastly', 'group': 'Other'},
 {'name': 'Figma', 'kind': 'greenhouse', 'slug': 'figma', 'group': 'Other'},
 {'name': 'Fivetran', 'kind': 'greenhouse', 'slug': 'fivetran', 'group': 'Other'},
 {'name': 'GitLab', 'kind': 'greenhouse', 'slug': 'gitlab', 'group': 'Other'},
 {'name': 'Grafana Labs', 'kind': 'greenhouse', 'slug': 'grafanalabs', 'group': 'Other'},
 {'name': 'HashiCorp', 'kind': 'workable', 'slug': 'hashicorp', 'group': 'Other'},
 {'name': 'Hex', 'kind': 'ashby', 'slug': 'hex', 'group': 'Other'},
 {'name': 'Linear', 'kind': 'ashby', 'slug': 'linear', 'group': 'Other'},
 {'name': 'Mercury', 'kind': 'ashby', 'slug': 'mercury', 'group': 'Other'},
 {'name': 'MongoDB', 'kind': 'greenhouse', 'slug': 'mongodb', 'group': 'Other'},
 {'name': 'Owkin', 'kind': 'ashby', 'slug': 'owkin', 'group': 'Other'},
 {'name': 'Qonto', 'kind': 'ashby', 'slug': 'qonto', 'group': 'Other'},
 {'name': 'Reddit', 'kind': 'greenhouse', 'slug': 'reddit', 'group': 'Other'},
 {'name': 'Snowflake', 'kind': 'ashby', 'slug': 'snowflake', 'group': 'Other'},
 {'name': 'Vercel', 'kind': 'greenhouse', 'slug': 'vercel', 'group': 'Other'},
 {'name': '1Password', 'kind': 'ashby', 'slug': '1password', 'group': 'Security Companies'},
 {'name': 'Aisle',
  'kind': 'ashby',
  'slug': 'aisle',
  'board': 'https://aisle.com/careers',
  'group': 'Security Companies'},
 {'name': 'BeyondTrust', 'kind': 'greenhouse', 'slug': 'beyondtrust', 'group': 'Security Companies'},
 {'name': 'Bitwarden', 'kind': 'greenhouse', 'slug': 'bitwarden', 'group': 'Security Companies'},
 {'name': 'Cape Privacy', 'kind': 'ashby', 'slug': 'cape', 'group': 'Security Companies'},
 {'name': 'Chainguard', 'kind': 'greenhouse', 'slug': 'chainguard', 'group': 'Security Companies'},
 {'name': 'Checkmarx',
  'kind': 'checkmarx',
  'slug': 'checkmarx',
  'board': 'https://checkmarx.com/company/careers/',
  'search_url': 'https://checkmarx.com/company/careers/',
  'group': 'Security Companies'},
 {'name': 'Cloudflare', 'kind': 'greenhouse', 'slug': 'cloudflare', 'group': 'Security Companies'},
 {'name': 'Corgea',
  'kind': 'pw',
  'slug': 'corgea',
  'board': 'https://www.ycombinator.com/companies/corgea/jobs',
  'search_url': 'https://www.ycombinator.com/companies/corgea/jobs',
  'link_re': 'href="(/companies/corgea/jobs/[^"#?]+)"',
  'origin': 'https://www.ycombinator.com',
  'group': 'Security Companies'},
 {'name': 'CrowdStrike',
  'kind': 'pw',
  'slug': 'crowdstrike',
  'board': 'https://crowdstrike.wd5.myworkdayjobs.com/en-US/crowdstrikecareers?q=security',
  'search_url': 'https://crowdstrike.wd5.myworkdayjobs.com/en-US/crowdstrikecareers?q=security',
  'link_re': 'href="(/en-US/crowdstrikecareers/job/[^"]+)"',
  'origin': 'https://crowdstrike.wd5.myworkdayjobs.com',
  'wait_selector': "a[href*='/crowdstrikecareers/job/']",
  'group': 'Security Companies'},
 {'name': 'Cybereason', 'kind': 'greenhouse', 'slug': 'cybereason', 'group': 'Security Companies'},
 {'name': 'DepthFirst', 'kind': 'ashby', 'slug': 'depthfirst', 'group': 'Security Companies'},
 {'name': 'Doppler', 'kind': 'ashby', 'slug': 'doppler', 'group': 'Security Companies'},
 {'name': 'Drata', 'kind': 'ashby', 'slug': 'drata', 'group': 'Security Companies'},
 {'name': 'Elastic', 'kind': 'greenhouse', 'slug': 'elastic', 'group': 'Security Companies'},
 {'name': 'Endor Labs', 'kind': 'greenhouse', 'slug': 'endorlabs', 'group': 'Security Companies'},
 {'name': 'GitGuardian',
  'kind': 'pw',
  'slug': 'gitguardian',
  'board': 'https://www.gitguardian.com/careers',
  'search_url': 'https://www.gitguardian.com/careers',
  'link_re': 'href="(/job-openings/\\d+-[a-z0-9-]+)"',
  'origin': 'https://www.gitguardian.com',
  'group': 'Security Companies'},
 {'name': 'Netskope', 'kind': 'greenhouse', 'slug': 'netskope', 'group': 'Security Companies'},
 {'name': 'Nord Security', 'kind': 'ashby', 'slug': 'nord-security', 'group': 'Security Companies'},
 {'name': 'Okta', 'kind': 'greenhouse', 'slug': 'okta', 'group': 'Security Companies'},
 {'name': 'Pixee',
  'kind': 'pixee',
  'slug': 'pixee',
  'board': 'https://app.dover.com/jobs/pixee',
  'search_url': 'https://app.dover.com/jobs/pixee',
  'group': 'Security Companies'},
 {'name': 'PQShield', 'kind': 'greenhouse', 'slug': 'pqshield', 'group': 'Security Companies'},
 {'name': 'SandboxAQ', 'kind': 'ashby', 'slug': 'sandboxaq', 'group': 'Security Companies'},
 {'name': 'Semgrep',
  'kind': 'pw',
  'slug': 'semgrep',
  'board': 'https://semgrep.dev/about/careers/',
  'search_url': 'https://semgrep.dev/about/careers/',
  'link_re': 'href="(https?://[^"]*greenhouse[^"]*/semgrep/jobs/\\d+[^"]*|/about/careers/[^"#?/]+/?)"',
  'origin': 'https://semgrep.dev',
  'wait_selector': "a[href*='/jobs/'], a[href*='/careers/']",
  'group': 'Security Companies'},
 {'name': 'Snyk', 'kind': 'ashby', 'slug': 'snyk', 'group': 'Security Companies'},
 {'name': 'Socket', 'kind': 'ashby', 'slug': 'socket', 'group': 'Security Companies'},
 {'name': 'Tailscale', 'kind': 'greenhouse', 'slug': 'tailscale', 'group': 'Security Companies'},
 {'name': 'Wiz', 'kind': 'ashby', 'slug': 'wiz', 'group': 'Security Companies'},
 {'name': 'XBOW', 'kind': 'ashby', 'slug': 'xbowcareers', 'group': 'Security Companies'},
 {'name': 'Yubico', 'kind': 'greenhouse', 'slug': 'yubico', 'group': 'Security Companies'},
 {'name': 'ZeroPath',
  'kind': 'pw',
  'slug': 'zeropath',
  'board': 'https://zeropath.com/careers',
  'search_url': 'https://zeropath.com/careers',
  'link_re': 'href="(https?://jobs\\.ashbyhq\\.com/[^"#?]+/[a-f0-9-]{20,}|/careers/[^"#?]+|https?://[^"]*(?:greenhouse|lever|workable|ashby)[^"]*)"',
  'origin': 'https://zeropath.com',
  'group': 'Security Companies'},

 # --- Verified 2026-10-07 via debug/probe_new_catalog.py --------------------
 # Cars
 {'name': 'Lucid Motors', 'kind': 'greenhouse', 'slug': 'lucidmotors', 'group': 'Cars'},
 {'name': 'Scout Motors', 'kind': 'greenhouse', 'slug': 'scoutmotors', 'group': 'Cars'},
 # Verified 2026-10-07 via debug/probe_misses_pw.py — Lever/pw recovered
 # after JS render.
 {'name': 'Zoox', 'kind': 'lever', 'slug': 'zoox', 'group': 'Cars'},
 # Verified 2026-10-07 via debug/probe_rescue.py (round 3).
 {'name': 'Toyota',
  'kind': 'workday',
  'slug': 'toyota',
  'board': 'https://toyota.wd503.myworkdayjobs.com/TMNA',
  'group': 'Cars'},
 {'name': 'Polestar',
  'kind': 'workday',
  'slug': 'polestar',
  'board': 'https://polestarcars.wd1.myworkdayjobs.com/External',
  'group': 'Cars'},
 {'name': 'BMW',
  'kind': 'pw',
  'slug': 'bmw',
  'board': 'https://www.bmwgroup.jobs/en.html',
  'search_url': 'https://www.bmwgroup.jobs/en.html',
  'link_re': 'href="(/en/jobfinder/job-description-copy\\.\\d+\\.html)"',
  'origin': 'https://www.bmwgroup.jobs',
  'wait_selector': "a[href*='/jobfinder/']",
  'scroll': True,
  'group': 'Cars'},
 {'name': 'GM',
  'kind': 'pw',
  'slug': 'gm',
  'board': 'https://search-careers.gm.com/en/',
  'search_url': 'https://search-careers.gm.com/en/',
  'link_re': 'href="(/en/jobs/jr-\\d+/[a-z0-9-]+/)"',
  'origin': 'https://search-careers.gm.com',
  'wait_selector': "a[href*='/jobs/jr-']",
  'scroll': True,
  'group': 'Cars'},

 # Media
 {'name': 'The New York Times', 'kind': 'greenhouse', 'slug': 'thenewyorktimes', 'group': 'Media'},
 # Verified 2026-10-07 via debug/probe_misses_pw.py (JS-render pass).
 {'name': 'Substack', 'kind': 'ashby', 'slug': 'substack', 'group': 'Media'},
 # Verified 2026-10-07 via debug/probe_rescue.py.
 {'name': 'Dow Jones',
  'kind': 'workday',
  'slug': 'dowjones',
  'board': 'https://newscorp.wd3.myworkdayjobs.com/Dow_Jones_Careers',
  'group': 'Media'},
 {'name': 'SoundCloud', 'kind': 'greenhouse', 'slug': 'soundcloud71', 'group': 'Media'},
 {'name': 'The Atlantic',
  'kind': 'workday',
  'slug': 'theatlantic',
  'board': 'https://atlanticmedia.wd1.myworkdayjobs.com/Careers',
  'group': 'Media'},
 {'name': 'Vox Media', 'kind': 'greenhouse', 'slug': 'voxmedia', 'group': 'Media'},
 {'name': 'Axios', 'kind': 'greenhouse', 'slug': 'axios', 'group': 'Media'},
 {'name': 'Peloton', 'kind': 'greenhouse', 'slug': 'peloton', 'group': 'Media'},
 {'name': 'Semafor', 'kind': 'greenhouse', 'slug': 'semafor', 'group': 'Media'},

 # Startups (YC-recent / unicorns / dev-tools not already in another bucket)
 {'name': 'Decagon', 'kind': 'ashby', 'slug': 'decagon', 'group': 'Startups'},
 {'name': 'Supabase', 'kind': 'ashby', 'slug': 'supabase', 'group': 'Startups'},
 {'name': 'PostHog', 'kind': 'ashby', 'slug': 'posthog', 'group': 'Startups'},
 {'name': 'Resend', 'kind': 'ashby', 'slug': 'resend', 'group': 'Startups'},
 {'name': 'Dust', 'kind': 'ashby', 'slug': 'dust', 'group': 'Startups'},
 {'name': 'Granola', 'kind': 'ashby', 'slug': 'granola', 'group': 'Startups'},
 {'name': 'Ramp', 'kind': 'ashby', 'slug': 'ramp', 'group': 'Startups'},
 {'name': 'Carta', 'kind': 'greenhouse', 'slug': 'carta', 'group': 'Startups'},
 {'name': 'Chime', 'kind': 'greenhouse', 'slug': 'chime', 'group': 'Startups'},
 {'name': 'Affirm', 'kind': 'greenhouse', 'slug': 'affirm', 'group': 'Startups'},
 {'name': 'Airtable', 'kind': 'greenhouse', 'slug': 'airtable', 'group': 'Startups'},
 {'name': 'PlanetScale', 'kind': 'greenhouse', 'slug': 'planetscale', 'group': 'Startups'},
 {'name': 'Neon', 'kind': 'ashby', 'slug': 'neon', 'group': 'Startups'},
 {'name': 'Render', 'kind': 'ashby', 'slug': 'render', 'group': 'Startups'},
 {'name': 'Vapi', 'kind': 'ashby', 'slug': 'vapi', 'group': 'Startups'},
 {'name': 'Buildkite', 'kind': 'greenhouse', 'slug': 'buildkite', 'group': 'Startups'},
 {'name': 'Clerk', 'kind': 'ashby', 'slug': 'clerk', 'group': 'Startups'},
 {'name': 'WorkOS', 'kind': 'ashby', 'slug': 'workos', 'group': 'Startups'},
 {'name': 'Temporal', 'kind': 'ashby', 'slug': 'temporal', 'group': 'Startups'},
 {'name': 'Mozilla', 'kind': 'greenhouse', 'slug': 'mozilla', 'group': 'Startups'},
 {'name': 'Instacart', 'kind': 'greenhouse', 'slug': 'instacart', 'group': 'Startups'},

 # Verified 2026-10-07 via debug/probe_misses.py — ashby slug extracted
 # from the vanity career page's embedded Ashby references.
 {'name': 'Notion', 'kind': 'ashby', 'slug': 'notion', 'group': 'Startups'},
 # Verified 2026-10-07 via debug/probe_misses_pw.py (JS-render pass).
 {'name': 'Zapier', 'kind': 'ashby', 'slug': 'zapier', 'group': 'Startups'},
 # Verified 2026-10-07 via debug/probe_rescue.py.
 {'name': 'Convex', 'kind': 'ashby', 'slug': 'convex-dev', 'group': 'AI Startups'},
 {'name': 'DoorDash',
  'kind': 'pw',
  'slug': 'doordash',
  'board': 'https://careersatdoordash.com/job-search/',
  'search_url': 'https://careersatdoordash.com/job-search/',
  'link_re': 'href="(https://careersatdoordash\\.com/jobs/[a-z0-9-]+/\\d+)"',
  'origin': 'https://careersatdoordash.com',
  'wait_selector': "a[href*='careersatdoordash.com/jobs/']",
  'scroll': True,
  'group': 'Startups'},

 # pw-generic entries — link_re verified against the saved debug dump.
 # Re-run debug/probe_misses_regex.py to re-check if a site changes shape.
 {'name': 'Shopify',
  'kind': 'pw',
  'slug': 'shopify',
  'board': 'https://www.shopify.com/careers',
  'search_url': 'https://www.shopify.com/careers/search',
  'link_re': 'href="(/careers/[^"#?]+_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"',
  'origin': 'https://www.shopify.com',
  'wait_selector': "a[href*='/careers/']",
  'scroll': True,
  'group': 'Startups'},
 {'name': 'Plaid',
  'kind': 'pw',
  'slug': 'plaid',
  'board': 'https://plaid.com/careers/openings/',
  'search_url': 'https://plaid.com/careers/openings/',
  'link_re': 'href="(/careers/openings/[^"#?]+/[^"#?]+/[^"#?]+/)"',
  'origin': 'https://plaid.com',
  'wait_selector': "a[href*='/careers/openings/']",
  'scroll': True,
  'group': 'Startups'},
 {'name': 'Retool',
  'kind': 'pw',
  'slug': 'retool',
  'board': 'https://retool.com/careers',
  'search_url': 'https://retool.com/careers',
  'link_re': 'href="(/careers/[a-z0-9-]+--[a-z0-9-]+--[a-z0-9-]+)"',
  'origin': 'https://retool.com',
  'wait_selector': "a[href*='/careers/']",
  'scroll': True,
  'group': 'Startups'},
 {'name': 'Fly.io',
  'kind': 'pw',
  'slug': 'flyio',
  'board': 'https://fly.io/jobs/',
  'search_url': 'https://fly.io/jobs/',
  'link_re': 'href="(/jobs/[a-z][a-z0-9-]+/)"',
  'origin': 'https://fly.io',
  'wait_selector': "a[href*='/jobs/']",
  'group': 'Startups'},

 # FHE
 # Zama is scraped via the WTJ API (api.welcometothejungle.com/api/v3)
 # — more reliable than the old Playwright scrape of jobs.zama.org.
 # The `kind` stays `wttj_company` (that's the fetcher), but the group
 # is 'FHE' so Zama sits next to Fhenix / Duality in the onboarding
 # catalog, not buried under the generic WTJ bucket.
 {'name': 'Zama', 'kind': 'wttj_company', 'slug': 'zama',
  'board': 'https://www.welcometothejungle.com/fr/companies/zama',
  'group': 'FHE'},
 # Well-known French tech companies on WTJ. Seeded 2026-10-07 — slugs
 # are the ones used in https://www.welcometothejungle.com/fr/companies/<slug>.
 # Some may 404 (WTJ moved them / renamed them); those return 0 jobs
 # and should be removed from this list when spotted.
 # Aircall isn't on WTJ — hosted on greenhouse (slug=aircallioinc)
 # per debug/probe_find_career_url.py. Kept in the WTJ group because
 # that's where the discovery flow surfaced them.
 {'name': 'Aircall', 'kind': 'greenhouse', 'slug': 'aircallioinc',
  'board': 'https://aircall.io/careers/',
  'group': 'Welcome to the Jungle'},
 {'name': 'Back Market', 'kind': 'wttj_company', 'slug': 'back-market',
  'board': 'https://www.welcometothejungle.com/fr/companies/back-market',
  'group': 'Welcome to the Jungle'},
 {'name': 'BlaBlaCar', 'kind': 'wttj_company', 'slug': 'blablacar',
  'board': 'https://www.welcometothejungle.com/fr/companies/blablacar',
  'group': 'Welcome to the Jungle'},
 {'name': 'Deezer', 'kind': 'wttj_company', 'slug': 'deezer',
  'board': 'https://www.welcometothejungle.com/fr/companies/deezer',
  'group': 'Welcome to the Jungle'},
 {'name': 'Spendesk', 'kind': 'wttj_company', 'slug': 'spendesk',
  'board': 'https://www.welcometothejungle.com/fr/companies/spendesk',
  'group': 'Welcome to the Jungle'},
 {'name': 'PayFit', 'kind': 'wttj_company', 'slug': 'payfit',
  'board': 'https://www.welcometothejungle.com/fr/companies/payfit',
  'group': 'Welcome to the Jungle'},
 {'name': 'Swile', 'kind': 'wttj_company', 'slug': 'swile',
  'board': 'https://www.welcometothejungle.com/fr/companies/swile',
  'group': 'Welcome to the Jungle'},
 {'name': 'Malt', 'kind': 'wttj_company', 'slug': 'malt',
  'board': 'https://www.welcometothejungle.com/fr/companies/malt',
  'group': 'Welcome to the Jungle'},
 {'name': 'Mirakl', 'kind': 'wttj_company', 'slug': 'mirakl',
  'board': 'https://www.welcometothejungle.com/fr/companies/mirakl',
  'group': 'Welcome to the Jungle'},
 # Contentsquare isn't on WTJ — hosted on Lever.
 {'name': 'Contentsquare', 'kind': 'lever', 'slug': 'contentsquare',
  'board': 'https://contentsquare.com/careers/',
  'group': 'Welcome to the Jungle'},
 # Getaround uses Polymer (jobs.polymer.co/getaround-<uuid>/...), not
 # a supported ATS — scrape their careers page via kind=pw and pick
 # up the polymer.co job URLs from the rendered HTML.
 {'name': 'Getaround', 'kind': 'pw', 'slug': 'getaround',
  'board': 'https://fr.getaround.com/careers',
  'search_url': 'https://fr.getaround.com/careers',
  'link_re': r'href="(https?://jobs\.polymer\.co/getaround[^"#?]+)"',
  'origin': 'https://jobs.polymer.co',
  'wait_selector': "a[href*='polymer.co']",
  'group': 'Welcome to the Jungle'},
 {'name': 'Pigment', 'kind': 'wttj_company', 'slug': 'pigment',
  'board': 'https://www.welcometothejungle.com/fr/companies/pigment',
  'group': 'Welcome to the Jungle'},
 {'name': '360Learning', 'kind': 'wttj_company', 'slug': '360learning',
  'board': 'https://www.welcometothejungle.com/fr/companies/360learning',
  'group': 'Welcome to the Jungle'},
 # Slugs below currently 0-job — real slugs TBD (probe_wttj_slug_find.py).
 # OpenClassrooms uses Teamtailor on a custom domain. Hrefs are
 # absolute URLs (verified via debug/probe_fix_link_re.py 2026-10-07),
 # so link_re captures the full URL.
 {'name': 'OpenClassrooms', 'kind': 'pw', 'slug': 'openclassrooms',
  'board': 'https://jobs.openclassrooms.com/fr/jobs',
  'search_url': 'https://jobs.openclassrooms.com/fr/jobs',
  'link_re': r'href="(https?://jobs\.openclassrooms\.com/fr/jobs/[0-9]+-[^"#?]+)"',
  'origin': 'https://jobs.openclassrooms.com',
  'wait_selector': "a[href*='/fr/jobs/']",
  'group': 'Welcome to the Jungle'},
 # Vestiaire Collective isn't on WTJ — hosted on Lever.
 {'name': 'Vestiaire Collective', 'kind': 'lever', 'slug': 'vestiairecollective',
  'board': 'https://careers.vestiairecollective.com/',
  'group': 'Welcome to the Jungle'},
 # Shift Technology is on Greenhouse (slug=shifttechnology, no hyphen).
 {'name': 'Shift Technology', 'kind': 'greenhouse', 'slug': 'shifttechnology',
  'board': 'https://job-boards.greenhouse.io/shifttechnology',
  'group': 'Welcome to the Jungle'},
 {'name': 'Withings', 'kind': 'wttj_company', 'slug': 'withings',
  'board': 'https://www.welcometothejungle.com/fr/companies/withings',
  'group': 'Welcome to the Jungle'},
 {'name': 'Yousign', 'kind': 'wttj_company', 'slug': 'yousign',
  'board': 'https://www.welcometothejungle.com/fr/companies/yousign',
  'group': 'Welcome to the Jungle'},
 {'name': 'Lifen', 'kind': 'wttj_company', 'slug': 'lifen',
  'board': 'https://www.welcometothejungle.com/fr/companies/lifen',
  'group': 'Welcome to the Jungle'},
 # Lydia (now Sumeria) uses Teamtailor on a custom domain. Hrefs
 # are absolute URLs (verified via debug/probe_fix_link_re.py).
 {'name': 'Lydia', 'kind': 'pw', 'slug': 'lydia',
  'board': 'https://jobs.lydia-app.com/jobs',
  'search_url': 'https://jobs.lydia-app.com/jobs',
  'link_re': r'href="(https?://jobs\.lydia-app\.com/jobs/[0-9]+-[^"#?]+)"',
  'origin': 'https://jobs.lydia-app.com',
  'wait_selector': "a[href*='/jobs/']",
  'group': 'Welcome to the Jungle'},
 {'name': '6sense', 'kind': 'wttj_company', 'slug': '6sense',
  'board': 'https://www.welcometothejungle.com/fr/companies/6sense',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'ABBYY', 'kind': 'wttj_company', 'slug': 'abbyy',
  'board': 'https://www.welcometothejungle.com/fr/companies/abbyy',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'AbCellera Biologics', 'kind': 'wttj_company', 'slug': 'abcellera-biologics',
  'board': 'https://www.welcometothejungle.com/fr/companies/abcellera-biologics',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Abnormal Security', 'kind': 'wttj_company', 'slug': 'abnormal-security',
  'board': 'https://www.welcometothejungle.com/fr/companies/abnormal-security',
  'group': 'Welcome to the Jungle'},  # 30 jobs
 {'name': 'Abridge', 'kind': 'wttj_company', 'slug': 'abridge',
  'board': 'https://www.welcometothejungle.com/fr/companies/abridge',
  'group': 'Welcome to the Jungle'},  # 34 jobs
 {'name': 'Acadenice', 'kind': 'wttj_company', 'slug': 'acadenice',
  'board': 'https://www.welcometothejungle.com/fr/companies/acadenice',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'ACAI Travel', 'kind': 'wttj_company', 'slug': 'acai-travel',
  'board': 'https://www.welcometothejungle.com/fr/companies/acai-travel',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'acceldata', 'kind': 'wttj_company', 'slug': 'acceldata',
  'board': 'https://www.welcometothejungle.com/fr/companies/acceldata',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Achievers', 'kind': 'wttj_company', 'slug': 'achievers',
  'board': 'https://www.welcometothejungle.com/fr/companies/achievers',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'ActiveCampaign', 'kind': 'wttj_company', 'slug': 'activecampaign',
  'board': 'https://www.welcometothejungle.com/fr/companies/activecampaign',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Ada', 'kind': 'wttj_company', 'slug': 'ada',
  'board': 'https://www.welcometothejungle.com/fr/companies/ada',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Adthena', 'kind': 'wttj_company', 'slug': 'adthena',
  'board': 'https://www.welcometothejungle.com/fr/companies/adthena',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Aera Technology', 'kind': 'wttj_company', 'slug': 'aera-technology',
  'board': 'https://www.welcometothejungle.com/fr/companies/aera-technology',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Aeva', 'kind': 'wttj_company', 'slug': 'aeva',
  'board': 'https://www.welcometothejungle.com/fr/companies/aeva',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Agility Robotics', 'kind': 'wttj_company', 'slug': 'agility-robotics',
  'board': 'https://www.welcometothejungle.com/fr/companies/agility-robotics',
  'group': 'Welcome to the Jungle'},  # 12 jobs
 {'name': 'AiDash', 'kind': 'wttj_company', 'slug': 'aidash',
  'board': 'https://www.welcometothejungle.com/fr/companies/aidash',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Aidence', 'kind': 'wttj_company', 'slug': 'aidence',
  'board': 'https://www.welcometothejungle.com/fr/companies/aidence',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Aily Labs', 'kind': 'wttj_company', 'slug': 'aily-labs',
  'board': 'https://www.welcometothejungle.com/fr/companies/aily-labs',
  'group': 'Welcome to the Jungle'},  # 13 jobs
 {'name': 'Air Space Intelligence', 'kind': 'wttj_company', 'slug': 'air-space-intelligence',
  'board': 'https://www.welcometothejungle.com/fr/companies/air-space-intelligence',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'AirDNA', 'kind': 'wttj_company', 'slug': 'airdna',
  'board': 'https://www.welcometothejungle.com/fr/companies/airdna',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'AISI', 'kind': 'wttj_company', 'slug': 'aisi',
  'board': 'https://www.welcometothejungle.com/fr/companies/aisi',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'AKASA', 'kind': 'wttj_company', 'slug': 'akasa',
  'board': 'https://www.welcometothejungle.com/fr/companies/akasa',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'akirolabs', 'kind': 'wttj_company', 'slug': 'akirolabs',
  'board': 'https://www.welcometothejungle.com/fr/companies/akirolabs',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'AKUR8', 'kind': 'wttj_company', 'slug': 'akur8-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/akur8-1',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Alation', 'kind': 'wttj_company', 'slug': 'alation',
  'board': 'https://www.welcometothejungle.com/fr/companies/alation',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'AlayaCare', 'kind': 'wttj_company', 'slug': 'alayacare',
  'board': 'https://www.welcometothejungle.com/fr/companies/alayacare',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'ALCYCONIE', 'kind': 'wttj_company', 'slug': 'alcyconie',
  'board': 'https://www.welcometothejungle.com/fr/companies/alcyconie',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Alethea', 'kind': 'wttj_company', 'slug': 'alethea',
  'board': 'https://www.welcometothejungle.com/fr/companies/alethea',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Alluxio', 'kind': 'wttj_company', 'slug': 'alluxio',
  'board': 'https://www.welcometothejungle.com/fr/companies/alluxio',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Altana', 'kind': 'wttj_company', 'slug': 'altana',
  'board': 'https://www.welcometothejungle.com/fr/companies/altana',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Alteryx', 'kind': 'wttj_company', 'slug': 'alteryx',
  'board': 'https://www.welcometothejungle.com/fr/companies/alteryx',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'Ambience Healthcare', 'kind': 'wttj_company', 'slug': 'ambience-healthcare',
  'board': 'https://www.welcometothejungle.com/fr/companies/ambience-healthcare',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'AMP', 'kind': 'wttj_company', 'slug': 'amp',
  'board': 'https://www.welcometothejungle.com/fr/companies/amp',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Amperity', 'kind': 'wttj_company', 'slug': 'amperity',
  'board': 'https://www.welcometothejungle.com/fr/companies/amperity',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Amplemarket', 'kind': 'wttj_company', 'slug': 'amplemarket',
  'board': 'https://www.welcometothejungle.com/fr/companies/amplemarket',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Anomali', 'kind': 'wttj_company', 'slug': 'anomali',
  'board': 'https://www.welcometothejungle.com/fr/companies/anomali',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Anvilogic', 'kind': 'wttj_company', 'slug': 'anvilogic',
  'board': 'https://www.welcometothejungle.com/fr/companies/anvilogic',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Apheris', 'kind': 'wttj_company', 'slug': 'apheris',
  'board': 'https://www.welcometothejungle.com/fr/companies/apheris',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Applied Intuition', 'kind': 'wttj_company', 'slug': 'applied-intuition',
  'board': 'https://www.welcometothejungle.com/fr/companies/applied-intuition',
  'group': 'Welcome to the Jungle'},  # 162 jobs
 {'name': 'Applovin', 'kind': 'wttj_company', 'slug': 'applovin',
  'board': 'https://www.welcometothejungle.com/fr/companies/applovin',
  'group': 'Welcome to the Jungle'},  # 28 jobs
 {'name': 'AppZen', 'kind': 'wttj_company', 'slug': 'appzen',
  'board': 'https://www.welcometothejungle.com/fr/companies/appzen',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Aqemia', 'kind': 'wttj_company', 'slug': 'aqemia-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/aqemia-1',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Aqua Security', 'kind': 'wttj_company', 'slug': 'aqua-security',
  'board': 'https://www.welcometothejungle.com/fr/companies/aqua-security',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Arctic Wolf', 'kind': 'wttj_company', 'slug': 'arctic-wolf',
  'board': 'https://www.welcometothejungle.com/fr/companies/arctic-wolf',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Argile', 'kind': 'wttj_company', 'slug': 'remi',
  'board': 'https://www.welcometothejungle.com/fr/companies/remi',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Arista', 'kind': 'wttj_company', 'slug': 'arista',
  'board': 'https://www.welcometothejungle.com/fr/companies/arista',
  'group': 'Welcome to the Jungle'},  # 48 jobs
 {'name': 'Arondite', 'kind': 'wttj_company', 'slug': 'arondite',
  'board': 'https://www.welcometothejungle.com/fr/companies/arondite',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'ASAPP', 'kind': 'wttj_company', 'slug': 'asapp',
  'board': 'https://www.welcometothejungle.com/fr/companies/asapp',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Ask for the moon', 'kind': 'wttj_company', 'slug': 'ask-for-the-moon',
  'board': 'https://www.welcometothejungle.com/fr/companies/ask-for-the-moon',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'AssetWatch', 'kind': 'wttj_company', 'slug': 'assetwatch',
  'board': 'https://www.welcometothejungle.com/fr/companies/assetwatch',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'Astera Labs', 'kind': 'wttj_company', 'slug': 'astera-labs',
  'board': 'https://www.welcometothejungle.com/fr/companies/astera-labs',
  'group': 'Welcome to the Jungle'},  # 32 jobs
 {'name': 'Ataccama', 'kind': 'wttj_company', 'slug': 'ataccama',
  'board': 'https://www.welcometothejungle.com/fr/companies/ataccama',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Atomic AI', 'kind': 'wttj_company', 'slug': 'atomic-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/atomic-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'AutogenAI', 'kind': 'wttj_company', 'slug': 'autogenai',
  'board': 'https://www.welcometothejungle.com/fr/companies/autogenai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'AutoLeadStar', 'kind': 'wttj_company', 'slug': 'autoleadstar',
  'board': 'https://www.welcometothejungle.com/fr/companies/autoleadstar',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Automation Anywhere', 'kind': 'wttj_company', 'slug': 'automation-anywhere',
  'board': 'https://www.welcometothejungle.com/fr/companies/automation-anywhere',
  'group': 'Welcome to the Jungle'},  # 12 jobs
 {'name': 'AVEVA', 'kind': 'wttj_company', 'slug': 'aveva',
  'board': 'https://www.welcometothejungle.com/fr/companies/aveva',
  'group': 'Welcome to the Jungle'},  # 24 jobs
 {'name': 'Axelera AI', 'kind': 'wttj_company', 'slug': 'axelera-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/axelera-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Axion Ray', 'kind': 'wttj_company', 'slug': 'axion-ray',
  'board': 'https://www.welcometothejungle.com/fr/companies/axion-ray',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Axuall', 'kind': 'wttj_company', 'slug': 'axuall',
  'board': 'https://www.welcometothejungle.com/fr/companies/axuall',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'AZmed', 'kind': 'wttj_company', 'slug': 'azmed-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/azmed-1',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Babbar', 'kind': 'wttj_company', 'slug': 'babbar',
  'board': 'https://www.welcometothejungle.com/fr/companies/babbar',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Banz-Ai', 'kind': 'wttj_company', 'slug': 'banz-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/banz-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Basetwo', 'kind': 'wttj_company', 'slug': 'basetwo',
  'board': 'https://www.welcometothejungle.com/fr/companies/basetwo',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Beacon Biosignals', 'kind': 'wttj_company', 'slug': 'beacon-biosignals',
  'board': 'https://www.welcometothejungle.com/fr/companies/beacon-biosignals',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Beam', 'kind': 'wttj_company', 'slug': 'beam-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/beam-1',
  'group': 'Welcome to the Jungle'},  # 30 jobs
 {'name': 'Bear Robotics', 'kind': 'wttj_company', 'slug': 'bear-robotics',
  'board': 'https://www.welcometothejungle.com/fr/companies/bear-robotics',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Berkshire Grey', 'kind': 'wttj_company', 'slug': 'berkshire-grey',
  'board': 'https://www.welcometothejungle.com/fr/companies/berkshire-grey',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'BigHat Biosciences', 'kind': 'wttj_company', 'slug': 'bighat-biosciences',
  'board': 'https://www.welcometothejungle.com/fr/companies/bighat-biosciences',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Billy Grace', 'kind': 'wttj_company', 'slug': 'billy-grace',
  'board': 'https://www.welcometothejungle.com/fr/companies/billy-grace',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Bizzdesign', 'kind': 'wttj_company', 'slug': 'bizzdesign',
  'board': 'https://www.welcometothejungle.com/fr/companies/bizzdesign',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Blackbird AI', 'kind': 'wttj_company', 'slug': 'blackbird-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/blackbird-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'BlackSky Global', 'kind': 'wttj_company', 'slug': 'blacksky-global',
  'board': 'https://www.welcometothejungle.com/fr/companies/blacksky-global',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Blend', 'kind': 'wttj_company', 'slug': 'blend-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/blend-1',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Blue J Legal', 'kind': 'wttj_company', 'slug': 'blue-j-legal',
  'board': 'https://www.welcometothejungle.com/fr/companies/blue-j-legal',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Blue River Technology', 'kind': 'wttj_company', 'slug': 'blue-river-technology',
  'board': 'https://www.welcometothejungle.com/fr/companies/blue-river-technology',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Breek', 'kind': 'wttj_company', 'slug': 'breek',
  'board': 'https://www.welcometothejungle.com/fr/companies/breek',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Brighter AI', 'kind': 'wttj_company', 'slug': 'brighter-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/brighter-ai',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'BrightHire', 'kind': 'wttj_company', 'slug': 'brighthire',
  'board': 'https://www.welcometothejungle.com/fr/companies/brighthire',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'BulQ', 'kind': 'wttj_company', 'slug': 'bulq',
  'board': 'https://www.welcometothejungle.com/fr/companies/bulq',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Burq', 'kind': 'wttj_company', 'slug': 'burq',
  'board': 'https://www.welcometothejungle.com/fr/companies/burq',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Bynder', 'kind': 'wttj_company', 'slug': 'bynder',
  'board': 'https://www.welcometothejungle.com/fr/companies/bynder',
  'group': 'Welcome to the Jungle'},  # 16 jobs
 {'name': 'C3.ai', 'kind': 'wttj_company', 'slug': 'c3-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/c3-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'CAiDENN', 'kind': 'wttj_company', 'slug': 'caidenn',
  'board': 'https://www.welcometothejungle.com/fr/companies/caidenn',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Campus Cyber', 'kind': 'wttj_company', 'slug': 'campus-cyber',
  'board': 'https://www.welcometothejungle.com/fr/companies/campus-cyber',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Candid Health', 'kind': 'wttj_company', 'slug': 'candid-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/candid-health',
  'group': 'Welcome to the Jungle'},  # 32 jobs
 {'name': 'Canoe', 'kind': 'wttj_company', 'slug': 'canoe',
  'board': 'https://www.welcometothejungle.com/fr/companies/canoe',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Capmo', 'kind': 'wttj_company', 'slug': 'capmo',
  'board': 'https://www.welcometothejungle.com/fr/companies/capmo',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Caspar Health', 'kind': 'wttj_company', 'slug': 'caspar-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/caspar-health',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'CAST AI', 'kind': 'wttj_company', 'slug': 'cast-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/cast-ai',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'CB Insights', 'kind': 'wttj_company', 'slug': 'cb-insights',
  'board': 'https://www.welcometothejungle.com/fr/companies/cb-insights',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Chalk', 'kind': 'wttj_company', 'slug': 'chalk',
  'board': 'https://www.welcometothejungle.com/fr/companies/chalk',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'Chance', 'kind': 'wttj_company', 'slug': 'chance',
  'board': 'https://www.welcometothejungle.com/fr/companies/chance',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Character.ai', 'kind': 'wttj_company', 'slug': 'character-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/character-ai',
  'group': 'Welcome to the Jungle'},  # 13 jobs
 {'name': 'Checkr', 'kind': 'wttj_company', 'slug': 'checkr',
  'board': 'https://www.welcometothejungle.com/fr/companies/checkr',
  'group': 'Welcome to the Jungle'},  # 25 jobs
 {'name': 'CI&T', 'kind': 'wttj_company', 'slug': 'ci-t',
  'board': 'https://www.welcometothejungle.com/fr/companies/ci-t',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Circus Group', 'kind': 'wttj_company', 'slug': 'circus-group',
  'board': 'https://www.welcometothejungle.com/fr/companies/circus-group',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Citizen Health', 'kind': 'wttj_company', 'slug': 'citizen-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/citizen-health',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Citylitics', 'kind': 'wttj_company', 'slug': 'citylitics',
  'board': 'https://www.welcometothejungle.com/fr/companies/citylitics',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Cleerly', 'kind': 'wttj_company', 'slug': 'cleerly',
  'board': 'https://www.welcometothejungle.com/fr/companies/cleerly',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Cloudera', 'kind': 'wttj_company', 'slug': 'cloudera',
  'board': 'https://www.welcometothejungle.com/fr/companies/cloudera',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'CO2 AI', 'kind': 'wttj_company', 'slug': 'co2-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/co2-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Code Metal', 'kind': 'wttj_company', 'slug': 'code-metal',
  'board': 'https://www.welcometothejungle.com/fr/companies/code-metal',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'Cognism', 'kind': 'wttj_company', 'slug': 'cognism',
  'board': 'https://www.welcometothejungle.com/fr/companies/cognism',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Cohere Health', 'kind': 'wttj_company', 'slug': 'cohere-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/cohere-health',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'CommerceIQ', 'kind': 'wttj_company', 'slug': 'commerceiq',
  'board': 'https://www.welcometothejungle.com/fr/companies/commerceiq',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Connectly.ai', 'kind': 'wttj_company', 'slug': 'connectly-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/connectly-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Coralogix', 'kind': 'wttj_company', 'slug': 'coralogix',
  'board': 'https://www.welcometothejungle.com/fr/companies/coralogix',
  'group': 'Welcome to the Jungle'},  # 20 jobs
 {'name': 'Corelight', 'kind': 'wttj_company', 'slug': 'corelight',
  'board': 'https://www.welcometothejungle.com/fr/companies/corelight',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Counsel Health', 'kind': 'wttj_company', 'slug': 'counsel-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/counsel-health',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Coupa', 'kind': 'wttj_company', 'slug': 'coupa',
  'board': 'https://www.welcometothejungle.com/fr/companies/coupa',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Co–Star Astrology', 'kind': 'wttj_company', 'slug': 'co-star-astrology',
  'board': 'https://www.welcometothejungle.com/fr/companies/co-star-astrology',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Creative Fabrica', 'kind': 'wttj_company', 'slug': 'creative-fabrica',
  'board': 'https://www.welcometothejungle.com/fr/companies/creative-fabrica',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Credo AI', 'kind': 'wttj_company', 'slug': 'credo-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/credo-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Cresta', 'kind': 'wttj_company', 'slug': 'cresta',
  'board': 'https://www.welcometothejungle.com/fr/companies/cresta',
  'group': 'Welcome to the Jungle'},  # 58 jobs
 {'name': 'CrewAI', 'kind': 'wttj_company', 'slug': 'crewai',
  'board': 'https://www.welcometothejungle.com/fr/companies/crewai',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Current AI', 'kind': 'wttj_company', 'slug': 'current-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/current-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Cyberhaven', 'kind': 'wttj_company', 'slug': 'cyberhaven',
  'board': 'https://www.welcometothejungle.com/fr/companies/cyberhaven',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'd-Matrix', 'kind': 'wttj_company', 'slug': 'd-matrix',
  'board': 'https://www.welcometothejungle.com/fr/companies/d-matrix',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'Darktrace', 'kind': 'wttj_company', 'slug': 'darktrace',
  'board': 'https://www.welcometothejungle.com/fr/companies/darktrace',
  'group': 'Welcome to the Jungle'},  # 35 jobs
 {'name': 'Dashmote', 'kind': 'wttj_company', 'slug': 'dashmote',
  'board': 'https://www.welcometothejungle.com/fr/companies/dashmote',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'DataRobot', 'kind': 'wttj_company', 'slug': 'datarobot',
  'board': 'https://www.welcometothejungle.com/fr/companies/datarobot',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Datasnipper', 'kind': 'wttj_company', 'slug': 'datasnipper',
  'board': 'https://www.welcometothejungle.com/fr/companies/datasnipper',
  'group': 'Welcome to the Jungle'},  # 34 jobs
 {'name': 'DealHub.io', 'kind': 'wttj_company', 'slug': 'dealhub-io',
  'board': 'https://www.welcometothejungle.com/fr/companies/dealhub-io',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'DEFCON AI', 'kind': 'wttj_company', 'slug': 'defcon-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/defcon-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Defense Unicorns', 'kind': 'wttj_company', 'slug': 'defense-unicorns',
  'board': 'https://www.welcometothejungle.com/fr/companies/defense-unicorns',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Delphina', 'kind': 'wttj_company', 'slug': 'delphina',
  'board': 'https://www.welcometothejungle.com/fr/companies/delphina',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Descript', 'kind': 'wttj_company', 'slug': 'descript',
  'board': 'https://www.welcometothejungle.com/fr/companies/descript',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'DevRev', 'kind': 'wttj_company', 'slug': 'devrev',
  'board': 'https://www.welcometothejungle.com/fr/companies/devrev',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'Dext France', 'kind': 'wttj_company', 'slug': 'dext',
  'board': 'https://www.welcometothejungle.com/fr/companies/dext',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Dexterity', 'kind': 'wttj_company', 'slug': 'dexterity',
  'board': 'https://www.welcometothejungle.com/fr/companies/dexterity',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Diligent Robotics', 'kind': 'wttj_company', 'slug': 'diligent-robotics',
  'board': 'https://www.welcometothejungle.com/fr/companies/diligent-robotics',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'DISCO', 'kind': 'wttj_company', 'slug': 'disco-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/disco-1',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'Distyl', 'kind': 'wttj_company', 'slug': 'distyl',
  'board': 'https://www.welcometothejungle.com/fr/companies/distyl',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Doma', 'kind': 'wttj_company', 'slug': 'doma',
  'board': 'https://www.welcometothejungle.com/fr/companies/doma',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Domino Data Lab', 'kind': 'wttj_company', 'slug': 'domino-data-lab',
  'board': 'https://www.welcometothejungle.com/fr/companies/domino-data-lab',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Doppel', 'kind': 'wttj_company', 'slug': 'doppel',
  'board': 'https://www.welcometothejungle.com/fr/companies/doppel',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Doxel', 'kind': 'wttj_company', 'slug': 'doxel',
  'board': 'https://www.welcometothejungle.com/fr/companies/doxel',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'Drips', 'kind': 'wttj_company', 'slug': 'drips',
  'board': 'https://www.welcometothejungle.com/fr/companies/drips',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'DXC Technology', 'kind': 'wttj_company', 'slug': 'dxc-technology',
  'board': 'https://www.welcometothejungle.com/fr/companies/dxc-technology',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Ed.ai', 'kind': 'wttj_company', 'slug': 'ed-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/ed-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'EGYM', 'kind': 'wttj_company', 'slug': 'egym',
  'board': 'https://www.welcometothejungle.com/fr/companies/egym',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Eleos Health', 'kind': 'wttj_company', 'slug': 'eleos-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/eleos-health',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Elixirr', 'kind': 'wttj_company', 'slug': 'elixirr',
  'board': 'https://www.welcometothejungle.com/fr/companies/elixirr',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Ello', 'kind': 'wttj_company', 'slug': 'ello',
  'board': 'https://www.welcometothejungle.com/fr/companies/ello',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Ema', 'kind': 'wttj_company', 'slug': 'ema',
  'board': 'https://www.welcometothejungle.com/fr/companies/ema',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'Emburse', 'kind': 'wttj_company', 'slug': 'emburse',
  'board': 'https://www.welcometothejungle.com/fr/companies/emburse',
  'group': 'Welcome to the Jungle'},  # 19 jobs
 {'name': 'EnergyHub', 'kind': 'wttj_company', 'slug': 'energyhub',
  'board': 'https://www.welcometothejungle.com/fr/companies/energyhub',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Enova', 'kind': 'wttj_company', 'slug': 'enova',
  'board': 'https://www.welcometothejungle.com/fr/companies/enova',
  'group': 'Welcome to the Jungle'},  # 17 jobs
 {'name': 'Entera', 'kind': 'wttj_company', 'slug': 'entera',
  'board': 'https://www.welcometothejungle.com/fr/companies/entera',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Enterpret', 'kind': 'wttj_company', 'slug': 'enterpret',
  'board': 'https://www.welcometothejungle.com/fr/companies/enterpret',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Ethyca', 'kind': 'wttj_company', 'slug': 'ethyca',
  'board': 'https://www.welcometothejungle.com/fr/companies/ethyca',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'eToro', 'kind': 'wttj_company', 'slug': 'etoro',
  'board': 'https://www.welcometothejungle.com/fr/companies/etoro',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'EVA.AI', 'kind': 'wttj_company', 'slug': 'eva-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/eva-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'EvenUp', 'kind': 'wttj_company', 'slug': 'evenup',
  'board': 'https://www.welcometothejungle.com/fr/companies/evenup',
  'group': 'Welcome to the Jungle'},  # 31 jobs
 {'name': 'ever-T', 'kind': 'wttj_company', 'slug': 'ever-t',
  'board': 'https://www.welcometothejungle.com/fr/companies/ever-t',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'EvolutionIQ', 'kind': 'wttj_company', 'slug': 'evolutioniq',
  'board': 'https://www.welcometothejungle.com/fr/companies/evolutioniq',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Evolv Technology', 'kind': 'wttj_company', 'slug': 'evolv-technology',
  'board': 'https://www.welcometothejungle.com/fr/companies/evolv-technology',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Exa', 'kind': 'wttj_company', 'slug': 'exa',
  'board': 'https://www.welcometothejungle.com/fr/companies/exa',
  'group': 'Welcome to the Jungle'},  # 42 jobs
 {'name': 'Exiger', 'kind': 'wttj_company', 'slug': 'exiger',
  'board': 'https://www.welcometothejungle.com/fr/companies/exiger',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Expat-U', 'kind': 'wttj_company', 'slug': 'expat-u',
  'board': 'https://www.welcometothejungle.com/fr/companies/expat-u',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'ExtraHop', 'kind': 'wttj_company', 'slug': 'extrahop',
  'board': 'https://www.welcometothejungle.com/fr/companies/extrahop',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Fairmarkit', 'kind': 'wttj_company', 'slug': 'fairmarkit',
  'board': 'https://www.welcometothejungle.com/fr/companies/fairmarkit',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Fiddler AI', 'kind': 'wttj_company', 'slug': 'fiddler-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/fiddler-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Figure', 'kind': 'wttj_company', 'slug': 'figure-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/figure-1',
  'group': 'Welcome to the Jungle'},  # 29 jobs
 {'name': 'FinQuery', 'kind': 'wttj_company', 'slug': 'finquery',
  'board': 'https://www.welcometothejungle.com/fr/companies/finquery',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Firsthand', 'kind': 'wttj_company', 'slug': 'firsthand',
  'board': 'https://www.welcometothejungle.com/fr/companies/firsthand',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Flo', 'kind': 'wttj_company', 'slug': 'flo',
  'board': 'https://www.welcometothejungle.com/fr/companies/flo',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Flock', 'kind': 'wttj_company', 'slug': 'flock',
  'board': 'https://www.welcometothejungle.com/fr/companies/flock',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Flock Safety', 'kind': 'wttj_company', 'slug': 'flock-safety',
  'board': 'https://www.welcometothejungle.com/fr/companies/flock-safety',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'FlowX.AI', 'kind': 'wttj_company', 'slug': 'flowx-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/flowx-ai',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'Fonio.ai', 'kind': 'wttj_company', 'slug': 'fonio-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/fonio-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Forma.ai', 'kind': 'wttj_company', 'slug': 'forma-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/forma-ai',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Forter', 'kind': 'wttj_company', 'slug': 'forter',
  'board': 'https://www.welcometothejungle.com/fr/companies/forter',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Fourth', 'kind': 'wttj_company', 'slug': 'fourth',
  'board': 'https://www.welcometothejungle.com/fr/companies/fourth',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'FRANCE IA', 'kind': 'wttj_company', 'slug': 'france-ia-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/france-ia-1',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'French Tech Grand Paris', 'kind': 'wttj_company', 'slug': 'french-tech-paris',
  'board': 'https://www.welcometothejungle.com/fr/companies/french-tech-paris',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Front', 'kind': 'wttj_company', 'slug': 'front-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/front-1',
  'group': 'Welcome to the Jungle'},  # 17 jobs
 {'name': 'GIC', 'kind': 'wttj_company', 'slug': 'gic',
  'board': 'https://www.welcometothejungle.com/fr/companies/gic',
  'group': 'Welcome to the Jungle'},  # 24 jobs
 {'name': 'Glia', 'kind': 'wttj_company', 'slug': 'glia',
  'board': 'https://www.welcometothejungle.com/fr/companies/glia',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Globality', 'kind': 'wttj_company', 'slug': 'globality',
  'board': 'https://www.welcometothejungle.com/fr/companies/globality',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'GoDaddy', 'kind': 'wttj_company', 'slug': 'godaddy',
  'board': 'https://www.welcometothejungle.com/fr/companies/godaddy',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'GoGuardian', 'kind': 'wttj_company', 'slug': 'goguardian',
  'board': 'https://www.welcometothejungle.com/fr/companies/goguardian',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Govini', 'kind': 'wttj_company', 'slug': 'govini',
  'board': 'https://www.welcometothejungle.com/fr/companies/govini',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'GPTZero', 'kind': 'wttj_company', 'slug': 'gptzero',
  'board': 'https://www.welcometothejungle.com/fr/companies/gptzero',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Graphcore', 'kind': 'wttj_company', 'slug': 'graphcore',
  'board': 'https://www.welcometothejungle.com/fr/companies/graphcore',
  'group': 'Welcome to the Jungle'},  # 62 jobs
 {'name': 'Grayce', 'kind': 'wttj_company', 'slug': 'grayce',
  'board': 'https://www.welcometothejungle.com/fr/companies/grayce',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'H2O.ai', 'kind': 'wttj_company', 'slug': 'h2o-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/h2o-ai',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'HackerRank', 'kind': 'wttj_company', 'slug': 'hackerrank',
  'board': 'https://www.welcometothejungle.com/fr/companies/hackerrank',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Hadrian', 'kind': 'wttj_company', 'slug': 'hadrian',
  'board': 'https://www.welcometothejungle.com/fr/companies/hadrian',
  'group': 'Welcome to the Jungle'},  # 48 jobs
 {'name': 'Halcyon', 'kind': 'wttj_company', 'slug': 'halcyon',
  'board': 'https://www.welcometothejungle.com/fr/companies/halcyon',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'HarfangLab', 'kind': 'wttj_company', 'slug': 'harfanglab-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/harfanglab-1',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Hayden AI', 'kind': 'wttj_company', 'slug': 'hayden-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/hayden-ai',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Healx', 'kind': 'wttj_company', 'slug': 'healx',
  'board': 'https://www.welcometothejungle.com/fr/companies/healx',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Hedra', 'kind': 'wttj_company', 'slug': 'hedra',
  'board': 'https://www.welcometothejungle.com/fr/companies/hedra',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Hippocratic AI', 'kind': 'wttj_company', 'slug': 'hippocratic-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/hippocratic-ai',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'HOLENEK INGENIERIE', 'kind': 'wttj_company', 'slug': 'holenek-ingenierie',
  'board': 'https://www.welcometothejungle.com/fr/companies/holenek-ingenierie',
  'group': 'Welcome to the Jungle'},  # 19 jobs
 {'name': 'honeysales', 'kind': 'wttj_company', 'slug': 'honeysales',
  'board': 'https://www.welcometothejungle.com/fr/companies/honeysales',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Hopper', 'kind': 'wttj_company', 'slug': 'hopper',
  'board': 'https://www.welcometothejungle.com/fr/companies/hopper',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Horizon Surgical Systems', 'kind': 'wttj_company', 'slug': 'horizon-surgical-systems',
  'board': 'https://www.welcometothejungle.com/fr/companies/horizon-surgical-systems',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Horizon3', 'kind': 'wttj_company', 'slug': 'horizon3',
  'board': 'https://www.welcometothejungle.com/fr/companies/horizon3',
  'group': 'Welcome to the Jungle'},  # 60 jobs
 {'name': 'HP Enterprise', 'kind': 'wttj_company', 'slug': 'hp-enterprise',
  'board': 'https://www.welcometothejungle.com/fr/companies/hp-enterprise',
  'group': 'Welcome to the Jungle'},  # 30 jobs
 {'name': 'Hugging Face', 'kind': 'wttj_company', 'slug': 'hugging-face',
  'board': 'https://www.welcometothejungle.com/fr/companies/hugging-face',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Humanoid', 'kind': 'wttj_company', 'slug': 'humanoid-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/humanoid-1',
  'group': 'Welcome to the Jungle'},  # 95 jobs
 {'name': 'HumanSignal', 'kind': 'wttj_company', 'slug': 'humansignal',
  'board': 'https://www.welcometothejungle.com/fr/companies/humansignal',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Hume AI', 'kind': 'wttj_company', 'slug': 'hume-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/hume-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Hypatos', 'kind': 'wttj_company', 'slug': 'hypatos',
  'board': 'https://www.welcometothejungle.com/fr/companies/hypatos',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Hyperbolic', 'kind': 'wttj_company', 'slug': 'hyperbolic',
  'board': 'https://www.welcometothejungle.com/fr/companies/hyperbolic',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Hyperscience', 'kind': 'wttj_company', 'slug': 'hyperscience',
  'board': 'https://www.welcometothejungle.com/fr/companies/hyperscience',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Icertis', 'kind': 'wttj_company', 'slug': 'icertis',
  'board': 'https://www.welcometothejungle.com/fr/companies/icertis',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Ideogram', 'kind': 'wttj_company', 'slug': 'ideogram',
  'board': 'https://www.welcometothejungle.com/fr/companies/ideogram',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'IEX', 'kind': 'wttj_company', 'slug': 'iex',
  'board': 'https://www.welcometothejungle.com/fr/companies/iex',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Illuma Technology', 'kind': 'wttj_company', 'slug': 'illuma-technology',
  'board': 'https://www.welcometothejungle.com/fr/companies/illuma-technology',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Imagen Technologies', 'kind': 'wttj_company', 'slug': 'imagen-technologies',
  'board': 'https://www.welcometothejungle.com/fr/companies/imagen-technologies',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Incode Technologies', 'kind': 'wttj_company', 'slug': 'incode-technologies',
  'board': 'https://www.welcometothejungle.com/fr/companies/incode-technologies',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Innovapptive', 'kind': 'wttj_company', 'slug': 'innovapptive',
  'board': 'https://www.welcometothejungle.com/fr/companies/innovapptive',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Insurify', 'kind': 'wttj_company', 'slug': 'insurify',
  'board': 'https://www.welcometothejungle.com/fr/companies/insurify',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Intenseye', 'kind': 'wttj_company', 'slug': 'intenseye',
  'board': 'https://www.welcometothejungle.com/fr/companies/intenseye',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Intent HQ', 'kind': 'wttj_company', 'slug': 'intent-hq',
  'board': 'https://www.welcometothejungle.com/fr/companies/intent-hq',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Intrinsic', 'kind': 'wttj_company', 'slug': 'intrinsic',
  'board': 'https://www.welcometothejungle.com/fr/companies/intrinsic',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'IoT Valley', 'kind': 'wttj_company', 'slug': 'iot-valley',
  'board': 'https://www.welcometothejungle.com/fr/companies/iot-valley',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'IQVIA', 'kind': 'wttj_company', 'slug': 'iqvia-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/iqvia-1',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'Ironclad', 'kind': 'wttj_company', 'slug': 'ironclad',
  'board': 'https://www.welcometothejungle.com/fr/companies/ironclad',
  'group': 'Welcome to the Jungle'},  # 28 jobs
 {'name': 'Iterative Health', 'kind': 'wttj_company', 'slug': 'iterative-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/iterative-health',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Ivo AI Inc', 'kind': 'wttj_company', 'slug': 'ivo-ai-inc',
  'board': 'https://www.welcometothejungle.com/fr/companies/ivo-ai-inc',
  'group': 'Welcome to the Jungle'},  # 36 jobs
 {'name': 'Jacobian', 'kind': 'wttj_company', 'slug': 'jacobian',
  'board': 'https://www.welcometothejungle.com/fr/companies/jacobian',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Jampp', 'kind': 'wttj_company', 'slug': 'jampp',
  'board': 'https://www.welcometothejungle.com/fr/companies/jampp',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'January', 'kind': 'wttj_company', 'slug': 'january',
  'board': 'https://www.welcometothejungle.com/fr/companies/january',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Jellyfish', 'kind': 'wttj_company', 'slug': 'jellyfish',
  'board': 'https://www.welcometothejungle.com/fr/companies/jellyfish',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Jumio', 'kind': 'wttj_company', 'slug': 'jumio',
  'board': 'https://www.welcometothejungle.com/fr/companies/jumio',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'K Health', 'kind': 'wttj_company', 'slug': 'k-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/k-health',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Kalepa', 'kind': 'wttj_company', 'slug': 'kalepa',
  'board': 'https://www.welcometothejungle.com/fr/companies/kalepa',
  'group': 'Welcome to the Jungle'},  # 21 jobs
 {'name': 'Kayrros', 'kind': 'wttj_company', 'slug': 'kayrros',
  'board': 'https://www.welcometothejungle.com/fr/companies/kayrros',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'kea', 'kind': 'wttj_company', 'slug': 'kea',
  'board': 'https://www.welcometothejungle.com/fr/companies/kea',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Ketryx', 'kind': 'wttj_company', 'slug': 'ketryx',
  'board': 'https://www.welcometothejungle.com/fr/companies/ketryx',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Kinetic', 'kind': 'wttj_company', 'slug': 'kinetic',
  'board': 'https://www.welcometothejungle.com/fr/companies/kinetic',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'KINEXON', 'kind': 'wttj_company', 'slug': 'kinexon',
  'board': 'https://www.welcometothejungle.com/fr/companies/kinexon',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'KNIME', 'kind': 'wttj_company', 'slug': 'knime',
  'board': 'https://www.welcometothejungle.com/fr/companies/knime',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Kodiak Robotics', 'kind': 'wttj_company', 'slug': 'kodiak-robotics',
  'board': 'https://www.welcometothejungle.com/fr/companies/kodiak-robotics',
  'group': 'Welcome to the Jungle'},  # 29 jobs
 {'name': 'Kody', 'kind': 'wttj_company', 'slug': 'kody',
  'board': 'https://www.welcometothejungle.com/fr/companies/kody',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Kontakt.io', 'kind': 'wttj_company', 'slug': 'kontakt-io',
  'board': 'https://www.welcometothejungle.com/fr/companies/kontakt-io',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Labelbox', 'kind': 'wttj_company', 'slug': 'labelbox-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/labelbox-1',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Landbot', 'kind': 'wttj_company', 'slug': 'landbot',
  'board': 'https://www.welcometothejungle.com/fr/companies/landbot',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'LanguageWire', 'kind': 'wttj_company', 'slug': 'languagewire',
  'board': 'https://www.welcometothejungle.com/fr/companies/languagewire',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Leah AI', 'kind': 'wttj_company', 'slug': 'leah-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/leah-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'LeanDNA', 'kind': 'wttj_company', 'slug': 'leandna',
  'board': 'https://www.welcometothejungle.com/fr/companies/leandna',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Lendbuzz', 'kind': 'wttj_company', 'slug': 'lendbuzz',
  'board': 'https://www.welcometothejungle.com/fr/companies/lendbuzz',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Levelpath', 'kind': 'wttj_company', 'slug': 'levelpath',
  'board': 'https://www.welcometothejungle.com/fr/companies/levelpath',
  'group': 'Welcome to the Jungle'},  # 17 jobs
 {'name': 'Lexroom', 'kind': 'wttj_company', 'slug': 'query-juriste',
  'board': 'https://www.welcometothejungle.com/fr/companies/query-juriste',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Lightmatter', 'kind': 'wttj_company', 'slug': 'lightmatter',
  'board': 'https://www.welcometothejungle.com/fr/companies/lightmatter',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'LogicMonitor', 'kind': 'wttj_company', 'slug': 'logicmonitor',
  'board': 'https://www.welcometothejungle.com/fr/companies/logicmonitor',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'Loopio', 'kind': 'wttj_company', 'slug': 'loopio',
  'board': 'https://www.welcometothejungle.com/fr/companies/loopio',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'LoopMe', 'kind': 'wttj_company', 'slug': 'loopme',
  'board': 'https://www.welcometothejungle.com/fr/companies/loopme',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'mabl', 'kind': 'wttj_company', 'slug': 'mabl',
  'board': 'https://www.welcometothejungle.com/fr/companies/mabl',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'MadHive', 'kind': 'wttj_company', 'slug': 'madhive',
  'board': 'https://www.welcometothejungle.com/fr/companies/madhive',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Magic', 'kind': 'wttj_company', 'slug': 'magic-2',
  'board': 'https://www.welcometothejungle.com/fr/companies/magic-2',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Mapp', 'kind': 'wttj_company', 'slug': 'mapp',
  'board': 'https://www.welcometothejungle.com/fr/companies/mapp',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Mashgin', 'kind': 'wttj_company', 'slug': 'mashgin',
  'board': 'https://www.welcometothejungle.com/fr/companies/mashgin',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Matic', 'kind': 'wttj_company', 'slug': 'matic',
  'board': 'https://www.welcometothejungle.com/fr/companies/matic',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Matroid', 'kind': 'wttj_company', 'slug': 'matroid',
  'board': 'https://www.welcometothejungle.com/fr/companies/matroid',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Mechanical Orchard', 'kind': 'wttj_company', 'slug': 'mechanical-orchard',
  'board': 'https://www.welcometothejungle.com/fr/companies/mechanical-orchard',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Merantix', 'kind': 'wttj_company', 'slug': 'merantix',
  'board': 'https://www.welcometothejungle.com/fr/companies/merantix',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Mercanis', 'kind': 'wttj_company', 'slug': 'mercanis',
  'board': 'https://www.welcometothejungle.com/fr/companies/mercanis',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Merlin Labs', 'kind': 'wttj_company', 'slug': 'merlin-labs',
  'board': 'https://www.welcometothejungle.com/fr/companies/merlin-labs',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Metropolis', 'kind': 'wttj_company', 'slug': 'metropolis',
  'board': 'https://www.welcometothejungle.com/fr/companies/metropolis',
  'group': 'Welcome to the Jungle'},  # 31 jobs
 {'name': 'Mintlify', 'kind': 'wttj_company', 'slug': 'mintlify',
  'board': 'https://www.welcometothejungle.com/fr/companies/mintlify',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Mirage', 'kind': 'wttj_company', 'slug': 'mirage',
  'board': 'https://www.welcometothejungle.com/fr/companies/mirage',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Mithril', 'kind': 'wttj_company', 'slug': 'mithril',
  'board': 'https://www.welcometothejungle.com/fr/companies/mithril',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Modular', 'kind': 'wttj_company', 'slug': 'modular',
  'board': 'https://www.welcometothejungle.com/fr/companies/modular',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Moloco', 'kind': 'wttj_company', 'slug': 'moloco',
  'board': 'https://www.welcometothejungle.com/fr/companies/moloco',
  'group': 'Welcome to the Jungle'},  # 17 jobs
 {'name': 'MotherDuck', 'kind': 'wttj_company', 'slug': 'motherduck',
  'board': 'https://www.welcometothejungle.com/fr/companies/motherduck',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Motive', 'kind': 'wttj_company', 'slug': 'motive',
  'board': 'https://www.welcometothejungle.com/fr/companies/motive',
  'group': 'Welcome to the Jungle'},  # 42 jobs
 {'name': 'MRI Software', 'kind': 'wttj_company', 'slug': 'mri-software',
  'board': 'https://www.welcometothejungle.com/fr/companies/mri-software',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Multiverse', 'kind': 'wttj_company', 'slug': 'multiverse-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/multiverse-1',
  'group': 'Welcome to the Jungle'},  # 43 jobs
 {'name': 'Multiverse Computing', 'kind': 'wttj_company', 'slug': 'multiverse-computing',
  'board': 'https://www.welcometothejungle.com/fr/companies/multiverse-computing',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Music World Media', 'kind': 'wttj_company', 'slug': 'music-world-media',
  'board': 'https://www.welcometothejungle.com/fr/companies/music-world-media',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Mutiny', 'kind': 'wttj_company', 'slug': 'mutiny',
  'board': 'https://www.welcometothejungle.com/fr/companies/mutiny',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Naratis', 'kind': 'wttj_company', 'slug': 'vaquita',
  'board': 'https://www.welcometothejungle.com/fr/companies/vaquita',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'NavVis', 'kind': 'wttj_company', 'slug': 'navvis',
  'board': 'https://www.welcometothejungle.com/fr/companies/navvis',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Nayya', 'kind': 'wttj_company', 'slug': 'nayya',
  'board': 'https://www.welcometothejungle.com/fr/companies/nayya',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'NEC Software Solutions', 'kind': 'wttj_company', 'slug': 'nec-software-solutions',
  'board': 'https://www.welcometothejungle.com/fr/companies/nec-software-solutions',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Netomi', 'kind': 'wttj_company', 'slug': 'netomi',
  'board': 'https://www.welcometothejungle.com/fr/companies/netomi',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Netradyne', 'kind': 'wttj_company', 'slug': 'netradyne',
  'board': 'https://www.welcometothejungle.com/fr/companies/netradyne',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'NewsBreak', 'kind': 'wttj_company', 'slug': 'newsbreak',
  'board': 'https://www.welcometothejungle.com/fr/companies/newsbreak',
  'group': 'Welcome to the Jungle'},  # 39 jobs
 {'name': 'NewtonX', 'kind': 'wttj_company', 'slug': 'newtonx',
  'board': 'https://www.welcometothejungle.com/fr/companies/newtonx',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'NextRoll', 'kind': 'wttj_company', 'slug': 'nextroll',
  'board': 'https://www.welcometothejungle.com/fr/companies/nextroll',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Nooks', 'kind': 'wttj_company', 'slug': 'nooks',
  'board': 'https://www.welcometothejungle.com/fr/companies/nooks',
  'group': 'Welcome to the Jungle'},  # 47 jobs
 {'name': 'Norm AI', 'kind': 'wttj_company', 'slug': 'norm-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/norm-ai',
  'group': 'Welcome to the Jungle'},  # 12 jobs
 {'name': 'Normal Computing', 'kind': 'wttj_company', 'slug': 'normal-computing',
  'board': 'https://www.welcometothejungle.com/fr/companies/normal-computing',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Northbeam', 'kind': 'wttj_company', 'slug': 'northbeam',
  'board': 'https://www.welcometothejungle.com/fr/companies/northbeam',
  'group': 'Welcome to the Jungle'},  # 20 jobs
 {'name': 'Nosto', 'kind': 'wttj_company', 'slug': 'nosto',
  'board': 'https://www.welcometothejungle.com/fr/companies/nosto',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'nuvo', 'kind': 'wttj_company', 'slug': 'nuvo',
  'board': 'https://www.welcometothejungle.com/fr/companies/nuvo',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Obligo', 'kind': 'wttj_company', 'slug': 'obligo',
  'board': 'https://www.welcometothejungle.com/fr/companies/obligo',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Observe.AI', 'kind': 'wttj_company', 'slug': 'observe-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/observe-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'ODAIA', 'kind': 'wttj_company', 'slug': 'odaia',
  'board': 'https://www.welcometothejungle.com/fr/companies/odaia',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'OLX Group', 'kind': 'wttj_company', 'slug': 'olx-group',
  'board': 'https://www.welcometothejungle.com/fr/companies/olx-group',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Omaha Insights', 'kind': 'wttj_company', 'slug': 'omaha',
  'board': 'https://www.welcometothejungle.com/fr/companies/omaha',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Omnea', 'kind': 'wttj_company', 'slug': 'omnea',
  'board': 'https://www.welcometothejungle.com/fr/companies/omnea',
  'group': 'Welcome to the Jungle'},  # 38 jobs
 {'name': 'Omnidian', 'kind': 'wttj_company', 'slug': 'omnidian',
  'board': 'https://www.welcometothejungle.com/fr/companies/omnidian',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'OnCorps AI', 'kind': 'wttj_company', 'slug': 'oncorps-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/oncorps-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Onebrief', 'kind': 'wttj_company', 'slug': 'onebrief',
  'board': 'https://www.welcometothejungle.com/fr/companies/onebrief',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Ontra', 'kind': 'wttj_company', 'slug': 'ontra',
  'board': 'https://www.welcometothejungle.com/fr/companies/ontra',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Open Cosmos', 'kind': 'wttj_company', 'slug': 'open-cosmos',
  'board': 'https://www.welcometothejungle.com/fr/companies/open-cosmos',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'OpenText', 'kind': 'wttj_company', 'slug': 'opentext',
  'board': 'https://www.welcometothejungle.com/fr/companies/opentext',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Oportun', 'kind': 'wttj_company', 'slug': 'oportun',
  'board': 'https://www.welcometothejungle.com/fr/companies/oportun',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Optimove', 'kind': 'wttj_company', 'slug': 'optimove',
  'board': 'https://www.welcometothejungle.com/fr/companies/optimove',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Orasio', 'kind': 'wttj_company', 'slug': 'orasio',
  'board': 'https://www.welcometothejungle.com/fr/companies/orasio',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Orum', 'kind': 'wttj_company', 'slug': 'orum',
  'board': 'https://www.welcometothejungle.com/fr/companies/orum',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Osaro', 'kind': 'wttj_company', 'slug': 'osaro',
  'board': 'https://www.welcometothejungle.com/fr/companies/osaro',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'OTERIA', 'kind': 'wttj_company', 'slug': 'oteriacyberschool',
  'board': 'https://www.welcometothejungle.com/fr/companies/oteriacyberschool',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Otter.ai', 'kind': 'wttj_company', 'slug': 'otter-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/otter-ai',
  'group': 'Welcome to the Jungle'},  # 19 jobs
 {'name': 'Outreach', 'kind': 'wttj_company', 'slug': 'outreach',
  'board': 'https://www.welcometothejungle.com/fr/companies/outreach',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Overstory', 'kind': 'wttj_company', 'slug': 'overstory',
  'board': 'https://www.welcometothejungle.com/fr/companies/overstory',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'Owl Labs', 'kind': 'wttj_company', 'slug': 'owl-labs',
  'board': 'https://www.welcometothejungle.com/fr/companies/owl-labs',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Pagaya Investments', 'kind': 'wttj_company', 'slug': 'pagaya-investments',
  'board': 'https://www.welcometothejungle.com/fr/companies/pagaya-investments',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'PagerDuty', 'kind': 'wttj_company', 'slug': 'pagerduty',
  'board': 'https://www.welcometothejungle.com/fr/companies/pagerduty',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'PAIR Finance', 'kind': 'wttj_company', 'slug': 'pair-finance',
  'board': 'https://www.welcometothejungle.com/fr/companies/pair-finance',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Pallet', 'kind': 'wttj_company', 'slug': 'pallet',
  'board': 'https://www.welcometothejungle.com/fr/companies/pallet',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'Panaya', 'kind': 'wttj_company', 'slug': 'panaya',
  'board': 'https://www.welcometothejungle.com/fr/companies/panaya',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Pano AI', 'kind': 'wttj_company', 'slug': 'pano-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/pano-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Papaya', 'kind': 'wttj_company', 'slug': 'papaya-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/papaya-1',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Parloa', 'kind': 'wttj_company', 'slug': 'parloa',
  'board': 'https://www.welcometothejungle.com/fr/companies/parloa',
  'group': 'Welcome to the Jungle'},  # 23 jobs
 {'name': 'Partnerize', 'kind': 'wttj_company', 'slug': 'partnerize',
  'board': 'https://www.welcometothejungle.com/fr/companies/partnerize',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'PathAI', 'kind': 'wttj_company', 'slug': 'pathai',
  'board': 'https://www.welcometothejungle.com/fr/companies/pathai',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Pathway', 'kind': 'wttj_company', 'slug': 'pathway',
  'board': 'https://www.welcometothejungle.com/fr/companies/pathway',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Pattern Bioscience', 'kind': 'wttj_company', 'slug': 'pattern-bioscience',
  'board': 'https://www.welcometothejungle.com/fr/companies/pattern-bioscience',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'PayZen', 'kind': 'wttj_company', 'slug': 'payzen',
  'board': 'https://www.welcometothejungle.com/fr/companies/payzen',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Pearl', 'kind': 'wttj_company', 'slug': 'pearl',
  'board': 'https://www.welcometothejungle.com/fr/companies/pearl',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Pentera', 'kind': 'wttj_company', 'slug': 'pentera',
  'board': 'https://www.welcometothejungle.com/fr/companies/pentera',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'People.ai', 'kind': 'wttj_company', 'slug': 'people-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/people-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'PermitFlow', 'kind': 'wttj_company', 'slug': 'permitflow',
  'board': 'https://www.welcometothejungle.com/fr/companies/permitflow',
  'group': 'Welcome to the Jungle'},  # 31 jobs
 {'name': 'Perplexity AI', 'kind': 'wttj_company', 'slug': 'perplexity-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/perplexity-ai',
  'group': 'Welcome to the Jungle'},  # 100 jobs
 {'name': 'Personalis', 'kind': 'wttj_company', 'slug': 'personalis',
  'board': 'https://www.welcometothejungle.com/fr/companies/personalis',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Phagos', 'kind': 'wttj_company', 'slug': 'phagos-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/phagos-1',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Phaidra', 'kind': 'wttj_company', 'slug': 'phaidra',
  'board': 'https://www.welcometothejungle.com/fr/companies/phaidra',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Pimloc', 'kind': 'wttj_company', 'slug': 'pimloc',
  'board': 'https://www.welcometothejungle.com/fr/companies/pimloc',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Pinewood.AI', 'kind': 'wttj_company', 'slug': 'pinewood-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/pinewood-ai',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Plain Concepts', 'kind': 'wttj_company', 'slug': 'plain-concepts',
  'board': 'https://www.welcometothejungle.com/fr/companies/plain-concepts',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Plume Design', 'kind': 'wttj_company', 'slug': 'plume-design',
  'board': 'https://www.welcometothejungle.com/fr/companies/plume-design',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'PlusAI', 'kind': 'wttj_company', 'slug': 'plusai',
  'board': 'https://www.welcometothejungle.com/fr/companies/plusai',
  'group': 'Welcome to the Jungle'},  # 29 jobs
 {'name': 'Pony.ai', 'kind': 'wttj_company', 'slug': 'pony-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/pony-ai',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Praktika.ai', 'kind': 'wttj_company', 'slug': 'praktika-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/praktika-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Procurement Sciences AI', 'kind': 'wttj_company', 'slug': 'procurement-sciences-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/procurement-sciences-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Protex AI', 'kind': 'wttj_company', 'slug': 'protex-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/protex-ai',
  'group': 'Welcome to the Jungle'},  # 13 jobs
 {'name': 'Proton.ai', 'kind': 'wttj_company', 'slug': 'proton-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/proton-ai',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Proximie', 'kind': 'wttj_company', 'slug': 'proximie',
  'board': 'https://www.welcometothejungle.com/fr/companies/proximie',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'PulsePoint', 'kind': 'wttj_company', 'slug': 'pulsepoint',
  'board': 'https://www.welcometothejungle.com/fr/companies/pulsepoint',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Pyl.tech', 'kind': 'wttj_company', 'slug': 'pyl-tech',
  'board': 'https://www.welcometothejungle.com/fr/companies/pyl-tech',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Pôle Sud', 'kind': 'wttj_company', 'slug': 'pole-sud-1',
  'board': 'https://www.welcometothejungle.com/fr/companies/pole-sud-1',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Quantexa', 'kind': 'wttj_company', 'slug': 'quantexa',
  'board': 'https://www.welcometothejungle.com/fr/companies/quantexa',
  'group': 'Welcome to the Jungle'},  # 16 jobs
 {'name': 'quantilope', 'kind': 'wttj_company', 'slug': 'quantilope',
  'board': 'https://www.welcometothejungle.com/fr/companies/quantilope',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Quantinuum', 'kind': 'wttj_company', 'slug': 'quantinuum',
  'board': 'https://www.welcometothejungle.com/fr/companies/quantinuum',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Quinyx', 'kind': 'wttj_company', 'slug': 'quinyx',
  'board': 'https://www.welcometothejungle.com/fr/companies/quinyx',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Quora', 'kind': 'wttj_company', 'slug': 'quora',
  'board': 'https://www.welcometothejungle.com/fr/companies/quora',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Rad AI', 'kind': 'wttj_company', 'slug': 'rad-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/rad-ai',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Radar', 'kind': 'wttj_company', 'slug': 'radar',
  'board': 'https://www.welcometothejungle.com/fr/companies/radar',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Range', 'kind': 'wttj_company', 'slug': 'range',
  'board': 'https://www.welcometothejungle.com/fr/companies/range',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'RapidAI', 'kind': 'wttj_company', 'slug': 'rapidai',
  'board': 'https://www.welcometothejungle.com/fr/companies/rapidai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Reach Security', 'kind': 'wttj_company', 'slug': 'reach-security',
  'board': 'https://www.welcometothejungle.com/fr/companies/reach-security',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'RealAdvisor', 'kind': 'wttj_company', 'slug': 'realadvisor',
  'board': 'https://www.welcometothejungle.com/fr/companies/realadvisor',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'Reality Defender', 'kind': 'wttj_company', 'slug': 'reality-defender',
  'board': 'https://www.welcometothejungle.com/fr/companies/reality-defender',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Relativity Space', 'kind': 'wttj_company', 'slug': 'relativity-space',
  'board': 'https://www.welcometothejungle.com/fr/companies/relativity-space',
  'group': 'Welcome to the Jungle'},  # 50 jobs
 {'name': 'Relay Therapeutics', 'kind': 'wttj_company', 'slug': 'relay-therapeutics',
  'board': 'https://www.welcometothejungle.com/fr/companies/relay-therapeutics',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Relex', 'kind': 'wttj_company', 'slug': 'relex',
  'board': 'https://www.welcometothejungle.com/fr/companies/relex',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Replicant', 'kind': 'wttj_company', 'slug': 'replicant',
  'board': 'https://www.welcometothejungle.com/fr/companies/replicant',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Replika', 'kind': 'wttj_company', 'slug': 'replika',
  'board': 'https://www.welcometothejungle.com/fr/companies/replika',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Resolver', 'kind': 'wttj_company', 'slug': 'resolver',
  'board': 'https://www.welcometothejungle.com/fr/companies/resolver',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Revenue', 'kind': 'wttj_company', 'slug': 'revenue',
  'board': 'https://www.welcometothejungle.com/fr/companies/revenue',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Revv', 'kind': 'wttj_company', 'slug': 'revv',
  'board': 'https://www.welcometothejungle.com/fr/companies/revv',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Rigetti Computing', 'kind': 'wttj_company', 'slug': 'rigetti-computing',
  'board': 'https://www.welcometothejungle.com/fr/companies/rigetti-computing',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Right-Hand', 'kind': 'wttj_company', 'slug': 'right-hand',
  'board': 'https://www.welcometothejungle.com/fr/companies/right-hand',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Ripjar', 'kind': 'wttj_company', 'slug': 'ripjar',
  'board': 'https://www.welcometothejungle.com/fr/companies/ripjar',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Riskified', 'kind': 'wttj_company', 'slug': 'riskified',
  'board': 'https://www.welcometothejungle.com/fr/companies/riskified',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Rivercell', 'kind': 'wttj_company', 'slug': 'rivercell',
  'board': 'https://www.welcometothejungle.com/fr/companies/rivercell',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Rokt', 'kind': 'wttj_company', 'slug': 'rokt',
  'board': 'https://www.welcometothejungle.com/fr/companies/rokt',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Root Global', 'kind': 'wttj_company', 'slug': 'root-global',
  'board': 'https://www.welcometothejungle.com/fr/companies/root-global',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Rootly', 'kind': 'wttj_company', 'slug': 'rootly',
  'board': 'https://www.welcometothejungle.com/fr/companies/rootly',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Rotageek', 'kind': 'wttj_company', 'slug': 'rotageek',
  'board': 'https://www.welcometothejungle.com/fr/companies/rotageek',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Safe Security', 'kind': 'wttj_company', 'slug': 'safe-security',
  'board': 'https://www.welcometothejungle.com/fr/companies/safe-security',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Sahara AI', 'kind': 'wttj_company', 'slug': 'sahara-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/sahara-ai',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Salt Security', 'kind': 'wttj_company', 'slug': 'salt-security',
  'board': 'https://www.welcometothejungle.com/fr/companies/salt-security',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Samaya', 'kind': 'wttj_company', 'slug': 'samaya',
  'board': 'https://www.welcometothejungle.com/fr/companies/samaya',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Samba TV', 'kind': 'wttj_company', 'slug': 'samba-tv',
  'board': 'https://www.welcometothejungle.com/fr/companies/samba-tv',
  'group': 'Welcome to the Jungle'},  # 33 jobs
 {'name': 'SambaNova Systems', 'kind': 'wttj_company', 'slug': 'sambanova-systems',
  'board': 'https://www.welcometothejungle.com/fr/companies/sambanova-systems',
  'group': 'Welcome to the Jungle'},  # 27 jobs
 {'name': 'Sancare', 'kind': 'wttj_company', 'slug': 'sancare',
  'board': 'https://www.welcometothejungle.com/fr/companies/sancare',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Sardine', 'kind': 'wttj_company', 'slug': 'sardine',
  'board': 'https://www.welcometothejungle.com/fr/companies/sardine',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'Saronic', 'kind': 'wttj_company', 'slug': 'saronic',
  'board': 'https://www.welcometothejungle.com/fr/companies/saronic',
  'group': 'Welcome to the Jungle'},  # 48 jobs
 {'name': 'Scandit', 'kind': 'wttj_company', 'slug': 'scandit',
  'board': 'https://www.welcometothejungle.com/fr/companies/scandit',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'SchooLinks', 'kind': 'wttj_company', 'slug': 'schoolinks',
  'board': 'https://www.welcometothejungle.com/fr/companies/schoolinks',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Sea Machines Robotics', 'kind': 'wttj_company', 'slug': 'sea-machines-robotics',
  'board': 'https://www.welcometothejungle.com/fr/companies/sea-machines-robotics',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'SeeChange Technologies', 'kind': 'wttj_company', 'slug': 'seechange-technologies',
  'board': 'https://www.welcometothejungle.com/fr/companies/seechange-technologies',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Sense', 'kind': 'wttj_company', 'slug': 'sense',
  'board': 'https://www.welcometothejungle.com/fr/companies/sense',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Sensi.AI', 'kind': 'wttj_company', 'slug': 'sensi-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/sensi-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'SentinelOne', 'kind': 'wttj_company', 'slug': 'sentinelone',
  'board': 'https://www.welcometothejungle.com/fr/companies/sentinelone',
  'group': 'Welcome to the Jungle'},  # 57 jobs
 {'name': 'SEON', 'kind': 'wttj_company', 'slug': 'seon',
  'board': 'https://www.welcometothejungle.com/fr/companies/seon',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Shield AI', 'kind': 'wttj_company', 'slug': 'shield-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/shield-ai',
  'group': 'Welcome to the Jungle'},  # 47 jobs
 {'name': 'Siena', 'kind': 'wttj_company', 'slug': 'siena',
  'board': 'https://www.welcometothejungle.com/fr/companies/siena',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Sift', 'kind': 'wttj_company', 'slug': 'sift',
  'board': 'https://www.welcometothejungle.com/fr/companies/sift',
  'group': 'Welcome to the Jungle'},  # 34 jobs
 {'name': 'Simbe', 'kind': 'wttj_company', 'slug': 'simbe',
  'board': 'https://www.welcometothejungle.com/fr/companies/simbe',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Simple Machines', 'kind': 'wttj_company', 'slug': 'simple-machines',
  'board': 'https://www.welcometothejungle.com/fr/companies/simple-machines',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Sinch', 'kind': 'wttj_company', 'slug': 'sinch',
  'board': 'https://www.welcometothejungle.com/fr/companies/sinch',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Siro', 'kind': 'wttj_company', 'slug': 'siro',
  'board': 'https://www.welcometothejungle.com/fr/companies/siro',
  'group': 'Welcome to the Jungle'},  # 16 jobs
 {'name': 'SkinVision', 'kind': 'wttj_company', 'slug': 'skinvision',
  'board': 'https://www.welcometothejungle.com/fr/companies/skinvision',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Skydio', 'kind': 'wttj_company', 'slug': 'skydio',
  'board': 'https://www.welcometothejungle.com/fr/companies/skydio',
  'group': 'Welcome to the Jungle'},  # 60 jobs
 {'name': 'Skyral', 'kind': 'wttj_company', 'slug': 'skyral',
  'board': 'https://www.welcometothejungle.com/fr/companies/skyral',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'SkySpecs', 'kind': 'wttj_company', 'slug': 'skyspecs',
  'board': 'https://www.welcometothejungle.com/fr/companies/skyspecs',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Skyways', 'kind': 'wttj_company', 'slug': 'skyways',
  'board': 'https://www.welcometothejungle.com/fr/companies/skyways',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Slingshot Aerospace', 'kind': 'wttj_company', 'slug': 'slingshot-aerospace',
  'board': 'https://www.welcometothejungle.com/fr/companies/slingshot-aerospace',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Smartly.io', 'kind': 'wttj_company', 'slug': 'smartly-io',
  'board': 'https://www.welcometothejungle.com/fr/companies/smartly-io',
  'group': 'Welcome to the Jungle'},  # 19 jobs
 {'name': 'SnapLogic', 'kind': 'wttj_company', 'slug': 'snaplogic',
  'board': 'https://www.welcometothejungle.com/fr/companies/snaplogic',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Snapsheet', 'kind': 'wttj_company', 'slug': 'snapsheet',
  'board': 'https://www.welcometothejungle.com/fr/companies/snapsheet',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Snorkel AI', 'kind': 'wttj_company', 'slug': 'snorkel-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/snorkel-ai',
  'group': 'Welcome to the Jungle'},  # 32 jobs
 {'name': 'SOCi', 'kind': 'wttj_company', 'slug': 'soci',
  'board': 'https://www.welcometothejungle.com/fr/companies/soci',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Socure', 'kind': 'wttj_company', 'slug': 'socure',
  'board': 'https://www.welcometothejungle.com/fr/companies/socure',
  'group': 'Welcome to the Jungle'},  # 57 jobs
 {'name': 'Solidus Labs', 'kind': 'wttj_company', 'slug': 'solidus-labs',
  'board': 'https://www.welcometothejungle.com/fr/companies/solidus-labs',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'SOPHiA GENETICS', 'kind': 'wttj_company', 'slug': 'sophia-genetics',
  'board': 'https://www.welcometothejungle.com/fr/companies/sophia-genetics',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Sophos', 'kind': 'wttj_company', 'slug': 'sophos',
  'board': 'https://www.welcometothejungle.com/fr/companies/sophos',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'SoundHound AI', 'kind': 'wttj_company', 'slug': 'soundhound-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/soundhound-ai',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Speak', 'kind': 'wttj_company', 'slug': 'speak',
  'board': 'https://www.welcometothejungle.com/fr/companies/speak',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'Speechify', 'kind': 'wttj_company', 'slug': 'speechify',
  'board': 'https://www.welcometothejungle.com/fr/companies/speechify',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'SponsorUnited', 'kind': 'wttj_company', 'slug': 'sponsorunited',
  'board': 'https://www.welcometothejungle.com/fr/companies/sponsorunited',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Spot AI', 'kind': 'wttj_company', 'slug': 'spot-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/spot-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'SPREAD AI', 'kind': 'wttj_company', 'slug': 'spread-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/spread-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Sprig', 'kind': 'wttj_company', 'slug': 'sprig',
  'board': 'https://www.welcometothejungle.com/fr/companies/sprig',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Square Enix', 'kind': 'wttj_company', 'slug': 'square-enix',
  'board': 'https://www.welcometothejungle.com/fr/companies/square-enix',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Stability AI', 'kind': 'wttj_company', 'slug': 'stability-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/stability-ai',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Standard Bots', 'kind': 'wttj_company', 'slug': 'standard-bots',
  'board': 'https://www.welcometothejungle.com/fr/companies/standard-bots',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'SuiteSpot', 'kind': 'wttj_company', 'slug': 'suitespot',
  'board': 'https://www.welcometothejungle.com/fr/companies/suitespot',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Suki', 'kind': 'wttj_company', 'slug': 'suki',
  'board': 'https://www.welcometothejungle.com/fr/companies/suki',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Super Annotate', 'kind': 'wttj_company', 'slug': 'super-annotate',
  'board': 'https://www.welcometothejungle.com/fr/companies/super-annotate',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'super.AI', 'kind': 'wttj_company', 'slug': 'super-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/super-ai',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Swapcard', 'kind': 'wttj_company', 'slug': 'swapcard',
  'board': 'https://www.welcometothejungle.com/fr/companies/swapcard',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Swayable', 'kind': 'wttj_company', 'slug': 'swayable',
  'board': 'https://www.welcometothejungle.com/fr/companies/swayable',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'System', 'kind': 'wttj_company', 'slug': 'system',
  'board': 'https://www.welcometothejungle.com/fr/companies/system',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Tabs', 'kind': 'wttj_company', 'slug': 'tabs',
  'board': 'https://www.welcometothejungle.com/fr/companies/tabs',
  'group': 'Welcome to the Jungle'},  # 20 jobs
 {'name': 'tacton', 'kind': 'wttj_company', 'slug': 'tacton',
  'board': 'https://www.welcometothejungle.com/fr/companies/tacton',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Taktile', 'kind': 'wttj_company', 'slug': 'taktile',
  'board': 'https://www.welcometothejungle.com/fr/companies/taktile',
  'group': 'Welcome to the Jungle'},  # 31 jobs
 {'name': 'Tandem Health', 'kind': 'wttj_company', 'slug': 'tandem-health-global-sas',
  'board': 'https://www.welcometothejungle.com/fr/companies/tandem-health-global-sas',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Tavus', 'kind': 'wttj_company', 'slug': 'tavus',
  'board': 'https://www.welcometothejungle.com/fr/companies/tavus',
  'group': 'Welcome to the Jungle'},  # 13 jobs
 {'name': 'TBAuctions', 'kind': 'wttj_company', 'slug': 'tbauctions',
  'board': 'https://www.welcometothejungle.com/fr/companies/tbauctions',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'TEAMWAY', 'kind': 'wttj_company', 'slug': 'teamway',
  'board': 'https://www.welcometothejungle.com/fr/companies/teamway',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Techspert', 'kind': 'wttj_company', 'slug': 'techspert',
  'board': 'https://www.welcometothejungle.com/fr/companies/techspert',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Tenable', 'kind': 'wttj_company', 'slug': 'tenable',
  'board': 'https://www.welcometothejungle.com/fr/companies/tenable',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Tennr', 'kind': 'wttj_company', 'slug': 'tennr',
  'board': 'https://www.welcometothejungle.com/fr/companies/tennr',
  'group': 'Welcome to the Jungle'},  # 23 jobs
 {'name': 'Tensordyne', 'kind': 'wttj_company', 'slug': 'tensordyne',
  'board': 'https://www.welcometothejungle.com/fr/companies/tensordyne',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'TetraScience', 'kind': 'wttj_company', 'slug': 'tetrascience',
  'board': 'https://www.welcometothejungle.com/fr/companies/tetrascience',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'text.cortex', 'kind': 'wttj_company', 'slug': 'text-cortex',
  'board': 'https://www.welcometothejungle.com/fr/companies/text-cortex',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Textio', 'kind': 'wttj_company', 'slug': 'textio',
  'board': 'https://www.welcometothejungle.com/fr/companies/textio',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Thread AI', 'kind': 'wttj_company', 'slug': 'thread-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/thread-ai',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'TIFIN', 'kind': 'wttj_company', 'slug': 'tifin',
  'board': 'https://www.welcometothejungle.com/fr/companies/tifin',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Tiger Data', 'kind': 'wttj_company', 'slug': 'tiger-data',
  'board': 'https://www.welcometothejungle.com/fr/companies/tiger-data',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Tipalti', 'kind': 'wttj_company', 'slug': 'tipalti',
  'board': 'https://www.welcometothejungle.com/fr/companies/tipalti',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'Tome', 'kind': 'wttj_company', 'slug': 'tome',
  'board': 'https://www.welcometothejungle.com/fr/companies/tome',
  'group': 'Welcome to the Jungle'},  # 18 jobs
 {'name': 'Topline Pro', 'kind': 'wttj_company', 'slug': 'topline-pro',
  'board': 'https://www.welcometothejungle.com/fr/companies/topline-pro',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Topsort', 'kind': 'wttj_company', 'slug': 'topsort',
  'board': 'https://www.welcometothejungle.com/fr/companies/topsort',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Torq', 'kind': 'wttj_company', 'slug': 'torq',
  'board': 'https://www.welcometothejungle.com/fr/companies/torq',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'traide', 'kind': 'wttj_company', 'slug': 'traide',
  'board': 'https://www.welcometothejungle.com/fr/companies/traide',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'TribalScale', 'kind': 'wttj_company', 'slug': 'tribalscale',
  'board': 'https://www.welcometothejungle.com/fr/companies/tribalscale',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Trullion', 'kind': 'wttj_company', 'slug': 'trullion',
  'board': 'https://www.welcometothejungle.com/fr/companies/trullion',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Trunk Tools', 'kind': 'wttj_company', 'slug': 'trunk-tools',
  'board': 'https://www.welcometothejungle.com/fr/companies/trunk-tools',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Twelve Labs', 'kind': 'wttj_company', 'slug': 'twelve-labs',
  'board': 'https://www.welcometothejungle.com/fr/companies/twelve-labs',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Twin Health', 'kind': 'wttj_company', 'slug': 'twin-health',
  'board': 'https://www.welcometothejungle.com/fr/companies/twin-health',
  'group': 'Welcome to the Jungle'},  # 16 jobs
 {'name': 'uberall', 'kind': 'wttj_company', 'slug': 'uberall',
  'board': 'https://www.welcometothejungle.com/fr/companies/uberall',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'UJET', 'kind': 'wttj_company', 'slug': 'ujet',
  'board': 'https://www.welcometothejungle.com/fr/companies/ujet',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'UltraEdge', 'kind': 'wttj_company', 'slug': 'ultraedge',
  'board': 'https://www.welcometothejungle.com/fr/companies/ultraedge',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'unitQ', 'kind': 'wttj_company', 'slug': 'unitq',
  'board': 'https://www.welcometothejungle.com/fr/companies/unitq',
  'group': 'Welcome to the Jungle'},  # 5 jobs
 {'name': 'Unzer', 'kind': 'wttj_company', 'slug': 'unzer',
  'board': 'https://www.welcometothejungle.com/fr/companies/unzer',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Updraft', 'kind': 'wttj_company', 'slug': 'updraft',
  'board': 'https://www.welcometothejungle.com/fr/companies/updraft',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Urbint', 'kind': 'wttj_company', 'slug': 'urbint',
  'board': 'https://www.welcometothejungle.com/fr/companies/urbint',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'UVeye', 'kind': 'wttj_company', 'slug': 'uveye',
  'board': 'https://www.welcometothejungle.com/fr/companies/uveye',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Valdera', 'kind': 'wttj_company', 'slug': 'valdera',
  'board': 'https://www.welcometothejungle.com/fr/companies/valdera',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Vectara', 'kind': 'wttj_company', 'slug': 'vectara',
  'board': 'https://www.welcometothejungle.com/fr/companies/vectara',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Vectra AI', 'kind': 'wttj_company', 'slug': 'vectra-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/vectra-ai',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Vendelux', 'kind': 'wttj_company', 'slug': 'vendelux',
  'board': 'https://www.welcometothejungle.com/fr/companies/vendelux',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Veriff', 'kind': 'wttj_company', 'slug': 'veriff',
  'board': 'https://www.welcometothejungle.com/fr/companies/veriff',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Vic.ai', 'kind': 'wttj_company', 'slug': 'vic-ai',
  'board': 'https://www.welcometothejungle.com/fr/companies/vic-ai',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'VideaHealth', 'kind': 'wttj_company', 'slug': 'videahealth',
  'board': 'https://www.welcometothejungle.com/fr/companies/videahealth',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'Vise', 'kind': 'wttj_company', 'slug': 'vise',
  'board': 'https://www.welcometothejungle.com/fr/companies/vise',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Visian', 'kind': 'wttj_company', 'slug': 'visian',
  'board': 'https://www.welcometothejungle.com/fr/companies/visian',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Viz', 'kind': 'wttj_company', 'slug': 'viz',
  'board': 'https://www.welcometothejungle.com/fr/companies/viz',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Vocca', 'kind': 'wttj_company', 'slug': 'vocca',
  'board': 'https://www.welcometothejungle.com/fr/companies/vocca',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'Volta software', 'kind': 'wttj_company', 'slug': 'volta',
  'board': 'https://www.welcometothejungle.com/fr/companies/volta',
  'group': 'Welcome to the Jungle'},  # 4 jobs
 {'name': 'Voxel', 'kind': 'wttj_company', 'slug': 'voxel',
  'board': 'https://www.welcometothejungle.com/fr/companies/voxel',
  'group': 'Welcome to the Jungle'},  # 7 jobs
 {'name': 'Voxie Inc', 'kind': 'wttj_company', 'slug': 'voxie-inc',
  'board': 'https://www.welcometothejungle.com/fr/companies/voxie-inc',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Voyado', 'kind': 'wttj_company', 'slug': 'voyado',
  'board': 'https://www.welcometothejungle.com/fr/companies/voyado',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Waiv, formerly Owkin Dx', 'kind': 'wttj_company', 'slug': 'waiv',
  'board': 'https://www.welcometothejungle.com/fr/companies/waiv',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Wealth.com', 'kind': 'wttj_company', 'slug': 'wealth-com',
  'board': 'https://www.welcometothejungle.com/fr/companies/wealth-com',
  'group': 'Welcome to the Jungle'},  # 13 jobs
 {'name': 'webAI', 'kind': 'wttj_company', 'slug': 'webai',
  'board': 'https://www.welcometothejungle.com/fr/companies/webai',
  'group': 'Welcome to the Jungle'},  # 14 jobs
 {'name': 'WEKA', 'kind': 'wttj_company', 'slug': 'weka',
  'board': 'https://www.welcometothejungle.com/fr/companies/weka',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'WellSaid Labs', 'kind': 'wttj_company', 'slug': 'wellsaid-labs',
  'board': 'https://www.welcometothejungle.com/fr/companies/wellsaid-labs',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Wilgo', 'kind': 'wttj_company', 'slug': 'bongoway',
  'board': 'https://www.welcometothejungle.com/fr/companies/bongoway',
  'group': 'Welcome to the Jungle'},  # 3 jobs
 {'name': 'Windfall', 'kind': 'wttj_company', 'slug': 'windfall',
  'board': 'https://www.welcometothejungle.com/fr/companies/windfall',
  'group': 'Welcome to the Jungle'},  # 11 jobs
 {'name': 'WireScreen', 'kind': 'wttj_company', 'slug': 'wirescreen',
  'board': 'https://www.welcometothejungle.com/fr/companies/wirescreen',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Workato', 'kind': 'wttj_company', 'slug': 'workato',
  'board': 'https://www.welcometothejungle.com/fr/companies/workato',
  'group': 'Welcome to the Jungle'},  # 21 jobs
 {'name': 'Writer', 'kind': 'wttj_company', 'slug': 'writer',
  'board': 'https://www.welcometothejungle.com/fr/companies/writer',
  'group': 'Welcome to the Jungle'},  # 29 jobs
 {'name': 'xAI', 'kind': 'wttj_company', 'slug': 'xai',
  'board': 'https://www.welcometothejungle.com/fr/companies/xai',
  'group': 'Welcome to the Jungle'},  # 74 jobs
 {'name': 'YESWEHACK', 'kind': 'wttj_company', 'slug': 'yeswehack',
  'board': 'https://www.welcometothejungle.com/fr/companies/yeswehack',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Yext', 'kind': 'wttj_company', 'slug': 'yext',
  'board': 'https://www.welcometothejungle.com/fr/companies/yext',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'you.com', 'kind': 'wttj_company', 'slug': 'you-com',
  'board': 'https://www.welcometothejungle.com/fr/companies/you-com',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'Yourban', 'kind': 'wttj_company', 'slug': 'yourban',
  'board': 'https://www.welcometothejungle.com/fr/companies/yourban',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Yxir', 'kind': 'wttj_company', 'slug': 'yxir',
  'board': 'https://www.welcometothejungle.com/fr/companies/yxir',
  'group': 'Welcome to the Jungle'},  # 2 jobs
 {'name': 'zaizi', 'kind': 'wttj_company', 'slug': 'zaizi',
  'board': 'https://www.welcometothejungle.com/fr/companies/zaizi',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Zefir', 'kind': 'wttj_company', 'slug': 'zefir',
  'board': 'https://www.welcometothejungle.com/fr/companies/zefir',
  'group': 'Welcome to the Jungle'},  # 9 jobs
 {'name': 'Zeitview', 'kind': 'wttj_company', 'slug': 'zeitview',
  'board': 'https://www.welcometothejungle.com/fr/companies/zeitview',
  'group': 'Welcome to the Jungle'},  # 6 jobs
 {'name': 'Zendar', 'kind': 'wttj_company', 'slug': 'zendar',
  'board': 'https://www.welcometothejungle.com/fr/companies/zendar',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'Zenika', 'kind': 'wttj_company', 'slug': 'zenika',
  'board': 'https://www.welcometothejungle.com/fr/companies/zenika',
  'group': 'Welcome to the Jungle'},  # 51 jobs
 {'name': 'Zilliz', 'kind': 'wttj_company', 'slug': 'zilliz',
  'board': 'https://www.welcometothejungle.com/fr/companies/zilliz',
  'group': 'Welcome to the Jungle'},  # 8 jobs
 {'name': 'ZILO', 'kind': 'wttj_company', 'slug': 'zilo',
  'board': 'https://www.welcometothejungle.com/fr/companies/zilo',
  'group': 'Welcome to the Jungle'},  # 1 jobs
 {'name': 'ZoomInfo', 'kind': 'wttj_company', 'slug': 'zoominfo',
  'board': 'https://www.welcometothejungle.com/fr/companies/zoominfo',
  'group': 'Welcome to the Jungle'},  # 15 jobs
 {'name': 'Zum', 'kind': 'wttj_company', 'slug': 'zum',
  'board': 'https://www.welcometothejungle.com/fr/companies/zum',
  'group': 'Welcome to the Jungle'},  # 10 jobs
 {'name': 'Fhenix',
  'kind': 'pw',
  'slug': 'fhenix',
  'board': 'https://www.fhenix.io/careers',
  'search_url': 'https://www.fhenix.io/careers',
  'link_re': 'href="(/jobs/[a-z][^"#?]*)"',
  'origin': 'https://www.fhenix.io',
  'wait_selector': "a[href*='/jobs/']",
  'group': 'FHE'},
 {'name': 'Duality',
  'kind': 'pw',
  'slug': 'duality',
  'board': 'https://dualitytech.com/careers/',
  'search_url': 'https://dualitytech.com/careers/',
  'link_re': 'href="(https?://dualitytech\\.com/careers/[a-z0-9-]+/)"',
  'origin': 'https://dualitytech.com',
  'wait_selector': "a[href*='/careers/']",
  'group': 'FHE'},

 # Blockchain / crypto
 {'name': 'Coinbase', 'kind': 'greenhouse', 'slug': 'coinbase', 'group': 'Blockchain'},
 {'name': 'Fireblocks', 'kind': 'greenhouse', 'slug': 'fireblocks', 'group': 'Blockchain'},
 {'name': 'OpenZeppelin', 'kind': 'greenhouse', 'slug': 'openzeppelin', 'group': 'Blockchain'},
 {'name': 'Phantom', 'kind': 'ashby', 'slug': 'phantom', 'group': 'Blockchain'},
 {'name': 'Aptos Labs', 'kind': 'greenhouse', 'slug': 'aptoslabs', 'group': 'Blockchain'},
 {'name': 'Consensys', 'kind': 'greenhouse', 'slug': 'consensys', 'group': 'Blockchain'},
 {'name': 'Dune', 'kind': 'ashby', 'slug': 'dune', 'group': 'Blockchain'},
 {'name': 'Paradigm', 'kind': 'ashby', 'slug': 'paradigm', 'group': 'Blockchain'},
 {'name': 'Blockchain.com', 'kind': 'greenhouse', 'slug': 'blockchain', 'group': 'Blockchain'},

 # Verified 2026-10-07 via debug/probe_misses.py — Ashby/Lever slugs
 # recovered from the companies' custom career-page HTML.
 {'name': 'Kraken', 'kind': 'ashby', 'slug': 'kraken', 'group': 'Blockchain'},
 # Verified 2026-10-07 via debug/probe_misses_pw.py (JS-render pass).
 {'name': 'Ledger', 'kind': 'ashby', 'slug': 'ledger', 'group': 'Blockchain'},
 {'name': 'Alchemy', 'kind': 'ashby', 'slug': 'alchemy', 'group': 'Blockchain'},
 {'name': 'Mysten Labs', 'kind': 'ashby', 'slug': 'mystenlabs', 'group': 'Blockchain'},
 {'name': 'Uniswap Labs', 'kind': 'ashby', 'slug': 'uniswap', 'group': 'Blockchain'},
 {'name': 'Immutable', 'kind': 'lever', 'slug': 'immutable', 'group': 'Blockchain'},
 # Verified 2026-10-07 via debug/probe_rescue.py.
 {'name': 'Chainalysis', 'kind': 'ashby', 'slug': 'chainalysis-careers', 'group': 'Blockchain'},
 {'name': 'Circle',
  'kind': 'workday',
  'slug': 'circle',
  'board': 'https://circle.wd1.myworkdayjobs.com/Circle',
  'group': 'Blockchain'}]
