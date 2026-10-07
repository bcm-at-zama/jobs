#!/usr/bin/env bash
# Export a clean open-source snapshot of this repo to TARGET_DIR.
#
# The private repo stays untouched. Only tracked files are exported
# (via `git archive`), and personal directories are stripped:
#
#   - data/      — personal preferences, caches, state DBs
#   - business/  — market-analysis artifact written for the owner
#   - planning/  — internal tickets / roadmap mentioning the owner
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

# Export tracked files at HEAD (ignores untracked debug/, venvs, caches),
# then strip the three personal directories at extract time.
git archive --format=tar HEAD \
  | tar -x -C "$TARGET" \
      --exclude='data/*' \
      --exclude='business/*' \
      --exclude='planning/*'

# Belt-and-braces: remove any now-empty top-level dirs the exclude left behind.
rmdir "$TARGET/data" "$TARGET/business" "$TARGET/planning" 2>/dev/null || true

echo "  Exported clean snapshot → $TARGET"
echo "  Next steps for the open-source copy:"
echo "    cd $TARGET && git init && git add . && git commit -m 'Initial commit'"
