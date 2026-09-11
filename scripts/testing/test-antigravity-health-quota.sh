#!/usr/bin/env bash
# Verify scripts/health/antigravity-health.sh detects Gemini Code Assist quota exhaustion
# (HTTP 429 RESOURCE_EXHAUSTED) from a fixture Antigravity IDE log, and reports quota_status
# honestly (unknown, not faked) when no such evidence exists. This is the regression test
# for the rewrite that replaced the dead-gemini-CLI check with the real IDE+inbox lane check
# — see .agent/memory/issues-backlog.md (Antigravity persistent failure hidden by broken
# health signal).
#
# Hermeticity: this test MUST NOT depend on the real repo's .agent/collaboration/antigravity-
# inbox state. aq-antigravity-inbox hardcodes its own REPO/INBOX resolution (no env override
# in that script — verified by reading it), so the only way to control the "undrained" signal
# from the caller side is to point antigravity-health.sh's AQ_ANTIGRAVITY_INBOX_BIN override at
# a stub `aq-antigravity-inbox verify --json` instead of the real one. Every case below does
# this, so results are identical no matter what the real repo's inbox currently contains (it
# may legitimately have undrained tasks in some checkouts — that's real signal, not something
# this test should trip over). AQ_ANTIGRAVITY_INBOX_DIR is likewise pointed at a controlled
# temp dir so check #3 (directory presence) is hermetic too.
#
# Exit-code contract under test (Rule 19 gate corollary — see the header of
# antigravity-health.sh for the full rationale): 0 = healthy; 3 = degraded for an
# EXTERNAL/environmental reason (quota exhausted, or undrained inbox tasks) — our own
# components are fine, so callers like the tier0 --pre-commit gate must not hard-block
# on this; 1 = OUR script/config is broken (missing binary/inbox script/inbox dir) — a
# genuine regression callers SHOULD block on. See scripts/testing/harness_qa/phases/
# phase0.py check 0.6.2 for the consumer of this distinction.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HEALTH_SCRIPT="${ROOT_DIR}/scripts/health/antigravity-health.sh"
BASH_BIN="$(command -v bash)"
BASE_PATH="${PATH}"

TMP_HOME="$(mktemp -d)"
trap 'rm -rf "${TMP_HOME}"' EXIT

mkdir -p "${TMP_HOME}/bin" "${TMP_HOME}/inbox-dir"

# Stub `antigravity` binary so the IDE-present check passes without a real GUI install.
cat > "${TMP_HOME}/bin/antigravity" <<'EOF'
#!/usr/bin/env bash
echo "stub antigravity: $*"
EOF
chmod +x "${TMP_HOME}/bin/antigravity"

# Stub `aq-antigravity-inbox` — implements only `verify --json` with a controllable
# undrained_count, so check #5 is decoupled from the real repo's actual inbox contents.
write_inbox_stub() {
  local undrained_count="$1"
  cat > "${TMP_HOME}/bin/aq-antigravity-inbox-stub" <<EOF
#!/usr/bin/env bash
if [[ "\$1" == "verify" ]]; then
  echo '{"ok": $( [[ "${undrained_count}" == "0" ]] && echo true || echo false ), "undrained_count": ${undrained_count}, "undrained": []}'
fi
EOF
  chmod +x "${TMP_HOME}/bin/aq-antigravity-inbox-stub"
}

run_check() {
  local inbox_dir="${1:-${TMP_HOME}/inbox-dir}"
  env -i \
    HOME="${TMP_HOME}" \
    PATH="${TMP_HOME}/bin:${BASE_PATH}" \
    AQ_ANTIGRAVITY_INBOX_BIN="${TMP_HOME}/bin/aq-antigravity-inbox-stub" \
    AQ_ANTIGRAVITY_INBOX_DIR="${inbox_dir}" \
    "${BASH_BIN}" "${HEALTH_SCRIPT}" --check --json
}

