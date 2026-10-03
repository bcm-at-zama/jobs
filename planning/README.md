# planning/

Lightweight ticket tracker. One file per ticket, Markdown, no tooling.

## Layout

```
planning/
├── open/      ← work to do (sorted by priority)
├── closed/    ← done or abandoned (kept for history)
└── README.md  ← this file
```

**Opening a ticket** → create a file in `open/`.
**Closing a ticket** → `git mv open/XX-slug.md closed/`. That's it.
**Reopening** → move it back.

## Naming

```
NN-short-slug.md
```

- `NN` = two-digit sequence number (zero-padded), **unique across both
  directories**. Grep both when picking the next one.
- `slug` = short-and-descriptive (e.g. `onboarding-wizard`,
  `sort-by-claude-score`).

## Frontmatter (optional but useful)

Each ticket starts with a block of key-value lines:

```markdown
# TICKET-NN — Human-readable title

- **status:** open · in-progress · blocked · closed
- **priority:** P0 (ship-blocking) · P1 (soon) · P2 (nice-to-have)
- **effort:** S (<1h) · M (1-4h) · L (4h+)
- **created:** YYYY-MM-DD
- **owner:** Benoit / Claude / unassigned
```

Then free-form sections. The template below is a suggestion — adapt per
ticket.

### Suggested sections

- **Context** — why does this matter, which pain point does it address
- **Scope** — what's in, what's explicitly out
- **Acceptance criteria** — a bullet list that any reader can
  tick off; "done" means every bullet is true
- **Notes** — implementation hints, open questions, references

## Workflow conventions

- Tickets are atomic — if it needs 3 PRs, it's 3 tickets.
- Use `git mv` to close, not deletion. The history + original filename
  stay intact.
- When closing, append a `## Resolution` section with 1-2 sentences
  on what was done and the commit SHA.
- Blocked tickets stay in `open/` with `status: blocked` and a note
  explaining what unblocks them.
