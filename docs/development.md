# Development & contributor guide

Everything beyond "I just want to use it". If you landed here from the
README, this is where the geeky bits live.

---

## Adding a company

Open `data/user_config.py` and add a line to `SOURCES`:

```python
{"name": "Anthropic", "kind": "greenhouse", "slug": "anthropic",
 "queries": ["security", "research"]},
```

- `kind` is one of `greenhouse`, `lever`, `ashby`, `workday`, `phenom`,
  `bamboohr`, `pinpoint`, `umantis`, `successfactors`, `eightfold`,
  `smartrecruiters`, or `pw` for the Playwright fallback.
- `slug` is the ATS board identifier (the part after the ATS domain).
- `queries` filters titles client-side. Leave `[]` to see everything;
  tighten later.

Full step-by-step per ATS (how to find the slug, the Workday tenant,
the board ID, etc.):
[`planning/adding-ats-sources.md`](../planning/adding-ats-sources.md).

---

## Project layout

| Directory    | Purpose                                                   |
|--------------|-----------------------------------------------------------|
| `src/`       | Application source. Open-sourceable, zero personal data.  |
| `tests/`     | Test suite (stdlib `unittest`, no deps, ~70 tests).       |
| `data/`      | **Your** personal data: config, profile, state, caches.   |
| `debug/`     | Scraper probes, HTML dumps, exploration scripts.          |
| `planning/`  | Tickets (`open/` + `closed/`), ATS recipes, workflow docs.|
| `knowledge/` | Freeform notes and research.                              |
| `script/`    | Shell scripts (push, etc.) invoked by `make`.             |
| `docs/`      | User-facing documentation (this file, screenshots).       |

---

## Development

```bash
make test       # ~70 tests, <100ms, stdlib unittest
make commit     # git add + commit + push (via script/push.sh)
make help       # list every target
```

House rules — tests after every edit, no personal data in `src/`,
verify scrapers against debug dumps — live in
[`CLAUDE.md`](../CLAUDE.md).

---

## Contributing

Tickets in [`planning/open/`](../planning/open). PRs welcome — see
`CONTRIBUTING.md` when it exists (tracked as
[TICKET-07](../planning/open/07-contributing-guide.md)).
