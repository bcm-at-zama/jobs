# CLAUDE.md — house rules for this repo

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

## Related principles

- Prefer editing existing scrapers over cloning new ones — if a slug is
  wrong, that's a one-line fix, not a rewrite.
- When adding a new board, always start with `queries: []` so we see every
  posting; the user narrows the queries once we've confirmed the scraper
  works end to end.

## When you need something from me — ask explicitly, and remind

- When you need an input from me (a URL, a probe output, a decision between
  two options, a confirmation before a destructive action), state it
  explicitly as a question and stop.
- If I move on to another topic without answering, you MUST re-ask on your
  next turn. Do not silently drop the question and do not proceed with a
  guess.
- Rationale: it is easy for me to miss a question buried at the end of a
  long paragraph. Losing the question means losing the correct fix.
