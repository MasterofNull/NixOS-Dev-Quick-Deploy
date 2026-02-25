#!/usr/bin/env bash
# Weekly research sync + scoring for AI/LLM/agentic developments.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

VALIDATE_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --validate-only) VALIDATE_ONLY=true ;;
  esac
done

REPORT_DATE="$(date +%Y-%m-%d)"
REPORT_PATH="${REPO_ROOT}/docs/development/IMPROVEMENT-DISCOVERY-REPORT-${REPORT_DATE}.md"
SCORECARD_PATH="${REPO_ROOT}/data/ai-research-scorecard.json"

if [[ "$VALIDATE_ONLY" == "true" ]]; then
  if [[ ! -f "$SCORECARD_PATH" ]]; then
    "$0" >/dev/null 2>&1 || true
  fi
  [[ -f "$SCORECARD_PATH" ]] || { echo "Missing scorecard: $SCORECARD_PATH" >&2; exit 1; }
  jq -e '.generated_at != null and .sources_scanned >= 0 and .candidate_count >= 0' "$SCORECARD_PATH" >/dev/null
  echo "PASS: research sync scorecard exists and is valid."
  exit 0
fi

python3 "${SCRIPT_DIR}/discover-improvements.py" >/dev/null

if [[ ! -f "$REPORT_PATH" ]]; then
  # fallback to newest report if date stamp differs
  REPORT_PATH="$(ls -1t "${REPO_ROOT}/docs/development"/IMPROVEMENT-DISCOVERY-REPORT-*.md 2>/dev/null | head -n1 || true)"
fi

[[ -n "$REPORT_PATH" && -f "$REPORT_PATH" ]] || { echo "No discovery report produced" >&2; exit 1; }

candidate_count="$(grep -c "^- \*\*Repo:\*\*" "$REPORT_PATH" || true)"
release_mentions="$(grep -c "Latest release" "$REPORT_PATH" || true)"

python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
scorecard = {
  "generated_at": datetime.now(timezone.utc).isoformat(),
  "report_path": str(Path(r"$REPORT_PATH")),
  "sources_scanned": int($release_mentions),
  "candidate_count": int($candidate_count),
  "notes": "Weekly AI research sync scorecard"
}
out = Path(r"$SCORECARD_PATH")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
PY

# Optional AIDB import (best effort; does not fail sync if unavailable)
if curl -fsS --max-time 4 --connect-timeout 2 "${AIDB_URL%/}/health" >/dev/null 2>&1; then
  payload_file="$(mktemp)"
  content="$(sed 's/"/\\"/g' "$REPORT_PATH" | head -n 1200)"
  cat > "$payload_file" <<JSON
{
  "project": "NixOS-Dev-Quick-Deploy",
  "relative_path": "research/$(basename "$REPORT_PATH")",
  "title": "Weekly AI research sync report",
  "content_type": "text/markdown",
  "content": "$content"
}
JSON
  if [[ -n "${AIDB_API_KEY:-}" ]]; then
    curl -fsS -X POST "${AIDB_URL%/}/documents" -H "Content-Type: application/json" -H "X-API-Key: ${AIDB_API_KEY}" -d @"$payload_file" >/dev/null 2>&1 || true
  fi
  rm -f "$payload_file"
fi

echo "PASS: research sync completed (${REPORT_PATH})"
