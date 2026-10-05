# jobs — your personal job hunt dashboard

Tired of refreshing twelve career tabs every morning? Tired of generic
job boards burying real postings under sponsored noise, paywalled
filters, and ghost roles? **`jobs` runs on your laptop. You pick the
companies. You own the data. Your favourite AI chatbot ranks every
opening against your profile.** One `make run`, one browser tab, every
job you care about.

<!-- TODO: capture a screenshot of the Ranked view (post `make run` +
     after clicking C once) and save to docs/screenshots/ranked.png.
     Tracked in planning/open/09-screenshots-demo.md. -->

---

## Why you'd want this

- **One cross-company view.** Scrapes career pages directly — Greenhouse,
  Lever, Ashby, Workday, Phenom, BambooHR, SuccessFactors, Eightfold,
  SmartRecruiters, custom Playwright. Dozens of ATS types, one unified
  list. No noise, no sponsored posts, no "jobs for you" feed.

- **Fit score on every row.** One click (`C`) hands every visible
  posting to the LLM of your choice — Claude.ai, ChatGPT, Gemini,
  anything with a chat UI — which rates each one `/10` against the
  profile you wrote. The ranked view puts the two or three roles you
  should actually read at the top, ahead of the hundred that look
  vaguely interesting on paper.

- **Full application pipeline.** Like → To Apply → Applied → Pipeline.
  State lives in local JSON files you can grep, back up, and version.
  Nothing is on anyone else's server.

- **Zero API cost for scoring.** The `C` button copies a batched prompt
  to your clipboard and opens the chat tab of your choice. Any
  subscription you already pay for (Claude.ai Pro, ChatGPT Plus,
  Gemini Advanced, …) handles the scoring. No API key, no per-token
  bill.

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
- **A subscription to any chat LLM** (Claude.ai, ChatGPT, Gemini,
  DeepSeek, …) if you want fit scoring. The `C` button is wired to
  Claude.ai by default, but the paste bar accepts any model's reply as
  long as it follows the simple `N. X/10 — reason` format. Without a
  chat subscription you still get the cross-company dashboard,
  filters, and pipeline — just no fit score.

No database. No account. No cloud. Everything runs locally.

---

## In the browser

Top-right action buttons:

| Button | What it does |
|--------|--------------|
| **R**  | Refresh — re-fetches every source (~30-90 s). |
| **C**  | Scores every visible job with the LLM of your choice. See [Scoring with the C button](#scoring-with-the-c-button) below. |
| **⚙**  | Set a reusable chat URL (Claude.ai, ChatGPT, Gemini, …) so `C` always opens the same conversation and keeps prior permissions / context. |

Tabs at the top: **All · New · Ranked · Spontaneous · Liked · To Apply ·
Pipeline**. On every tab:

- `⌘/Ctrl-click` a tab → opens every job URL in that view.
- `⌥/Alt-click` → copies the URLs to clipboard.
- `⇧-click` → asks Claude about them (opens Claude.ai with the prompt).

Each row has state buttons (`+1` · `TA` · `✓` · `R` · `K`) that move
the job through your pipeline.

### Scoring with the C button

The `C` button rates every visible job `/10` against your profile
using your preferred LLM (Claude.ai, ChatGPT, Gemini, …). You use the
chat subscription you already pay for — zero per-token cost. The flow
is manual — you glue two tabs together with a copy-paste — but it
finishes in under a minute even for 150 jobs.

**First time:**

1. Open `data/profile.md` and write 1-2 paragraphs about the role you
   want: seniority, domain, geography, dealbreakers, salary floor. The
   LLM uses this to rate each posting.
2. Open `data/user_config.py` and make sure your `SOURCES` list is
   reasonable — the fewer irrelevant companies, the shorter the batched
   prompt.
3. Optional: click **⚙** (top right) once to pin the chat URL of your
   preferred LLM — e.g. `https://chatgpt.com/c/<id>` or
   `https://claude.ai/chat/<id>`. Subsequent `C` clicks open THAT same
   conversation, which (a) keeps whatever fetch / search permissions
   the model has already received and (b) lets the model carry context
   from previous scoring rounds. Without a pinned URL `C` just opens
   `https://claude.ai/new`.

**Every time you want to score:**

1. Click **C** (top right). The jobs page copies a batched prompt to
   your clipboard and opens your pinned chat (or a fresh Claude.ai
   tab).
2. In the chat tab:
   - If the prompt landed directly in the input (fresh Claude.ai tab,
     short enough URL), just hit **Enter**.
   - Otherwise the input is empty — paste (**⌘V** / **Ctrl-V**) and
     send.
3. Approve any URL-fetch / web-browse permission the model asks for
   (first time only on a pinned chat).
4. Wait for the model to finish. The expected reply format is one
   line per job:
   ```
   1. 8/10 — fit reason in 2-3 sentences on a single line
   2. 7/10 — another fit reason
   ```
5. **Copy the full reply** (⌘A then ⌘C in the chat tab).
6. Switch back to the jobs tab. A sticky paste bar appeared at the
   bottom of the page — **paste** (⌘V) into it.
7. The parser extracts the scores automatically. Each row gets a
   purple **Score: X/10** badge; hover for the reason. The paste bar
   self-dismisses after a second.

**Where scores land:**

- The purple score badge powers the **Ranked** tab (jobs flattened
  cross-company, sorted by fit DESC).
- Scores persist to `data/claude_fit_cache.json` — a refresh (R) won't
  lose them, and another browser session will show the same scores.

**Tips:**

- **Pin a chat URL (⚙).** Removes one friction point per run (no
  permission dialog) and lets the model build context across sessions.
- **Rate incrementally.** Switch to the **New** tab to score only
  newly-fetched jobs instead of the whole list.
- **Modifier-click.** `⇧-click` a tab to ask the LLM a free-form
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