# For visibility only: show what the REAL repo inbox looks like right now, and prove the
# test does not read it (every case below passes an explicit AQ_ANTIGRAVITY_INBOX_BIN stub).
if [[ -x "${ROOT_DIR}/scripts/ai/aq-antigravity-inbox" ]]; then
  REAL_UNDRAINED="$("${ROOT_DIR}/scripts/ai/aq-antigravity-inbox" verify --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("undrained_count","?"))' 2>/dev/null || echo "?")"
  echo "INFO: real repo inbox undrained_count=${REAL_UNDRAINED} (irrelevant to this test — stubbed out below)"
fi

# ── Case 1: fixture log WITH RESOURCE_EXHAUSTED -> quota_status=exhausted, unhealthy ──────
FIXTURE_SESSION="${TMP_HOME}/.config/Antigravity/logs/20260910T000000"
mkdir -p "${FIXTURE_SESSION}"
cat > "${FIXTURE_SESSION}/ls-main.log" <<'EOF'
2026-09-10 00:00:01.000 [error] [LS Main stderr] I0910 00:00:01.000000 1 planner_generator.go:318] Encountered retryable api error. retrying in 5s. Error (The model API is currently overloaded and may experience intermittent errors.): RESOURCE_EXHAUSTED (code 429): Resource has been exhausted (e.g. check quota).: RESOURCE_EXHAUSTED (code 429): Resource has been exhausted (e.g. check quota).
EOF
write_inbox_stub 0

OUTPUT="$(run_check)" && EXIT_CODE=0 || EXIT_CODE=$?
printf '%s\n' "${OUTPUT}" | grep -q '"quota_status":"exhausted"'
printf '%s\n' "${OUTPUT}" | grep -q '"status":"unhealthy"'
[[ "${EXIT_CODE}" -eq 3 ]] || { echo "FAIL: expected exit 3 (external/degraded) on exhausted quota, got ${EXIT_CODE}"; exit 1; }
echo "PASS: quota exhaustion fixture -> quota_status=exhausted, status=unhealthy, exit=3 (external, non-blocking)"

# ── Case 2: no matching evidence + drained inbox -> quota_status=ok, healthy, exit=0 ──────
cat > "${FIXTURE_SESSION}/ls-main.log" <<'EOF'
2026-09-10 00:00:01.000 [info] [LS Main stderr] normal startup, nothing interesting here.
EOF
write_inbox_stub 0

OUTPUT="$(run_check)" && EXIT_CODE=0 || EXIT_CODE=$?
printf '%s\n' "${OUTPUT}" | grep -q '"quota_status":"ok"'
printf '%s\n' "${OUTPUT}" | grep -q '"status":"healthy"'
printf '%s\n' "${OUTPUT}" | grep -q '"undrained_count":"0"'
[[ "${EXIT_CODE}" -eq 0 ]] || { echo "FAIL: expected exit 0 with no quota evidence + drained inbox, got ${EXIT_CODE}"; exit 1; }
echo "PASS: clean log + drained inbox -> quota_status=ok, status=healthy, exit=0"

# ── Case 3: no Antigravity log directory at all -> quota_status=unknown, still healthy ────
rm -rf "${TMP_HOME}/.config/Antigravity"
write_inbox_stub 0

OUTPUT="$(run_check)" && EXIT_CODE=0 || EXIT_CODE=$?
printf '%s\n' "${OUTPUT}" | grep -q '"quota_status":"unknown"'
[[ "${EXIT_CODE}" -eq 0 ]] || { echo "FAIL: expected exit 0 with no log dir + drained inbox, got ${EXIT_CODE}"; exit 1; }
echo "PASS: no log directory + drained inbox -> quota_status=unknown (honest, not faked), exit=0"

# ── Case 4: no quota issue, but 3 undrained tasks -> degraded, exit=1 (proves the undrained
#    signal is real and testable in isolation, independent of whatever the real repo's inbox
#    happens to contain right now) ─────────────────────────────────────────────────────────
write_inbox_stub 3

