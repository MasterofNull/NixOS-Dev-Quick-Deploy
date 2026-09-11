#!/usr/bin/env bash
# antigravity-health.sh — health check for the REAL Antigravity advisory lane
#
# Real lane (current, as of 2026-09): the Antigravity IDE (`antigravity` binary, its own
# Google-account OAuth session, Gemini Code Assist via cloudaicompanion.googleapis.com) +
# the file-based advisory inbox at .agent/collaboration/antigravity-inbox/, driven by
# scripts/ai/aq-antigravity-inbox (claim / wake / complete / verify). Tasks are dropped as
# .md files in the inbox; `aq-antigravity-inbox wake` nudges the IDE with
# `antigravity chat --reuse-window --mode agent <prompt>`; the IDE claims + writes its own
# output. There is no headless keyed API call and no local secret — auth is whatever Google
# account is signed into the IDE.
#
# The `gemini` CLI lane (~/.gemini/*, `gemini -p ...`, @google/gemini-cli npm) is DEAD —
# retired 2026-07 (IneligibleTierError on the free tier). Do NOT check for it here; see
# scripts/ai/delegate-to-antigravity's own header for the same statement.
#
# Why this rewrite exists: the previous version of this script only checked the dead gemini
# lane, so it kept reporting "healthy" while the real lane silently failed for days. The
# real failure mode is Google-account quota exhaustion on Gemini Code Assist
# (cloudaicompanion.googleapis.com -> HTTP 429 RESOURCE_EXHAUSTED), which is invisible
# unless something reads the IDE's own logs — that's check #4 below, and it is the point
# of this rewrite. See .agent/memory/issues-backlog.md (Antigravity persistent failure).
#
# Checks (--check, no network, no quota spend):
#   1. `antigravity` IDE binary is on PATH
#   2. scripts/ai/aq-antigravity-inbox exists and is executable
#   3. .agent/collaboration/antigravity-inbox/ inbox directory exists
#   4. Quota scan: newest session under ~/.config/Antigravity/logs/ is scanned (local files
#      only, no network) for RESOURCE_EXHAUSTED / "(code 429)" / cloudaicompanion exhaustion
#      evidence. Reported as quota_status: ok | exhausted | exhausted_stale | unknown.
#   5. Undrained signal: scripts/ai/aq-antigravity-inbox verify --json (the existing
#      fail-closed drain audit — tasks nudged but never completed). Reported as
#      undrained_count.
#
# --smoke (opt-in only — spends the account's live Gemini Code Assist quota):
#   6. Runs a real `antigravity chat --reuse-window --mode agent "..."` prompt and checks
#      whether it comes back with the expected reply or a 429/RESOURCE_EXHAUSTED error.
#
# Usage:
#   scripts/health/antigravity-health.sh [--check|--smoke] [--json]
#
# Exit codes (Rule 19 gate corollary: a live external-service outage is an environmental
# signal, not a staged-change regression — callers like the tier0 pre-commit gate must
# distinguish it from a genuine local/config break, so this contract has three states,
# not two):
#   0  healthy
#   1  broken: script/config fault on OUR side — antigravity binary missing, inbox script
#      missing/not executable, inbox directory missing, or an unrecognized --smoke failure.
#      This IS a regression callers should block on.
#   3  degraded for an EXTERNAL/environmental reason — Gemini Code Assist quota exhausted,
#      or the inbox has undrained tasks (IDE not processing). Our components are present
#      and correctly configured; the live external lane state is bad. Callers (e.g. the
#      tier0 --pre-commit gate) should surface this as visible-but-non-blocking, not fail
#      the gate on it — see scripts/testing/harness_qa/phases/phase0.py check 0.6.2.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# Both overridable for hermetic testing (scripts/testing/test-antigravity-health-quota.sh) —
# production always falls back to the real repo paths. Note: aq-antigravity-inbox itself
# hardcodes its own REPO/INBOX resolution (Path(__file__).resolve().parents[2]) and has no
# env override, so AQ_ANTIGRAVITY_INBOX_DIR only affects check #3 (directory presence) here;
# to make check #5 (undrained, which shells out to aq-antigravity-inbox verify) hermetic too,
# tests point AQ_ANTIGRAVITY_INBOX_BIN at a stub rather than the real inbox supervisor.
INBOX_BIN="${AQ_ANTIGRAVITY_INBOX_BIN:-${REPO_ROOT}/scripts/ai/aq-antigravity-inbox}"
INBOX_DIR="${AQ_ANTIGRAVITY_INBOX_DIR:-${REPO_ROOT}/.agent/collaboration/antigravity-inbox}"
ANTIGRAVITY_LOG_ROOT="${HOME}/.config/Antigravity/logs"
QUOTA_RECENT_WINDOW_S="${QUOTA_RECENT_WINDOW_S:-86400}"  # 24h: evidence newer than this counts as "current"

