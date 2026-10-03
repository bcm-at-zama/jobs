# TICKET-02 — Install guide (README.md at the repo root)

- **status:** open
- **priority:** P1
- **effort:** M
- **created:** 2026-10-03
- **owner:** unassigned

## Context

The repo currently has `CLAUDE.md` (house rules for the AI) and
`business/README.md` (how to build the PDF), but no top-level
`README.md` that a human visiting the repo for the first time would
read. Without one, GitHub shows a bare file listing and anyone
discovering the project (via Show HN, r/selfhosted, a tweet) has to
read source code to figure out what it does and how to run it.

The install story has moving pieces: Python 3.11+, Playwright + its
Chromium download, optional Ollama (for local LLM scoring), optional
`ANTHROPIC_API_KEY` (for Claude-based scoring + the `?`/C buttons),
first-time cache warmup (~200s). A new user needs each step spelled
out in order with "does this look right?" checkpoints.

## Scope

**In:**

- A top-level `README.md` with the following sections, in order:
  1. **What it is** — 2-3 sentences, screenshot or ASCII mock-up.
  2. **Who it's for** — explicit (senior engineers / managers chasing
     ATS-native boards + wanting LLM-scored, locally-ranked results).
  3. **Prerequisites** — Python 3.11+, 2 GB RAM free for Playwright
     Chromium, macOS or Linux (Windows via WSL untested).
  4. **Install** — exact commands, one block per concern:
     - clone + venv
     - `pip install` playwright + anthropic (optional)
     - `playwright install chromium`
     - optional: install + run Ollama with a small model
  5. **First run** — `python3 jobs.py` and wait ~200s on the first
     cold run, then open the browser link printed to stdout.
  6. **Personalize** — point to `user_config.example.py` and, once
     TICKET-01 is done, to `python3 jobs.py --onboard`.
  7. **Daily use** — subsequent runs with warm cache take 5-10s.
  8. **Troubleshooting** — common issues (403 from Cloudflare,
     Playwright Chromium missing, LLM scoring disabled because no
     profile).
  9. **Project layout** — one line per top-level dir (`data/`,
     `tests/`, `business/`, `planning/`).
  10. **Contributing** — point to `CLAUDE.md` for AI contributors and
      planning tickets for human ones.
  11. **License** — pick one (likely MIT or AGPL).

**Out of scope:**

- Dockerfile / docker-compose (becomes a separate ticket).
- Hosted / managed-SH offering (business/analysis.md path D).
- Full API documentation of every function in `jobs.py`.

## Design notes

- Keep it under 300 lines. Longer READMEs get skimmed and skipped.
- Lead with the screenshot — the UI is the "wow" moment for this
  project; words don't carry it.
- No shell escaping funny business — every command in a `sh` fenced
  block should be copy-pasteable as-is.
- Mention that `make test` is one command and runs in < 1s. Trust-
  builder for cautious readers.
- Link to `business/analysis.md` from the README for people curious
  about why this exists vs. JobSpy / JobSentinel.

## Acceptance criteria

- [ ] `README.md` exists at the repo root.
- [ ] A fresh user following the steps top-to-bottom gets a running
      `jobs.html` on their machine with zero out-of-band questions.
- [ ] At least one real screenshot (not ASCII) is embedded. Store it
      under `docs/screenshots/` so the README stays markdown-only.
- [ ] All commands referenced in the README are tested on both macOS
      (Benoit's primary) and at least one Linux distro.
- [ ] A license file (`LICENSE`) is added matching the README claim.
- [ ] `make test` stays green.

## Open questions

- License choice. MIT is standard and permissive. AGPL would require
  derivative hosted services to open-source their changes — relevant
  if a company tries to resell this as a SaaS.
- Does the README mention the SENIORITY_XP / IC_LEVEL_XP tables up
  front (so big-tech users immediately see the value), or save that
  for the "Personalize" section?
