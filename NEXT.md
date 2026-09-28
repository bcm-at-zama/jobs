# Session summary — 2026-09-28

## What's ready for you

### 5 new ATS fetchers (in jobs.py)

Each is now selectable via `kind: "…"` in a SOURCES entry:

| kind | fetcher | first usage |
|---|---|---|
| `workday` | Sonos, Dolby (Playwright fallback), TODO: 20+ others | `fetch_workday` |
| `bamboohr` | Softube | `fetch_bamboohr` |
| `pinpoint` | inMusic Brands (= Native Instruments + Moog + many more) | `fetch_pinpoint` |
| `umantis` | Yamaha corp | `fetch_umantis` |
| `successfactors` | Sennheiser | `fetch_successfactors` |

**Workday is the big unlock** — see TODO.txt for the 20+ big-tech companies now reachable.

### 23 new Music Companies in config.py

Grouped in "Music Companies":

- **ATS-clean fetch**: Softube (BambooHR), inMusic Brands (Pinpoint), Yamaha (Umantis), Sonos (Workday), Sennheiser (SuccessFactors), Bose (Phenom — same as Microsoft/NVIDIA)
- **Playwright best-effort**: Focusrite, Roland, Korg, Marshall, Ibanez, Gibson, PRS Guitars, Boss, Fractal Audio, Seymour Duncan, Yamaha Guitar Group, PreSonus, Elektron, Dolby, MOTU, iZotope, Antares

All have a `COMPANY_INFO` blurb (3-4 sentences) + headcount + revenue estimates from public 2024–2025 data.

### Skipped

- Indeed-only sites (blocked): Ernie Ball, Music Tribe/Behringer, DiMarzio
- URL not found: Lâg, Nord Keyboards, Peavey
- User declined: Taylor Guitars, Kemper, SSL, Positive Grid

Full details in TODO.txt "Music wave 5 skipped / hard-to-scrape".

## What you should do first when you're back

1. **Verify Wave 5 fetchers actually work** (container is Cloudflare-blocked, so I couldn't test end-to-end):
   ```
   .venv-macos/bin/python debug/test_new_fetchers.py
   ```
   This tries every Wave 5 source and prints `→ N matched jobs` per source. Anything at 0 either has 0 matching jobs (fine, remove queries) or is broken (I'll debug).

2. **Full refresh** to see the new companies in the UI:
   ```
   python3 jobs.py --clear-cache list --skip-llm
   ```
   Expect ~60-80s. Music Companies section will grow from ~13 to ~36 sources.

3. **Adopt Workday for GAFAM-adjacent** — TODO.txt has a 3-minute recipe. Add Amazon, Adobe, Salesforce, Intel, Netflix, Palantir, Cisco, Zoom (etc.) using the workday kind. Each is a 4-line config entry now.

## Known risks / caveats

- **Playwright scrapers use best-guess `link_re`** — the sites without a known ATS (16 of the 23) rely on regex patterns I guessed from their URL structure. Some may return 0 jobs because the actual HTML uses a different anchor pattern. When that happens, the debug HTML dump lands in `debug/debug-<slug>-1.html` — send me the file and I'll fix the regex.
- **Sennheiser / SuccessFactors** — this ATS is complex and my extractor is a best-effort HTML scrape. If it returns 0 jobs, we may need Playwright-based rendering.
- **iZotope** — post-Soundwide merger, they might share the Native Instruments careers portal (I have both configured).

## Files changed

- `jobs.py` — 5 new fetchers added, all registered in FETCHERS
- `config.py` — 23 new SOURCES entries + 23 new COMPANY_INFO entries + 23 new GROUP_OF mappings
- `TODO.txt` — reflect Workday unlock, note skipped music brands
- `debug/test_new_fetchers.py` — new helper for Mac-side verification
- `debug/music_url_probe.sh`, `debug/ats_api_probe.sh` — Cloudflare-blocked in container, kept for reference
- `NEXT.md` — this file
