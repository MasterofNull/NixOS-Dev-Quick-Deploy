#!/usr/bin/env bash
# tier0.d/check-flake-age.sh - run the 48h locked-input age guard as a tracked maintenance signal.
# Rule 19 gate corollary: an input getting younger than 48h is a time signal, not a regression a
# change introduced, so it must never block a commit or deploy. It FAILS only under --maintenance
# (the scheduled run); every other mode skips it (no ~5s nix call per commit) and says so.
# Env: FLAKE_AGE_GUARD overrides the guard script (tests).
set -euo pipefail
MODE="${1:---pre-commit}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GUARD="${FLAKE_AGE_GUARD:-$ROOT/scripts/governance/check-flake-age.sh}"
tag="[tier0.d/check-flake-age]"
if [[ "$MODE" != "--maintenance" ]]; then
  echo "$tag SKIP: time-class signal, enforced under --maintenance only (mode $MODE)"
  exit 0
fi
cd "$ROOT"
if out="$(bash "$GUARD" 2>&1)"; then
  echo "$tag PASS (--maintenance): $(tail -n 1 <<<"$out")"
else
  printf '%s\n' "$out" | grep -E '^(FAIL|RESULT)' | sed "s|^|$tag |" >&2 || printf '%s\n' "$out" >&2
  echo "$tag FAIL (--maintenance): locked flake input(s) younger than 48h or lock metadata unreadable; refresh/hold per the flake-refresh flow" >&2
  exit 1
fi
