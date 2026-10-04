# TICKET-05 — Industry presets

- **status:** open
- **priority:** P1
- **effort:** M
- **created:** 2026-10-03
- **owner:** unassigned

## Context

`SOURCES` currently contains 147 hand-picked companies tuned for
Benoit's hunt: cybersecurity, big tech, music tech. A new user looking
at this list has three bad options:

1. Keep all 147 → scrapes companies they don't care about, 200s per
   cold run just to see 2 relevant jobs.
2. Delete the ~140 they don't want → tedious, requires knowing which
   is which.
3. Start from `user_config.example.py` → only 3 sources, miss the
   long tail.

The onboarding wizard (TICKET-01) needs something to bootstrap from.
That "something" is a set of named industry presets each listing
10-30 companies.

## Scope

**In:**

- A new file `presets.py` (or `config_presets/*.py`) exposing
  `PRESETS = {name: [source_dict, ...]}` with at least these buckets:
  - **AI / ML** — OpenAI, Anthropic, Cohere, Mistral, HuggingFace,
    xAI, Cursor, Perplexity, Scale AI, Replicate, Together, …
  - **Security** — CrowdStrike, Palo Alto, Wiz, Snyk, 1Password,
    Chainguard, Semgrep, BeyondTrust, Checkmarx, Pixee, …
  - **FinTech** — Stripe, Block, PayPal, Robinhood, Qonto, Doctolib,
    Alan, …
  - **DevTools** — GitHub, GitLab, HashiCorp, Datadog, Fastly,
    Cloudflare, Elastic, Snowflake, …
  - **Big Tech** — Apple, Google, Meta, Microsoft, NVIDIA, Amazon,
    Netflix, LinkedIn, Salesforce, Adobe, Cisco, Intel, Qualcomm,
    IBM, SAP
  - **Music Tech** (Benoit's niche — keep as evidence that specialty
    presets work) — Ableton, Arturia, Native Instruments, Fender, …
  - **Startups (AI)** — Thinking Machines, Rain, Etched, Prime
    Intellect, Physical Intelligence, Suno, Udio, Pika, …
- Each entry is the same shape as current `SOURCES` dicts
  (`name`, `kind`, `slug`, optional `board`, `queries=[]`).
- Onboarding wizard (TICKET-01) picks presets by name and concatenates
  them into the generated `user_config.py`.
- A `tests/test_presets.py` asserts:
  - Every preset has ≥ 10 entries.
  - Every entry's `kind` is registered in `FETCHERS`.
  - No duplicate slug within a preset.

**Out of scope:**

- A community-sourced preset registry (that's a later ticket).
- Preset deltas / inheritance (user picks AI + Security without
  dedup logic — simpler to accept dupes and let `dedup_by_url`
  handle them downstream).
- Per-preset default `queries`.

## Design notes

- Keep each preset's companies ordered the way they appear in the
  current `config.SOURCES` (so Benoit's bias is preserved for anyone
  picking the same preset).
- Document somewhere obvious (CLAUDE.md or presets.py docstring) that
  presets ARE opinionated — they reflect "senior IC roles in that
  industry". A junior-role preset is a different ticket.
- When adding a new company to the main `SOURCES`, decide which
  preset(s) it belongs to. The test ensures no company dangles outside
  all presets (or explicitly document the exception).

## Acceptance criteria

- [ ] `presets.py` exists with the 7 named presets listed above.
- [ ] Each preset has ≥ 10 entries, all with valid `kind`.
- [ ] `tests/test_presets.py` passes and covers the kind/duplicate
      invariants.
- [ ] `make test` stays green.
- [ ] A user picking "AI + Security" in the onboarding wizard
      (TICKET-01) ends up with a `user_config.py` containing the
      union of both presets.

## Open questions

- Overlap: Snyk is both security and DevTools. Dedupe at preset
  selection, or let it appear in both? Lean: appear in both; the
  engine already dedupes by URL.
- Should the user_config.py written by the wizard EMBED the preset
  list verbatim (lots of lines, user can edit) or just reference
  `from presets import PRESETS; SOURCES = PRESETS["ai"] + PRESETS["security"]`
  (one line, less flexible)? Lean: embed verbatim — it's clearer and
  survives preset refactors.
