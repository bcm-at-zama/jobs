# jobs — your personal job hunt dashboard

Tired of refreshing twelve career tabs every morning? Tired of generic
job boards burying real postings under sponsored noise, paywalled
filters, and ghost roles? **`jobs` runs on your laptop. You pick the
companies. You own the data. Claude ranks every opening against your
profile.** One `make run`, one browser tab, every job you care about.

<!-- TODO: capture a screenshot of the Ranked view (post `make run` +
     after clicking C once) and save to docs/screenshots/ranked.png.
     Tracked in planning/open/09-screenshots-demo.md. -->

---

## Why you'd want this

- **One cross-company view.** Scrapes career pages directly — Greenhouse,
  Lever, Ashby, Workday, Phenom, BambooHR, SuccessFactors, Eightfold,
  SmartRecruiters, custom Playwright. Dozens of ATS types, one unified
  list. No noise, no sponsored posts, no "jobs for you" feed.

- **Fit score on every row.** One click (`C`) sends every visible
  posting to Claude, which rates each one `/10` against the profile you
  wrote. The ranked view puts the two or three roles you should
  actually read at the top — ahead of the hundred that look vaguely
  interesting on paper.

- **Full application pipeline.** Like → To Apply → Applied → Pipeline.
  State lives in local JSON files you can grep, back up, and version.
  Nothing is on anyone else's server.

- **Zero API cost for scoring.** The `C` button opens Claude.ai in your
  browser and pastes a batched prompt — Claude.ai handles it with your
  existing Pro / Max / Team subscription. No API key, no per-token bill.

---

## Quick start

```bash
git clone <this-repo> jobs && cd jobs
make install      # venv + Python deps + Playwright Chromium (~2 min)
make onboarding   # creates data/user_config.py + data/profile.md
# edit data/user_config.py (SOURCES, blacklist, highlights)
# edit data/profile.md    (1-2 paragraphs about the role you want)
make run          # fetch every source, open the browser
```

Daily use: just `make run`. The HTML lands in your browser; everything
else is point-and-click.

---

## Requirements

- **macOS or Linux** with Python 3.11+.
- **Chrome / Chromium** installed by `make install` (via Playwright).
- **A Claude.ai subscription** (Pro, Max, or Team) if you want fit
  scoring. Free alternatives: use the UI without the `C` button — you
  still get the cross-company dashboard, filters, and pipeline.

No database. No account. No cloud. Everything runs locally.

---

## In the browser

Top-right action buttons:

| Button | What it does |
|--------|--------------|
| **R**  | Refresh — re-fetches every source (~30-90 s). |
| **C**  | Scores every visible job with Claude. See [Scoring with the C button](#scoring-with-the-c-button) below. |
| **⚙**  | Set a reusable Claude.ai chat URL so `C` always opens the same conversation (preserves tool permissions). |

Tabs at the top: **All · New · Ranked · Spontaneous · Liked · To Apply ·
Pipeline**. On every tab:

- `⌘/Ctrl-click` a tab → opens every job URL in that view.
- `⌥/Alt-click` → copies the URLs to clipboard.
- `⇧-click` → asks Claude about them (opens Claude.ai with the prompt).

Each row has state buttons (`+1` · `TA` · `✓` · `R` · `K`) that move
the job through your pipeline.

### Scoring with the C button

The `C` button rates every visible job `/10` against your profile. It
uses your Claude.ai subscription (web, not API), so there's zero
per-token cost. The flow is manual — you glue two tabs together with a
copy-paste — but it finishes in under a minute even for 150 jobs.

**First time:**

1. Open `data/profile.md` and write 1-2 paragraphs about the role you
   want: seniority, domain, geography, dealbreakers, salary floor.
   Claude uses this to rate each posting.
2. Open `data/user_config.py` and make sure your `SOURCES` list is
   reasonable — the fewer irrelevant companies, the less Claude work.

**Every time you want to score:**

1. Click **C** (top right). The jobs page copies a batched prompt to
   your clipboard and opens a new Claude.ai tab (or jumps to the chat
   URL you pinned via **⚙**).
2. In the Claude tab:
   - If the prompt landed in the chat input, just hit **Enter**.
   - If the prompt was too long for the URL, Claude.ai will be empty —
     paste (**⌘V** / **Ctrl-V**) and send.
3. Give Claude access to fetch URLs when it asks (first time only —
   pin a chat with **⚙** so permissions carry over on subsequent runs).
4. Wait for Claude to finish rating all jobs. The reply follows this
   format:
   ```
   1. 8/10 — fit raison … — SAL: $150k-$200k
   2. 7/10 — fit raison … — SAL: none
   ```
5. **Copy the full reply** (⌘A then ⌘C in the Claude tab).
6. Switch back to the jobs tab. A sticky paste bar appeared at the
   bottom of the page — **paste** (⌘V) into it.
7. The parser extracts the scores and salaries automatically. Each row
   gets a purple **Score: X/10** badge; hover for the reason. The paste
   bar self-dismisses after a second.

**Where scores land:**

- The purple score badge is what powers the **Ranked** tab (jobs
  flattened cross-company, sorted by fit DESC).
- Scores persist to `data/claude_fit_cache.json` — a refresh (R) won't
  lose them, and another browser session will show the same scores.
- Extracted salaries land in `data/llm_cache.json` and show as the
  yellow `💰` badge on each row.

**Tips:**

- **Pin a chat URL (⚙).** Normally Claude asks permission each run to
  fetch job pages. If you pin a chat, the permissions carry over and
  subsequent runs skip the prompt entirely.
- **Rate incrementally.** Switch to the **New** tab to score only
  newly-fetched jobs instead of the whole list.
- **Modifier-click.** `⇧-click` a tab to ask Claude a free-form
  question about those specific jobs (shortlisting, comparisons, etc.)
  without going through the scoring prompt.

---

## Going deeper

Adding a new company, project layout, development workflow,
contributing → see [`docs/development.md`](docs/development.md).

---

## License

[MIT](LICENSE). Fork it, use it commercially, ship a derivative — just
keep the copyright line.
