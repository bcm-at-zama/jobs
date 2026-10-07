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
echo "  Next steps for the open-source copy:"
echo "    cd $TARGET && git init && git add . && git commit -m 'Initial commit'"
