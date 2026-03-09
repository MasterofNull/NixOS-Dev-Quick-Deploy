#!/usr/bin/env bash
# Refresh legacy AI dashboard metrics cache from the live dashboard API.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

OUTPUT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nixos-system-dashboard"
OUTPUT_FILE=""
API_URL="${DASHBOARD_API_URL%/}/api/ai/metrics"

usage() {
  cat <<'EOF'
Usage: scripts/observability/collect-ai-metrics.sh [--output FILE] [--api-url URL]

Fetches the live dashboard AI metrics payload and writes the legacy cache file:
  ~/.local/share/nixos-system-dashboard/ai_metrics.json
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      OUTPUT_FILE="${2:?missing value for --output}"
      shift 2
      ;;
    --api-url)
      API_URL="${2:?missing value for --api-url}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${OUTPUT_FILE}" ]]; then
  OUTPUT_FILE="${OUTPUT_DIR}/ai_metrics.json"
fi

mkdir -p "$(dirname "${OUTPUT_FILE}")"
tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

echo "scripts/observability/collect-ai-metrics.sh refreshes the legacy dashboard cache from ${API_URL}." >&2
curl -fsS "${API_URL}" > "${tmp_file}"
python3 -m json.tool "${tmp_file}" > "${OUTPUT_FILE}"
echo "Wrote ${OUTPUT_FILE}"