MODE="check"
JSON_OUTPUT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)  MODE="check"; shift ;;
    --smoke)  MODE="smoke"; shift ;;
    --json)   JSON_OUTPUT=1; shift ;;
    --help|-h)
      cat <<'EOF'
Usage: antigravity-health.sh [--check|--smoke] [--json]
  --check   Validate the real lane's components + scan local logs for quota exhaustion
            evidence (default, no network call, no quota spend)
  --smoke   Also send a live prompt through `antigravity chat` — WARNING: this consumes
            the signed-in Google account's Gemini Code Assist quota
  --json    Emit JSON result
EOF
      exit 0 ;;
    *) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 1 ;;
  esac
done

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().rstrip("\n")))' <<<"${1:-}"
}

STATUS="unknown"
REASON=""
QUOTA_STATUS="unknown"
QUOTA_EVIDENCE_SESSION=""
QUOTA_EVIDENCE_AGE_S=""
UNDRAINED_COUNT="unknown"
SMOKE_RESULT="not_tested"
ANTIGRAVITY_BIN="$(command -v antigravity 2>/dev/null || echo "")"

emit_result() {
  local exit_code="$1"
  if [[ "${JSON_OUTPUT}" -eq 1 ]]; then
    printf '{'
    printf '"status":%s,'                  "$(json_escape "${STATUS}")"
    printf '"reason":%s,'                  "$(json_escape "${REASON}")"
    printf '"quota_status":%s,'            "$(json_escape "${QUOTA_STATUS}")"
    printf '"quota_evidence_session":%s,'  "$(json_escape "${QUOTA_EVIDENCE_SESSION}")"
    printf '"quota_evidence_age_s":%s,'    "$(json_escape "${QUOTA_EVIDENCE_AGE_S}")"
    printf '"undrained_count":%s,'         "$(json_escape "${UNDRAINED_COUNT}")"
    printf '"smoke_result":%s,'            "$(json_escape "${SMOKE_RESULT}")"
    printf '"antigravity_bin":%s,'         "$(json_escape "${ANTIGRAVITY_BIN}")"
    printf '"inbox_bin":%s,'               "$(json_escape "${INBOX_BIN}")"
    printf '"delegate_bin":%s,'            "$(json_escape "${INBOX_BIN}")"
    printf '"inbox_dir":%s'                "$(json_escape "${INBOX_DIR}")"
    printf '}\n'
  else
    printf 'status=%s\n'                  "${STATUS}"
    printf 'reason=%s\n'                  "${REASON}"
    printf 'quota_status=%s\n'            "${QUOTA_STATUS}"
    printf 'quota_evidence_session=%s\n'  "${QUOTA_EVIDENCE_SESSION}"
    printf 'quota_evidence_age_s=%s\n'    "${QUOTA_EVIDENCE_AGE_S}"
    printf 'undrained_count=%s\n'         "${UNDRAINED_COUNT}"
    printf 'smoke_result=%s\n'            "${SMOKE_RESULT}"
    printf 'antigravity_bin=%s\n'         "${ANTIGRAVITY_BIN}"
    printf 'inbox_bin=%s\n'               "${INBOX_BIN}"
    printf 'inbox_dir=%s\n'               "${INBOX_DIR}"
  fi
  exit "${exit_code}"
}

# ── 1. antigravity IDE binary on PATH ─────────────────────────────────────────
if [[ -z "${ANTIGRAVITY_BIN}" ]]; then
  STATUS="unhealthy"
  REASON="'antigravity' IDE binary not found in PATH — the advisory lane has no IDE to nudge"
  emit_result 1
