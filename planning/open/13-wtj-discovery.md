# WTJ company discovery

**Status**: open · **Owner**: Benoit / Claude · **Priority**: low (nice-to-have)

## Problem

The `Welcome to the Jungle` source was removed on 2026-10-07 because
it contributed ~0 jobs for two independent reasons:

1. **No extractable URLs in the rendered HTML.** The WTJ aggregator is
   a Next.js SPA that fetches job cards via XHR after render. The
   `networkidle` wait fallback didn't catch those requests reliably —
   dumps surveyed on 2026-10-07 had **0** `/fr/companies/*/jobs/*`
   hrefs across 756 total hrefs in 3 query dumps (`debug/debug-wttj-{CTO,VP,security}-1.html`).
2. **CloudFront WAF blocks headless chromium.** A live-render probe
   (`debug/probe_wttj_live_render.py`) got a 403 from CloudFront on
   `/fr/jobs`, `/fr/companies/<slug>`, and `/fr/companies` — all 923 B
   identical error pages. Also `/robots.txt`. So headless Playwright
   can't even reach the pages, let alone render them.

Benoit's original intent was *discovery*: on every refresh, surface
WTJ-hosted companies that aren't yet in the catalog, so he could tick
them from the Edit-companies modal (⌘E) and have them tracked.
Discovery is impossible as long as (1) and (2) both hold.

## What still works

- **Per-company custom WTJ-hosted domains** like `jobs.zama.org` are
  NOT behind CloudFront and NOT a SPA — they render static-enough HTML
  that `kind=pw` with the right `link_re` works first try. Zama is in
  the catalog today and reliably returns its ~3 postings. New WTJ-hosted
  companies can be added manually in this shape.

## Approaches to revisit

Ordered by effort. Any of them unblocks discovery.

### A. Playwright-stealth + non-headless fallback (~1 day)

- Install `playwright-stealth` (`pip install playwright-stealth`),
  patch WTJ context with `stealth_sync(context)`.
- If 403 still fires, fall back to `headless=False` for WTJ-only
  (user sees a Chromium window flash for 2 s during refresh).
- Then still need to beat the SPA — wait for the specific result-card
  selector (needs a fresh non-headless probe to identify it) OR capture
  the XHR response via `page.on("response")`.
- Risk: Cloudflare/CloudFront arms race, might stop working again.

### B. Reverse-engineer the WTJ API (~0.5-2 days, biggest payoff)

- A real-browser Network tab visit to `/fr/jobs?query=security` would
  show the actual API URL (likely `https://api.welcometothejungle.com/
  graphql` or similar) and the response shape.
- A direct `urllib` call from Python (NOT headless chromium) might
  slip past CloudFront, since CloudFront fingerprints on JA3/TLS, not
  just user-agent, and a plain `urllib.request.urlopen` has a very
  different fingerprint than headless-chrome.
- If the API responds, discovery is trivial: it returns JSON with
  company name + slug + job title + location, structured. No HTML
  parsing at all.
- Risk: API shape may change; API may require auth.

### C. Scrape via Google cached results (~0.5 day)

- `google.com/search?q=site:welcometothejungle.com/fr/companies/`
  returns thousands of indexed company pages.
- Extract company slugs from the Google result list, no WTJ visit
  needed.
- Google is more scraper-friendly than CloudFront but has its own
  rate limiting and markup churn.

### D. Manual curation (current state)

- Keep adding WTJ-hosted companies by hand, one at a time, in the
  shape of Zama. No automation. Simplest but slowest.

## Recommendation when revisited

Try **B** first. The payoff is highest (structured JSON) and the probe
is just a single `urllib.request` call — cheap to attempt. If API is
locked down too, fall back to **A** then **C**.

## Pointers

- Current removal commit: `git log -- src/jobs.py | head` (search for
  "wttj" / "Welcome to the Jungle") — the old `fetch_wttj` is in git
  history as a reference implementation.
- Debug dumps that confirm the problem are kept at
  `debug/debug-wttj-*.html` on Benoit's Mac.
- Live-render probe that demonstrates CloudFront 403:
  `debug/probe_wttj_live_render.py`.
