# TICKET-10 — Launch plan (Show HN + GitHub polish)

- **status:** open
- **priority:** P2
- **effort:** M
- **created:** 2026-10-03
- **owner:** unassigned
- **blocked by:** 01, 02, 04, 05, 07, 08, 09

## Context

Shipping to GitHub is not launching. 140+ repos tagged `job-scraper`
exist already; without a deliberate launch, this one is noise. One
good Show HN or r/selfhosted post with the right framing can get 500
stars + a few recurring contributors on day one. A bad one gets 3
stars and nothing.

This ticket is the "merchandising" wrapper around everything the
other tickets produce.

## Scope

**In:**

- **GitHub repo polish:**
  - 1-line repo description that explains the value in 15 words.
    Draft: *"Self-hosted job-search aggregator for senior
    engineers: 100+ company boards, LLM-scored, locally-tracked."*
  - Topics: `self-hosted`, `job-search`, `job-aggregator`,
    `job-scraper`, `python`, `playwright`, `ats`, `greenhouse`,
    `ashby`, `workday`, `llm`.
  - Pinned README section visible on repo home.
- **Show HN draft** (`planning/launch/show-hn.md`):
  - Title: concrete, specific, not "I built X". Draft:
    *"Show HN: Self-hosted job aggregator with LLM-scored fit per
    posting (100+ ATS boards)"*
  - Body: 150-250 words, personal voice. Covers (a) why you built
    it, (b) what makes it different from JobSpy / JobSentinel,
    (c) scope note (self-hosted on your IP, not SaaS), (d) link
    to screenshots, (e) explicit "don't use this to spam
    recruiters" ask.
  - First comment (self-reply) prepared with install one-liner.
- **r/selfhosted draft** (`planning/launch/reddit-selfhosted.md`):
  - Different framing from HN (less "I built", more "here's a tool
    that solves X"). Rules forbid self-promo without context.
- **Awesome-selfhosted PR** (`planning/launch/awesome-selfhosted.md`):
  - One-line entry per their contributing guide.
- **Pre-staged replies** to the predictable questions:
  - "What about JobSpy?" → different problem space (consumer boards
    vs ATS, no state, no scoring).
  - "Legal risk?" → scope note, hiQ v. LinkedIn, your IP only.
  - "Why self-hosted and not SaaS?" → see business/analysis.md
    section on hosting hurdles.
  - "Can I add [company]?" → see CONTRIBUTING.md.
- A `launch-checklist.md` — go/no-go for the day:
  - All tests green
  - Dockerfile builds on fresh Mac + fresh Ubuntu
  - Screenshots up to date
  - README reads well on GitHub (not just locally)
  - Scope + legal section visible above the fold
  - CONTRIBUTING.md complete
  - LICENSE present
  - Repo description + topics set

**Out of scope:**

- Paid ads / sponsored posts.
- Twitter / LinkedIn personal account posting (that's up to Benoit).
- Mailing lists.
- Press outreach.

## Design notes

- HN rewards specificity and personal story over marketing. "Hey
  there, I'm X, I was job hunting, got tired of Y, built Z" is the
  format that works.
- Timing: aim for a Monday or Tuesday morning US-east time
  (10:00-11:00 EST). HN front-page staying power is highest then.
- Don't launch on a day you can't babysit the comments. First 2-3
  hours of HN are make-or-break; you need to be replying.

## Acceptance criteria

- [ ] GitHub repo has the description + topics set.
- [ ] `planning/launch/show-hn.md` exists, < 300 words.
- [ ] `planning/launch/reddit-selfhosted.md` exists.
- [ ] `planning/launch/awesome-selfhosted.md` exists.
- [ ] `planning/launch/launch-checklist.md` exists and every item is
      checkable (not "do a good launch", but "Dockerfile builds on
      Ubuntu 24.04 LTS").
- [ ] A dress-rehearsal: post the Show HN body as a GitHub issue in a
      private repo first to catch typos.

## Open questions

- When? Likely after TICKETS 01-09 all close. Don't launch until all
  the muzzle-flashes line up.
- What persona? Benoit's own name (established engineer, lends
  credibility) vs. anonymous (safer if the project ends up
  controversial). Lean: his own name.