fi

# ── 2. Inbox supervisor script present + executable ───────────────────────────
if [[ ! -x "${INBOX_BIN}" ]]; then
  STATUS="unhealthy"
  REASON="aq-antigravity-inbox not found or not executable at ${INBOX_BIN}"
  emit_result 1
fi

# ── 3. Inbox directory present ─────────────────────────────────────────────────
if [[ ! -d "${INBOX_DIR}" ]]; then
  STATUS="unhealthy"
  REASON="antigravity-inbox directory not found at ${INBOX_DIR}"
  emit_result 1
fi

# ── 4. Quota scan (local log read only — no network, no quota spend) ─────────
scan_quota() {
  if [[ ! -d "${ANTIGRAVITY_LOG_ROOT}" ]]; then
    QUOTA_STATUS="unknown"
    return
  fi
  # Session dirs are timestamp-named (YYYYMMDDTHHMMSS) but a just-created session (e.g. a
  # second window) can exist with zero log files yet — sorting by name alone can pick an
  # empty dir and hide real evidence one session back. Walk newest-first and use the first
  # dir that actually has candidate log files.
  local all_dirs
  all_dirs="$(find "${ANTIGRAVITY_LOG_ROOT}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -r)"
  if [[ -z "${all_dirs}" ]]; then
    QUOTA_STATUS="unknown"
    return
  fi
  local session_dir="" candidates=() f d
  while IFS= read -r d; do
    [[ -z "${d}" ]] && continue
    session_dir="${ANTIGRAVITY_LOG_ROOT}/${d}"
    candidates=()
    for f in "${session_dir}/ls-main.log" "${session_dir}/cloudcode.log" "${session_dir}"/window*/exthost/google.antigravity/Antigravity.log; do
      [[ -f "${f}" ]] && candidates+=("${f}")
    done
    if [[ "${#candidates[@]}" -gt 0 ]]; then
      QUOTA_EVIDENCE_SESSION="${d}"
      break
    fi
  done <<<"${all_dirs}"
  if [[ "${#candidates[@]}" -eq 0 ]]; then
    QUOTA_STATUS="unknown"
    QUOTA_EVIDENCE_SESSION=""
    return
  fi
  # Deliberately NOT a bare "429" grep: port numbers and timestamps routinely contain the
  # substring "429" and produced false positives during rewrite validation. Require the
  # actual RESOURCE_EXHAUSTED error text, a parenthesised "(code 429)" (the Code Assist
  # client's own error format), or an explicit cloudaicompanion exhaustion/quota mention.
  local pattern='RESOURCE_EXHAUSTED|\(code 429\)|cloudaicompanion[^\n]*(exhaust|quota)'
  local hit_file=""
  for f in "${candidates[@]}"; do
    if grep -qE "${pattern}" "${f}" 2>/dev/null; then
      hit_file="${f}"
      break
    fi
  done
  if [[ -z "${hit_file}" ]]; then
    QUOTA_STATUS="ok"
    return
  fi
  local mtime now age
  mtime="$(stat -c %Y "${hit_file}" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  age=$(( now - mtime ))
  QUOTA_EVIDENCE_AGE_S="${age}"
  if [[ "${age}" -le "${QUOTA_RECENT_WINDOW_S}" ]]; then
    QUOTA_STATUS="exhausted"
  else
    QUOTA_STATUS="exhausted_stale"
  fi
}
scan_quota

# ── 5. Undrained signal (reuse aq-antigravity-inbox's own fail-closed audit) ──
scan_undrained() {
  local out
  out="$(timeout 10 "${INBOX_BIN}" verify --json 2>/dev/null || true)"
  if [[ -n "${out}" ]]; then
    UNDRAINED_COUNT="$(python3 -c '
import json, sys
try:
    print(json.loads(sys.argv[1]).get("undrained_count", "unknown"))
except Exception:
    print("unknown")
' "${out}" 2>/dev/null || echo unknown)"
  fi
}
scan_undrained

