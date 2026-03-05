#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

# Guard against stale migration path tokens that reintroduce bad target paths.
if rg -n "scripts/archive/deprecated|archive/archive/deprecated" \
  README.md docs scripts config .github \
  --glob '!docs/archive/**' \
  --glob '!archive/**' \
  --glob '!scripts/governance/check-archive-path-consistency.sh' \
  --glob '!docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md' >/tmp/archive-path-consistency.fail 2>/dev/null; then
  echo "[archive-path] FAIL: inconsistent deprecated archive path tokens found:"
  sed -n '1,120p' /tmp/archive-path-consistency.fail
  rm -f /tmp/archive-path-consistency.fail
  exit 1
fi

rm -f /tmp/archive-path-consistency.fail
echo "[archive-path] PASS: archive path tokens are consistent."
