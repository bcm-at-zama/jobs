# Refreshing the WTJ catalog by sector

The "Welcome to the Jungle" group in `src/catalog.py` is populated in
bulk from the public Algolia company directory, filtered by sector.
This note explains how to re-run that flow when you want to change
categories, broaden/narrow the filter, or just refresh after a few
months.

## TL;DR — one command

```
PYTHONPATH=src python3 debug/bulk_populate_wttj_catalog.py
```

Prints ready-to-paste catalog entries + saves them to
`data/wttj_verified.json` for the apply step. Takes ~4 minutes
(Algolia pagination + one WTJ API call per candidate slug).

## Where the sector filter lives

`src/wttj_discovery.py` — `DEFAULT_SECTOR_FACETS` at the top of the
file. Current value (Cybersecurity + AI/ML only):

```python
DEFAULT_SECTOR_FACETS = [
    "sectors_name.fr.Tech:Cybersécurité",
    "sectors_name.fr.Tech:Intelligence artificielle / Machine Learning",
]
```

### Facet format

Each entry is `<facet_name>:<value>`. Algolia AND's across different
facet names, OR's within the same facet name. Our values live under
`sectors_name.fr.Tech:*` (French labels, Tech parent category).

### Finding facet names for new sectors

The sector labels WTJ exposes are visible on their public filter
page. In French:

- `sectors_name.fr.Tech:Cybersécurité`
- `sectors_name.fr.Tech:Intelligence artificielle / Machine Learning`
- `sectors_name.fr.Tech:Logiciels` (SaaS/software — very broad, ~2000 hits)
- `sectors_name.fr.Tech:Big Data`
- `sectors_name.fr.Tech:FinTech / InsurTech`
- `sectors_name.fr.Tech:SaaS / Cloud Services`

To discover others: open https://www.welcometothejungle.com/fr/companies
with DevTools → Network → filter XHR → tick a sector checkbox → look
at the outbound Algolia POST body for the exact facet string.

### The 1000-hit cap

Algolia's public search caps every query at **1000 hits**. Pick a
narrow enough sector combo that the total `nbHits` the probe reports
stays under 1000, otherwise you silently miss companies past the cap.
Cybersecurity + AI/ML returns ~990 — a safe near-limit.

If you want a broader net, split into multiple sector-specific runs
instead of OR'ing them into one giant query.

## What the probe does

1. **Fetches candidates** — POSTs to Algolia (`csekhvms53-dsn.algolia.net`)
   paginated at 100/page, up to 50 pages (5000 cap).
2. **Dedupes vs the current catalog** — skips any name or slug already
   tracked under any kind (greenhouse, ashby, wttj_company, …).
3. **Validates each slug** — one GET to
   `api.welcometothejungle.com/api/v3/organizations/<slug>/jobs` per
   candidate. Keeps only slugs that return ≥1 real job. This filters
   out dead WTJ pages and companies that stopped posting.
4. **Emits paste-ready blocks** for the three files that need updating,
   AND saves everything to `data/wttj_verified.json` for scripted
   application.

## Applying the output

Three places need the new entries:

| File | Section | What to add |
|------|---------|-------------|
| `src/catalog.py` | `WTTJ_SOURCES` block (or wherever the WTJ group lives) | `{'name': ..., 'kind': 'wttj_company', 'slug': ..., 'board': ..., 'group': 'Welcome to the Jungle'}` |
| `data/user_config.py` | `SOURCES` list | Same shape as catalog, plus `'queries': []` |
| `src/config.py` | `GROUP_OF` dict | `'<name>': 'Welcome to the Jungle'` |

The probe prints each block separately so pasting is mechanical.
Alternatively, write a `debug/apply_wttj_verified.py` script that
reads `data/wttj_verified.json` and inserts programmatically.

## Verifying the result

Per `CLAUDE.md` "TEST before claiming it works":

```
make test
```

Then run the end-to-end WTJ fetcher check:

```
PYTHONPATH=src python3 debug/test_wttj_sources.py
```

Reports ✓/✗/⚠ per entry — any ✗ means the slug validated at
population time but no longer returns jobs (company stopped posting
between populate + test). Any ⚠ means the fetcher errored (sandbox
network issue or WTJ 5xx).

## Why this isn't automated end-to-end

Three reasons we keep "run probe → paste blocks" as a two-step flow
instead of a one-shot script:

1. The dedupe step wants a human glance — occasionally the probe
   suggests a company we deliberately removed earlier (dead ATS,
   location mismatch) and we want to NOT re-add it.
2. Adding 500+ sources at once dramatically increases per-run fetch
   time; a human should decide "yes, add them all" rather than silent
   mass-add.
3. The three files are source-controlled and the user wants the
   additions as a reviewable commit, not a magic diff from a script.

If you want to automate it anyway, the shape is:

```
python3 debug/apply_wttj_verified.py   # reads data/wttj_verified.json
                                       # writes catalog + user_config + config
                                       # runs make test at the end
```

## When to re-run

- After broadening or narrowing the sector filter in `DEFAULT_SECTOR_FACETS`
- Every ~6 months to pick up companies newly added to WTJ
- If a batch of WTJ sources suddenly go to 0 jobs (`debug/test_wttj_sources.py`
  shows many ✗) — WTJ may have rotated the Algolia API key; re-run
  `debug/probe_wttj_xhr_capture.py` first to refresh it.
