#!/usr/bin/env bash
# Enforce the staged suspend/resume workload contract.
set -euo pipefail

TAG="[tier0.d/check-suspend-resume-contract]"
MODE="${1:---pre-commit}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
CONTRACT="config/suspend-resume-workloads.json"
TEST="scripts/testing/test-suspend-resume-contract.py"
cd "${REPO_ROOT}"

[[ -f "${TEST}" ]] || {
  echo "${TAG} FAIL: missing ${TEST}" >&2
  exit 1
}

detect_added_workload_declarations() {
  awk '
    /^\+\+\+/ { next }
    /^\+/ && ($0 ~ /systemd(\.user)?\.(services|timers)(\.[A-Za-z0-9_".-]+)?[[:space:]]*=/ || $0 ~ /AQ_SUSPEND_CONTRACT:/) { print }
  '
}

if [[ "${MODE}" == "--self-test" ]]; then
  positive="$(printf '%s\n' '+systemd.services.example-worker = {' | detect_added_workload_declarations)"
  user_timer="$(printf '%s\n' '+systemd.user.timers.example-refresh = {' | detect_added_workload_declarations)"
  marker="$(printf '%s\n' '+# AQ_SUSPEND_CONTRACT: example-worker' | detect_added_workload_declarations)"
  negative="$(printf '%s\n' '+++ b/example.nix' '+  description = "not a declaration";' | detect_added_workload_declarations)"
  [[ -n "${positive}" && -n "${user_timer}" && -n "${marker}" && -z "${negative}" ]] || {
    echo "${TAG} FAIL: added-workload detector did not fail closed" >&2
    exit 1
  }
  echo "${TAG} PASS: added-workload detector fixtures"
  exit 0
fi

temporary_contract="$(mktemp)"
trap 'unlink "${temporary_contract}" 2>/dev/null || true' EXIT

if [[ "${MODE}" == "--pre-commit" ]]; then
  if ! git show ":${CONTRACT}" >"${temporary_contract}" 2>/dev/null; then
    echo "${TAG} FAIL: staged ${CONTRACT} is required" >&2
    exit 1
  fi

  added_workload_declarations="$({
    git diff --cached --unified=0 -- '*.nix' '*.sh' '*.py' 2>/dev/null || true
  } | detect_added_workload_declarations)"
  if [[ -n "${added_workload_declarations}" ]] && \
     ! git diff --cached --name-only -- "${CONTRACT}" | grep -qx "${CONTRACT}"; then
    echo "${TAG} FAIL: a managed service/timer or AQ_SUSPEND_CONTRACT marker was added without a staged ${CONTRACT} update" >&2
    exit 1
  fi
  source_label="staged"
else
  [[ -f "${CONTRACT}" ]] || {
    echo "${TAG} FAIL: missing ${CONTRACT}" >&2
    exit 1
  }
  cp "${CONTRACT}" "${temporary_contract}"
  source_label="source"
fi

python3 "${TEST}" --contract "${temporary_contract}"
python3 "${TEST}" --contract "${temporary_contract}" --self-test
echo "${TAG} PASS: ${source_label} suspend/resume workload contract is valid"
