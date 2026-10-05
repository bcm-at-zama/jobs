#!/usr/bin/env bash
# Commit + push the repo code. Per-user state (data/*.json, data/profile.md,
# etc.) is gitignored by design — if you want to back it up on a private
# branch, use `git add -f data/`.
#
# Called by `make commit`.
set -e

git add src tests business planning knowledge script
git add CLAUDE.md Makefile README.md LICENSE
# Personal preferences live in data/user_config.py (loaded by src/config.py
# at import time). Explicitly tracked so a private backup includes it —
# add it to .gitignore when turning this repo into an open-source clone.
git add -f data/user_config.py

git commit -am "Update"
git push
git status
