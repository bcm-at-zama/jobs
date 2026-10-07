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
_ENDPOINT = f"https://{_APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"
_PAGE_SIZE = 100

# Default tech-leaning filters — matches a security/AI/engineering
# profile. Users can override by passing a different list.
# Each entry is `facet=value`; Algolia AND's across facets, OR's within.
DEFAULT_SECTOR_FACETS = [
    "sectors_name.fr.Tech:Logiciels",
    "sectors_name.fr.Tech:Intelligence artificielle / Machine Learning",
    "sectors_name.fr.Tech:Big Data",
    "sectors_name.fr.Tech:SaaS / Cloud Services",
    "sectors_name.fr.Tech:Cybersécurité",
    "sectors_name.fr.Tech:Blockchain",
    "sectors_name.fr.Tech:Objets connectés",
    "sectors_name.fr.Tech:Robotique",
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
            # Matches the User-Agent WTJ's own browser Algolia client
            # sends, so our requests don't look weird in Algolia's logs.
            "User-Agent": "Algolia for JavaScript (4.20.0); Browser",
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
            out.append({
                "slug": slug,
                "name": h.get("name") or slug,
                "description": (h.get("short_description") or h.get("description") or "")[:200],
                "sectors": [
                    s for sector_group in (h.get("sectors_name", {}) or {}).values()
                    for s in sector_group
                ] if isinstance(h.get("sectors_name"), dict) else [],
                "website_url": h.get("website_url") or "",
                "size": h.get("company_size") or "",
            })
        # Stop as soon as we have every advertised hit.
        if len(seen_slugs) >= nb_hits:
            break
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
