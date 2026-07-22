#!/usr/bin/env bash
# Focused regression test for tier0-validation-gate.sh --staged-isolated mode.
#
# Proves three things about the opt-in staged-index isolation added to stop
# unrelated in-flight edits (a different slice mid-edit) from contaminating
# an unrelated commit's gate run:
#   1. An UNSTAGED, unrelated violation under ai-stack/ fails the whole-tree
#      (non-isolated) run but is invisible to --staged-isolated, because the
#      isolation snapshot only contains HEAD + the staged index — an
#      unstaged edit elsewhere was never part of that snapshot.
#   2. A genuinely STAGED, VALID change still gets validated (and passes)
#      under --staged-isolated — isolation must snapshot and check what was
#      actually staged, not just report a lucky pass on an empty diff.
#   3. A genuinely STAGED violation still fails under --staged-isolated,
#      because it IS part of what would actually be committed — isolation
#      must never weaken the gate, only shield it from unrelated noise.
#
# Every assertion below is against the gate's REAL exit code, captured with
# `set +e; ...; rc=$?; set -e` — never `cmd || true`, which discards the
# exit status of the very thing being asserted and would let a broken
# --staged-isolated (e.g. one that silently no-ops or always exits 0) pass
# this test undetected.
#
# Uses gate_llama_payload_ssot (a plain grep over ai-stack/) as the failing
# probe: deterministic, offline, no service dependency, and — critically —
# NOT filtered by collect_changed_files(), so it faithfully reproduces the
# "whole working tree" contamination path the isolation fix targets.
#
# Safety: the shared checkout, index, and stash are read-only inputs. The
# frozen candidate gate is overlaid into a disposable local clone under /tmp,
# and every fixture add/reset happens only in that clone's independent index.
#
# Offline: no network calls. Runs the frozen candidate gate three times
# (whole-tree, isolated-with-valid-staged-change, isolated-staged-violation)
# — each invocation runs the full 20+ gate battery (~80-90s observed in this
# environment).

set -euo pipefail

SOURCE_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_GATE="${SOURCE_REPO}/scripts/governance/tier0-validation-gate.sh"
TEST_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/tier0-staged-isolation-test.XXXXXX")"
TEST_REPO="${TEST_PARENT}/repo"

cleanup() {
  rm -rf "${TEST_PARENT}"
}
trap cleanup EXIT

# Clone committed objects locally without hardlinks, so the test can exercise
# real worktree/index behavior while remaining physically independent from the
# shared development checkout. Untracked and unstaged source-repo work are not
# imported by git clone.
git clone --quiet --no-hardlinks "${SOURCE_REPO}" "${TEST_REPO}"

GATE_SCRIPT="${TEST_REPO}/scripts/governance/tier0-validation-gate.sh"
DIRTY_FIXTURE_REL="ai-stack/tier0_isolation_probe_dirty.py"
VALID_FIXTURE_REL="docs/README.md"
STAGED_FIXTURE_REL="ai-stack/tier0_isolation_probe_staged.py"
DIRTY_FIXTURE="${TEST_REPO}/${DIRTY_FIXTURE_REL}"
VALID_FIXTURE="${TEST_REPO}/${VALID_FIXTURE_REL}"
STAGED_FIXTURE="${TEST_REPO}/${STAGED_FIXTURE_REL}"

# The candidate gate may be an uncommitted change in the shared checkout.
# Overlay and stage that exact candidate inside the disposable repository so
# its own --staged-isolated worktree materializes the implementation under
# test, rather than silently testing the older committed gate.
cp "${SOURCE_GATE}" "${GATE_SCRIPT}"
git -C "${TEST_REPO}" add -- scripts/governance/tier0-validation-gate.sh

# A normal live checkout provides four ignored operational projections that
# Phase-0 intentionally validates. Populate them as UNSTAGED live inputs in
# the disposable repository. The candidate gate must project them into its
# nested isolated worktree without ever adding them to either index.
OPERATIONAL_INPUTS=(
  .agent/collaboration/PULSE.log
  .agent/collaboration/RESUME.json
  .agents/improvement/candidates.json
  .agents/delegation/registry.jsonl
)
for operational_input in "${OPERATIONAL_INPUTS[@]}"; do
  mkdir -p "$(dirname "${TEST_REPO}/${operational_input}")"
  cp "${SOURCE_REPO}/${operational_input}" "${TEST_REPO}/${operational_input}"
done
mkdir -p "${TEST_REPO}/.agent/qa"

cd "${TEST_REPO}"

fixture_body_valid() {
  cat <<'MD'
<!-- Transient valid fixture used by test-tier0-staged-isolation.sh. -->
MD
}

fixture_body_bad() {
  cat <<'PY'
#!/usr/bin/env python3
# Tier0 staged-isolation test fixture (transient) - see test-tier0-staged-isolation.sh
payload = {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 100}
PY
}

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# Runs the gate script and captures its REAL exit code in GATE_RC (output in
# GATE_OUT). Toggles errexit off only around the one command whose status
# we are about to assert on, then immediately back on — the correct way to
# let a nonzero exit reach an explicit assertion instead of aborting the
# test script (what plain `set -e` would do) or discarding the code (what
# `cmd || true` would do).
run_gate() {
  set +e
  GATE_OUT="$("${GATE_SCRIPT}" "$@" 2>&1)"
  GATE_RC=$?
  set -e
}

