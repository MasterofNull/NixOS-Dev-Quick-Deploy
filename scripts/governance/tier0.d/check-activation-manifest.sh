#!/usr/bin/env bash
# check-activation-manifest.sh — Tier 0 activation manifest gate (Rules 15/23, P5.2)
# New runtime entrypoints must be named in config/activation-manifest.json and wired
# (live caller, enable option set, health signal) or carry a dated deferral.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

exec python3 "$REPO_ROOT/scripts/governance/check-activation-manifest.py" --staged --repo-root "$REPO_ROOT"