# ── Compose result ─────────────────────────────────────────────────────────────
compose_check_result() {
  if [[ "${QUOTA_STATUS}" == "exhausted" ]]; then
    STATUS="unhealthy"
    REASON="Gemini Code Assist quota exhausted (HTTP 429 RESOURCE_EXHAUSTED) on the signed-in Google account — account quota, not our automation; check the account's Code Assist tier/quota. Evidence: ${ANTIGRAVITY_LOG_ROOT}/${QUOTA_EVIDENCE_SESSION} (${QUOTA_EVIDENCE_AGE_S}s old)."
    return
  fi
  if [[ "${UNDRAINED_COUNT}" != "unknown" && "${UNDRAINED_COUNT}" != "0" ]]; then
    STATUS="degraded"
    REASON="${UNDRAINED_COUNT} inbox task(s) nudged but not drained — the Antigravity IDE is not processing the inbox (possible quota exhaustion or the IDE is not running). quota_status=${QUOTA_STATUS}."
    return
  fi
  STATUS="healthy"
  if [[ "${QUOTA_STATUS}" == "unknown" ]]; then
    REASON="antigravity IDE + inbox lane present; no Antigravity IDE session logs found to check quota — quota_status=unknown (not verified healthy, just no evidence of exhaustion)."
  elif [[ "${QUOTA_STATUS}" == "exhausted_stale" ]]; then
    REASON="antigravity IDE + inbox lane present; last quota-exhaustion evidence is older than ${QUOTA_RECENT_WINDOW_S}s (session ${QUOTA_EVIDENCE_SESSION}) — treating as recovered, no undrained tasks."
  else
    REASON="antigravity IDE + inbox lane present; no quota exhaustion evidence in latest session; no undrained tasks."
  fi
}

if [[ "${MODE}" != "smoke" ]]; then
  compose_check_result
  SMOKE_RESULT="not_tested"
  if [[ "${STATUS}" == "healthy" ]]; then
    emit_result 0
  fi
  # By this point checks #1-#3 (component presence) have already emit_result 1'd above if
  # they failed — everything compose_check_result can produce here (quota exhausted or
  # undrained tasks) is an external/environmental signal, not a script/config break.
  emit_result 3
fi

# ── 6. Smoke test (--smoke mode only — spends live account quota) ─────────────
if [[ "${JSON_OUTPUT}" -ne 1 ]]; then
  printf 'WARNING: --smoke sends a live prompt through the Antigravity IDE (antigravity chat), which consumes the signed-in Google account'"'"'s Gemini Code Assist quota. Only use this when you specifically need to verify live model access.\n' >&2
fi

SMOKE_OUT="$(timeout 45 antigravity chat --reuse-window --mode agent \
  "Reply with exactly one word: pong" \
  2>&1 </dev/null || true)"

if echo "${SMOKE_OUT}" | grep -qiE 'RESOURCE_EXHAUSTED|\(code 429\)'; then
  QUOTA_STATUS="exhausted"
  QUOTA_EVIDENCE_AGE_S=0
  SMOKE_RESULT="quota_exhausted"
  STATUS="unhealthy"
  REASON="Live smoke call hit Gemini Code Assist quota exhaustion (HTTP 429 RESOURCE_EXHAUSTED) on the signed-in Google account — account quota, not our automation; check the account's Code Assist tier/quota."
  emit_result 3  # external/environmental — see exit-code contract in header
elif echo "${SMOKE_OUT}" | grep -qi "pong"; then
  SMOKE_RESULT="ok"
  compose_check_result
  if [[ "${STATUS}" == "healthy" || "${STATUS}" == "degraded" ]]; then
    REASON="smoke call succeeded (antigravity chat responded); ${REASON}"
  fi
  if [[ "${STATUS}" == "healthy" ]]; then
    emit_result 0
  fi
  # compose_check_result only reaches "unhealthy"/"degraded" here via quota/undrained
  # signal (log-based quota evidence can still say exhausted even if this one live call
  # got through) — external/environmental, same as the --check path above.
  emit_result 3
else
  SMOKE_RESULT="unexpected_output: ${SMOKE_OUT:0:200}"
  STATUS="unhealthy"
  REASON="Smoke call to antigravity chat returned unexpected output (not the expected reply, no clear 429) — cannot confirm the lane is live."
  emit_result 1
fi
