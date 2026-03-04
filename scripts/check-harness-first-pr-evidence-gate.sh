#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PATTERNS_FILE="${ROOT_DIR}/config/harness-first-high-impact-paths.txt"
POLICY_FILE="${ROOT_DIR}/config/harness-first-policy.json"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

[[ -f "${PATTERNS_FILE}" ]] || fail "missing high-impact pattern file: ${PATTERNS_FILE}"
[[ -f "${POLICY_FILE}" ]] || fail "missing policy file: ${POLICY_FILE}"
command -v git >/dev/null 2>&1 || fail "git is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

# PR-only gate unless explicitly forced (FORCE_HARNESS_FIRST_EVIDENCE_GATE=true).
if [[ "${FORCE_HARNESS_FIRST_EVIDENCE_GATE:-false}" != "true" ]]; then
  if [[ "${GITHUB_EVENT_NAME:-}" != "pull_request" && -z "${GITHUB_BASE_REF:-}" ]]; then
    pass "non-PR context; skipping harness-first PR evidence gate"
    exit 0
  fi
fi

BASE_REF="${BASE_REF:-${GITHUB_BASE_REF:-}}"
if [[ -z "${BASE_REF}" ]]; then
  fail "unable to determine base ref (set BASE_REF or GITHUB_BASE_REF)"
fi

if ! git rev-parse --verify --quiet "origin/${BASE_REF}" >/dev/null; then
  git fetch --no-tags --depth=200 origin "${BASE_REF}:${BASE_REF}" >/dev/null 2>&1 || true
  git fetch --no-tags --depth=200 origin "${BASE_REF}" >/dev/null 2>&1 || true
fi

if git rev-parse --verify --quiet "origin/${BASE_REF}" >/dev/null; then
  DIFF_BASE="origin/${BASE_REF}"
elif git rev-parse --verify --quiet "${BASE_REF}" >/dev/null; then
  DIFF_BASE="${BASE_REF}"
else
  fail "could not resolve base ref ${BASE_REF}; ensure checkout fetch depth includes base branch"
fi

DIFF_RANGE="${DIFF_BASE}...HEAD"
if ! git merge-base "${DIFF_BASE}" HEAD >/dev/null 2>&1; then
  DIFF_RANGE="${DIFF_BASE}..HEAD"
fi

mapfile -t changed_files < <(git diff --name-only --diff-filter=ACMR "${DIFF_RANGE}")

if [[ ${#changed_files[@]} -eq 0 ]]; then
  pass "no changed files in diff; skipping"
  exit 0
fi

mapfile -t path_prefixes < <(grep -Ev '^\s*($|#)' "${PATTERNS_FILE}")
[[ ${#path_prefixes[@]} -gt 0 ]] || fail "no usable path prefixes in ${PATTERNS_FILE}"

high_impact_changes=()
for file in "${changed_files[@]}"; do
  for prefix in "${path_prefixes[@]}"; do
    if [[ "${file}" == "${prefix}"* ]]; then
      high_impact_changes+=("${file}")
      break
    fi
  done
done

if [[ ${#high_impact_changes[@]} -eq 0 ]]; then
  pass "no high-impact path changes; evidence file not required"
  exit 0
fi

mapfile -t added_evidence_files < <(git diff --name-status --diff-filter=A "${DIFF_RANGE}" \
  | awk '{print $2}' \
  | grep -E '^docs/harness-first/evidence/[0-9]{4}-[0-9]{2}-[0-9]{2}-[A-Za-z0-9._-]+\.md$' || true)

if [[ ${#added_evidence_files[@]} -eq 0 ]]; then
  {
    echo "FAIL: high-impact paths changed but no new evidence file was added"
    echo "Required format: docs/harness-first/evidence/YYYY-MM-DD-<task-id>.md"
    echo "High-impact changed files:"
    printf '  - %s\n' "${high_impact_changes[@]}"
  } >&2
  exit 1
fi

mapfile -t required_evidence_sections < <(python3 - "${POLICY_FILE}" <<'PY'
import json
import sys
from pathlib import Path

policy = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for section in policy.get("required_evidence_sections", []):
    print(section)
PY
)

for evidence_file in "${added_evidence_files[@]}"; do
  [[ -f "${ROOT_DIR}/${evidence_file}" ]] || fail "evidence file missing in workspace: ${evidence_file}"
  for section in "${required_evidence_sections[@]}"; do
    grep -Fq "${section}" "${ROOT_DIR}/${evidence_file}" || fail "evidence file ${evidence_file} missing section: ${section}"
  done
done

pass "harness-first PR evidence gate satisfied (${#added_evidence_files[@]} evidence file(s))"
