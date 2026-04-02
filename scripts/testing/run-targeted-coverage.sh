#!/usr/bin/env bash
# Run targeted line-coverage suites for measurable production modules.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RCFILE="${ROOT_DIR}/scripts/testing/coverage/.coveragerc"
REPORT_DIR="${ROOT_DIR}/.reports/coverage-targeted"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "${REPORT_DIR}" "${REPORT_DIR}/html"

read_pct() {
  local json_path="$1"
  "${PYTHON_BIN}" - "$json_path" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)

files = payload.get("files") or {}
if not files:
    raise SystemExit("no file coverage data captured")

entry = next(iter(files.values()))
summary = entry.get("summary") or {}
print(f"{float(summary.get('percent_covered', 0.0)):.1f}")
PY
}

enforce_threshold() {
  local name="$1"
  local pct="$2"
  local threshold="$3"
  "${PYTHON_BIN}" - "$name" "$pct" "$threshold" <<'PY'
import sys

name = sys.argv[1]
pct = float(sys.argv[2])
threshold = float(sys.argv[3])
if pct < threshold:
    raise SystemExit(f"{name} coverage {pct:.1f}% is below threshold {threshold:.1f}%")
print(f"[coverage] {name}: {pct:.1f}% (threshold {threshold:.1f}%)")
PY
}

run_pytest_component() {
  local name="$1"
  local pythonpath="$2"
  local include="$3"
  local threshold="$4"
  shift 4

  local coverage_file="${REPORT_DIR}/.coverage.${name}"
  local old_pythonpath="${PYTHONPATH-}"
  rm -f "${coverage_file}"

  export PYTHONPATH="${pythonpath}${old_pythonpath:+:${old_pythonpath}}"
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage run --rcfile="${RCFILE}" -m pytest "$@"
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage json --rcfile="${RCFILE}" --include="${include}" -o "${REPORT_DIR}/${name}.json" >/dev/null
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage xml --rcfile="${RCFILE}" --include="${include}" -o "${REPORT_DIR}/${name}.xml" >/dev/null
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage html --rcfile="${RCFILE}" --include="${include}" -d "${REPORT_DIR}/html/${name}" >/dev/null
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage report --rcfile="${RCFILE}" -m --include="${include}" | tee "${REPORT_DIR}/${name}.txt"
  local pct
  pct="$(read_pct "${REPORT_DIR}/${name}.json")"
  enforce_threshold "${name}" "${pct}" "${threshold}"
  printf '| %s | %s | %s |\n' "${name}" "${pct}%" "${threshold}%" >> "${REPORT_DIR}/summary.md"

  if [[ -n "${old_pythonpath}" ]]; then
    export PYTHONPATH="${old_pythonpath}"
  else
    unset PYTHONPATH
  fi
}

run_script_component() {
  local name="$1"
  local pythonpath="$2"
  local include="$3"
  local threshold="$4"
  local script_path="$5"
  shift 5

  local coverage_file="${REPORT_DIR}/.coverage.${name}"
  local old_pythonpath="${PYTHONPATH-}"
  rm -f "${coverage_file}"

  export PYTHONPATH="${pythonpath}${old_pythonpath:+:${old_pythonpath}}"
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage run --rcfile="${RCFILE}" "${script_path}" "$@"
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage json --rcfile="${RCFILE}" --include="${include}" -o "${REPORT_DIR}/${name}.json" >/dev/null
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage xml --rcfile="${RCFILE}" --include="${include}" -o "${REPORT_DIR}/${name}.xml" >/dev/null
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage html --rcfile="${RCFILE}" --include="${include}" -d "${REPORT_DIR}/html/${name}" >/dev/null
  COVERAGE_FILE="${coverage_file}" "${PYTHON_BIN}" -m coverage report --rcfile="${RCFILE}" -m --include="${include}" | tee "${REPORT_DIR}/${name}.txt"
  local pct
  pct="$(read_pct "${REPORT_DIR}/${name}.json")"
  enforce_threshold "${name}" "${pct}" "${threshold}"
  printf '| %s | %s | %s |\n' "${name}" "${pct}%" "${threshold}%" >> "${REPORT_DIR}/summary.md"

  if [[ -n "${old_pythonpath}" ]]; then
    export PYTHONPATH="${old_pythonpath}"
  else
    unset PYTHONPATH
  fi
}

cat > "${REPORT_DIR}/summary.md" <<'EOF'
# Targeted Coverage Summary

| Component | Measured Coverage | Threshold |
| --- | --- | --- |
EOF

run_pytest_component \
  "context_store" \
  "${ROOT_DIR}/dashboard/backend" \
  "dashboard/backend/api/services/context_store.py" \
  "${TARGET_CONTEXT_STORE_MIN_PCT:-15}" \
  scripts/testing/test-context-store-service-state.py \
  scripts/testing/test-context-store-deployment-deps.py \
  scripts/testing/test-context-store-causality-edges.py \
  scripts/testing/test-deployment-graph-queries.py \
  scripts/testing/test-deployment-causality-clustering.py \
  scripts/testing/test-context-store-performance.py

run_pytest_component \
  "route_handler" \
  "${ROOT_DIR}/ai-stack/mcp-servers/hybrid-coordinator" \
  "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py" \
  "${TARGET_ROUTE_HANDLER_MIN_PCT:-28}" \
  ai-stack/mcp-servers/hybrid-coordinator/test_route_handler_optimizations.py

run_pytest_component \
  "ai_coordinator" \
  "${ROOT_DIR}/ai-stack/mcp-servers/hybrid-coordinator" \
  "ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator.py" \
  "${TARGET_AI_COORDINATOR_MIN_PCT:-35}" \
  ai-stack/mcp-servers/hybrid-coordinator/test_ai_coordinator_model_awareness.py

run_script_component \
  "advanced_features" \
  "${ROOT_DIR}/ai-stack/mcp-servers/hybrid-coordinator:${ROOT_DIR}/ai-stack/mcp-servers" \
  "ai-stack/mcp-servers/hybrid-coordinator/advanced_features.py" \
  "${TARGET_ADVANCED_FEATURES_MIN_PCT:-50}" \
  scripts/testing/test-advanced-features-implementation.py

printf '\nCoverage artifacts written to %s\n' "${REPORT_DIR}"
