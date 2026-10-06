# TICKET-11 — Companies-to-add backlog

- **status:** open
- **priority:** P2
- **effort:** L (ongoing — tackle a few at a time)
- **created:** 2026-10-05
- **owner:** unassigned

## Summary

Standing backlog of companies worth adding to `config.py` once their ATS
is unlockable or someone finds the right URL. Each entry is tagged with
the fetcher kind we'd use. See `planning/adding-ats-sources.md` for the
step-by-step recipe per ATS.

## Legend

- `[P]`  = ~1 h Playwright custom scraper (small board or unique HTML)
- `[W]`  = Workday — supported via `kind: "workday"`
- `[SF]` = SuccessFactors — supported via `kind: "successfactors"`
- `[BH]` = BambooHR — supported via `kind: "bamboohr"`
- `[PP]` = Pinpoint HQ — supported via `kind: "pinpoint"`
- `[UM]` = Umantis — supported via `kind: "umantis"`
- `[SR]` = SmartRecruiters — TODO fetcher
- `[??]` = ATS not yet identified

## HIGH VALUE (crypto / dev tools / French / Benoit's profile)

| Company          | Kind | Notes |
|------------------|------|-------|
| GitGuardian      | —    | DEFERRED 2026-10-01: Cloudflare bot-protection blocks Playwright. Needs stealth setup. |
| BlaBlaCar        | [P]  | French travel — SmartRecruiters |
| Contentsquare    | [P]  | French analytics — SmartRecruiters |
| Aikido           | [P]  | Belgian appsec — greenhouse.io/aikido (embed only?) |
| Cyera            | [W]  | Israeli data security — unlockable now |
| Legit Security   | [W]  | Israeli appsec — unlockable now |
| Arnica           | [??] | Israeli appsec |
| Latacora         | [??] | US security consultancy |
| NCC Group        | [W]  | UK security consultancy — unlockable now |
| ~~Groq~~         | ~~[GH]~~ | DONE 2026-10-06 — added as `greenhouse` / `groq` |
| Sakana AI        | [W]  | Tokyo AI lab — flaky Workable, keep an eye on it |

## MEDIUM VALUE (music tech — Benoit's founder space)

| Company            | Kind | Notes |
|--------------------|------|-------|
| Native Instruments | —    | BROKEN 2026-10-01: careers page has no job HTML links (JS). Removed. Need real ATS URL from user. |
| Splash             | [P]  | Music AI |
| Serato             | [P]  | DJ software |
| Bandcamp           | [P]  | Epic Games subsidiary |
| SoundCloud         | [P]  | |
| Spotify            | [W]  | Unlockable now |
| LANDR              | [P]  | Montreal — mastering / music AI |
| Roli               | [P]  | London MIDI hardware |
| Bitwig             | —    | DEFERRED 2026-10-01: bitwig.com/jobs = 404, /about has 0 openings |
| Sequential         | —    | DEFERRED 2026-10-01: 0 open positions |
| Deezer             | [P]  | Paris — French streaming |
| Tidal              | [P]  | Block subsidiary, separate ATS |
| Beatport           | —    | DEFERRED 2026-10-01: 0 open positions |

## GAFAM-adjacent (Workday unlocked for most)

| Company          | Kind | Notes |
|------------------|------|-------|
| Amazon / AWS     | —    | SKIPPED: amazon.jobs is custom (not Workday) + huge volume |
| Samsung          | [P]  | Proprietary careers site — SKIPPED pending scraper |
| Uber             | [SR] | SmartRecruiters |
| Tesla            | —    | SKIPPED: proprietary Taleo-based ATS, needs custom fetcher |
| ByteDance / TikTok | [P] | Proprietary (jobs.bytedance.com) |
| Booking.com      | [W]  | Unlockable now |
| Shopify          | [SR] | careers.shopify.com |
| Oracle           | —    | SKIPPED: Oracle iRecruitment is NOT a Workday variant. Custom fetcher needed. |
| ServiceNow       | [SR] | |
| Atlassian        | [SR] | |
| Zoom             | [W]  | Unlockable now |

## Music wave 5 skipped (blocked / declined)

| Company            | Reason |
|--------------------|--------|
| Ernie Ball         | Indeed-only — blocked |
| Music Tribe / Behringer | Indeed-only — blocked |
| DiMarzio           | Indeed-only — blocked |
| Lâg                | URL not found |
| Nord Keyboards     | URL not found (Clavia) |
| Peavey             | URL not found |
| Taylor Guitars     | User declined |
| Kemper             | User declined |
| Solid State Logic  | User declined |
| Positive Grid      | User declined |

## Flaky results (worked once, then didn't — retry probe)

| Company    | ATS       | Note |
|------------|-----------|------|
| Voyage AI  | Workable  | Was 200 with jobs=0, then 404 |
| HashiCorp  | Workable  | Was 200 with jobs=0, then 404 |
| Sakana AI  | Workable  | Same pattern |

## Probing a broken source

For each company marked `[BROKEN]`:

**Workday (board_id wrong, 404/422):**
1. Google "`<Company>` careers" → open the official careers page.
2. Click "Search jobs" or "View all jobs".
3. The URL should look like
   `https://<tenant>.wd<N>.myworkdayjobs.com/<board_id>` (sometimes with
   `/en-US/`). Capture it verbatim.

**Greenhouse (slug wrong, 404):**
1. Google "`<Company>` jobs greenhouse" or open their careers.
2. Click any job → URL should be `boards.greenhouse.io/<slug>/jobs/<id>`
   OR `job-boards.greenhouse.io/<slug>/jobs/<id>`.
3. Record the `<slug>`. If the URL is not Greenhouse, record the real ATS
   URL (lever.co, workable.com, smartrecruiters.com, ashbyhq.com, etc.)
   and its slug.

**Playwright (page has no job HTML links):**
1. Click any job on the company's careers page.
2. The job detail URL is usually a totally different domain (greenhouse,
   smartrecruiters, workable, …) — that is the real ATS.
3. Capture ONE example job URL; the ATS can then be identified and
   added properly.
