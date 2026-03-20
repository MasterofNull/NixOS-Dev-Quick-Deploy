#!/usr/bin/env bash
# Run the upstream A2A TCK against the live hybrid coordinator.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
A2A_TCK_REPO="${A2A_TCK_REPO:-https://github.com/a2aproject/a2a-tck}"
A2A_TCK_REF="${A2A_TCK_REF:-main}"
A2A_TCK_CACHE_DIR="${A2A_TCK_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/nixos-ai/a2a-tck}"
A2A_TCK_VENV="${A2A_TCK_VENV:-${A2A_TCK_CACHE_DIR}/.venv}"
A2A_TCK_CATEGORY="${A2A_TCK_CATEGORY:-mandatory}"
A2A_TCK_REPORT_PATH="${A2A_TCK_REPORT_PATH:-/tmp/a2a-tck-${A2A_TCK_CATEGORY}-report.json}"
A2A_TCK_LOG_PATH="${A2A_TCK_LOG_PATH:-/tmp/a2a-tck-${A2A_TCK_CATEGORY}.log}"

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
info() { printf '[INFO] %s\n' "$*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

usage() {
  cat <<'EOF'
Usage: scripts/testing/run-a2a-tck.sh [category]

Runs the upstream A2A Technology Compatibility Kit against the live hybrid
coordinator. Category defaults to the A2A_TCK_CATEGORY env var or `mandatory`.

Environment:
  HYB_URL                System-under-test base URL
  HYBRID_API_KEY         Optional X-API-Key value for authenticated RPC
  HYBRID_API_KEY_FILE    Secret file fallback for HYBRID_API_KEY
  A2A_TCK_REPO           Upstream TCK git repo
  A2A_TCK_REF            Branch/tag/ref to checkout
  A2A_TCK_CACHE_DIR      Local clone/cache directory
  A2A_TCK_VENV           Python virtualenv path for TCK dependencies
  A2A_TCK_CATEGORY       Test category: mandatory, capabilities, quality, all
  A2A_TCK_REPORT_PATH    JSON compliance report output path
  A2A_TCK_LOG_PATH       Full stdout/stderr log capture path
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ge 1 ]]; then
  A2A_TCK_CATEGORY="$1"
  A2A_TCK_REPORT_PATH="${A2A_TCK_REPORT_PATH:-/tmp/a2a-tck-${A2A_TCK_CATEGORY}-report.json}"
  shift
fi

need_cmd git
need_cmd python3

if [[ -z "$HYBRID_API_KEY" && -r "$HYBRID_API_KEY_FILE" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "$HYBRID_API_KEY_FILE")"
fi
if [[ -z "$HYBRID_API_KEY" ]]; then
  for candidate in /run/secrets/hybrid_coordinator_api_key /run/secrets/hybrid_api_key; do
    if [[ -r "$candidate" ]]; then
      HYBRID_API_KEY="$(tr -d '[:space:]' < "$candidate")"
      break
    fi
  done
fi

mkdir -p "$(dirname "$A2A_TCK_CACHE_DIR")"
if [[ ! -d "$A2A_TCK_CACHE_DIR/.git" ]]; then
  info "Cloning upstream A2A TCK into ${A2A_TCK_CACHE_DIR}"
  git clone --depth 1 --branch "$A2A_TCK_REF" "$A2A_TCK_REPO" "$A2A_TCK_CACHE_DIR" >/dev/null
else
  info "Refreshing upstream A2A TCK in ${A2A_TCK_CACHE_DIR}"
  git -C "$A2A_TCK_CACHE_DIR" fetch --depth 1 origin "$A2A_TCK_REF" >/dev/null
  git -C "$A2A_TCK_CACHE_DIR" checkout -q FETCH_HEAD
fi

if [[ ! -x "${A2A_TCK_VENV}/bin/python" ]]; then
  info "Creating TCK virtualenv at ${A2A_TCK_VENV}"
  python3 -m venv "$A2A_TCK_VENV"
fi

info "Installing TCK dependencies"
"${A2A_TCK_VENV}/bin/python" -m pip install --upgrade pip >/dev/null
"${A2A_TCK_VENV}/bin/python" -m pip install -e "$A2A_TCK_CACHE_DIR" >/dev/null

export A2A_AUTH_TYPE=""
export A2A_AUTH_TOKEN=""
export A2A_AUTH_HEADER=""
unset A2A_AUTH_HEADERS || true

if [[ -n "$HYBRID_API_KEY" ]]; then
  export A2A_AUTH_TYPE="apikey"
  export A2A_AUTH_TOKEN="$HYBRID_API_KEY"
  export A2A_AUTH_HEADER="X-API-Key"
  pass "configured TCK API-key auth"
else
  info "No hybrid API key found; TCK will run without authenticated RPC headers"
fi

mkdir -p "$(dirname "$A2A_TCK_REPORT_PATH")"
mkdir -p "$(dirname "$A2A_TCK_LOG_PATH")"
report_name="$(basename "$A2A_TCK_REPORT_PATH")"
cache_report_path="${A2A_TCK_CACHE_DIR}/reports/${report_name}"
info "Running upstream A2A TCK category=${A2A_TCK_CATEGORY} against ${HYB_URL}"
set +e
(
  cd "$A2A_TCK_CACHE_DIR"
  cmd=(
    "${A2A_TCK_VENV}/bin/python"
    run_tck.py
    --sut-url "$HYB_URL"
    --category "$A2A_TCK_CATEGORY"
  )
  if [[ "$A2A_TCK_CATEGORY" == "all" ]]; then
    cmd+=(--compliance-report "$report_name")
  fi
  cmd+=("$@")
  "${cmd[@]}"
 ) 2>&1 | tee "$A2A_TCK_LOG_PATH"
exit_code="${PIPESTATUS[0]}"
set -e

if [[ -f "$cache_report_path" ]]; then
  cp "$cache_report_path" "$A2A_TCK_REPORT_PATH"
fi

printf 'TCK log: %s\n' "$A2A_TCK_LOG_PATH"
if [[ -f "$A2A_TCK_REPORT_PATH" ]]; then
  printf 'Compliance report: %s\n' "$A2A_TCK_REPORT_PATH"
else
  printf 'Compliance report: not generated for category=%s (use category=all)\n' "$A2A_TCK_CATEGORY"
fi

if [[ "$exit_code" -ne 0 ]]; then
  info "TCK exited non-zero (${exit_code}); showing condensed summary"
  rg -n 'short test summary info|FAILED |ERROR |Compliance level|Overall score' "$A2A_TCK_LOG_PATH" || true
  fail "A2A TCK ${A2A_TCK_CATEGORY} failed"
fi

pass "A2A TCK ${A2A_TCK_CATEGORY}"
