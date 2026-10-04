# TICKET-09 — Screenshots + demo asset for README / launch

- **status:** open
- **priority:** P2
- **effort:** S
- **created:** 2026-10-03
- **owner:** unassigned

## Context

The UI is the single most compelling thing about this project. A good
screenshot sells it in 2 seconds; a code snippet from `jobs.py` sells
it to nobody. The README install guide (TICKET-02) and the launch
plan (TICKET-10) both block on having real visuals.

## Scope

**In:**

- At least 4 PNG screenshots stored under `docs/screenshots/`:
  1. **Main view** — a company section with 5-10 visible jobs, Claude
     score badges, seniority badges, salary badges, one Liked row at
     top. Chosen so a reader *immediately* sees "this is job hunting
     with a brain".
  2. **Filters sidebar** — the Show Liked / Rejected / Applied
     toggles, seniority filter checkboxes, locations picker expanded.
  3. **Claude paste bar** — the C-button triggered flow with the
     bottom bar visible, ready to accept pasted scores.
  4. **Spontaneous application** — the ✉ row at the top of a section
     with no visible jobs matching current filters.
- A short screencast (< 60s, mp4 or gif) walking through:
  - Open the HTML.
  - Click C → paste Claude's response → scores appear.
  - Click `?` on a job → opens Claude.ai.
  - Reject a job with ×, undo with Cmd-Z.
- README links to screenshots via relative paths (`docs/screenshots/main.png`).
- Full-size images; GitHub renders them inline when embedded via
  `![alt](path)`.

**Out of scope:**

- A product-marketing landing page.
- Dark/light mode variants of the screenshots (the UI is dark; ship
  that).
- Localized versions.

## Design notes

- Capture at 2x retina so GitHub's downscaling looks sharp.
- Use realistic job titles (not "Lorem Ipsum"); OK to use the actual
  current fetch state at the time of capture.
- Scrub any obviously-private data (API keys in URLs if any, personal
  email addresses in Liked notes).
- Screen recording: QuickTime on Mac is fine. Convert to webm/gif via
  `ffmpeg` for GitHub autoplay (gif too big; webm not supported in
  README on all browsers — mp4 safest).

## Acceptance criteria

- [ ] 4 PNG screenshots exist under `docs/screenshots/`.
- [ ] Screencast (mp4 or gif) exists at `docs/screenshots/demo.mp4`
      or `.gif`, < 10 MB.
- [ ] README references them with relative paths and they render
      inline on GitHub.
- [ ] All screenshots scrubbed of private data (verified by a second
      pair of eyes).

## Open questions

- Who takes the screencast? Benoit on his Mac is easiest. Could also
  be scripted via Playwright but that's overkill.
- Light-mode variants? Current UI is dark-only; adding a light mode
  is a separate ticket.
