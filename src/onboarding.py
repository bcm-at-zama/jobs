"""Interactive onboarding wizard — walks a new user through configuring
their personal jobs board. Entry point: `jobs.py --onboard` (also wired
to `make onboarding`).

MVP scope: welcome + company selection via per-group dialog. Future
steps (keywords, blacklists, review) will be added once the group
dialog UX is validated end-to-end.

Lives next to jobs.py in src/ so it imports the catalog without any
PYTHONPATH tweaks.
"""
from __future__ import annotations

import datetime as _dt
import os
import pprint
import shutil
import sys
from itertools import groupby

from catalog import CATALOG


# =============================================================================
# Rendering helpers — stdlib only, no colour deps.
# =============================================================================

def _hr(title: str = "") -> str:
    bar = "=" * 70
    return f"\n{bar}\n{title}\n{bar}" if title else f"\n{bar}"


def _step_header(n: int, total: int, title: str) -> None:
    print(_hr(f"Step {n}/{total} — {title}"))


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        line = input(f"{prompt}{suffix} > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(1)
    return line or default


def _ask_yn(prompt: str, default: bool = False) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    ans = _ask(f"{prompt} {hint}").lower()
    if not ans:
        return default
    return ans in ("y", "yes", "o", "oui")


# =============================================================================
# Company selection — per-group dialog
# =============================================================================

def _group_catalog():
    """Return [(group_name, [entry, ...]), ...] sorted by group then name."""
    rows = sorted(CATALOG, key=lambda e: (e["group"].lower(), e["name"].lower()))
    out = []
    for g, items in groupby(rows, key=lambda e: e["group"]):
        out.append((g, list(items)))
    return out


def _render_group(group_name: str, entries: list[dict], selected: set[str],
                  group_idx: int, group_total: int) -> None:
    """Render the current state of a group — two-column layout."""
    n_on = sum(1 for e in entries if e["name"] in selected)
    print(_hr(f"Group {group_idx}/{group_total}: {group_name} ({n_on}/{len(entries)} selected)"))
    # Two-column grid for readability. Rows are the shorter of the two halves.
    half = (len(entries) + 1) // 2
    left, right = entries[:half], entries[half:]
    width = max((len(e["name"]) for e in entries), default=20) + 6
    for i in range(half):
        line = _fmt_entry(i + 1, left[i], selected, width)
        if i < len(right):
            line += _fmt_entry(half + i + 1, right[i], selected, width)
        print("  " + line)
    print()
    print("  Commands:  a  (all on)   n  (all off)   1 3 5  (flip)   d  (done, next group)")


def _fmt_entry(idx: int, entry: dict, selected: set[str], width: int) -> str:
    mark = "x" if entry["name"] in selected else " "
    return f"[{idx:>3}] [{mark}] {entry['name']:<{width}}"


def _run_group_dialog(group_name: str, entries: list[dict], selected: set[str],
                      group_idx: int, group_total: int) -> None:
    """Mutate `selected` based on user input until they type 'd'."""
    name_by_idx = {i + 1: e["name"] for i, e in enumerate(entries)}
    while True:
        _render_group(group_name, entries, selected, group_idx, group_total)
        raw = _ask("")
        if not raw:
            continue
        cmd = raw.lower()
        if cmd == "d":
            return
        if cmd == "a":
            for e in entries:
                selected.add(e["name"])
            continue
        if cmd == "n":
            for e in entries:
                selected.discard(e["name"])
            continue
        # Treat anything else as a space- or comma-separated list of indices.
        tokens = [t for t in raw.replace(",", " ").split() if t]
        valid = True
        indices = []
        for t in tokens:
            try:
                i = int(t)
            except ValueError:
                print(f"  ✗ not a number: {t!r}")
                valid = False
                break
            if i not in name_by_idx:
                print(f"  ✗ out of range: {i} (valid: 1..{len(entries)})")
                valid = False
                break
            indices.append(i)
        if not valid:
            continue
        # Flip each index.
        for i in indices:
            name = name_by_idx[i]
            if name in selected:
                selected.discard(name)
            else:
                selected.add(name)


# =============================================================================
# File writing
# =============================================================================

def _build_user_config(selected: set[str]) -> str:
    """Serialise the selected companies into a user_config.py string.
    HIGHLIGHTS / TITLE_BLACKLIST / LOCATION_BLACKLIST are left as empty
    stubs for the user to fill in later (future wizard steps)."""
    chosen = [e for e in CATALOG if e["name"] in selected]
    chosen.sort(key=lambda e: (e["group"].lower(), e["name"].lower()))
    sources = []
    for e in chosen:
        entry = {k: v for k, v in e.items() if k != "group"}
        entry["queries"] = []
        sources.append(entry)
    header = f'''"""data/user_config.py — generated by `make onboarding` on {_dt.datetime.now().isoformat(timespec='seconds')}.

Personal preferences live here, outside src/, so src/ can stay
open-sourceable with zero personal data. src/config.py loads this file
at import time and overrides its empty defaults.

Edit by hand or re-run `make onboarding` to pick a different set of
companies. The wizard asks before overwriting an existing file.
"""

'''
    body = (
        "HIGHLIGHTS = []  # add keywords to draw in yellow (edit by hand for now)\n\n"
        "TITLE_BLACKLIST = []  # title substrings (case-insensitive) that hide a job\n\n"
        "LOCATION_BLACKLIST = []  # locations where you don't want to see jobs\n\n"
        f"SOURCES = {pprint.pformat(sources, width=120, sort_dicts=False)}\n"
    )
    return header + body


def _confirm_overwrite(path: str) -> bool:
    """Return True when the user wants to overwrite the existing file.
    Prints the backup path that'll be used."""
    try:
        n_sources, mtime = _summarize_existing(path)
    except Exception:
        n_sources, mtime = ("?", "?")
    backup = _backup_path(path)
    print()
    print(f"⚠  {path} already exists ({n_sources} sources, modified {mtime}).")
    print(f"   If you continue, a backup will be written to {backup}.")
    return _ask_yn("Overwrite?", default=False)


def _summarize_existing(path: str) -> tuple[int, str]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("_existing_uc", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    n = len(getattr(mod, "SOURCES", []) or [])
    ts = _dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
    return n, ts


def _backup_path(path: str) -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{path}.bak.{stamp}"


# =============================================================================
# Entry point
# =============================================================================

def run_wizard(data_dir: str = "data") -> int:
    """Run the full onboarding flow. Returns a POSIX exit code."""
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, "user_config.py")

    print(_hr("Welcome to jobs!"))
    print("This wizard configures your personal board in a few minutes.")
    print("You can rerun it any time via `make onboarding`.")

    if os.path.isfile(out_path):
        if not _confirm_overwrite(out_path):
            print("\nCancelled. Your existing config was not touched.")
            return 0

    _step_header(1, 2, "Companies to track")
    print("Pick which companies to scrape, group by group.")
    print("You can skip a group entirely (just type 'd' to move on).")

    selected: set[str] = set()
    groups = _group_catalog()
    for idx, (gname, entries) in enumerate(groups, 1):
        _run_group_dialog(gname, entries, selected, idx, len(groups))

    _step_header(2, 2, "Review & write")
    chosen = sorted(selected)
    print(f"  {len(chosen)} companies selected.")
    if chosen:
        preview = ", ".join(chosen[:12]) + (f", … (+{len(chosen) - 12})" if len(chosen) > 12 else "")
        print(f"  {preview}")

    if not _ask_yn(f"Write {out_path}?", default=True):
        print("Cancelled. Nothing was written.")
        return 0

    if os.path.isfile(out_path):
        backup = _backup_path(out_path)
        shutil.copy2(out_path, backup)
        print(f"  ✓ Backup: {backup}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_build_user_config(selected))
    print(f"  ✓ Wrote {out_path}")
    print()
    print("Next steps:")
    print("  • Edit HIGHLIGHTS / TITLE_BLACKLIST / LOCATION_BLACKLIST by hand")
    print("    in your new user_config.py (the wizard will cover these in a")
    print("    future version).")
    print("  • Run  make run  to fetch and open your board.")
    return 0


if __name__ == "__main__":
    sys.exit(run_wizard(os.environ.get("JOBS_DATA_DIR", "data")))
