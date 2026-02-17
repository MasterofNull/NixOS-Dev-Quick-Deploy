#!/usr/bin/env bash
#
# Check flake-derived package counts against committed baseline.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GENERATOR="${PROJECT_ROOT}/scripts/generate-package-counts.sh"
BASELINE_PATH="${PROJECT_ROOT}/config/package-count-baseline.json"
FLAKE_REF="path:${PROJECT_ROOT}"
WRITE_BASELINE=false

usage() {
  cat <<'EOF'
Usage: ./scripts/check-package-count-drift.sh [options]

Options:
  --flake-ref REF      Flake reference (default: path:<repo-root>)
  --baseline PATH      Baseline JSON file (default: config/package-count-baseline.json)
  --write-baseline     Refresh baseline from current flake counts and exit
  -h, --help           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --baseline)
      BASELINE_PATH="${2:?missing value for --baseline}"
      shift 2
      ;;
    --write-baseline)
      WRITE_BASELINE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -x "$GENERATOR" ]]; then
  echo "ERROR: Generator script missing or not executable: ${GENERATOR}" >&2
  exit 1
fi

if [[ "$WRITE_BASELINE" == true ]]; then
  "${GENERATOR}" --flake-ref "$FLAKE_REF" --output "$BASELINE_PATH"
  echo "Baseline refreshed: ${BASELINE_PATH}"
  exit 0
fi

if [[ ! -f "$BASELINE_PATH" ]]; then
  echo "ERROR: Baseline file not found: ${BASELINE_PATH}" >&2
  echo "Run ./scripts/check-package-count-drift.sh --write-baseline to create it." >&2
  exit 1
fi

tmp_file="$(mktemp)"
cleanup() {
  rm -f "$tmp_file"
}
trap cleanup EXIT

"${GENERATOR}" --flake-ref "$FLAKE_REF" --output "$tmp_file" >/dev/null

if ! diff -u "$BASELINE_PATH" "$tmp_file" >/dev/null; then
  echo "Package count drift detected against baseline: ${BASELINE_PATH}" >&2
  echo "Diff:" >&2
  diff -u "$BASELINE_PATH" "$tmp_file" >&2 || true
  echo "If this drift is expected, refresh baseline with:" >&2
  echo "  ./scripts/check-package-count-drift.sh --write-baseline" >&2
  exit 1
fi

echo "Package count baseline check passed."