OUTPUT="$(run_check)" && EXIT_CODE=0 || EXIT_CODE=$?
printf '%s\n' "${OUTPUT}" | grep -q '"quota_status":"unknown"'
printf '%s\n' "${OUTPUT}" | grep -q '"status":"degraded"'
printf '%s\n' "${OUTPUT}" | grep -q '"undrained_count":"3"'
[[ "${EXIT_CODE}" -eq 3 ]] || { echo "FAIL: expected exit 3 (external/degraded) with 3 undrained tasks, got ${EXIT_CODE}"; exit 1; }
echo "PASS: 3 undrained tasks (deliberately non-empty fake inbox) -> status=degraded, exit=3 (external, non-blocking)"

# ── Case 5: inbox directory itself missing -> unhealthy (proves AQ_ANTIGRAVITY_INBOX_DIR
#    hermetically controls check #3, independent of the real repo's actual inbox dir) ─────
write_inbox_stub 0
OUTPUT="$(run_check "${TMP_HOME}/no-such-inbox-dir")" && EXIT_CODE=0 || EXIT_CODE=$?
printf '%s\n' "${OUTPUT}" | grep -q '"status":"unhealthy"'
printf '%s\n' "${OUTPUT}" | grep -qi "inbox directory not found"
[[ "${EXIT_CODE}" -eq 1 ]] || { echo "FAIL: expected exit 1 with missing inbox dir, got ${EXIT_CODE}"; exit 1; }
echo "PASS: missing inbox directory -> status=unhealthy, exit=1"

# ── Case 6: --smoke mode hits a live 429 -> exit=3 (external, same contract as --check) ───
# Stub `antigravity chat ...` to emit a RESOURCE_EXHAUSTED response instead of "pong", so the
# smoke branch (scripts/health/antigravity-health.sh's own "if grep RESOURCE_EXHAUSTED" path)
# is exercised without spending real account quota.
cat > "${TMP_HOME}/bin/antigravity" <<'EOF'
#!/usr/bin/env bash
echo "RESOURCE_EXHAUSTED (code 429): Resource has been exhausted (e.g. check quota)."
EOF
chmod +x "${TMP_HOME}/bin/antigravity"
mkdir -p "${FIXTURE_SESSION}"
cat > "${FIXTURE_SESSION}/ls-main.log" <<'EOF'
2026-09-10 00:00:01.000 [info] [LS Main stderr] normal startup, nothing interesting here.
EOF
write_inbox_stub 0

OUTPUT="$(env -i \
  HOME="${TMP_HOME}" \
  PATH="${TMP_HOME}/bin:${BASE_PATH}" \
  AQ_ANTIGRAVITY_INBOX_BIN="${TMP_HOME}/bin/aq-antigravity-inbox-stub" \
  AQ_ANTIGRAVITY_INBOX_DIR="${TMP_HOME}/inbox-dir" \
  "${BASH_BIN}" "${HEALTH_SCRIPT}" --smoke --json)" && EXIT_CODE=0 || EXIT_CODE=$?
printf '%s\n' "${OUTPUT}" | grep -q '"smoke_result":"quota_exhausted"'
printf '%s\n' "${OUTPUT}" | grep -q '"quota_status":"exhausted"'
[[ "${EXIT_CODE}" -eq 3 ]] || { echo "FAIL: expected exit 3 on live-smoke 429, got ${EXIT_CODE}"; exit 1; }
echo "PASS: --smoke hits live 429 -> smoke_result=quota_exhausted, exit=3 (external, non-blocking)"

# Restore the "pong" stub for symmetry, in case this file grows more cases after this point.
cat > "${TMP_HOME}/bin/antigravity" <<'EOF'
#!/usr/bin/env bash
echo "stub antigravity: $*"
EOF
chmod +x "${TMP_HOME}/bin/antigravity"

echo "PASS: antigravity-health.sh quota + undrained detection behaves correctly on all fixtures, independent of the real repo inbox state"
