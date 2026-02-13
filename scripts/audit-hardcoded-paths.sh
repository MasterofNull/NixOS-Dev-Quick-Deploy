#!/usr/bin/env bash
#
# Audit for hardcoded paths that should use XDG or config variables.
# Usage: scripts/audit-hardcoded-paths.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

patterns=(
  "/home/"
  "/tmp/"
  "/var/tmp/"
)

exclude_globs=(
  "--glob" "!.git/*"
  "--glob" "!archive/**"
  "--glob" "!docs/archive/**"
  "--glob" "!deprecated/**"
  "--glob" "!result/**"
  "--glob" "!venv/**"
  "--glob" "!**/*.log"
  "--glob" "!**/*.lock"
  "--glob" "!dashboard.html.backup-*"
  "--glob" "!scripts/audit-hardcoded-paths.sh"
)

cd "$ROOT_DIR"

echo "Hardcoded path audit (root: $ROOT_DIR)"
echo ""

for pattern in "${patterns[@]}"; do
  echo "Pattern: $pattern"
  if rg -n "${exclude_globs[@]}" "$pattern" .; then
    echo ""
  else
    echo "  (no matches)"
    echo ""
  fi
done

echo "Suggestions:"
echo "  • Replace /home/<user> with \$HOME or XDG paths."
echo "  • Replace /tmp and /var/tmp with \$TMPDIR or mktemp."
echo "  • Record exceptions in SYSTEM-UPGRADE-ROADMAP.md (Phase 14.5)."
