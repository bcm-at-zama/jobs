#!/usr/bin/env bash
# Commit + push repo code only. Per-user state (data/*.json) is gitignored
# by design — if you want to back it up on a private branch, use
# `git add -f data/`.
set -e

git add jobs.py
git add improve_locations.py
git add CLAUDE.md
git add config.py
git add TODO.txt
git add NEXT.md
git add TOREVIEW.md
git add config_blurbs.py
git add business
git add Makefile tests/*.py

git commit -am "Update"
git push
git status
