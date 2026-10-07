"""WTJ company discovery via Algolia.

Welcome to the Jungle hosts a public Algolia-powered company directory
with ~4000 entries. We call the Algolia multi-queries endpoint directly
with the public search key extracted from WTJ's JS bundle (reverse-
engineered on 2026-10-07 — see planning/open/13-wtj-discovery.md,
superseded by this module).

What this module does:
  - fetch_candidates(sector_filters) → list[dict] of {slug, name,
    description, sectors, cover_url, website_url}. One POST per call,
    paginated internally.
  - cache_candidates(path, data) / load_candidates(path): persist to
    data/wttj_discovered.json so the main board can read it at render
    time (shown in the Edit-companies modal as "Discovered on WTJ").

Why Algolia directly, not Playwright:
  - WTJ's /fr/companies* pages return a CloudFront 403 to headless
    chromium (confirmed via debug/probe_wttj_live_render.py).
  - WTJ's /fr/jobs* pages return a Next.js shell with no job data —
    the SPA hydrates via XHR to Algolia.
  - plain urllib → Algolia bypasses both the WAF and the SPA. One
    tiny POST → structured JSON. No browser needed, no fragility.

Risk: WTJ redeploys and the public API key / index name rotates.
Mitigation: the key is public-by-design (it's embedded in every
visitor's JS bundle), so rotation is rare. If it happens, re-run
debug/probe_wttj_xhr_capture.py to grab the fresh key.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


_APP_ID = "CSEKHVMS53"
_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
_INDEX = "wk_cms_organizations_production"
# The browser-side Algolia client sends the agent as a URL-encoded
# query param (not a header). Algolia's edge checks this to classify
# the client — omitting it gets us 403'd from datacenter IPs. The
# matching Origin / Referer below also helps when Algolia has HTTP-
# referer-based restrictions on the key.
_ALGOLIA_AGENT = (
    "Algolia%20for%20JavaScript%20(4.20.0)"
    "%3B%20Browser"
    "%3B%20JS%20Helper%20(3.14.0)"
    "%3B%20react%20(18.2.0)"
    "%3B%20react-instantsearch%20(6.40.4)"
)
_ENDPOINT = (
    f"https://{_APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"
    f"?x-algolia-agent={_ALGOLIA_AGENT}"
    f"&search_origin=companies_search_client"
)
_PAGE_SIZE = 100

# Default filters — Cybersecurity + AI/ML only. Narrow enough to stay
# well under Algolia's 1000-hit per-query cap, and matches the user's
# core interest. Edit this list to broaden or re-target discovery.
# Each entry is `facet=value`; Algolia AND's across facets, OR's within
# the same facet name.
DEFAULT_SECTOR_FACETS = [
    "sectors_name.fr.Tech:Cybersécurité",
    "sectors_name.fr.Tech:Intelligence artificielle / Machine Learning",
]


def _post_algolia(index: str, params: str) -> dict:
    """One POST to Algolia multi-queries. Returns the parsed JSON."""
    body = json.dumps({
        "requests": [{"indexName": index, "params": params}],
    }).encode()
    req = urllib.request.Request(
        _ENDPOINT,
        data=body,
        method="POST",
        headers={
            "X-Algolia-API-Key": _API_KEY,
            "X-Algolia-Application-Id": _APP_ID,
            "Content-Type": "application/x-www-form-urlencoded",
            # Origin + Referer match WTJ's own browser so Algolia's
            # HTTP-referer whitelist on this key accepts us. Without
            # them, requests from unknown origins (datacenter IPs,
            # curl, bare python) get a 403.
            "Origin": "https://www.welcometothejungle.com",
            "Referer": "https://www.welcometothejungle.com/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.4 Safari/605.1.15"
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _facets_to_params(facets: list, page: int) -> str:
    """Encode an Algolia search string: hitsPerPage + page + facetFilters.
    facetFilters is a JSON-encoded list within the query string."""
    import urllib.parse
    # Algolia expects each OR-group as a sub-list. We OR within each
    # facet name (Logiciels OR AI OR Big Data…), AND across facet
    # names. For a flat list of same-facet values, group them.
    by_facet = {}
    for f in facets:
        name, _, value = f.partition(":")
        by_facet.setdefault(name, []).append(f)
    facet_filters = list(by_facet.values())
    pieces = [
        f"hitsPerPage={_PAGE_SIZE}",
        f"page={page}",
        f"facetFilters={urllib.parse.quote(json.dumps(facet_filters))}",
    ]
    return "&".join(pieces)


def fetch_candidates(sector_facets: list = None, max_pages: int = 50) -> list:
    """Hit Algolia for every company in the user's sector filter. Returns
    a flat list of {slug, name, description, sectors, website_url}.

    `max_pages=50` caps at 5000 companies, which is well above the
    4219 nbHits the broadest filter returns today. Lower for tests."""
    facets = sector_facets if sector_facets is not None else DEFAULT_SECTOR_FACETS
    out = []
    seen_slugs = set()
    for page in range(max_pages):
        params = _facets_to_params(facets, page)
        try:
            data = _post_algolia(_INDEX, params)
        except Exception as e:
            sys.stdout.write(f"[wttj_discovery] algolia POST failed (page={page}): {e}\n")
            break
        results = (data.get("results") or [{}])[0]
        hits = results.get("hits") or []
        nb_hits = results.get("nbHits") or 0
        if not hits:
            break
        for h in hits:
            slug = h.get("slug")
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            # Sectors is a list of {name, parent_name} dicts in the
            # real Algolia schema — flatten to names.
            sectors = []
            for s in (h.get("sectors") or []):
                if isinstance(s, dict) and s.get("name"):
                    sectors.append(s["name"])
            offices = []
            for o in (h.get("offices") or []):
                if isinstance(o, dict):
                    city = (o.get("city") or "").strip()
                    cc = (o.get("country_code") or "").strip()
                    if city or cc:
                        offices.append({"city": city, "country_code": cc})
            out.append({
                "slug": slug,
                "name": h.get("name") or slug,
                # jobs_count tells us whether this company has anything
                # worth fetching — top-ranked candidates by jobs_count
                # are the ones to validate first.
                "jobs_count": h.get("jobs_count") or 0,
                "nb_employees": h.get("nb_employees"),
                "sectors": sectors,
                "offices": offices,
                "reference": h.get("reference") or "",
            })
        # Stop as soon as we have every advertised hit.
        if len(seen_slugs) >= nb_hits:
            break
    return out


# =============================================================================
# Per-company jobs via the WTJ public JSON API.
# Reverse-engineered 2026-10-07 via debug/probe_wttj_company_api.py.
# =============================================================================

_WTTJ_API = "https://api.welcometothejungle.com"
_WTTJ_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    "Accept": "application/json, */*;q=0.5",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
    "Origin": "https://www.welcometothejungle.com",
    "Referer": "https://www.welcometothejungle.com/",
}


def fetch_wttj_company_detail(slug: str) -> dict:
    """GET /api/v1/organizations/<slug>. Returns a flat dict with the
    external website URL + metadata. Raises on HTTP failure so
    callers can decide to skip."""
    url = f"{_WTTJ_API}/api/v1/organizations/{slug}"
    req = urllib.request.Request(url, headers=_WTTJ_API_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        payload = json.loads(r.read().decode())
    org = payload.get("organization") or {}
    return {
        "slug": org.get("slug") or slug,
        "name": org.get("name") or "",
        # The external website — WTJ confusingly calls this
        # media_website_url. For Zama this is "https://zama.ai".
        "website_url": org.get("media_website_url") or "",
        "sectors": [
            s.get("name") for s in (org.get("sectors") or []) if s.get("name")
        ],
        "offices": [
            {"city": o.get("city") or "", "country_code": o.get("country_code") or ""}
            for o in (org.get("offices") or [])
        ],
        "nb_employees": org.get("nb_employees"),
    }


def fetch_wttj_jobs(slug: str, lang: str = "fr") -> list:
    """GET /api/v3/organizations/<slug>/jobs. Returns a list of job
    dicts in the shape jobs.py's pipeline consumes:
      {"title": …, "locations": [...], "url": …, "description": "",
       "blob": …}
    `lang` ("fr" or "en") only affects the public jobs URL we construct —
    the API itself returns the same data either way.

    The server-side default per_page is 30 and `per_page` is NOT an
    accepted query param (422 "Unexpected field: per_page") — so we
    paginate with `page` only."""
    out = []
    page = 1
    while True:
        url = f"{_WTTJ_API}/api/v3/organizations/{slug}/jobs?page={page}"
        req = urllib.request.Request(url, headers=_WTTJ_API_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            sys.stdout.write(f"[wttj_jobs] {slug!r} page={page} failed: {e}\n")
            break
        hits = data.get("data") or []
        for j in hits:
            job_slug = j.get("slug") or ""
            if not job_slug:
                continue
            # offices[] is the authoritative location list; office{} is
            # just the first one. Keep every office as a "City, CC" entry
            # so our location blacklist + display behave uniformly.
            locations = []
            for o in j.get("offices") or []:
                city = (o.get("city") or "").strip()
                cc = (o.get("country_code") or "").strip()
                if city and cc:
                    locations.append(f"{city}, {cc}")
                elif city:
                    locations.append(city)
            title = (j.get("name") or "").strip()
            summary = j.get("company_summary") or ""
            out.append({
                "title": title,
                "locations": locations,
                "url": f"https://www.welcometothejungle.com/{lang}/companies/{slug}/jobs/{job_slug}",
                "description": "",
                "blob": " ".join(filter(None, [title, summary])),
                # Carry WTJ-specific extras for the UI to display if it wants.
                "contract_type": j.get("contract_type") or "",
                "remote": j.get("remote") or "",
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "salary_currency": j.get("salary_currency") or "",
                "experience_min": j.get("experience_min"),
            })
        meta = data.get("metadata") or {}
        total_pages = meta.get("page_count") or 1
        if page >= total_pages:
            break
        page += 1
    return out


def cache_candidates(path: str, data: list) -> None:
    """Write to data/wttj_discovered.json atomically so a mid-write
    crash never leaves a half-file that fails to parse at read time."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": int(time.time()),
            "candidates": data,
        }, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_candidates(path: str) -> dict:
    """Load from data/wttj_discovered.json. Returns an empty dict when
    the cache is missing or malformed — callers treat that as "no
    discovery data yet", not an error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
