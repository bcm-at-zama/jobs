#!/usr/bin/env bash
# Export a clean open-source snapshot of this repo to TARGET_DIR.
#
# The private repo stays untouched. Only tracked files are exported
# (via `git archive`), and personal directories are stripped:
#
#   - data/      — personal preferences, caches, state DBs
#   - business/  — market-analysis artifact written for the owner
#   - planning/  — internal tickets / roadmap mentioning the owner
#   - .claude/   — local Claude Code settings (permissions, workflow)
#
# Also drops .git history (open source should start from a fresh init).
#
# Usage:
#   bash script/export-opensource.sh /path/to/target
#
# The target directory must not exist (safety).
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $0 TARGET_DIR" >&2
  exit 2
fi

TARGET="$1"

if [ -e "$TARGET" ]; then
  echo "error: $TARGET already exists — refusing to overwrite." >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

mkdir -p "$TARGET"

# Copy tracked files only (via `git ls-files`), from the WORKING TREE
# so local uncommitted edits are included. Strip personal directories.
# `git ls-files` already excludes untracked debug/, venvs, caches.
git ls-files \
  | grep -Ev '^(data|business|planning|\.claude)/' \
  | tar -cf - -T - \
  | tar -xf - -C "$TARGET"

echo "  Exported clean snapshot → $TARGET"

# Smoke test: the OSS clone must at minimum (1) import cleanly with an
# empty user_config, (2) have a CLI that parses --help, (3) pass the
# framework test suite in `tests/`. User-decision tests live in
# `data/tests/` and are intentionally absent here — Makefile skips the
# second suite when data/tests/ is missing.
echo "  Running smoke test on exported snapshot..."
(
  cd "$TARGET"
  PYTHONPATH=src python3 -c "import config, jobs"      >/dev/null
  PYTHONPATH=src python3 src/jobs.py --help            >/dev/null
  make test                                            >/dev/null 2>&1
) || {
  echo "  SMOKE TEST FAILED — $TARGET may be missing files or have broken imports." >&2
  echo "  Re-run manually to see the error:" >&2
  echo "    cd $TARGET && make test" >&2
  exit 1
}
echo "  Smoke test passed (imports OK, --help OK, tests/ passing)."

echo "  Next steps for the open-source copy:"
echo "    cd $TARGET && git init && git add . && git commit -m 'Initial commit'"
