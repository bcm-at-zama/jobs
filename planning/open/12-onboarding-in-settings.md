# TICKET-12 — Re-run onboarding from the Settings modal

- **status:** open
- **priority:** P2
- **effort:** M
- **created:** 2026-10-05
- **owner:** unassigned

## Context

The HTML-based onboarding wizard (TICKET-01) runs standalone via
`make onboarding` — fine for the first install, but awkward once the
user already has a board open and realises they want to add / remove
companies, re-tune the title blacklist, etc.

The `⚙` Settings modal is the natural place to launch a re-onboarding
flow: user is already in the UI, has their state loaded, just wants to
tweak the config without going back to a terminal.

## Scope

**In:**

- Add an "Edit sources & filters…" button inside the `⚙` Settings modal.
- Clicking it opens the same onboarding dialogs the standalone wizard
  uses (same groups, same per-group `a` / `n` / individual flip UX).
- Pre-populates the dialogs from the current `data/user_config.py`
  (companies currently in `SOURCES` are pre-checked, HIGHLIGHTS /
  BLACKLIST lists pre-filled).
- On Save: POSTs the new state to the server (new endpoint, e.g.
  `/write-user-config`), which writes `data/user_config.py` + a
  timestamped backup, then triggers a page reload so the user sees
  the result immediately.

**Out of scope:**

- Changing the directory layout.
- Multi-user scenarios.
- Live preview of fetched jobs during editing.

## Dependencies

- TICKET-01 — standalone HTML wizard must ship first (it defines the
  dialog markup + the write-user-config server endpoint we can reuse).

## Acceptance criteria

- [ ] `⚙` modal has a visible "Edit sources & filters…" button.
- [ ] Clicking it opens the onboarding dialog with the current config
      pre-populated (SOURCES companies ticked, keywords/blacklists
      pre-filled).
- [ ] Saving writes `data/user_config.py` + a `.bak.<timestamp>` copy.
- [ ] After save, the page reloads so the next `make run` state uses
      the new config (or a lightweight "re-fetch with new filters"
      prompt).
- [ ] `make test` stays green.
