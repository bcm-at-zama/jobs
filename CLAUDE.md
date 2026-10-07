# CLAUDE.md — house rules for this repo

## Repository layout — do NOT create directories without asking

Only the following top-level directories exist. If you think you need a
new one, ASK FIRST — don't just create it.

| Directory   | Purpose                                                       |
|-------------|---------------------------------------------------------------|
| `src/`      | Application source code (`.py`). This may become open source. |
| `tests/`    | Test suite (`.py`). Always kept separate from `src/`.         |
| `data/`     | **User's personal data** — profile, applied, liked, rejected, caches. Not open-sourced. |
| `debug/`    | Everything debug-related: probes, HTML dumps, exploration scripts. |
| `planning/` | Tickets, roadmap, reference docs about the project workflow.  |
| `knowledge/`| `.md` / `.txt` notes capturing your understanding or research. Build this up as you learn the codebase. |
| `script/`   | Shell scripts invoked by `make` targets or run directly (e.g. `push.sh`). |
| `docs/`     | User-facing documentation (dev guide, screenshots). Linked from `README.md`. |

## No personal data in `src/`

Source code (anything in `src/`) may be published as open source. It
must contain ZERO personal data belonging to the user — no preferences,
no filters, no profile fields, no custom highlight keywords, no
user-specific URLs. If a file in `src/` carries personal values, split
them out into `data/` (user-overridable) and leave only neutral defaults
or empty placeholders in `src/`.

Before adding a value to a `src/` file, ask yourself: "would this be
awkward if a stranger ran this exact file?" If yes, the value belongs
in `data/`.

## No geeky details in user-facing UI

The browser UI is for the user, not the implementer. Keep internal
file paths, implementation notes, backup suffixes, env-var names,
class names and other plumbing OUT of visible text (titles, modals,
status lines, tooltips the user actually reads).

- Bad: "Changes save to `data/user_config.py` (with a timestamped
  backup). Click `R` to re-fetch."
- Good: "Your board rebuilds automatically after you save."

Those details still belong in code comments, docstrings, `CLAUDE.md`
and `planning/`. Just not where the user sees them.

## Run `make test` after every edit, and grow the suite

**This is non-negotiable, and pre-authorized.** After any edit to
`jobs.py`, `config.py`, or anything the tests depend on, run:

```
make test
```

Do NOT ask for permission to run `make test` — it is pre-authorized,
read-only (no state changes outside `debug/`), and finishes in ~40ms.
Just run it.

If it fails, the edit is not done — fix the breakage before claiming the
task is complete. If the failure is a stale test expectation (the edit was
intentional and the test should be updated), update the test with a clear
reason. Never silently delete or skip a test to make the suite green.

**Add a test for every bug fix or new behavior.** The test suite in
`tests/` is organized by concern (`test_locations.py`, `test_scrapers.py`,
`test_seniority.py`, `test_blacklist.py`, `test_spontaneous.py`,
`test_config.py`, `test_scoring.py`). When fixing a regression, add the
case that reproduces it before applying the fix — this both proves the
fix works and prevents the same regression from reappearing.

Pattern to follow:
- New blacklist entry? → `tests/test_blacklist.py`
- New location shape (e.g. "<country> - <city>")? → `tests/test_locations.py`
- New scraper or regex change? → `tests/test_scrapers.py`, assert against
  the existing `debug/debug-*.html` dump
- New big-tech `SENIORITY_XP` / `IC_LEVEL_XP` entry? → `tests/test_seniority.py`
- New spontaneous pattern? → `tests/test_spontaneous.py`

The suite uses stdlib `unittest` only (no pip install), runs in ~40ms,
and currently has 50+ tests. There is no excuse to skip it.

## Test before shipping

**Do not guess at regex, selectors, or URL patterns.** If I'm about to add or
modify a scraper (`link_re`, `wait_selector`, board URL, etc.), I must first
verify the pattern against real evidence:

1. **The user's debug dumps live in `/workspace/debug-*.html`.** They are the
   ground truth for what Playwright rendered on the user's machine. I have
   direct read access to these files — I don't need the user to paste or
   forward anything. If a dump exists, always inspect it before changing a
   scraper for that source.
2. If no dump exists yet (new source), say so — don't invent a pattern from
   a vague URL guess.
3. After editing, verify the new regex against the existing dump with a
   quick Python one-liner. Only ship if it extracts at least one URL.

Rationale: many rounds have been wasted where I asked the user to "envoyez
me le dump" when the file was already on disk in `/workspace/`. That is
purely my failure — the user shouldn't have to re-run for me to see data
I could just open.

## When you can't verify

Only two legitimate reasons to change a scraper without dump verification:
  - the source is brand new and no dump exists (say so)
  - the source's URL changed and even the old dump is stale (say so)

In every other case: read the dump first.

## Never patch blindly

Never propose a "blind" patch (a guessed URL, regex, or selector) to save a
round trip. Wasted rounds waste more time than one extra probe. If you can't
verify from a dump or a probe output, produce a probe script and stop until
the user runs it. The only edits allowed without verification are those the
user has explicitly authorized in the current message.

## Commands must be ONE line

Any command I give the user to run must fit on **a single line** with
no backslash continuations and no embedded newlines. Multi-line shell
commands are mis-copied in half of pastes (the user ends up running
only the first line and getting a confusing error).

Bad:
```
python3 debug/probe.py \\
    https://a.com \\
    https://b.com
```

Good:
```
python3 debug/probe.py https://a.com https://b.com
```

If a command would be too long for one line, wrap it in a `.py` under
`debug/` instead (per the probe rule above) and give the user a
one-liner that runs the script.

## Don't be lazy — automate before asking

