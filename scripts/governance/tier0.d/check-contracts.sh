#!/usr/bin/env bash
# tier0.d/check-contracts.sh - contract guard (control-plane consolidation S1, D-R5-3).
# Always on (unlike check-owned-scope.sh): runs `harness-contracts contracts` (registry, contract
# files, lock, base-ref ratchet) and `harness-contracts boundaries` (import, subprocess, HTTP,
# event and dynamic call scan) from config/system-state-authorities.yaml. Fails closed: a missing
# or stale binary is a FAIL, never a skip. Exits 0 only when both checks pass.
#   --pre-commit            staged blobs only; ratchet against HEAD (CONTRACTS_BASE_REF overrides)
#   anything else           whole tree
#   --maintenance           whole tree, and expired baseline exceptions FAIL instead of WARN
set -uo pipefail

TAG="[tier0.d/check-contracts]"
REPO_ROOT="$(git rev-parse --show-toplevel)"
MODE="${1:---pre-commit}"

usable() { # a binary that predates the guard rejects --guard-version; no registry is read, so a broken registry is reported as one
    [[ -n "$1" && -x "$1" ]] && "$1" --guard-version >/dev/null 2>&1
}

BIN="${HARNESS_CONTRACTS_BIN:-}"
if ! usable "$BIN"; then
    BIN="$(command -v harness-contracts || true)"
fi
if ! usable "$BIN"; then
    NIX_OUT="$(nix build --no-link --print-out-paths "$REPO_ROOT#harness-contracts" 2>/dev/null | tail -n1 || true)"
    BIN="${NIX_OUT:+$NIX_OUT/bin/harness-contracts}"
fi
if ! usable "$BIN"; then
    echo "$TAG FAIL: harness-contracts with the contracts/boundaries subcommands is unavailable (not on PATH or stale; nix build .#harness-contracts failed)" >&2
    exit 1
fi

STAGED=()
EXTRA=()
BASE=(--base-ref "${CONTRACTS_BASE_REF:-HEAD}")
case "$MODE" in
    --pre-commit) STAGED=(--staged) ;;
    --maintenance) EXTRA=(--maintenance) ;;
esac

rc=0
"$BIN" --root "$REPO_ROOT" contracts ${STAGED[@]+"${STAGED[@]}"} ${EXTRA[@]+"${EXTRA[@]}"} "${BASE[@]}" 2>&1 | sed "s|^|$TAG |"
[[ "${PIPESTATUS[0]}" -eq 0 ]] || rc=1
"$BIN" --root "$REPO_ROOT" boundaries ${STAGED[@]+"${STAGED[@]}"} ${EXTRA[@]+"${EXTRA[@]}"} 2>&1 | sed "s|^|$TAG |"
[[ "${PIPESTATUS[0]}" -eq 0 ]] || rc=1
exit "$rc"
