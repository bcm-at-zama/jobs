# A Simple Job Board for Users

A self-hosted job hunt dashboard that scrapes company career pages
directly, scores each posting against YOUR profile with an LLM, and
puts every opening you care about in one browser tab.

## What it does

`jobs` runs on your laptop, fetches postings from the career pages of
the companies YOU care about (dozens of ATS types supported out of the
box — Greenhouse, Lever, Ashby, Workday, Phenom, BambooHR, Pinpoint,
Umantis, SuccessFactors, Eightfold, SmartRecruiters, custom
Playwright), scores each opening with Ollama or Claude against the
profile you write in Markdown, and renders everything as a static HTML
page you drive from your browser. State (liked, to apply, applied,
rejected) is persisted as local JSON files — nothing leaves your
machine.

**What you get:**

- **One cross-company view.** No more opening twelve career tabs to
  check whether anything new showed up this morning. One refresh gives
  you every new opening across every company you track, grouped by
  industry and ranked how you want.
- **Fit signal on every row.** Click C and the engine asks Claude to
  rate each visible posting against your profile out of 10, with a
  one-sentence reason. The ranking separates the two or three
  job-you-should-actually-read from the hundred that look vaguely
  interesting on paper.
- **No noise, no gatekeepers.** Every posting comes from the company's
  own ATS, not a search aggregator. No sponsored posts, no "jobs for
  you" feed trained on someone else's clicks, no premium tier required
  to see salary bands or old-but-still-open roles.
- **Your pipeline stays yours.** When you click Applied, that goes into
  a JSON file on your disk. You own the data, you can grep it, you can
  back it up on your own private repo, and no third party gets to
  decide when they lock you out of your own history.

## Screenshots

<!-- TODO: capture Ranked view, All view with filters, Pipeline tab,
     C-button paste bar. Save to docs/screenshots/ and link below. -->

![Ranked view](docs/screenshots/ranked.png)
![All view with filters](docs/screenshots/all.png)
![Pipeline](docs/screenshots/pipeline.png)

## Quick start

### 1. Clone & requirements

```bash
git clone <this-repo> jobs && cd jobs
# Python 3.11+ required. No pip install needed for the core engine —
# the test suite + scrapers run on stdlib only. Playwright is only
# needed for sources tagged kind: "pw" in your config.
pip install playwright && playwright install chromium   # optional
```

### 2. Onboarding — tell the engine what you care about

Copy the example config into `data/` (gitignored by default — your
preferences stay private):

```bash
cp src/user_config.example.py data/user_config.py
```

Edit `data/user_config.py`:

- `SOURCES` — one entry per company. Each entry picks an ATS `kind`
  (e.g. `greenhouse`, `ashby`, `workday`) and the board `slug`. See
  `planning/adding-ats-sources.md` for the per-ATS recipe (~3 min to
  add a new company).
- `TITLE_BLACKLIST` — substrings that hide any posting (case-
  insensitive). Use it to drop "Intern", "Account Executive", etc.
- `LOCATION_BLACKLIST` — countries or cities you don't want (hidden
  when ALL listed locations match a blacklist entry).
- `HIGHLIGHTS` — keywords drawn in yellow in titles and descriptions.

Optional but recommended: write `data/profile.md` with 1-2 paragraphs
describing the role you want (seniority, domain, geography, dealbreakers,
salary floor). The LLM scorer reads this to generate a fit score per
job.

### 3. Pick a scorer (optional)

The engine runs fine without any LLM — you just lose the fit score
column. Two backends supported:

- **Ollama (local, free):** `brew install ollama && ollama pull qwen2.5:7b`.
  Set `SCORER = "ollama"` in your config.
- **Claude (API, paid):** set `ANTHROPIC_API_KEY` in your environment,
  then `SCORER = "claude"` in your config.

### 4. Run

```bash
python3 src/jobs.py
```

First run fetches every source (expect 30-90s depending on how many
companies). Subsequent runs cache descriptions and are much faster.
The script writes `data/jobs.html` and opens it in your browser.

### 5. Daily use

- **R** button (top right) — refresh (re-fetch every source).
- **AI** button — re-run LLM scoring on jobs that got new descriptions.
- **C** button — ask Claude to rate every visible job out of 10. Opens
  claude.ai with a batched prompt; paste the reply back in the bar at
  the bottom of the page.
- **Tabs** at the top — All / New / Ranked / Spontaneous / Liked / To
  Apply / Pipeline. `⌘/Ctrl-click` opens every URL in that tab,
  `⌥/Alt-click` copies them to clipboard, `⇧-click` asks Claude about
  them.

## Requirements

- Python 3.11+ (stdlib only for the core engine).
- Playwright + Chromium — only for `kind: "pw"` sources.
- Ollama OR an `ANTHROPIC_API_KEY` — only if you want LLM scoring.
- No database. All state is JSON files under `data/`.

## Project layout

| Directory    | Purpose                                                  |
|--------------|----------------------------------------------------------|
| `src/`       | Application source code. Open-sourceable.                |
| `tests/`     | Test suite (`unittest` stdlib only, ~75 tests, <100 ms). |
| `data/`      | Your personal data: profile, config, state, caches. Gitignore this when forking. |
| `debug/`     | Scraper probes, HTML dumps, exploration scripts.         |
| `planning/`  | Tickets (`open/` + `closed/`), ATS recipes, workflow docs. |
| `knowledge/` | Freeform notes and research.                             |
| `script/`    | Shell scripts invoked by `make` targets.                 |

## Development

```bash
make test             # ~75 tests, <100ms, stdlib unittest
make commit           # git add src/ tests/ … + commit + push
```

House rules live in `CLAUDE.md` (test after every edit, no personal
data in `src/`, verify scraper changes against debug dumps, etc.).

## Contributing

See `planning/open/` for the current ticket backlog. A `CONTRIBUTING.md`
with PR/issue templates is tracked in `planning/open/07-contributing-
guide.md`.

## License

[MIT](LICENSE). Fork it, use it commercially, ship a derivative — just
keep the copyright line.
