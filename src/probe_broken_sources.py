#!/usr/bin/env python3
"""Probe the ATS endpoints for the sources returning 0 jobs.

Must be run from the user's machine — the sandbox VM is blocked by
Cloudflare on both boards-api.greenhouse.io and api.ashbyhq.com (403 on
every slug, even known-working ones).

For each source, we probe the public JSON API with the slug currently
configured in config.py and report:
  - HTTP status
  - job count (if 200)
  - a sample of 3 job titles (to confirm it's the right board)
  - for ambiguous cases, a suggested slug to try next

For Snyk, the current config uses a Playwright generic scraper, but the
debug dump at /workspace/debug/debug-snyk-1.html shows the real jobs are
Ashby jobs at jobs.ashbyhq.com/98cd1a00-...  — so we also test whether
the Ashby friendly slug "snyk" works.

Usage:  python3 probe_broken_sources.py
"""
import json
import sys
import urllib.request
import urllib.error

GREENHOUSE_SOURCES = [
    ("Airbnb",         "airbnb"),
    ("Dataiku",        "dataiku"),
    ("Spitfire Audio", "spitfire"),
]

ASHBY_SOURCES = [
    ("Nord Security", "nord-security"),
    ("Pinecone",      "pinecone"),
    # Extra Ashby slug candidates for Snyk — current config is pw-based but
    # the Snyk dump shows it's really an Ashby board.
    ("Snyk (Ashby?)", "snyk"),
]


def probe(url, name):
    print(f"\n=== {name} ===")
    print(f"GET {url}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"HTTP {resp.status}")
            data = json.load(resp)
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}  ({e.reason})")
        return None
    except Exception as e:
        print(f"ERROR: {e!r}")
        return None


def summarize_greenhouse(data, name):
    if not data:
        return
    jobs = data.get("jobs") or []
    print(f"Greenhouse jobs count: {len(jobs)}")
    for j in jobs[:3]:
        print(f"  - {j.get('title','?')}  @  {j.get('location',{}).get('name','?')}")
    if not jobs:
        print(f"  !! {name}: board loaded but empty — slug may be wrong "
              "(or board actually has 0 postings)")


def summarize_ashby(data, name):
    if not data:
        return
    # Ashby posting-API shape: {"jobs":[{"title":..., "locationName":...}]}
    jobs = data.get("jobs") or []
    print(f"Ashby jobs count: {len(jobs)}")
    for j in jobs[:3]:
        print(f"  - {j.get('title','?')}  @  {j.get('locationName','?')}")
    if not jobs:
        print(f"  !! {name}: board loaded but empty — slug may be wrong")


def main():
    print("Probing Greenhouse endpoints …")
    for name, slug in GREENHOUSE_SOURCES:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        data = probe(url, name)
        summarize_greenhouse(data, name)

    print("\n\nProbing Ashby endpoints …")
    for name, slug in ASHBY_SOURCES:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        data = probe(url, name)
        summarize_ashby(data, name)

    print("""

Interpretation guide:
  - HTTP 200 + jobs list        → slug is correct, scraper should work
                                   (if it still returns 0 jobs in jobs.py,
                                    the bug is in the fetcher, not the slug)
  - HTTP 404                    → slug is wrong, try alternative spellings
  - HTTP 200 + 0 jobs           → slug is correct but board is empty
  - HTTP 403 everywhere         → your IP is being blocked (unlikely from
                                   a residential ISP; try again from a
                                   different network)
""")


if __name__ == "__main__":
    sys.exit(main() or 0)
