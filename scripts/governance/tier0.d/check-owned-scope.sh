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

CARGO_MANIFEST="$REPO_ROOT/crates/contract-validator/Cargo.toml"
if ! command -v cargo >/dev/null 2>&1; then
    echo "WARN: cargo not found; skipping binary scope gate"
    exit 0
fi

BASE_ARG=("${SCOPE_BASE:-HEAD}")
ALLOW_UNCOMMITTED_ARG=()
if [[ "${ALLOW_UNCOMMITTED:-0}" == "1" ]]; then
    ALLOW_UNCOMMITTED_ARG=("--allow-uncommitted")
fi

cargo run --quiet --manifest-path "$CARGO_MANIFEST" -- --root "$REPO_ROOT" scope-gate --owned "$OWNED_PATHS" --base "${BASE_ARG[@]}" "${ALLOW_UNCOMMITTED_ARG[@]}"