# --- Part 0: explicit isolation setup failures must fail before any gate ----
MISSING_INPUT_REL="${OPERATIONAL_INPUTS[0]}"
MISSING_INPUT="${TEST_REPO}/${MISSING_INPUT_REL}"
mv "${MISSING_INPUT}" "${MISSING_INPUT}.missing"
echo "=== --staged-isolated: missing operational input => expect early FAIL ==="
run_gate --pre-commit --staged-isolated
mv "${MISSING_INPUT}.missing" "${MISSING_INPUT}"
if [[ ${GATE_RC} -eq 0 ]]; then
  fail "--staged-isolated exited 0 despite a missing required operational input"
fi
if ! grep -q "operational input is missing, non-regular, or a symlink: ${MISSING_INPUT_REL}" <<<"${GATE_OUT}"; then
  echo "${GATE_OUT}" | tail -40 >&2
  fail "missing operational input did not produce the expected fail-closed diagnostic"
fi
if grep -q "Checking Python syntax" <<<"${GATE_OUT}"; then
  echo "${GATE_OUT}" | tail -40 >&2
  fail "explicit isolation failure fell through into the validation gates"
fi
echo "PASS: explicit isolation fails closed before gates when an operational input is missing"

# --- Part 1: unstaged, unrelated dirty file must be isolated OUT, while a
#             genuinely VALID staged change must still be validated (pass) --
fixture_body_bad > "${DIRTY_FIXTURE}"
# Deliberately NOT staged — simulates another slice mid-edit on an unrelated
# file, exactly the scenario that motivated this fix (B3-C1's gate failing
# only because L2B-B was mid-edit elsewhere).

fixture_body_valid >> "${VALID_FIXTURE}"
git -C "${TEST_REPO}" add -- "${VALID_FIXTURE_REL}"
# Genuinely valid staged change — proves the isolated run actually snapshots
# and validates what's staged, rather than trivially "passing" because
# nothing was staged at all.

echo "=== whole-tree (no isolation): expect FAIL on build_llama_payload SSOT ==="
run_gate --pre-commit
if [[ ${GATE_RC} -eq 0 ]] || ! grep -q "FAIL: build_llama_payload SSOT" <<<"${GATE_OUT}"; then
  echo "${GATE_OUT}" | tail -40 >&2
  fail "whole-tree run did not fail (rc=${GATE_RC}) on the dirty fixture — fixture pattern is not a valid probe"
fi
echo "PASS: whole-tree run correctly fails (rc=${GATE_RC}) on the unrelated dirty fixture (confirms contamination exists without isolation)"

echo "=== --staged-isolated: valid staged change + unrelated dirty file => expect PASS (rc=0) ==="
run_gate --pre-commit --staged-isolated
if [[ ${GATE_RC} -ne 0 ]]; then
  echo "${GATE_OUT}" | tail -60 >&2
  fail "--staged-isolated exited non-zero (rc=${GATE_RC}) despite only a valid staged change being present — isolation is not working (the unrelated dirty fixture, or some other spurious failure, leaked into the snapshot)"
fi
if grep -q "FAIL: build_llama_payload SSOT" <<<"${GATE_OUT}"; then
  echo "${GATE_OUT}" | tail -60 >&2
  fail "--staged-isolated exited 0 (rc=${GATE_RC}) yet still reported the dirty-fixture SSOT failure string — inconsistent gate output, do not trust rc=0 here"
fi
if ! grep -q "Staged-isolated mode: validating clean HEAD" <<<"${GATE_OUT}"; then
  echo "${GATE_OUT}" | tail -60 >&2
  fail "--staged-isolated did not report entering isolation mode (silent fallback to whole-tree?) even though it exited 0 — cannot attribute the pass to isolation actually running"
fi
echo "PASS: --staged-isolated exits 0 (rc=${GATE_RC}), isolates the unrelated unstaged edit, and still validates the genuinely staged change"

rm -f "${DIRTY_FIXTURE}"
git -C "${TEST_REPO}" reset -q -- "${VALID_FIXTURE_REL}"
git -C "${TEST_REPO}" restore --worktree -- "${VALID_FIXTURE_REL}"

# --- Part 2: a genuinely STAGED violation must still fail under isolation --
fixture_body_bad > "${STAGED_FIXTURE}"
git -C "${TEST_REPO}" add -- "${STAGED_FIXTURE_REL}"

echo "=== --staged-isolated: expect FAIL (rc!=0) on a genuinely staged violation ==="
run_gate --pre-commit --staged-isolated
if [[ ${GATE_RC} -eq 0 ]]; then
  echo "${GATE_OUT}" | tail -60 >&2
  fail "--staged-isolated exited 0 (should have failed) on a genuinely staged violation — isolation is weakening the gate"
fi
if ! grep -q "FAIL: build_llama_payload SSOT" <<<"${GATE_OUT}"; then
  echo "${GATE_OUT}" | tail -60 >&2
  fail "--staged-isolated failed (rc=${GATE_RC}) but not for the expected SSOT reason — investigate before trusting this probe"
fi
echo "PASS: --staged-isolated correctly fails (rc=${GATE_RC}) a genuinely staged violation (isolation does not weaken the gate)"

git -C "${TEST_REPO}" reset -q -- "${STAGED_FIXTURE_REL}"
rm -f "${STAGED_FIXTURE}"

echo ""
echo "PASS: tier0 --staged-isolated isolates unrelated in-flight edits (hides unstaged noise while still validating genuinely staged changes — good or bad) without ever weakening the gate"
