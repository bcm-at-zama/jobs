#!/usr/bin/env python3
"""
improve_locations.py — interactively audit and fix location normalization.

Workflow:
  1. `python3 jobs.py --skip-scoring` (run at least once so raw_locations.txt is written).
  2. `python3 improve_locations.py`   (this script).

For each raw location string it shows:
  - the current normalized output (city + country + display + group)
  - a heuristic status:
      OK     — grouped under a real country
      WARN   — grouped under "Other" (likely means we lack a city→country hint)
      HINT   — the country segment looks like a bogus city (e.g. "New York City")

You're asked whether to keep, edit or skip. Accepted answers become entries
you can paste directly into jobs.py's `_CITY_TO_COUNTRY` / `_COUNTRY_ALIASES`
tables. The script prints a suggestion block at the end.

Run non-interactively with `--report` to just print the audit table without
prompts.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

sys.path.insert(0, ".")
import jobs

RAW = "raw_locations.txt"


def load_raw():
    try:
        with open(RAW, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        sys.exit(f"{RAW} not found — run `python3 jobs.py --skip-scoring` first.")


COLOR_RED = "\033[31m"
COLOR_YEL = "\033[33m"
COLOR_GRN = "\033[32m"
COLOR_DIM = "\033[2m"
COLOR_END = "\033[0m"


def classify(raw):
    """Return (status_label, ansi_color, normalized_entries, group_label)."""
    flat = jobs._flatten_locations([raw])
    if not flat:
        return "DROP", COLOR_DIM, flat, "—"
    groups = jobs._group_locations(flat)
    country_labels = [g for g, _ in groups]
    joined = ", ".join(country_labels)
    if not groups:
        return "DROP", COLOR_DIM, flat, "—"
    # if a group is "Other" flag it
    if any(g == "Other" for g, _ in groups):
        return "WARN", COLOR_YEL, flat, joined
    # A country segment that is actually a city → suspicious
    for f in flat:
        if "," in f:
            tail = f.rsplit(",", 1)[1].strip()
            key = jobs._city_key(tail)
            if key in jobs._CITY_TO_COUNTRY:
                return "HINT", COLOR_RED, flat, joined
    return "OK", COLOR_GRN, flat, joined


def print_report(raws):
    counts = Counter()
    rows = []
    for raw in raws:
        status, col, flat, groups = classify(raw)
        counts[status] += 1
        rows.append((status, col, raw, flat, groups))
    print(f"{'STATUS':6}  {'RAW':40}  →  NORMALIZED / GROUP")
    print("-" * 100)
    for status, col, raw, flat, groups in rows:
        line = f"{col}{status:6}{COLOR_END}  {raw[:38]:40}  →  {flat}   [{groups}]"
        print(line)
    print()
    print("summary:", dict(counts))


def prompt_audit(raws):
    """Walk each entry; user can approve, propose a country, or skip."""
    additions_city = {}          # city_key → country
    additions_country = {}       # normalized country name (for aliases)
    for i, raw in enumerate(raws, 1):
        status, col, flat, groups = classify(raw)
        if status == "OK":
            continue
        print()
        print(f"[{i}/{len(raws)}] {col}{status}{COLOR_END}  raw={raw!r}")
        print(f"    current normalization: {flat}")
        print(f"    grouped as: {groups}")
        ans = input("    (k)eep as-is / (c)ountry=<Country> / city=<City>,<Country> / (s)kip: ").strip()
        if ans in ("", "k", "keep"):
            continue
        if ans in ("s", "skip"):
            continue
        if ans.startswith("c=") or ans.startswith("country="):
            country = ans.split("=", 1)[1].strip()
            # Guess the "city" as the first flat entry's first segment
            if flat:
                first = flat[0]
                city_seg = first.split(",")[0].strip()
                key = jobs._city_key(city_seg)
                additions_city[key] = country
                print(f"    added: _CITY_TO_COUNTRY[{key!r}] = {country!r}")
        elif ans.startswith("city="):
            body = ans.split("=", 1)[1]
            if "," not in body:
                print("    expected city=<Name>,<Country>")
                continue
            city, country = [x.strip() for x in body.split(",", 1)]
            key = jobs._city_key(city)
            additions_city[key] = country
            print(f"    added: _CITY_TO_COUNTRY[{key!r}] = {country!r}")
    print()
    print("=" * 60)
    print("Suggested additions to jobs.py:")
    print("=" * 60)
    if additions_city:
        print("# in _CITY_TO_COUNTRY:")
        for k, v in sorted(additions_city.items()):
            print(f'    "{k}": "{v}",')
    if not additions_city:
        print("(nothing new)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true",
                    help="Print the audit table and exit (no prompts).")
    args = ap.parse_args()
    raws = load_raw()
    if args.report:
        print_report(raws)
        return
    print_report(raws)
    print()
    print("Now walking through each WARN/HINT entry — hit ENTER to keep, or")
    print("type c=<Country> / city=<City>,<Country> to add a mapping.")
    prompt_audit(raws)


if __name__ == "__main__":
    main()
