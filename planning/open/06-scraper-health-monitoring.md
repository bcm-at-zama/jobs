# TICKET-06 — Scraper health monitoring + "likely broken" UI badge

- **status:** open
- **priority:** P2
- **effort:** M
- **created:** 2026-10-03
- **owner:** unassigned

## Context

Boards change their HTML. In the past two months of this project alone,
scraper regressions landed for Cisco, Bose, IBM, Snyk, LinkedIn,
Seymour Duncan, Marshall. For Benoit, catching these takes 5 minutes
because he reads every log line. For an OSS user, a silent "0 jobs
fetched" is indistinguishable from "there are genuinely zero openings".

The engine already prints `(ZERO fetched!)` in the per-source log line
but that's buried in stdout. The UI shows the counter but doesn't
distinguish "scraper broken" from "empty board".

## Scope

**In:**

- A persistent "scraper health" tracker: for each source, record the
  rolling last-5-runs fetched count. Store in `data/scraper_health.json`
  keyed by source name.
- A source is flagged **suspicious** when:
  - last run fetched 0 AND the run before was > 0 (sudden drop)
  - OR last 3 consecutive runs fetched 0 AND the source has EVER
    fetched > 0 (board stopped working)
- In the UI, a suspicious source's section header gets a red indicator
  with hover text explaining why ("Fetched 0 jobs — last ran OK on
  2026-09-28 with 42 jobs. Likely selector regression.").
- In the UI top banner, add a count of suspicious sources with a
  link to show them all.

**Out of scope:**

- Automated repair (regex fallback / selector detection). That's an
  AI-complete problem for now.
- Alerting via email / Slack. Can be a later ticket on top of the
  health JSON.
- Historical trend graphs. Overkill for the signal.

## Design notes

- The health JSON is append-only in spirit: never drop old entries.
  The last-5 window is a view over the raw history.
- Reset-signal: when a user manually edits a scraper (e.g. after fixing
  one), the next run's non-zero fetch should immediately clear the
  "suspicious" flag — no "cool-down" window.
- Edge case: a board truly having zero openings looks the same as a
  broken scraper for a day. The 3-consecutive-zeros heuristic reduces
  false positives but adds a 3-run delay. Acceptable.
- Edge case: new source (never fetched > 0) should NOT be flagged
  suspicious. The heuristic above handles this.

## Acceptance criteria

- [ ] `data/scraper_health.json` is written on every run with the
      per-source fetched counts.
- [ ] UI section headers display a red indicator for suspicious
      sources; hover text explains why.
- [ ] A top-banner counter shows total suspicious sources (0 means
      green banner, > 0 means amber).
- [ ] `tests/test_scraper_health.py` covers the "sudden drop",
      "3 consecutive zeros", "new source", and "reset after fix"
      cases.
- [ ] `make test` stays green.

## Open questions

- Should "fetched 0 after 3+ previous > 0 runs" page the user via a
  system notification? Platform-specific (osascript on Mac). Lean:
  no, keep it in-UI only — users who care re-render the HTML.
- Should the health JSON include fetch TIMING too (duration > 2×
  rolling average = suspicious)? Would catch half-broken scrapers
  that still return something. Lean: later, not in v1 of this ticket.
