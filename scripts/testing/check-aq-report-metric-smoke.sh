#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_SCRIPT="${ROOT_DIR}/scripts/ai/aq-report"
SEED_SCRIPT="${ROOT_DIR}/scripts/data/seed-routing-traffic.sh"
TOOL_SEED_SCRIPT="${ROOT_DIR}/scripts/data/seed-tool-audit-traffic.sh"
MIN_TOOL_BREADTH="${AQ_METRIC_SMOKE_MIN_TOOL_BREADTH:-5}"
AUDIT_LOOKBACK_MINUTES="${AQ_METRIC_SMOKE_AUDIT_LOOKBACK_MINUTES:-90}"
MIN_ENDPOINT_BREADTH="${AQ_METRIC_SMOKE_MIN_ENDPOINT_BREADTH:-5}"
SEED_RETRIES="${AQ_METRIC_SMOKE_SEED_RETRIES:-2}"
SEED_RETRY_BACKOFF_SECONDS="${AQ_METRIC_SMOKE_SEED_RETRY_BACKOFF_SECONDS:-3}"

fail() { echo "[FAIL] $*" >&2; exit 1; }
info() { echo "[INFO] $*"; }
pass() { echo "[PASS] $*"; }

[[ -x "${REPORT_SCRIPT}" ]] || fail "missing ${REPORT_SCRIPT}"

run_with_retries() {
  local desc="$1"
  local log_path="$2"
  shift 2
  local attempt=1
  local max_attempts=$((SEED_RETRIES + 1))
  local rc=0

  while (( attempt <= max_attempts )); do
    if "$@" >"${log_path}" 2>&1; then
      return 0
    fi
    rc=$?
    if (( attempt == max_attempts )); then
      return "${rc}"
    fi
    info "${desc} failed on attempt ${attempt}/${max_attempts}; retrying in ${SEED_RETRY_BACKOFF_SECONDS}s"
    sleep "${SEED_RETRY_BACKOFF_SECONDS}"
    attempt=$((attempt + 1))
  done
  return "${rc}"
}

seeded=false
if [[ -x "${SEED_SCRIPT}" ]] && [[ -r "/run/secrets/hybrid_coordinator_api_key" || -n "${HYBRID_API_KEY:-}" ]]; then
  info "Seeding routing/cache traffic before metric smoke check"
  if run_with_retries "seed-routing-traffic" /tmp/aq-metric-smoke-seed.log "${SEED_SCRIPT}" --count 6 --replay 1; then
    seeded=true
  else
    fail "seed-routing-traffic failed"
  fi
fi

if [[ -x "${TOOL_SEED_SCRIPT}" ]] && [[ "${seeded}" == "true" ]]; then
  info "Seeding tool-audit traffic"
  if ! run_with_retries "seed-tool-audit-traffic" /tmp/aq-tool-smoke-seed.log "${TOOL_SEED_SCRIPT}"; then
    fail "seed-tool-audit-traffic failed"
  fi
fi

report_json="$(mktemp)"
trap 'rm -f "${report_json}"' EXIT
python3 "${REPORT_SCRIPT}" --since=7d --format=json > "${report_json}"

python3 - "${report_json}" "${seeded}" "${TOOL_AUDIT_LOG_PATH:-/var/log/nixos-ai-stack/tool-audit.jsonl}" "${TOOL_AUDIT_LOG_PATH_FALLBACK:-/var/log/ai-audit-sidecar/tool-audit.jsonl}" "/tmp/aq-tool-smoke-seed.log" "${MIN_TOOL_BREADTH}" "${AUDIT_LOOKBACK_MINUTES}" "${MIN_ENDPOINT_BREADTH}" <<'PY'
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
seeded = sys.argv[2].strip().lower() == "true"
tool_audit_primary = Path(sys.argv[3])
tool_audit_fallback = Path(sys.argv[4])
seed_log = Path(sys.argv[5])
min_tool_breadth = int(sys.argv[6])
audit_lookback_minutes = int(sys.argv[7])
min_endpoint_breadth = int(sys.argv[8])
routing = doc.get("routing", {}) if isinstance(doc.get("routing"), dict) else {}
cache = doc.get("cache", {}) if isinstance(doc.get("cache"), dict) else {}
hints = doc.get("hint_adoption", {}) if isinstance(doc.get("hint_adoption"), dict) else {}
tools = doc.get("tool_performance", {}) if isinstance(doc.get("tool_performance"), dict) else {}

def recent_tool_breadth() -> int:
    # Fallback breadth check from raw audit stream when aq-report tool table is sparse.
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=audit_lookback_minutes)
    ignore = {"manual_probe", "run_sandboxed", "shell_execute"}
    names = set()
    for path in (tool_audit_primary, tool_audit_fallback):
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts_raw = row.get("timestamp")
                    if not isinstance(ts_raw, str) or not ts_raw:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_raw.rstrip("Z")).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
                    if ts < cutoff:
                        continue
                    name = str(row.get("tool_name", "")).strip().lower()
                    if not name or name in ignore:
                        continue
                    names.add(name)
        except OSError:
            continue
    return len(names)

def seeded_endpoint_breadth() -> int:
    if not seed_log.exists():
        return 0
    endpoints = set()
    try:
        for raw in seed_log.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line.startswith("OK  /") and not line.startswith("OK /"):
                continue
            # Examples:
            # "OK  /hints?q=... (HTTP 200)"
            # "OK /query (HTTP 200)"
            endpoint = line.split("(HTTP", 1)[0]
            endpoint = endpoint.replace("OK", "", 1).strip()
            endpoint = endpoint.split("?", 1)[0]
            if endpoint:
                endpoints.add(endpoint)
    except OSError:
        return 0
    return len(endpoints)

errors = []
if seeded:
    if not routing.get("available"):
        errors.append("routing.available=false after seed")
    if (int(routing.get("local_n", 0) or 0) + int(routing.get("remote_n", 0) or 0)) <= 0:
        errors.append("routing split empty after seed")
    if not cache.get("available"):
        errors.append("cache.available=false after seed")
    if cache.get("hit_pct") is None:
        errors.append("cache.hit_pct null after seed")
    if not hints.get("available"):
        errors.append("hint_adoption.available=false")
    report_breadth = len(tools)
    audit_breadth = recent_tool_breadth()
    endpoint_breadth = seeded_endpoint_breadth()
    pass_by_report_or_audit = max(report_breadth, audit_breadth) >= min_tool_breadth
    pass_by_endpoint = endpoint_breadth >= min_endpoint_breadth
    if not (pass_by_report_or_audit or pass_by_endpoint):
        errors.append(
            f"tool_performance breadth too low after seed: "
            f"report={report_breadth}, recent_audit={audit_breadth}, endpoint_seed={endpoint_breadth}, "
            f"required_tool_breadth>={min_tool_breadth}, required_endpoint_breadth>={min_endpoint_breadth}, "
            f"audit_lookback_minutes={audit_lookback_minutes}"
        )
else:
    # Non-runtime/CI environment: enforce JSON schema presence only.
    for key in ("routing", "cache", "hint_adoption"):
        if key not in doc:
            errors.append(f"missing key: {key}")

if errors:
    print("[FAIL] aq-report metric smoke failed")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

if seeded:
    print("[PASS] aq-report runtime metric smoke validated after seeded traffic")
else:
    print("[PASS] aq-report metric schema smoke validated (no runtime seed available)")
PY
