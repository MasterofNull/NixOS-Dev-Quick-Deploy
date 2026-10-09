#!/usr/bin/env bash
# test-check-checkout-fresh.sh — validate the checkout freshness guard
#
# Tests:
#   1. Clone is up-to-date → exit 0
#   2. Behind origin with a conflicting uncommitted edit → exit 3, edit kept
#   3. ALLOW_STALE_CHECKOUT=1 → exit 0 + warning (even if behind)
#   4. Unreachable origin → exit 0 + warning (offline systems don't block)
#   5. Clean clone behind origin → fast-forwarded, exit 0, HEAD == origin/main
#   6. AUTO_FAST_FORWARD=0 with clean clone behind → exit 3, HEAD unchanged
#
set -u

TMPDIR="${TMPDIR:-/tmp}"
TEST_ROOT="$TMPDIR/test-checkout-fresh-$$"
PASSED=0
FAILED=0

# Compute absolute path to the guard script from this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GUARD_SCRIPT="$REPO_ROOT/scripts/governance/check-checkout-fresh.sh"

cleanup() {
  rm -rf "$TEST_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT" || exit 1

echo "=== test-check-checkout-fresh.sh ==="
echo "Guard script: $GUARD_SCRIPT"
echo "Repo root: $REPO_ROOT"
echo

# Test 1: Clone is up-to-date
echo "[TEST 1] Clone is up-to-date → exit 0"
test1_passed=0
ORIGIN_REPO="$TEST_ROOT/origin.git"
CLONE_REPO="$TEST_ROOT/clone"
mkdir -p "$ORIGIN_REPO" || true
git init --bare "$ORIGIN_REPO" >/dev/null 2>&1 || true
TEMP_WORK="$TEST_ROOT/temp-work"
mkdir -p "$TEMP_WORK" || true
cd "$TEMP_WORK"
git init -q >/dev/null 2>&1 || true
git config user.email "test@test.local" >/dev/null 2>&1 || true
git config user.name "Test User" >/dev/null 2>&1 || true
echo "test" > file.txt
git add file.txt >/dev/null 2>&1 || true
git commit -m "initial" -q >/dev/null 2>&1 || true
git remote add origin "$ORIGIN_REPO" >/dev/null 2>&1 || true
git push -u origin main -q >/dev/null 2>&1 || git push -u origin HEAD:main -q >/dev/null 2>&1 || true
git clone "$ORIGIN_REPO" "$CLONE_REPO" -q >/dev/null 2>&1 || true
cd "$CLONE_REPO" || exit 1
if REPO="$CLONE_REPO" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  echo "  ✓ PASS: exit 0 when up-to-date"
  ((PASSED++)) || true
  test1_passed=1
else
  EXIT_CODE=$?
  echo "  ✗ FAIL: expected exit 0, got $EXIT_CODE"
  ((FAILED++)) || true
fi
cd "$TEST_ROOT" || exit 1
echo

# Test 2: Clone is behind origin by 1 commit → exit 3
echo "[TEST 2] Clone is behind origin by 1 commit → exit 3"
test2_passed=0
ORIGIN_REPO2="$TEST_ROOT/origin2.git"
CLONE_REPO2="$TEST_ROOT/clone2"
mkdir -p "$ORIGIN_REPO2" || true
git init --bare "$ORIGIN_REPO2" >/dev/null 2>&1 || true
TEMP_WORK2="$TEST_ROOT/temp-work2"
mkdir -p "$TEMP_WORK2" || true
cd "$TEMP_WORK2"
git init -q >/dev/null 2>&1 || true
git config user.email "test@test.local" >/dev/null 2>&1 || true
git config user.name "Test User" >/dev/null 2>&1 || true
echo "test1" > file.txt
git add file.txt >/dev/null 2>&1 || true
git commit -m "commit1" -q >/dev/null 2>&1 || true
git remote add origin "$ORIGIN_REPO2" >/dev/null 2>&1 || true
git push -u origin main -q >/dev/null 2>&1 || git push -u origin HEAD:main -q >/dev/null 2>&1 || true
echo "test2" >> file.txt
git commit -am "commit2" -q >/dev/null 2>&1 || true
git push -q >/dev/null 2>&1 || true
git clone "$ORIGIN_REPO2" "$CLONE_REPO2" -q >/dev/null 2>&1 || true
cd "$CLONE_REPO2" || exit 1
git config user.email "test@test.local" >/dev/null 2>&1 || true
git config user.name "Test User" >/dev/null 2>&1 || true
git fetch origin -q >/dev/null 2>&1 || true
git reset -q --hard HEAD~1 >/dev/null 2>&1 || true
# Uncommitted local edit to a file the incoming commit changes: a fast-forward
# would overwrite it, so the guard must refuse and keep the edit.
echo "local-uncommitted" > file.txt
if REPO="$CLONE_REPO2" bash "$GUARD_SCRIPT" > /tmp/test-output 2>&1; then
  echo "  ✗ FAIL: expected exit 3, got 0"
  ((FAILED++)) || true
else
  EXIT_CODE=$?
  if [[ $EXIT_CODE -eq 3 ]]; then
    if grep -q "behind origin/main" /tmp/test-output && grep -qx "local-uncommitted" "$CLONE_REPO2/file.txt"; then
      echo "  ✓ PASS: exit 3 with error message"
      ((PASSED++)) || true
      test2_passed=1
    else
      echo "  ✗ FAIL: exit 3 but no 'behind origin/main' message"
      ((FAILED++)) || true
    fi
  else
    echo "  ✗ FAIL: expected exit 3, got $EXIT_CODE"
    ((FAILED++)) || true
  fi
fi
cd "$TEST_ROOT" || exit 1
echo

# Test 3: ALLOW_STALE_CHECKOUT=1 → exit 0 + warning
echo "[TEST 3] ALLOW_STALE_CHECKOUT=1 → exit 0 + warning"
test3_passed=0
CLONE_REPO3="$TEST_ROOT/clone3"
mkdir -p "$CLONE_REPO3" || true
cd "$CLONE_REPO3"
git init -q >/dev/null 2>&1 || true
git config user.email "test@test.local" >/dev/null 2>&1 || true
git config user.name "Test User" >/dev/null 2>&1 || true
git remote add origin /nonexistent/origin.git >/dev/null 2>&1 || true
if REPO="$CLONE_REPO3" ALLOW_STALE_CHECKOUT=1 bash "$GUARD_SCRIPT" > /tmp/test-output 2>&1; then
  if grep -q "ALLOW_STALE_CHECKOUT" /tmp/test-output; then
    echo "  ✓ PASS: exit 0 with ALLOW_STALE_CHECKOUT override"
    ((PASSED++)) || true
    test3_passed=1
  else
    echo "  ✗ FAIL: exit 0 but no ALLOW_STALE_CHECKOUT message"
    ((FAILED++)) || true
  fi
else
  EXIT_CODE=$?
  echo "  ✗ FAIL: expected exit 0, got $EXIT_CODE"
  ((FAILED++)) || true
fi
cd "$TEST_ROOT" || exit 1
echo

# Test 4: Unreachable origin → exit 0 + warning
echo "[TEST 4] Unreachable origin → exit 0 + warning"
test4_passed=0
CLONE_REPO4="$TEST_ROOT/clone4"
mkdir -p "$CLONE_REPO4" || true
cd "$CLONE_REPO4"
git init -q >/dev/null 2>&1 || true
git config user.email "test@test.local" >/dev/null 2>&1 || true
git config user.name "Test User" >/dev/null 2>&1 || true
git remote add origin /nonexistent/origin.git >/dev/null 2>&1 || true
if REPO="$CLONE_REPO4" bash "$GUARD_SCRIPT" > /tmp/test-output 2>&1; then
  if grep -q "WARN" /tmp/test-output; then
    echo "  ✓ PASS: exit 0 with warning when origin unreachable"
    ((PASSED++)) || true
    test4_passed=1
  else
    echo "  ✗ FAIL: exit 0 but no WARN message"
    ((FAILED++)) || true
  fi
else
  EXIT_CODE=$?
  echo "  ✗ FAIL: expected exit 0, got $EXIT_CODE"
  ((FAILED++)) || true
fi
cd "$TEST_ROOT" || exit 1
echo

# Tests 5/6: clean clone behind origin (no local edits) — reuse origin2 history.
make_behind_clone() {
  git clone "$ORIGIN_REPO2" "$1" -q >/dev/null 2>&1 || true
  git -C "$1" reset -q --hard HEAD~1 >/dev/null 2>&1 || true
}

echo "[TEST 5] Clean clone behind origin → fast-forward, exit 0"
CLONE_REPO5="$TEST_ROOT/clone5"
make_behind_clone "$CLONE_REPO5"
if REPO="$CLONE_REPO5" bash "$GUARD_SCRIPT" > "$TEST_ROOT/out5" 2>&1 \
    && [[ "$(git -C "$CLONE_REPO5" rev-parse HEAD)" == "$(git -C "$CLONE_REPO5" rev-parse origin/main)" ]] \
    && grep -q "Fast-forwarded" "$TEST_ROOT/out5"; then
  echo "  ✓ PASS: fast-forwarded to origin/main"
  ((PASSED++)) || true
else
  echo "  ✗ FAIL: expected fast-forward + exit 0"; sed -n 1,5p "$TEST_ROOT/out5"
  ((FAILED++)) || true
fi
echo

echo "[TEST 6] AUTO_FAST_FORWARD=0 → exit 3, HEAD unchanged"
CLONE_REPO6="$TEST_ROOT/clone6"
make_behind_clone "$CLONE_REPO6"
BEFORE6="$(git -C "$CLONE_REPO6" rev-parse HEAD)"
REPO="$CLONE_REPO6" AUTO_FAST_FORWARD=0 bash "$GUARD_SCRIPT" > "$TEST_ROOT/out6" 2>&1
EXIT6=$?
if [[ $EXIT6 -eq 3 && "$(git -C "$CLONE_REPO6" rev-parse HEAD)" == "$BEFORE6" ]]; then
  echo "  ✓ PASS: opt-out keeps the blocking behaviour"
  ((PASSED++)) || true
else
  echo "  ✗ FAIL: expected exit 3 and unchanged HEAD, got $EXIT6"
  ((FAILED++)) || true
fi
echo

echo "=== Test Results ==="
echo "Passed: $PASSED"
echo "Failed: $FAILED"

if [[ $FAILED -eq 0 ]]; then
  echo "✓ All tests passed"
  exit 0
else
  echo "✗ Some tests failed"
  exit 1
fi
