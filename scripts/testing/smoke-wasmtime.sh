#!/usr/bin/env bash
# smoke-wasmtime.sh — Phase 66.1: Wasmtime L2 sandbox smoke test
# Verifies wasmtime is available in PATH and can execute a minimal WASM module.
# Usage: bash scripts/testing/smoke-wasmtime.sh [--verbose]
# Exit 0 = pass, exit 1 = fail, exit 2 = skip (wasmtime not in PATH)
set -euo pipefail

VERBOSE=0
for arg in "$@"; do [[ "$arg" == "--verbose" ]] && VERBOSE=1; done

log()  { [[ $VERBOSE -eq 1 ]] && echo "[smoke-wasmtime] $*" >&2 || true; }
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
skip() { echo "SKIP: $*"; exit 2; }

# ── Gate: wasmtime must be in PATH ─────────────────────────────────────────────
if ! command -v wasmtime &>/dev/null; then
  skip "wasmtime not in PATH — activate nix develop .#full first (Phase 66.1 staged in devShells.full)"
fi

WASMTIME_BIN=$(command -v wasmtime)
log "wasmtime binary: $WASMTIME_BIN"

# ── Check 1: wasmtime --version exits 0 ────────────────────────────────────────
VERSION=$("$WASMTIME_BIN" --version 2>&1) || fail "wasmtime --version failed"
log "version: $VERSION"
pass "wasmtime --version: $VERSION"

# ── Check 2: compile + run a minimal WAT module ────────────────────────────────
# Inline WAT (WebAssembly Text format) for a trivial add(2,3)=5 function.
# Compiled to binary WASM at test time — no pre-built blob needed.
WAT_FILE=$(mktemp --suffix=.wat)
WASM_FILE=$(mktemp --suffix=.wasm)
trap 'rm -f "$WAT_FILE" "$WASM_FILE"' EXIT

cat >"$WAT_FILE" <<'WAT'
(module
  (func $add (export "add") (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add)
  (func $_start (export "_start"))
)
WAT

log "WAT module written to $WAT_FILE"

# Compile WAT → WASM using wasmtime's bundled wat2wasm (via --wasm option) or wat feature
# wasmtime can run WAT files directly (it compiles internally)
RESULT=$("$WASMTIME_BIN" run --invoke add "$WAT_FILE" 2 3 2>&1) || fail "wasmtime run --invoke add failed: $RESULT"
log "invoke result: $RESULT"

# Result should contain "5"
if echo "$RESULT" | grep -q "^5$"; then
  pass "wasmtime run --invoke add 2 3 = 5 (L2 WASM execution confirmed)"
else
  fail "Expected result=5, got: $RESULT"
fi

# ── Check 3: fuel limiting (sandboxing primitive) ──────────────────────────────
# --fuel N limits execution to N wasm instructions — a key sandbox knob
FUEL_RESULT=$("$WASMTIME_BIN" run --fuel 100000 --invoke add "$WAT_FILE" 2 3 2>&1) || fail "wasmtime --fuel 100000 run failed"
log "fuel-limited result: $FUEL_RESULT"
if echo "$FUEL_RESULT" | grep -q "^5$"; then
  pass "wasmtime --fuel 100000: execution completes within budget"
else
  fail "Fuel-limited run gave unexpected output: $FUEL_RESULT"
fi

echo ""
echo "=== smoke-wasmtime PASS (3/3 checks) ==="
echo "    Phase 66.1: Wasmtime L2 sandbox verified in devShells.full"
echo "    Next: Phase 66.2 — wire WASMTIME_TOOLS in shell_tools.py (requires nixos-rebuild)"
