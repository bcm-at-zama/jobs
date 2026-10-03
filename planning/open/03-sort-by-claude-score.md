# TICKET-03 — Sort visible jobs by Claude fit score

- **status:** open
- **priority:** P2
- **effort:** S
- **created:** 2026-10-03
- **owner:** unassigned

## Context

Once the user clicks the **C** button and pastes Claude's response, every
visible job gets a `Score: N/10` badge. Today the ordering of jobs inside
each company section is: liked → score (where "score" is the LLM salary
extractor, not Claude's fit score) → seniority → title. The Claude fit
score is shown but not used for sorting, so the user has to scan every
badge manually to find the 9/10 roles. For sections with 20+ visible
jobs this defeats the purpose of scoring.

## Scope

**In:**

- A new toolbar toggle: **"Sort by Claude score"** (checkbox).
- When ON:
  - Within each section, jobs sort descending by Claude fit score.
  - Jobs without a Claude score sort last (keeping current secondary
    ordering within the no-score bucket).
  - Ties on score fall back to the existing sort order (title asc).
- When OFF: the current sort order applies (today's behavior).
- The toggle state persists in `localStorage` under the same filter
  state key as the other toggles.
- Changing the toggle re-sorts without a full page reload (DOM
  reordering only).

**Out of scope:**

- Sorting across sections (keeping company grouping intact).
- Changing the Ollama score sort (that's a different number).
- Numerical display changes (badge stays `Score: N/10`).

## Design notes

- Score data is already in `localStorage` under `CLAUDE_FIT_KEY` keyed
  by URL. No new fetch needed.
- Re-sort implementation: `applyFilters` already walks every `li.job` to
  decide visibility. Extend it to also sort each `ul[data-section]`
  when the toggle is on. Use `ul.appendChild(li)` in sorted order —
  cheap even for 100+ jobs.
- Edge case: liked / to-apply / applied rows currently float to the top
  of their section (`moveLiToTop`). Decision: when sort-by-score is on,
  **state still wins over score** (liked/applied stay on top). The user
  cares more about where they are in the process than about score.

## Acceptance criteria

- [ ] Checkbox labeled "Sort by Claude score" visible in the toolbar
      near the other show/hide filter checkboxes.
- [ ] Toggling ON re-sorts every visible section so highest-score jobs
      appear first; no-score jobs appear last.
- [ ] Toggling OFF restores the baseline sort within 1 frame (no reload).
- [ ] State machine still wins: liked/applied rows stay at the top of
      their section regardless of score.
- [ ] Toggle state persists across refreshes via `localStorage`.
- [ ] A test in `tests/test_locations.py` or a new `tests/test_sort.py`
      asserts the sort key function returns the expected ordering for
      a small fixture.
- [ ] `make test` stays green.

## Open questions

- Should the toggle default to ON once the user has scored at least one
  job? Would surface the fit immediately. Risk: silent re-ordering on
  first paste could confuse users expecting the previous layout.
- Should sections with ZERO Claude scores hide the toggle, or just no-op?
  Lean toward "visible but no-op" so the UI is predictable.
