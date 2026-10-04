# TICKET-07 — CONTRIBUTING.md + issue/PR templates

- **status:** open
- **priority:** P2
- **effort:** S
- **created:** 2026-10-03
- **owner:** unassigned

## Context

Once this ships OSS, the maintenance load (fixing broken scrapers,
adding new companies, patching location regexes) needs to be
distributable. Without a `CONTRIBUTING.md`, every PR is a conversation
from zero. Without issue templates, every "it doesn't work" issue
costs 2 round trips to triage.

The repo already has strong conventions (`CLAUDE.md`, `make test`,
`debug/*.html` dumps as ground truth) — they just aren't surfaced to
humans.

## Scope

**In:**

- `CONTRIBUTING.md` at the repo root, covering:
  - **How to add a new source.** Step-by-step for the 4 easy
    kinds (greenhouse / ashby / workday / phenom): slug discovery,
    config entry, test run.
  - **How to fix a broken scraper.** Pointer to the debug dump
    convention (`debug/debug-<name>-*.html`), the CLAUDE.md rule
    "always inspect the dump first".
  - **Testing.** `make test` runs the whole suite in < 1s. Every PR
    adds at least one case to `tests/`.
  - **Code style.** Short, no gratuitous comments, PEP-8-ish via
    whatever the user's IDE enforces. No new deps without a very
    good reason.
  - **Commit message convention.** Current pattern is terse
    ("Update"). For OSS, suggest conventional-commits-lite:
    `fix(scraper): cisco card regex`, `feat(ui): sort by score`.
- `.github/ISSUE_TEMPLATE/scraper-broken.md`:
  - Expected / observed / debug dump attached.
- `.github/ISSUE_TEMPLATE/feature-request.md`:
  - Problem / proposed solution / alternatives considered.
- `.github/PULL_REQUEST_TEMPLATE.md`:
  - What / why / test coverage / `make test` output.

**Out of scope:**

- A full code-of-conduct (point to Contributor Covenant from
  CONTRIBUTING.md if needed).
- CLA / DCO (overkill for this scale).
- Governance docs.

## Acceptance criteria

- [ ] `CONTRIBUTING.md` exists at the repo root, < 300 lines.
- [ ] `.github/ISSUE_TEMPLATE/` has at least `scraper-broken.md` and
      `feature-request.md`.
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` references `make test`.
- [ ] Every template renders cleanly in the GitHub "new issue / new
      PR" UI (test this on a staging repo first).
- [ ] CONTRIBUTING.md links back to `CLAUDE.md` for the "verify
      against debug dump" rule and the "add a test for every change"
      rule.

## Open questions

- Should the issue template auto-tag with labels (`scraper-broken`,
  `enhancement`, `help wanted`)? Yes if GitHub lets us set labels via
  template front-matter — it does.
- Code-of-conduct required or not? Lean: not required for a project
  of this size, but add it when the first non-Benoit contributor
  shows up.
