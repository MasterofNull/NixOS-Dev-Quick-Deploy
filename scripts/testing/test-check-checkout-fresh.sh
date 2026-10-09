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
#   7. Behind + local pure append to issues-backlog.md + incoming append → ff, suffix re-applied
#   8. Behind + local NON-append edit to issues-backlog.md → exit 3, nothing changed
#   9. Allowlisted append + non-allowlisted overlapping edit → exit 3, nothing changed
#  10. ff fails after restore (untracked file collides with incoming add) → exit 3, tree byte-identical
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

# Tests 7-10: append-only auto-merge. Each builds its own origin + clone.
BL=".agent/memory/issues-backlog.md"
# $1=name; creates $TEST_ROOT/$1-origin.git and clone $TEST_ROOT/$1 whose HEAD is
# the base commit (backlog with 3 lines + other.txt); origin/main has 1 more commit
# appended by $2 (a shell snippet run in a scratch clone, then pushed).
make_append_fixture() {
  local name="$1" incoming="$2"
  local o="$TEST_ROOT/$name-origin.git" w="$TEST_ROOT/$name-work" c="$TEST_ROOT/$name"
  git init --bare -q "$o" >/dev/null 2>&1
  git init -q "$w" >/dev/null 2>&1
  git -C "$w" config user.email t@t.local; git -C "$w" config user.name T
  mkdir -p "$w/.agent/memory"
  printf 'line1\nline2\nline3\n' > "$w/$BL"
  echo base > "$w/other.txt"
  git -C "$w" add -A; git -C "$w" commit -qm base
  git -C "$w" remote add origin "$o"
  git -C "$w" push -q origin HEAD:main >/dev/null 2>&1
  git clone -q "$o" "$c" >/dev/null 2>&1
  git -C "$c" config user.email t@t.local; git -C "$c" config user.name T
  ( cd "$w" && eval "$incoming" )
  git -C "$w" add -A; git -C "$w" commit -qm incoming
  git -C "$w" push -q origin HEAD:main >/dev/null 2>&1
  git -C "$c" fetch -q origin
}

echo "[TEST 7] Local pure append + incoming append → ff, suffix re-applied, exit 0"
make_append_fixture t7 "printf 'incoming4\n' >> $BL"
C7="$TEST_ROOT/t7"
printf 'local-a\nlocal-b' >> "$C7/$BL"   # note: no trailing newline, must be preserved
EXPECT7=$'line1\nline2\nline3\nincoming4\nlocal-a\nlocal-b'
REPO="$C7" bash "$GUARD_SCRIPT" > "$TEST_ROOT/out7" 2>&1; EXIT7=$?
if [[ $EXIT7 -eq 0 ]] \
   && [[ "$(git -C "$C7" rev-parse HEAD)" == "$(git -C "$C7" rev-parse origin/main)" ]] \
   && printf '%s' "$EXPECT7" | cmp -s - "$C7/$BL" \
   && grep -q "re-applied local appends to: $BL" "$TEST_ROOT/out7"; then
  echo "  ✓ PASS: fast-forwarded and local suffix re-applied"
  ((PASSED++)) || true
else
  echo "  ✗ FAIL: exit=$EXIT7"; sed -n 1,8p "$TEST_ROOT/out7"; cat "$C7/$BL"
  ((FAILED++)) || true
fi
echo

echo "[TEST 8] Local NON-append edit + incoming change → exit 3, nothing changed"
make_append_fixture t8 "printf 'incoming4\n' >> $BL"
C8="$TEST_ROOT/t8"
printf 'line1\nLOCAL-EDIT\nline3\nextra\n' > "$C8/$BL"
cp "$C8/$BL" "$TEST_ROOT/before8"; BEFORE8="$(git -C "$C8" rev-parse HEAD)"
REPO="$C8" bash "$GUARD_SCRIPT" > "$TEST_ROOT/out8" 2>&1; EXIT8=$?
if [[ $EXIT8 -eq 3 ]] && cmp -s "$C8/$BL" "$TEST_ROOT/before8" \
   && [[ "$(git -C "$C8" rev-parse HEAD)" == "$BEFORE8" ]] \
   && grep -q "Overlapping local edits.*$BL" "$TEST_ROOT/out8"; then
  echo "  ✓ PASS: non-append edit blocks, file and HEAD untouched"
  ((PASSED++)) || true
else
  echo "  ✗ FAIL: exit=$EXIT8"; sed -n 1,12p "$TEST_ROOT/out8"
  ((FAILED++)) || true
fi
echo

echo "[TEST 9] Allowlisted append + non-allowlisted overlapping edit → exit 3, nothing modified"
make_append_fixture t9 "printf 'incoming4\n' >> $BL; echo changed >> other.txt"
C9="$TEST_ROOT/t9"
printf 'local-a\n' >> "$C9/$BL"
echo local-other >> "$C9/other.txt"
cp "$C9/$BL" "$TEST_ROOT/before9a"; cp "$C9/other.txt" "$TEST_ROOT/before9b"; BEFORE9="$(git -C "$C9" rev-parse HEAD)"
REPO="$C9" bash "$GUARD_SCRIPT" > "$TEST_ROOT/out9" 2>&1; EXIT9=$?
if [[ $EXIT9 -eq 3 ]] && cmp -s "$C9/$BL" "$TEST_ROOT/before9a" \
   && cmp -s "$C9/other.txt" "$TEST_ROOT/before9b" \
   && [[ "$(git -C "$C9" rev-parse HEAD)" == "$BEFORE9" ]] \
   && grep -q "Overlapping local edits.*other.txt" "$TEST_ROOT/out9"; then
  echo "  ✓ PASS: mixed overlap blocks, nothing modified"
  ((PASSED++)) || true
else
  echo "  ✗ FAIL: exit=$EXIT9"; sed -n 1,12p "$TEST_ROOT/out9"
  ((FAILED++)) || true
fi
echo

echo "[TEST 10] ff fails after restore (untracked file collides with incoming add) → exit 3, byte-identical"
make_append_fixture t10 "printf 'incoming4\n' >> $BL; echo new > collide.txt"
C10="$TEST_ROOT/t10"
printf 'local-a\nlocal-b' >> "$C10/$BL"
echo mine > "$C10/collide.txt"
cp -p "$C10/$BL" "$TEST_ROOT/before10"; BEFORE10="$(git -C "$C10" rev-parse HEAD)"
REPO="$C10" bash "$GUARD_SCRIPT" > "$TEST_ROOT/out10" 2>&1; EXIT10=$?
if [[ $EXIT10 -eq 3 ]] && cmp -s "$C10/$BL" "$TEST_ROOT/before10" \
   && [[ "$(cat "$C10/collide.txt")" == "mine" ]] \
   && [[ "$(git -C "$C10" rev-parse HEAD)" == "$BEFORE10" ]] \
   && [[ -z "$(git -C "$C10" diff --cached --name-only)" ]]; then
  echo "  ✓ PASS: failed ff rolled the tree back byte-for-byte"
  ((PASSED++)) || true
else
  echo "  ✗ FAIL: exit=$EXIT10"; sed -n 1,12p "$TEST_ROOT/out10"
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