**When I'm about to ask the user to look something up by hand ("please
open their careers page and tell me what you see", "paste the URL",
"check which ATS they use"), I MUST first ask: can I ship a probe
that does this discovery automatically?**

Default lazy pattern (bad):
- "Can you open aircall.io and tell me their ATS?"
- "Please find their careers URL and paste it."
- "Open DevTools, filter XHR, copy the request."

Correct pattern:
- Ship a `.py` probe that brute-forces the likely URLs / endpoints /
  slug variants / selector patterns on the user's Mac. The user runs
  one command, the probe reports the answer.
- Only ask the user to look manually AFTER the probe has exhausted
  the automatable options and failed, AND I've said so explicitly in
  the response ("the probe tried X, Y, Z — none worked; this one
  genuinely needs your eyes").

Rationale: asking the user to do what I could have scripted wastes
their time and chat context. One extra line in a probe (another URL
variant, another regex, another candidate slug) usually saves 3-5
turns of ping-ponging.

Pair with the probe rule above: automate first, probe second, user
third.

## Never remove what doesn't work — FIX it

**When something is broken (wrong slug, dead URL, failed scrape, 0-job
company, missing API endpoint, …): fix the root cause. Do not silently
delete the entry and declare victory.** This has happened too many
times:

- Wrong WTJ slug → I removed the catalog entry instead of searching
  Algolia by name to find the real one.
- A scraper returned 0 jobs → I dropped the source instead of
  diagnosing (wait selector, link regex, pagination).

Removal is a last-resort action, taken only when:
- The company genuinely no longer exists on that platform (verified
  from multiple angles — Algolia search by name, Google, their own
  domain), AND
- The user explicitly approves the removal in the current message.

Default playbook when something is broken:
1. Produce a probe that pinpoints WHERE it breaks (which call fails,
   which selector misses, which slug 404s).
2. Try alternatives (name-based lookup, variant slugs, different API
   endpoint, longer wait selector, scroll trigger, …).
3. Report findings + propose the fix. Removal is NOT a fix.

## Probes are always .py scripts under debug/

Any time I need you to run something from your Mac — fetching a URL,
checking an ATS slug, dumping a page, confirming a selector, probing
anything — I MUST ship it as a Python script under `debug/` and point
you at it. Never paste a bare `curl` / `grep` / shell one-liner for you
to copy. Reasons:

- A `.py` file is reviewable and re-runnable. Shell one-liners pasted
  in prose rot the moment the chat scrolls.
- It lives in `debug/` (per the repo layout rule), with a module
  docstring explaining what it does and what to look for in the output.
- It stays stdlib-only (`urllib`, `json`, `re`, `sys`) so you can run
  it with plain `python3 debug/probe_foo.py` — no venv activation, no
  deps, no surprises.
- It should print a clear human summary AND a machine-readable
  (JSON-fenced) block at the bottom so pasting the result back is
  mechanical, not a search-and-copy exercise.

Minimum shape:

```python
#!/usr/bin/env python3
"""Probe <what> — explain why, note any sandbox-blocked endpoints,
mention which group / scraper this feeds, and what to paste back."""
# stdlib only; prints progress + a ```json block at the end.
```

Exception: once a probe already exists for the exact thing you need
(e.g. `debug/probe_broken_sources.py`), reuse it instead of writing a
new one. "Shell one-liner" is NOT the exception — build or extend a
probe.

## Related principles

- Prefer editing existing scrapers over cloning new ones — if a slug is
  wrong, that's a one-line fix, not a rewrite.
- When adding a new board, always start with `queries: []` so we see every
  posting; the user narrows the queries once we've confirmed the scraper
  works end to end.
- When adding a new big-tech source, also add a `SENIORITY_XP` entry in
  `config.py` if the company has a public leveling grid (Cisco grades, IBM
  bands, Google L-levels, Meta E-levels, LinkedIn IC-levels, Microsoft 6x
  bands, Apple ICT, etc.). Otherwise the generic `SENIORITY_XP_DEFAULT`
  fallback kicks in (~5y Senior / ~8y Staff / ~12y+ Principal), which is
  fine for startups but misleading for a big company with atypical bands.
  Startups: don't invent entries — rely on the fallback.

## Ask one thing at a time

When I need an input from you, I MUST ask ONE question per turn. Not
three. Not "A, B, or C — also D?". One question, scoped, with a clear
default where sensible.

Why: when I pile several questions into one message, the ones at the
end get missed. The dialog devolves into "you asked three things, I
answered one". Serialising keeps us in sync.

If I have multiple pending questions, pick the one that unblocks the
most work and ask it. Keep the others as a mental TODO; raise them in
later turns, one by one, as earlier questions get answered.

Exception: when the questions are truly a single multi-choice decision
("stop / continue / cancel?"), that's one question with options — fine.
What's NOT fine is "do you want X? Also Y? Also Z?".

## When you need something from me — ask explicitly, and remind

- When you need an input from me (a URL, a probe output, a decision between
  two options, a confirmation before a destructive action), state it
  explicitly as a question and stop.
- If I move on to another topic without answering, you MUST re-ask on your
  next turn. Do not silently drop the question and do not proceed with a
  guess.
- **Re-ask ONE question at a time, even when a backlog has built up.**
  Combine with the "Ask one thing at a time" rule above: if I've skipped
  three pending questions, do NOT dump all three back at me on the next
  turn — pick the most load-bearing one and ask ONLY that. The others
  stay on your mental TODO and surface, still one at a time, in later
  turns as earlier questions get answered.
- Rationale: it is easy for me to miss a question buried at the end of a
  long paragraph. Losing the question means losing the correct fix.
  Dumping a backlog of three re-asks has the same failure mode — I
  answer one, miss two, and we re-converge on nothing.
