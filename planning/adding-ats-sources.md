# Adding a new ATS-hosted company (3 minutes)

Supported fetcher kinds (set via `kind:` in a SOURCES entry in `config.py`):

| kind              | ATS                 | First usage                        |
|-------------------|---------------------|------------------------------------|
| `workday`         | Workday             | Sonos, Dolby, Adobe, PayPal, …     |
| `bamboohr`        | BambooHR            | Softube                            |
| `pinpoint`        | Pinpoint HQ         | inMusic Brands                     |
| `umantis`         | Umantis             | Yamaha corp                        |
| `successfactors`  | SuccessFactors      | Sennheiser, SAP                    |
| `greenhouse`      | Greenhouse          | many                               |
| `lever`           | Lever               | Palantir                           |
| `ashby`           | Ashby               | many                               |
| `phenom`          | Phenom              | NVIDIA, Qualcomm, Cisco            |
| `eightfold`       | Eightfold           | Netflix                            |
| `pw`              | Playwright fallback | sites without a known ATS          |

## Workday — step-by-step

1. **Find the Workday URL.** It looks like:
   ```
   https://<tenant>.wd1.myworkdayjobs.com/<BoardName>
   ```
   Some tenants are `wd3`, `wd5`, etc. (the number is the Workday
   data-center). Follow where the company's "Careers" link redirects.

2. **Add to `config.py` → `SOURCES`:**
   ```python
   {"name": "Adobe", "kind": "workday", "slug": "adobe",
    "queries": ["security", "cryptography", "CTO", "VP"],
    "board": "https://adobe.wd5.myworkdayjobs.com/external_experienced"},
   ```

3. **Add to `COMPANY_INFO`** with a short blurb + headcount + revenue.

4. **Add to `GROUP_OF`** (`"Big Tech"`, `"Security Companies"`, etc.).

5. **Verify:**
   ```
   python3 jobs.py --clear-cache list --skip-llm --only Adobe
   ```

## BambooHR / Pinpoint HQ / Umantis / SuccessFactors

Same 5-step recipe. The `slug` is the subdomain / tenant name found in
the board URL. Concrete examples live in `config.py` under:

- `Softube` (BambooHR)
- `inMusic Brands` (Pinpoint)
- `Yamaha corp` (Umantis)
- `Sonos` (Workday)
- `Sennheiser` (SuccessFactors)

## Common gotchas

- **URL ends in `/en-US/`** — Workday handles this transparently, but
  the `board` field should NOT include the locale suffix; the fetcher
  will append it when needed.
- **404 after a few runs** — Workable tenants sometimes rotate their
  board IDs. Re-probe when you see a flaky source.
- **Big-tech leveling grid** — if the company publishes IC levels (L4,
  E5, etc.), add a `SENIORITY_XP` entry so the UI shows accurate XP
  badges instead of the generic fallback (~5 y Senior / ~8 y Staff /
  ~12 y+ Principal).
