#!/usr/bin/env bash
set -euo pipefail

# Validate that runtime aq-report sections are populated after seeded traffic.
# Intended for post-deploy smoke checks (not strict CI on hosts without services).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_SCRIPT="${ROOT_DIR}/scripts/aq-report"
ALLOW_EMPTY="${ALLOW_EMPTY:-false}"

if [[ ! -x "${REPORT_SCRIPT}" ]]; then
  echo "[FAIL] missing executable ${REPORT_SCRIPT}" >&2
  exit 2
fi

tmp_json="$(mktemp)"
trap 'rm -f "${tmp_json}"' EXIT

python3 "${REPORT_SCRIPT}" --since=7d --format=json >"${tmp_json}"

python3 - "${tmp_json}" "${ALLOW_EMPTY}" <<'PY'
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
allow_empty = str(sys.argv[2]).strip().lower() == "true"

routing = doc.get("routing", {}) if isinstance(doc.get("routing"), dict) else {}
cache = doc.get("cache", {}) if isinstance(doc.get("cache"), dict) else {}
hints = doc.get("hint_adoption", {}) if isinstance(doc.get("hint_adoption"), dict) else {}
intent = doc.get("intent_contract_compliance", {}) if isinstance(doc.get("intent_contract_compliance"), dict) else {}

errors = []
if not bool(routing.get("available", False)):
    errors.append("routing.available=false")
if not bool(cache.get("available", False)):
    errors.append("cache.available=false")
if not bool(hints.get("available", False)):
    errors.append("hint_adoption.available=false")
if not bool(intent.get("available", False)):
    errors.append("intent_contract_compliance.available=false")

local_n = int(routing.get("local_n", 0) or 0)
remote_n = int(routing.get("remote_n", 0) or 0)
if (local_n + remote_n) == 0 and not allow_empty:
    errors.append("routing split empty (local_n+remote_n==0)")
if cache.get("hit_pct") is None and not allow_empty:
    errors.append("cache.hit_pct is null")

if errors:
    print("[FAIL] aq-report runtime section checks failed:")
    for e in errors:
        print(f"- {e}")
    raise SystemExit(1)

print("[PASS] aq-report runtime sections validated")
print(f"[INFO] routing local={local_n} remote={remote_n} cache_hit_pct={cache.get('hit_pct')}")
PY
