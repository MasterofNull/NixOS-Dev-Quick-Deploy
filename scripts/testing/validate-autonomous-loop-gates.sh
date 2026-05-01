#!/usr/bin/env bash
# validate-autonomous-loop-gates.sh — Phase 17.4 CI gate
#
# Validates that the Phase 17 closed-loop improver is correctly wired:
#   1. experiment_executor.py and sandbox_validator.py exist
#   2. autonomous_loop.py has no placeholder text
#   3. All three Python modules compile cleanly
#   4. NixOS autonomous-improvement.nix parses cleanly
#
# Usage: bash scripts/testing/validate-autonomous-loop-gates.sh
# Exit:  0 on all pass, 1 on first failure

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AUTONOMOUS_DIR="$REPO_ROOT/ai-stack/autonomous-improvement"
PASS=0
FAIL=0

_pass() { printf 'PASS: %s\n' "$1"; PASS=$((PASS + 1)); }
_fail() { printf 'FAIL: %s\n' "$1"; FAIL=$((FAIL + 1)); }

# -------------------------------------------------------------------
# 1. Required files exist
# -------------------------------------------------------------------
for f in \
    "$AUTONOMOUS_DIR/experiment_executor.py" \
    "$AUTONOMOUS_DIR/sandbox_validator.py" \
    "$AUTONOMOUS_DIR/autonomous_loop.py"
do
    if [ -f "$f" ]; then
        _pass "file exists: $(basename "$f")"
    else
        _fail "missing file: $f"
    fi
done

# -------------------------------------------------------------------
# 2. No placeholder text in autonomous_loop.py
# -------------------------------------------------------------------
if grep -q "not yet implemented\|Placeholder: In real implementation" \
    "$AUTONOMOUS_DIR/autonomous_loop.py" 2>/dev/null; then
    _fail "autonomous_loop.py still contains placeholder text"
else
    _pass "autonomous_loop.py has no placeholder text"
fi

# -------------------------------------------------------------------
# 3. Python syntax checks
# -------------------------------------------------------------------
for f in \
    "$AUTONOMOUS_DIR/experiment_executor.py" \
    "$AUTONOMOUS_DIR/sandbox_validator.py" \
    "$AUTONOMOUS_DIR/autonomous_loop.py"
do
    if python3 -m py_compile "$f" 2>/dev/null; then
        _pass "py_compile: $(basename "$f")"
    else
        _fail "py_compile failed: $f"
    fi
done

# -------------------------------------------------------------------
# 4. NixOS module parses cleanly
# -------------------------------------------------------------------
NIX_MODULE="$REPO_ROOT/nix/modules/services/autonomous-improvement.nix"
if [ -f "$NIX_MODULE" ]; then
    if nix-instantiate --parse "$NIX_MODULE" > /dev/null 2>&1; then
        _pass "nix parse: autonomous-improvement.nix"
    else
        _fail "nix parse failed: $NIX_MODULE"
    fi
else
    _fail "missing: $NIX_MODULE"
fi

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
