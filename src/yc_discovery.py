"""Y Combinator company discovery via api.ycombinator.com + per-company
ATS detection.

What this module does:
  - fetch_candidates(tags, industries) → list[dict] of YC companies
    matching the given tag/industry filters, deduped by slug. One GET
    per page × filter; no auth needed.
  - detect_ats(website) → {"kind": ..., "slug": ..., "jobs": N,
    "board": ...} by probing the company's own careers page for links
    to known ATS platforms (greenhouse / lever / ashby / workable /
    workday), then validating each candidate against the ATS's own
    public API so false positives (incidental links on a careers page)
    get rejected.
  - cache_candidates(path, data) / load_candidates(path): persist to
    data/yc_discovered.json so a later refresh can reuse the list.

Why YC's public API, not Algolia:
  - api.ycombinator.com/v0.1/companies is a plain JSON endpoint that
    accepts server-side `?tags=X` and `?industries=Y` filters.
  - No API key, no WAF, no auth — a one-line urllib call.
  - Reverse-engineered 2026-10-07 via debug/probe_yc_filter_and_jobs.py.

Why ATS detection, not WAAS scraping:
  - workatastartup.com is pure client-side rendered — HTML has zero
    job data without login (confirmed via debug/probe_waas_html_parse.py).
  - Hitting each company's native ATS (greenhouse / ashby / …) gives
    structured data via a public JSON API, matching what our existing
    fetchers consume.
  - Companies without a public ATS (JS-rendered careers pages,
    hiring-via-network-only) are skipped — a future round can add a
    Playwright-based detection fallback.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


_YC_API = "https://api.ycombinator.com/v0.1/companies"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
       "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")


# =============================================================================
# Candidate pool — YC companies API
# =============================================================================

# Default sector filters. Mirror the WTJ discovery defaults (Cybersecurity +
# AI/ML). Each entry is "<param>=<value>", where <param> is `tags` or
# `industries` (both are server-side honored; others silently ignored).
# Companies get UNIONed across filters and deduped by slug.
DEFAULT_YC_FILTERS = [
    "tags=Cybersecurity",
    "industries=Security",
    "tags=Artificial%20Intelligence",
    "tags=AI",
    "tags=Machine%20Learning",
]

# Quality filter applied AFTER the server-side tag/industry pull. The
# raw pool (Cybersecurity + AI/ML) is ~1600 companies, most of which are
# 1-3 person pre-seed companies that don't have a public ATS at all.
# We keep companies that are EITHER established (teamSize >= floor)
# OR fresh out of recent batches (meaningful hiring signal even at
# small team sizes). Logical OR — a company qualifies if it meets EITHER.
MIN_TEAM_SIZE = 20
RECENT_BATCHES = ["F26", "S26", "W26"]


def _get(url: str, timeout: int = 12) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json, text/html, */*;q=0.5",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def _fetch_one_filter(param_val: str, max_pages: int = 200) -> list:
    """Walk every page for a single `?param=value` filter."""
    out = []
    page = 1
    while page <= max_pages:
        status, body = _get(f"{_YC_API}?page={page}&{param_val}")
        if status != 200 or not body:
            break
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            break
        companies = data.get("companies") or []
        if not companies:
            break
        for c in companies:
            out.append({
                "slug": c.get("slug") or "",
                "name": c.get("name") or "",
                "website": c.get("website") or "",
                "batch": c.get("batch") or "",
                "industries": c.get("industries") or [],
                "tags": c.get("tags") or [],
                "status": c.get("status") or "",
                "teamSize": c.get("teamSize"),
                "oneLiner": c.get("oneLiner") or "",
            })
        total_pages = data.get("totalPages") or 1
        if page >= total_pages:
            break
        page += 1
    return out


def apply_quality_filter(candidates: list,
                         min_team_size: int = MIN_TEAM_SIZE,
                         recent_batches: list = None) -> list:
    """Keep companies that are established (teamSize >= min_team_size)
    OR in one of the recent batches. Both knobs are passed through from
    fetch_candidates(); this is a pure function so unit tests can hit
    it without a network call."""
    if recent_batches is None:
        recent_batches = RECENT_BATCHES
    batches_set = set(recent_batches or [])
    return [
        c for c in candidates
        if (c.get("teamSize") or 0) >= min_team_size
        or (c.get("batch") or "") in batches_set
    ]


def fetch_candidates(filters: list = None,
                     min_team_size: int = MIN_TEAM_SIZE,
                     recent_batches: list = None) -> list:
    """UNION of YC companies matching any of the given filters, deduped
    by slug, then narrowed to Active companies with a website that are
    EITHER established (teamSize >= min_team_size) OR in a recent batch.

    Passing min_team_size=0 and recent_batches=[] disables the quality
    filter (returns the full tagged pool)."""
    filters = filters if filters is not None else DEFAULT_YC_FILTERS
    by_slug = {}
    for f in filters:
        for c in _fetch_one_filter(f):
            if c["slug"] and c["slug"] not in by_slug:
                by_slug[c["slug"]] = c
    pool = [
        c for c in by_slug.values()
        if (c.get("status") or "Active") == "Active"
        and (c.get("website") or "").startswith("http")
    ]
    out = apply_quality_filter(pool, min_team_size, recent_batches)
    # Sort by teamSize desc so bigger (more likely hiring) go first.
    out.sort(key=lambda c: -(c.get("teamSize") or 0))
    return out


# =============================================================================
# ATS detection — scan a company's careers HTML for links to known ATSes
# =============================================================================

_ATS_PATTERNS = [
    # Greenhouse: boards-api.greenhouse.io/v1/boards/<slug>/jobs
    ("greenhouse", re.compile(
        r'(?:job-boards|boards)\.greenhouse\.io/'
        r'(?:embed/job_board\?for=)?([a-z0-9][a-z0-9_-]+)',
        re.IGNORECASE)),
    # Lever: jobs.lever.co/<slug>
    ("lever", re.compile(
        r'jobs\.lever\.co/([a-z0-9][a-z0-9_-]+)', re.IGNORECASE)),
    # Ashby — both shapes, each anchored on ".ashbyhq.com" to avoid
    # false positives against unrelated protocol-relative URLs (prior
    # regex captured //ajax.googleapis.com → bogus "ashby:ajax").
    ("ashby", re.compile(
        r'jobs\.ashbyhq\.com/([a-z0-9][a-z0-9_-]+)', re.IGNORECASE)),
    ("ashby", re.compile(
        r'(?:https?:)?//([a-z0-9][a-z0-9_-]+)\.ashbyhq\.com', re.IGNORECASE)),
    # Workable: apply.workable.com/<slug>
    ("workable", re.compile(
        r'apply\.workable\.com/([a-z0-9][a-z0-9_-]+)', re.IGNORECASE)),
    # Workday: <tenant>.wdN.myworkdayjobs.com/<site>. Two-group capture;
    # join with "|" so a single composite string carries both pieces
    # through to the validator / catalog-writer.
    ("workday", re.compile(
        r'(?:https?://)?([a-z0-9-]+\.wd[0-9]+)\.myworkdayjobs\.com/'
        r'(?:[a-z-]+/)?([A-Za-z0-9_-]+)', re.IGNORECASE)),
]

_IGNORE_SLUGS = {
    "www", "jobs", "boards", "embed", "api", "assets", "static", "cdn",
    "en-us", "en-gb", "fr-fr",
}

_CAREERS_PATHS = ["/careers", "/jobs", "/about/careers",
                  "/company/careers", "/"]


def _detect_from_html(html: str) -> list:
    """Return deduped (kind, slug) tuples found in the HTML."""
    hits = []
    seen = set()
    for kind, pat in _ATS_PATTERNS:
        for m in pat.finditer(html):
            if kind == "workday":
                tenant_pod = (m.group(1) or "").lower()
                site = m.group(2) or ""
                if not tenant_pod or not site:
                    continue
                if site.lower() in _IGNORE_SLUGS:
                    continue
                slug = f"{tenant_pod}|{site}"
            else:
                slug = (m.group(1) or "").lower().strip("-_")
            if not slug or slug in _IGNORE_SLUGS:
                continue
            key = (kind, slug)
            if key in seen:
                continue
            seen.add(key)
            hits.append(key)
    return hits


def _validate_ats(kind: str, slug: str) -> int | None:
    """Hit the ATS's own public API to confirm the slug returns jobs.
    Returns the job count on success, None on failure."""
    if kind == "workday":
        try:
            tenant_pod, site = slug.split("|", 1)
        except ValueError:
            return None
        tenant = tenant_pod.split(".")[0]
        url = (f"https://{tenant_pod}.myworkdayjobs.com/wday/cxs/"
               f"{tenant}/{site}/jobs")
        body_bytes = json.dumps({
            "appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "",
        }).encode()
        req = urllib.request.Request(url, data=body_bytes, method="POST",
                                     headers={
                                         "User-Agent": _UA,
                                         "Content-Type": "application/json",
                                         "Accept": "application/json",
                                     })
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read().decode(errors="replace")
            data = json.loads(raw)
        except Exception:
            return None
        return len(data.get("jobPostings") or [])

    url = {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{slug}?limit=1",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "workable": f"https://apply.workable.com/api/v3/accounts/{slug}/jobs",
    }.get(kind)
    if not url:
        return None
    status, body = _get(url, timeout=10)
    if status != 200 or not body:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if kind == "greenhouse":
        jobs = data.get("jobs") or []
    elif kind == "lever":
        jobs = data if isinstance(data, list) else []
    elif kind == "ashby":
        jobs = (data.get("jobs")
                or (data.get("apiKey") and data.get("jobBoard", {}).get("jobs"))
                or [])
    elif kind == "workable":
        jobs = data.get("results") or data.get("jobs") or []
    else:
        jobs = []
    return len(jobs)


def _board_url(kind: str, slug: str) -> str:
    """Public URL for a given ATS slug — matches what src/jobs.py's
    board_url_for() would compute, so the catalog entry's `board` is
    the same shape users already see for other sources."""
    if kind == "workday":
        tenant_pod, site = slug.split("|", 1)
        return f"https://{tenant_pod}.myworkdayjobs.com/{site}"
    return {
        "greenhouse": f"https://job-boards.greenhouse.io/{slug}",
        "lever": f"https://jobs.lever.co/{slug}",
        "ashby": f"https://jobs.ashbyhq.com/{slug}",
        "workable": f"https://apply.workable.com/{slug}",
    }.get(kind, "")


def detect_ats(website: str) -> dict | None:
    """Probe a company's careers page, detect ATS, validate it.
    Returns {kind, slug, jobs, board, careers_url} on success, else None."""
    if not website:
        return None
    m = re.match(r'^(https?://[^/]+)', website)
    if not m:
        return None
    origin = m.group(1)
    tried = set()
    for path in _CAREERS_PATHS:
        url = origin + path
        if url in tried:
            continue
        tried.add(url)
        status, body = _get(url, timeout=10)
        if status != 200 or not body:
            continue
        for kind, slug in _detect_from_html(body):
            n = _validate_ats(kind, slug)
            if n is not None and n >= 1:
                return {
                    "kind": kind,
                    "slug": slug,
                    "jobs": n,
                    "board": _board_url(kind, slug),
                    "careers_url": url,
                }
    return None


def catalog_slug_for(kind: str, slug: str) -> str:
    """What the catalog entry's `slug` field should be. For most ATSes
    it's the same string; Workday uses the tenant as slug since the
    full URL carries the pod + site info."""
    if kind == "workday":
        tenant_pod, _ = slug.split("|", 1)
        return tenant_pod.split(".")[0]
    return slug


# =============================================================================
# Cache helpers
# =============================================================================

def cache_candidates(path: str, candidates: list) -> None:
    """Atomic write — mid-crash never leaves a half-file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": int(time.time()),
            "candidates": candidates,
        }, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_candidates(path: str) -> dict:
    """Returns {} on missing/malformed cache."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
