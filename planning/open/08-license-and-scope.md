# TICKET-08 — LICENSE + "self-hosted on your own IP" scope note

- **status:** open
- **priority:** P1
- **effort:** S
- **created:** 2026-10-03
- **owner:** unassigned

## Context

Two things missing before any OSS launch:

1. **No LICENSE file.** GitHub shows "no license", which legally means
   "all rights reserved" — nobody can safely use, modify, or
   redistribute. This blocks adoption, even by users who'd happily
   contribute back.

2. **No scope statement.** Running this engine from Benoit's
   residential IP is defensible under hiQ v. LinkedIn (public data,
   personal use). Running it on a cloud VPS that scrapes LinkedIn on
   behalf of multiple users is a different legal position with
   different risks. Users must know which flavour they're deploying.

## Scope

**In:**

- Add a `LICENSE` file at the repo root. Candidate licenses:
  - **MIT** — maximum permissiveness, lets any downstream fork
    without obligation. Low friction.
  - **AGPL-3.0** — any derivative service exposed over the network
    must open-source its changes. Protects against a company
    forking → closed SaaS.
  - **PolyForm Non-Commercial** — permits non-commercial use;
    requires a paid license for commercial deployment. Niche.
  - Recommendation: **MIT** for maximum community growth. If a
    specific company tries to monetize it later, the author can
    always relicense future contributions under something stricter.
- A README section titled "Scope and legal" (or similar) stating:
  - This is designed for **self-hosted use on your own machine**
    with your own residential IP.
  - Scraping LinkedIn / Google / Apple / Workday from your laptop
    for personal job-hunting is defensible (hiQ v. LinkedIn,
    2022). Public VPS deployment at scale is NOT, and is explicitly
    unsupported.
  - The author provides no warranty against anti-bot IP bans, HTML
    schema changes, or Terms-of-Service enforcement.
- A `SECURITY.md` with a basic responsible disclosure address.

**Out of scope:**

- Legal review by a real lawyer — the scope note is best-effort
  wording derived from hiQ and public ToS language, not legal advice.
- CLA for contributors (overkill).
- Changing the license later — committed decisions stay.

## Acceptance criteria

- [ ] `LICENSE` exists at the repo root with the chosen license text.
- [ ] GitHub repo page shows the correct license badge.
- [ ] README has a "Scope and legal" section visible above the fold
      (before Install).
- [ ] `SECURITY.md` exists with at least a one-line contact.
- [ ] The scope note explicitly names LinkedIn, Google, Apple,
      Workday as "do not deploy on a public VPS".

## Open questions

- MIT vs AGPL — product decision. AGPL stronger moat if someone tries
  to SaaS this; MIT easier to adopt. Benoit's call.
- Should the UI itself show a one-line "self-hosted on your own IP"
  banner on first run, dismissable? Would catch users who skipped the
  README. Lean: yes, dismissable, text link to README's scope section.
