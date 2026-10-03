# TICKET-01 — Onboarding wizard for new users

- **status:** open
- **priority:** P1
- **effort:** L
- **created:** 2026-10-03
- **owner:** unassigned

## Context

Today, a new user who clones the repo gets a `config.py` tuned for
Benoit's job hunt (147 companies in cybersecurity + big tech + music
tech, blacklist on India/Thailand/Japan, highlight on "security" and
"cryptography"). Nothing is obviously wrong, but nothing is theirs
either. The current onboarding path requires reading `config.py`
end-to-end and editing it by hand.

`user_config.example.py` was added in October 2026 as a minimal
template, but copying + editing still assumes the user is comfortable
with Python literal syntax, knows what an ATS "kind" is, and knows
which companies to include. For non-engineers (adjacent discipline, PM,
designer), this is a wall.

## Scope

**In:**

- A one-command onboarding flow (`python3 jobs.py --onboard`) that
  interactively collects:
  - **Industries** of interest (checkbox-ish — "AI / ML", "Security",
    "FinTech", "DevTools", "Music tech", "Climate", "Health", etc.).
    Each industry maps to a curated preset list of companies the engine
    already knows how to scrape.
  - **Seniority** target (IC / Manager / Director / VP), narrows which
    titles are kept vs. dropped.
  - **Geography preferences:** "allow" list of countries/cities, and
    an "exclude" list.
  - **Keywords** to highlight in descriptions.
  - **LLM backend** (none / Ollama / Claude API) — see which the user
    already has set up.
- Writes a `user_config.py` next to `config.py`, with comments pointing
  back to each question so the user can re-edit by hand later.
- Shows the next command to run after onboarding completes.

**Out of scope (deferred to later tickets):**

- A full web UI for onboarding (CLI-first is enough).
- Automated discovery of new ATS boards (user-driven for now).
- Per-user LLM API-key management beyond "paste the key here".
- Migration of an existing `rejected.json` from a previous config.

## Design notes

- The industry → company presets are the hardest part. Likely need a
  new `config_presets.py` with ~5-10 presets, each listing 10-30
  companies. Hand-curated at first; could grow community-sourced
  later.
- CLI prompts should default to the simplest option (e.g. "all remote
  OK?" → yes). The user should finish in 2 minutes, not 20.
- Use the stdlib — no `rich` or `questionary` deps. `input()` + a
  numbered list is enough.

## Acceptance criteria

- [ ] `python3 jobs.py --onboard` exists and runs without errors on a
      fresh clone with no prior state.
- [ ] A new file `user_config.py` is written at the repo root with
      user-tuned `SOURCES`, `TITLE_BLACKLIST`, `LOCATION_BLACKLIST`,
      `HIGHLIGHT_WORDS` lists.
- [ ] If `user_config.py` already exists, the wizard asks before
      overwriting (default: no).
- [ ] At least 5 industry presets are shipped (AI, Security, FinTech,
      DevTools, Music tech), each with ≥10 companies that the engine
      can scrape today.
- [ ] A test (`tests/test_onboarding.py`) runs the wizard in a
      scripted mode (feeding fake stdin) and asserts the generated
      file is a valid Python module that the main engine can import.
- [ ] `make test` stays green.

## Open questions

- Should the wizard also write a `data/profile.md` by asking a few
  open-ended questions ("describe the role you're looking for in 2-3
  sentences")? Would unblock LLM scoring on day 1, but makes the
  wizard longer.
- Should industries be mutually exclusive (pick one) or additive (pick
  several)? Default: additive.
