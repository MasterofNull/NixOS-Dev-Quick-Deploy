#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
FRESHNESS="${REPO_ROOT}/scripts/ai/aq-ctx-freshness"

bash -n \
    "$FRESHNESS" \
    "${REPO_ROOT}/.githooks/post-merge" \
    "${REPO_ROOT}/.githooks/post-checkout" \
    "${REPO_ROOT}/scripts/ai/aq-session-start" \
    "${BASH_SOURCE[0]}"

set +e
check_output="$(cd "$REPO_ROOT" && "$FRESHNESS" --check 2>&1)"
check_rc=$?
set -e
printf '%s\n' "$check_output"

if (( check_rc != 0 && check_rc != 1 )); then
    printf 'FAIL: --check exited %d; expected 0 or 1\n' "$check_rc" >&2
    exit 1
fi

set +e
heal_output="$(cd "$REPO_ROOT" && "$FRESHNESS" --heal-shallow 2>&1)"
heal_rc=$?
set -e
[[ -n "$heal_output" ]] && printf '%s\n' "$heal_output"

if (( heal_rc != 0 )); then
    printf 'FAIL: --heal-shallow exited %d; expected 0\n' "$heal_rc" >&2
    exit 1
fi

grep -Fq 'graph_mtime < head_time' "$FRESHNESS"
grep -Fq 'git rev-parse --show-toplevel' "$FRESHNESS"
grep -Fq 'command -v lean-ctx' "$FRESHNESS"
grep -Fq 'SKIP: lean-ctx is not installed' "$FRESHNESS"
grep -Fq 'rev-parse --is-shallow-repository' "$FRESHNESS"
grep -Fq 'fetch_args=(fetch --unshallow)' "$FRESHNESS"
grep -Fq 'AQ_UNSHALLOW_DEPTH' "$FRESHNESS"
grep -Fq 'nohup setsid git' "$FRESHNESS"
grep -Fq '"${SCRIPT_DIR}/aq-ctx-freshness" --heal-shallow || true' \
    "${REPO_ROOT}/scripts/ai/aq-session-start"

printf 'PASS: aq-ctx-freshness syntax, check exit (%d), heal exit (%d), shallow/background/depth handling, and fail-safe integration\n' \
    "$check_rc" "$heal_rc"
