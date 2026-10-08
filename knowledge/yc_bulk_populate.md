# Refreshing the YC catalog by tag

The "Y Combinator" group in `src/catalog.py` is populated in bulk from
YC's public companies API, filtered by tag/industry. Each company is
added with its own detected ATS (greenhouse / lever / ashby / workable
/ workday), so job data comes from each company's own public API at
`make run` time.

## TL;DR — one command

```
make yc-refresh
```

Runs the full chain:
1. `debug/bulk_populate_yc_catalog.py` — fetches YC companies + detects/validates ATS per company
2. `debug/apply_yc_verified.py` — dedupes + patches catalog/user_config/config + runs `make test`

Takes ~20-40 minutes (ATS probe is slow — one careers-page fetch + up
to 4 API-validation calls per company).

## Where the tag filter lives

`src/yc_discovery.py` — `DEFAULT_YC_FILTERS` at the top of the file.
Current value (Cybersecurity + AI/ML):

```python
DEFAULT_YC_FILTERS = [
    "tags=Cybersecurity",
    "industries=Security",
    "tags=Artificial%20Intelligence",
    "tags=AI",
    "tags=Machine%20Learning",
]
```

### Filter format

Each entry is a URL query-string param: `tags=<Tag>` or
`industries=<Industry>`, URL-encoded (spaces → `%20`). The YC API
honors these server-side; passing an unknown param name is silently
ignored (returns the unfiltered full list, so don't typo).

Companies are UNIONed across filters and deduped by slug.

### Quality filter

After the server-side tag pull, `src/yc_discovery.py` applies a
local OR filter to drop the YC long tail of 1-3 person pre-seed
companies that don't yet have a public ATS:

```python
MIN_TEAM_SIZE = 20            # established enough to run a job board
RECENT_BATCHES = ["F26", "S26", "W26"]  # last 3 batches as of 2026-10
```

A company qualifies if **teamSize ≥ 20** OR **batch is in the recent
list** — the OR keeps both established alumni AND recent cohorts, while
dropping ancient tiny teams and pre-seed noise.

To refresh the batch list over time: look at `batches seen so far` in
`debug/probe_yc_filter_and_jobs.py` output (first 12 pages) and keep
the three most recent.

### Finding tag/industry values

Walk a few pages of `https://api.ycombinator.com/v0.1/companies` and
inspect the `tags` + `industries` arrays on real company entries.
Common values:
- Industries: `Security`, `B2B`, `Industrials`, `Defense`, `Fintech`,
  `Healthcare`, `Consumer`, `Education`
- Tags: `Cybersecurity`, `AI`, `Artificial Intelligence`, `Machine
  Learning`, `Generative AI`, `Developer Tools`, `SaaS`, `Robotics`,
  `Autonomous Vehicles`

See `debug/probe_yc_filter_and_jobs.py` output for the live counts.

## ATS detection — how it works

For each candidate's `website`, we try common careers paths in order:
`/careers`, `/jobs`, `/about/careers`, `/company/careers`, `/`. The
first page that returns 200 gets scanned with regexes targeting the
five supported ATS platforms:

| ATS | URL shape | Validation endpoint |
|-----|-----------|---------------------|
| Greenhouse | `boards.greenhouse.io/<slug>` or `job-boards.greenhouse.io/<slug>` | `boards-api.greenhouse.io/v1/boards/<slug>/jobs` |
| Lever | `jobs.lever.co/<slug>` | `api.lever.co/v0/postings/<slug>?limit=1` |
| Ashby | `jobs.ashbyhq.com/<slug>` or `<slug>.ashbyhq.com` | `api.ashbyhq.com/posting-api/job-board/<slug>` |
| Workable | `apply.workable.com/<slug>` | `apply.workable.com/api/v3/accounts/<slug>/jobs` |
| Workday | `<tenant>.wdN.myworkdayjobs.com/<site>` | `<tenant>.<pod>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` |

Each regex match is validated via its native API — only ATSes
returning `>= 1` real job get accepted. This catches false positives
(incidental "lever.co" references in blog posts, protocol-relative
URLs captured by overly loose patterns, etc.).

### Known limits

Current hit rate is **~30% on the top-60 by team size**. The remaining
~70% are mostly:
- JS-rendered careers pages (React SPAs that redirect client-side);
  our urllib GET sees an empty shell. Playwright-based detection
  would catch these — not shipped yet.
- Companies hiring via YC founder network only (no public ATS).
- Media / early-stage companies with no active hiring.

A future round can add Playwright-based detection for the long tail.
For now, hand-add specific companies that matter.

## Applying the output

Three places get updated (same shape as WTJ):

| File | Section | What's added |
|------|---------|--------------|
| `src/catalog.py` | after the WTJ block, before Blockchain | `{'name': ..., 'kind': 'ashby', 'slug': ..., 'board': ..., 'group': 'Y Combinator'}` |
| `data/user_config.py` | `SOURCES` list | Same shape, with `'queries': []` |
| `src/config.py` | `GROUP_OF` dict | `'<name>': "Y Combinator"` |

## Verifying the result

Per `CLAUDE.md` "TEST before claiming it works", the apply script runs
`make test` automatically at the end. To additionally verify every YC
source returns jobs end-to-end:

```
PYTHONPATH=src python3 debug/test_wttj_sources.py
```

(The WTJ end-to-end script iterates every source in every group; it
covers YC too.)

## When to re-run

- After broadening or narrowing `DEFAULT_YC_FILTERS`
- Every ~3-6 months to pick up new YC batches (F26, S27, …)
- If a batch of YC sources suddenly go to 0 jobs — the companies may
  have switched ATS; a refresh re-detects the new one.
