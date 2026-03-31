#!/usr/bin/env bash
# Verify aq-rag-prewarm adds a memory-recall seed when live report says recall is underused.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/ai/aq-rag-prewarm"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

REPORT_PATH="${TMP_DIR}/latest-aq-report.json"
KEY_PATH="${TMP_DIR}/hybrid.key"
FAKE_CURL="${TMP_DIR}/fake-curl.sh"
PAYLOAD_LOG="${TMP_DIR}/payloads.jsonl"
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

cat > "${FAKE_CURL}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
payload=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d)
      payload="$2"
      shift 2
      ;;
    -w)
      shift 2
      ;;
    -o|--max-time|--connect-timeout|-X|-H)
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
printf '%s\n' "${payload}" >> "${PAYLOAD_LOG:?}"
printf '200'
EOF
chmod +x "${FAKE_CURL}"

OUTPUT="$(
  AQ_REPORT_PATH="${REPORT_PATH}" \
  HYBRID_API_KEY_FILE="${KEY_PATH}" \
  HYBRID_API_KEY="test-key" \
  AQ_PREWARM_CURL_BIN="${FAKE_CURL}" \
  PAYLOAD_LOG="${PAYLOAD_LOG}" \
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
jq -e '
  select(.context.prewarm_prompt_id == "route_search_synthesis")
  | .generate_response == true
' "${PAYLOAD_LOG}" >/dev/null || {
  echo "FAIL: expected route_search_synthesis prewarm payload to enable generate_response" >&2
  exit 1
}
jq -e '
  select(.context.prewarm_prompt_id == "memory_recall_contextualise")
  | .generate_response == false
' "${PAYLOAD_LOG}" >/dev/null || {
  echo "FAIL: expected memory_recall_contextualise prewarm payload to stay retrieval-only" >&2
  exit 1
}

echo "PASS: aq-rag-prewarm selects memory recall seed and enables synthesis payloads only when needed"
