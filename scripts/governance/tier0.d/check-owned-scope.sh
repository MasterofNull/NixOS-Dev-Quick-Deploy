#!/usr/bin/env bash
# check-owned-scope.sh — Tier 0 check verifying modified files stay within slice ownership
# Part of W4-S1: Rust-backed owned-path scope gate

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# If OWNED_PATHS environment variable is present, enforce it
if [[ -z "${OWNED_PATHS:-}" ]]; then
    # In regular pre-commit / local development without an active slice brief constraint, pass
    exit 0
fi

echo "[tier0/check-owned-scope] Enforcing slice path ownership: $OWNED_PATHS"

# Fail closed: a trust gate that cannot run must not pass. The packaged binary is on PATH after the
# next rebuild; until then the flake package is built (cached after the first build).
VALIDATOR="$(command -v harness-contracts || true)"
if [[ -z "$VALIDATOR" ]]; then
    NIX_OUT="$(nix build --no-link --print-out-paths "$REPO_ROOT#harness-contracts" 2>/dev/null | tail -n1 || true)"
    [[ -n "$NIX_OUT" && -x "$NIX_OUT/bin/harness-contracts" ]] && VALIDATOR="$NIX_OUT/bin/harness-contracts"
fi
if [[ -z "$VALIDATOR" ]]; then
    echo "FAIL: harness-contracts binary unavailable (not on PATH; nix build .#harness-contracts failed)" >&2
    exit 1
fi

BASE_ARG=("${SCOPE_BASE:-HEAD}")
ALLOW_UNCOMMITTED_ARG=()
if [[ "${ALLOW_UNCOMMITTED:-0}" == "1" ]]; then
    ALLOW_UNCOMMITTED_ARG=("--allow-uncommitted")
fi

"$VALIDATOR" --root "$REPO_ROOT" scope-gate --owned "$OWNED_PATHS" --base "${BASE_ARG[@]}" "${ALLOW_UNCOMMITTED_ARG[@]}"
