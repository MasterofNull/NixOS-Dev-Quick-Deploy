#!/usr/bin/env bash
set -euo pipefail

# Validate aq-report JSON output contract for CI/runtime regression guarding.
# This check is intentionally service-agnostic: aq-report should still emit
# the expected top-level schema when Prometheus/Postgres are unavailable.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_SCRIPT="${ROOT_DIR}/scripts/aq-report"

if [[ ! -x "${REPORT_SCRIPT}" ]]; then
  echo "ERROR: missing executable ${REPORT_SCRIPT}" >&2
  exit 2
fi

tmp_json="$(mktemp)"
trap 'rm -f "${tmp_json}"' EXIT

python3 "${REPORT_SCRIPT}" --since=7d --format=json >"${tmp_json}"

python3 - "${tmp_json}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
doc = json.loads(path.read_text(encoding="utf-8"))

required = [
    "generated_at",
    "window",
    "tool_performance",
    "routing",
    "cache",
    "eval_trend",
    "strategy_leaderboard",
    "top_prompts",
    "query_gaps",
    "recommendations",
    "hint_adoption",
    "task_tooling_quality",
    "intent_contract_compliance",
    "tool_security_auditor",
    "semantic_tooling_autorun",
    "hint_diversity",
    "structured_actions",
]

missing = [k for k in required if k not in doc]
if missing:
    print(f"ERROR: aq-report missing required keys: {missing}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(doc.get("recommendations"), list):
    print("ERROR: aq-report.recommendations must be a list", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(doc.get("structured_actions"), list):
    print("ERROR: aq-report.structured_actions must be a list", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(doc.get("routing"), dict):
    print("ERROR: aq-report.routing must be an object", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(doc.get("cache"), dict):
    print("ERROR: aq-report.cache must be an object", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(doc.get("tool_security_auditor"), dict):
    print("ERROR: aq-report.tool_security_auditor must be an object", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(doc.get("semantic_tooling_autorun"), dict):
    print("ERROR: aq-report.semantic_tooling_autorun must be an object", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(doc.get("hint_diversity"), dict):
    print("ERROR: aq-report.hint_diversity must be an object", file=sys.stderr)
    raise SystemExit(1)

print("PASS: aq-report JSON contract validated")
PY
