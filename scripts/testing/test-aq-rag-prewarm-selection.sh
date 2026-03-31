#!/usr/bin/env bash
# Verify aq-rag-prewarm adds a memory-recall seed when live report says recall is underused.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/ai/aq-rag-prewarm"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

REPORT_PATH="${TMP_DIR}/latest-aq-report.json"
KEY_PATH="${TMP_DIR}/hybrid.key"
printf 'test-key\n' > "${KEY_PATH}"

cat > "${REPORT_PATH}" <<'EOF'
{
  "rag_posture": {
    "memory_recall_diagnosis": "unused",
    "prewarm_candidates": [
      {"id": "route_search_synthesis"}
    ]
  }
}
EOF

OUTPUT="$(
  AQ_REPORT_PATH="${REPORT_PATH}" \
  HYBRID_API_KEY_FILE="${KEY_PATH}" \
  HYBRID_API_KEY="test-key" \
  HYBRID_URL="http://127.0.0.1:9" \
  "${SCRIPT}" --from-report "${REPORT_PATH}" --max-prompts 2 --replay 1 --json
)"

printf '%s\n' "${OUTPUT}" | grep -q '"route_search_synthesis"' || {
  echo "FAIL: expected route_search_synthesis prompt id" >&2
  exit 1
}
printf '%s\n' "${OUTPUT}" | grep -q '"memory_recall_contextualise"' || {
  echo "FAIL: expected memory_recall_contextualise prompt id" >&2
  exit 1
}

echo "PASS: aq-rag-prewarm selects memory recall seed when recall is underused"
